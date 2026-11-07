"""Data update coordinator for the GWM vehicle integration."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import GwmApi, GwmApiError, GwmAuthError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REFRESH_MIN_INTERVAL,
    REFRESH_POLL_INTERVAL,
    REFRESH_POLL_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# 刷新状态
REFRESH_IDLE = "idle"
REFRESH_WAITING = "waiting"
REFRESH_DONE = "done"
REFRESH_TIMEOUT = "timeout"
REFRESH_FAILED = "failed"


class GwmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """轮询车况。tk 由 GwmApi 内部缓存并在失效时自动重换。"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: GwmApi) -> None:
        self.api = api
        self.entry = entry

        # 主动刷新（下车机重新上报）的状态
        self.refresh_status: str = REFRESH_IDLE
        self.refresh_seq: str | None = None
        self.refresh_requested_at: Any = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._last_request_monotonic: float = 0.0

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {api.vin}",
            update_interval=timedelta(seconds=int(scan_interval)),
        )

    # ------------------------------------------------------------------
    # 常规轮询
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.async_fetch_all()
        except GwmAuthError as err:
            # 交给 HA 走重新认证流程，用户只需重新粘贴 ssoTk
            raise ConfigEntryAuthFailed(str(err)) from err
        except GwmApiError as err:
            raise UpdateFailed(str(err)) from err

        # 主动刷新期间服务端会把车况缓存置空，GET_VEHICLE_STATE 会短暂返回
        # 没有 carStatus 的空壳。此时若直接覆盖，所有实体会瞬间变「未知」，
        # 而实际上只是数据正在更新 —— 沿用上一轮的数据，等下次轮询再取。
        if not _upload_time(data) and _upload_time(self.data):
            _LOGGER.debug("GWM 车况暂时为空（可能正在刷新），沿用上一轮数据")
            return self.data
        return data

    # ------------------------------------------------------------------
    # 主动刷新：把指令下发给车机，让它重新上报
    # ------------------------------------------------------------------
    @property
    def refresh_busy(self) -> bool:
        return bool(self._refresh_task and not self._refresh_task.done())

    async def async_request_vehicle_refresh(self) -> bool:
        """下发「刷新数据」并在后台等车机上报。

        返回是否真的下发了指令（冷却期内点第二次会返回 False）。
        """
        now = time.monotonic()
        if now - self._last_request_monotonic < REFRESH_MIN_INTERVAL:
            _LOGGER.info(
                "GWM 刷新指令刚下发过，%.0f 秒内不重复发送",
                REFRESH_MIN_INTERVAL - (now - self._last_request_monotonic),
            )
            return False
        self._last_request_monotonic = now

        try:
            seq = await self.api.async_request_vehicle_refresh()
        except GwmAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GwmApiError as err:
            self.refresh_status = REFRESH_FAILED
            self.async_update_listeners()
            raise HomeAssistantError(f"下发刷新指令失败: {err}") from err

        self.refresh_seq = seq
        self.refresh_requested_at = dt_util.utcnow()
        self.refresh_status = REFRESH_WAITING
        self.async_update_listeners()
        _LOGGER.info("GWM 刷新指令已下发（%s），等待车机上报", seq)

        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        self._refresh_task = self.entry.async_create_background_task(
            self.hass, self._async_poll_until_fresh(seq), name=f"{DOMAIN} refresh {seq}"
        )
        return True

    async def _async_poll_until_fresh(self, seq: str) -> None:
        """轮询 uploadTime，直到车机上报了比下发前更新的数据。

        App 在同一场景下是调 ``remote-ctrl/result`` 查指令执行结果，那条路要
        bt-auth-sign 签名走不通；但车机上报成功后服务端缓存的 uploadTime 一定
        会推进，用它判断等价且免签名。
        """
        before = _upload_time(self.data)
        deadline = dt_util.utcnow().timestamp() + REFRESH_POLL_TIMEOUT

        try:
            while dt_util.utcnow().timestamp() < deadline:
                await asyncio.sleep(REFRESH_POLL_INTERVAL)
                try:
                    data = await self.api.async_fetch_all()
                except GwmAuthError:
                    raise
                except GwmApiError as err:
                    _LOGGER.debug("GWM 刷新轮询失败: %s", err)
                    continue

                upload = _upload_time(data)
                if upload and upload != before:
                    self.refresh_status = REFRESH_DONE
                    self.async_set_updated_data(data)
                    _LOGGER.info(
                        "GWM 刷新完成，车机已上报新数据（uploadTime %s → %s）",
                        before,
                        upload,
                    )
                    return

            self.refresh_status = REFRESH_TIMEOUT
            self.async_update_listeners()
            _LOGGER.warning(
                "GWM 刷新指令 %s 已下发，但 %d 秒内车机未上报新数据"
                "（车辆可能处于休眠、地库无信号或 T-BOX 离线）",
                seq,
                REFRESH_POLL_TIMEOUT,
            )
        except asyncio.CancelledError:
            raise
        except GwmAuthError as err:
            self.refresh_status = REFRESH_FAILED
            self.async_update_listeners()
            _LOGGER.warning("GWM 刷新轮询时凭证失效: %s", err)


def _upload_time(data: Any) -> Any:
    """取车况上报时间戳（毫秒）。取不到返回 None。"""
    if not isinstance(data, dict):
        return None
    car_status = data.get("carStatus")
    if not isinstance(car_status, dict):
        return None
    return car_status.get("uploadTime")
