"""GWM (Great Wall Motor) vehicle integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GwmApi
from .const import (
    CONF_PHONE,
    CONF_SSO_ID,
    CONF_SSO_TOKEN,
    CONF_VIN,
    DOMAIN,
    STATIC_URL_PREFIX,
)
from .coordinator import GwmCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

# 静态图片路由只需注册一次（多个配置项共用）
_STATIC_KEY = f"{DOMAIN}_static_registered"


async def _async_register_static(hass: HomeAssistant) -> None:
    """把集成目录下的 brand/ 图片暴露成 HTTP 资源，用作设备头像。

    失败不影响主功能，只是没有头像。
    """
    if hass.data.get(_STATIC_KEY):
        return

    static_dir = Path(__file__).parent
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/{STATIC_URL_PREFIX}", str(static_dir), True)]
        )
    except ImportError:
        # 老版本 HA：同步注册
        try:
            hass.http.register_static_path(
                f"/{STATIC_URL_PREFIX}", str(static_dir), cache_headers=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("GWM 静态图片路由注册失败: %s", err)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("GWM 静态图片路由注册失败: %s", err)
    else:
        hass.data[_STATIC_KEY] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """建立配置项。"""
    api = GwmApi(
        async_get_clientsession(hass),
        sso_id=entry.data[CONF_SSO_ID],
        phone=entry.data[CONF_PHONE],
        sso_token=entry.data[CONF_SSO_TOKEN],
        vin=entry.data[CONF_VIN],
    )
    coordinator = GwmCoordinator(hass, entry, api)

    await _async_register_static(hass)

    # 首次拉取失败会抛 ConfigEntryNotReady / ConfigEntryAuthFailed，
    # 后者会自动触发重新认证流程。
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置项。"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """选项变更后重载。"""
    await hass.config_entries.async_reload(entry.entry_id)
