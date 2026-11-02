"""Async client for the GWM (Great Wall Motor) TSP API.

链路（逆向自长城汽车 App 2.1.3）：

    ssoId + phone + ssoTk  --APP_LOGIN-->  tokenId (tk)
    tk + vin               --GET_VEHICLE_STATE-->  车况 JSON

两个接口都不校验签名，唯一的坑是 ``tokenId`` 为单会话：
每次 APP_LOGIN 都会签发新 tk 并立刻作废上一个（旧 tk 再取数返回 c=-101）。
所以这里必须缓存 tk，仅在失效时重登一次，绝不能每次轮询都登录，
否则会一直把自己踢下线，并且会把手机 App 的车况会话一起顶掉。
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

from .const import (
    APP_LOGIN_URL,
    APP_TYPE,
    CODE_OK,
    CODE_TOKEN_INVALID,
    FN_APP_LOGIN,
    FN_GET_AIR_STS,
    FN_GET_ENGINE_STS,
    FN_GET_VEHICLE_STATE,
    PAYLOAD_HEADER,
    REQUEST_TIMEOUT,
    TSP_EAD_URL,
    TSP_HEADERS,
)

_LOGGER = logging.getLogger(__name__)


class GwmApiError(Exception):
    """Base error."""


class GwmAuthError(GwmApiError):
    """凭证失效（ssoTk 过期 / 被改密码 / 被踢下线）。需要用户重新抓包。"""


class GwmConnectionError(GwmApiError):
    """网络或服务端异常。"""


def _timestamp() -> str:
    """TSP 要求的时间戳格式：YYYYMMDDHHMMSSmmm（17 位）。"""
    now = dt_util.now()
    return now.strftime("%Y%m%d%H%M%S") + f"{now.microsecond // 1000:03d}"


def _payload_header(fn: str, token: str) -> dict[str, Any]:
    header = dict(PAYLOAD_HEADER)
    header.update(
        {
            "fn": fn,
            "mobileId": "",
            "ts": _timestamp(),
            "tk": token,
        }
    )
    return header


class GwmApi:
    """Stateless-ish API wrapper that owns the cached tokenId."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        sso_id: str,
        phone: str,
        sso_token: str,
        vin: str,
    ) -> None:
        self._session = session
        self._sso_id = sso_id
        self._phone = phone
        self._sso_token = sso_token
        self._vin = vin
        self._token: str | None = None
        self._login_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # 凭证
    # ------------------------------------------------------------------
    @property
    def vin(self) -> str:
        return self._vin

    @property
    def sso_token(self) -> str:
        return self._sso_token

    def update_sso_token(self, sso_token: str) -> None:
        """重新认证时替换凭证并作废当前 tk。"""
        self._sso_token = sso_token
        self._token = None

    def invalidate_token(self) -> None:
        self._token = None

    # ------------------------------------------------------------------
    # 换票
    # ------------------------------------------------------------------
    async def async_app_login(self) -> str:
        """用 ssoTk 换一个新的 tokenId。"""
        payload = {
            "body": {
                "ssoid": self._sso_id,
                "phone": self._phone,
                "appType": APP_TYPE,
                "ssoTk": self._sso_token,
            },
            "header": _payload_header(FN_APP_LOGIN, ""),
        }
        url = f"{APP_LOGIN_URL}?p={urllib.parse.quote(json.dumps(payload, separators=(',', ':')))}"

        data = await self._request_json(url, TSP_HEADERS)
        code = data.get("header", {}).get("c")
        message = data.get("header", {}).get("m") or "未知错误"

        if code != CODE_OK:
            raise GwmAuthError(f"换取 tokenId 失败: c={code} {message}")

        token = (data.get("body") or {}).get("tokenId")
        if not token:
            raise GwmAuthError(f"换取 tokenId 失败: 响应中没有 tokenId ({message})")

        _LOGGER.debug("GWM tokenId 已刷新: %s...", token[:8])
        self._token = token
        return token

    async def async_get_token(self, force: bool = False) -> str:
        """取缓存的 tk，没有则登录换一个。"""
        if not force and self._token:
            return self._token

        async with self._login_lock:
            # 双重检查：并发调用时只登录一次
            if not force and self._token:
                return self._token
            return await self.async_app_login()

    # ------------------------------------------------------------------
    # 车况
    # ------------------------------------------------------------------
    async def async_get_vehicle_state(self) -> dict[str, Any]:
        """只取车况原始 vehicleSts（配置流程校验用）。"""
        body = await self._async_call_with_retry(FN_GET_VEHICLE_STATE)
        return body.get("vehicleSts") or {}

    async def async_fetch_all(self) -> dict[str, Any]:
        """一次轮询取全部只读数据，合并成一个扁平结构供实体消费。

        车况是主数据，失败即整轮失败；空调与发动机状态属于附加信息，
        取不到时降级为空 dict，不影响主数据（老车型可能不支持这两个函数）。
        """
        body = await self._async_call_with_retry(FN_GET_VEHICLE_STATE)
        vehicle_sts = body.get("vehicleSts") or {}

        return {
            "vehicleSts": vehicle_sts,
            "carStatus": vehicle_sts.get("carStatus") or {},
            "lastUpdate": vehicle_sts.get("lastUpdate"),
            "air": await self._async_call_optional(FN_GET_AIR_STS),
            "engine": await self._async_call_optional(FN_GET_ENGINE_STS),
        }

    async def _async_call_with_retry(self, fn: str) -> dict[str, Any]:
        """调用 TSP 函数；遇到 -101（tk 失效）自动重登一次并重试。"""
        try:
            return await self._async_call(fn)
        except _TokenExpired:
            _LOGGER.debug("GWM tokenId 失效，正在重新换取")
            self.invalidate_token()
            await self.async_get_token(force=True)
            try:
                return await self._async_call(fn)
            except _TokenExpired as err:
                raise GwmAuthError("重新换取 tokenId 后仍然提示失效") from err

    async def _async_call_optional(self, fn: str) -> dict[str, Any]:
        """附加数据：失败只记日志，不打断轮询。"""
        try:
            return await self._async_call_with_retry(fn)
        except GwmAuthError:
            raise
        except GwmApiError as err:
            _LOGGER.debug("GWM 可选接口 %s 不可用: %s", fn, err)
            return {}

    async def _async_call(self, fn: str) -> dict[str, Any]:
        token = await self.async_get_token()
        payload = {
            "body": {"vin": self._vin},
            "header": _payload_header(fn, token),
        }
        url = f"{TSP_EAD_URL}?p={urllib.parse.quote(json.dumps(payload, separators=(',', ':')))}"

        headers = dict(TSP_HEADERS)
        headers["token"] = token

        data = await self._request_json(url, headers)
        header = data.get("header") or {}
        code = header.get("c")
        message = header.get("m") or "未知错误"

        if code == CODE_TOKEN_INVALID:
            raise _TokenExpired(message)
        if code != CODE_OK:
            raise GwmApiError(f"{fn} 调用失败: c={code} {message}")

        body = data.get("body")
        if not isinstance(body, dict):
            raise GwmApiError(f"{fn} 响应中没有 body")

        if fn == FN_GET_VEHICLE_STATE and not body.get("vehicleSts"):
            raise GwmApiError("获取车况失败: 响应中没有 vehicleSts")

        return body

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    async def _request_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        try:
            async with self._session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                if resp.status >= 500:
                    raise GwmConnectionError(f"服务端错误 HTTP {resp.status}")
                if resp.status >= 400:
                    raise GwmApiError(f"请求被拒绝 HTTP {resp.status}")
                text = await resp.text()
        except asyncio.TimeoutError as err:
            raise GwmConnectionError("请求超时") from err
        except aiohttp.ClientError as err:
            raise GwmConnectionError(f"网络错误: {err}") from err

        try:
            return json.loads(text)
        except ValueError as err:
            raise GwmApiError(f"响应不是合法 JSON: {text[:120]}") from err


class _TokenExpired(GwmApiError):
    """内部信号：tk 失效，需要重登。"""
