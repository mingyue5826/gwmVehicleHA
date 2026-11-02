"""Config flow for the GWM vehicle integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import GwmApi, GwmApiError, GwmAuthError, GwmConnectionError
from .const import (
    CONF_LICENSE_PLATE,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_SSO_ID,
    CONF_SSO_TOKEN,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    CONF_PHONE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def _async_validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """用用户填的凭证实跑一次登录 + 取车况，用于校验。"""
    api = GwmApi(
        async_get_clientsession(hass),
        sso_id=data[CONF_SSO_ID].strip(),
        phone=data[CONF_PHONE].strip(),
        sso_token=data[CONF_SSO_TOKEN].strip(),
        vin=data[CONF_VIN].strip().upper(),
    )
    await api.async_get_token(force=True)
    return await api.async_get_vehicle_state()


class GwmConfigFlow(ConfigFlow, domain=DOMAIN):
    """首次添加车辆。"""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

    # ------------------------------------------------------------------
    # 首次配置
    # ------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _async_validate(self.hass, user_input)
            except GwmAuthError:
                errors["base"] = "invalid_auth"
            except GwmConnectionError:
                errors["base"] = "cannot_connect"
            except GwmApiError:
                errors["base"] = "invalid_vin"
            except Exception:  # noqa: BLE001 - 兜底，避免流程崩掉
                _LOGGER.exception("GWM 配置校验时出现意外错误")
                errors["base"] = "unknown"
            else:
                vin = user_input[CONF_VIN].strip().upper()
                await self.async_set_unique_id(vin)
                self._abort_if_unique_id_configured()

                name = (user_input.get(CONF_VEHICLE_NAME) or "").strip() or DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_SSO_ID: user_input[CONF_SSO_ID].strip(),
                        CONF_PHONE: user_input[CONF_PHONE].strip(),
                        CONF_SSO_TOKEN: user_input[CONF_SSO_TOKEN].strip(),
                        CONF_VIN: vin,
                        CONF_VEHICLE_NAME: name,
                        CONF_MODEL: (user_input.get(CONF_MODEL) or "").strip(),
                        CONF_LICENSE_PLATE: (
                            user_input.get(CONF_LICENSE_PLATE) or ""
                        ).strip(),
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SSO_ID): cv.string,
                    vol.Required(CONF_PHONE): cv.string,
                    vol.Required(CONF_SSO_TOKEN): cv.string,
                    vol.Required(CONF_VIN): cv.string,
                    vol.Optional(CONF_VEHICLE_NAME, default=DEFAULT_NAME): cv.string,
                    vol.Optional(CONF_MODEL, default=""): cv.string,
                    vol.Optional(CONF_LICENSE_PLATE, default=""): cv.string,
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # ssoTk 过期后的重新认证
    # ------------------------------------------------------------------
    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id")
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        assert self._reauth_entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            merged = dict(self._reauth_entry.data)
            merged[CONF_SSO_TOKEN] = user_input[CONF_SSO_TOKEN].strip()
            try:
                await _async_validate(self.hass, merged)
            except GwmAuthError:
                errors["base"] = "invalid_auth"
            except GwmConnectionError:
                errors["base"] = "cannot_connect"
            except GwmApiError:
                errors["base"] = "invalid_vin"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("GWM 重新认证时出现意外错误")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry, data=merged
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_SSO_TOKEN): cv.string}),
            description_placeholders={
                "vin": self._reauth_entry.data.get(CONF_VIN, ""),
                "phone": self._reauth_entry.data.get(CONF_PHONE, ""),
            },
            errors=errors,
        )

    # ------------------------------------------------------------------
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GwmOptionsFlow()


class GwmOptionsFlow(OptionsFlow):
    """轮询间隔 + 静态信息。凭证走 reauth 流程。"""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        current = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Optional(CONF_VEHICLE_NAME, default=entry.data.get(CONF_VEHICLE_NAME, DEFAULT_NAME)): cv.string,
                    vol.Optional(CONF_MODEL, default=entry.data.get(CONF_MODEL, "")): cv.string,
                    vol.Optional(CONF_LICENSE_PLATE, default=entry.data.get(CONF_LICENSE_PLATE, "")): cv.string,
                }
            ),
        )
