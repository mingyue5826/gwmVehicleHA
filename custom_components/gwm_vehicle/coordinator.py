"""Data update coordinator for the GWM vehicle integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GwmApi, GwmAuthError, GwmApiError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GwmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """轮询车况。tk 由 GwmApi 内部缓存并在失效时自动重换。"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: GwmApi) -> None:
        self.api = api
        self.entry = entry

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {api.vin}",
            update_interval=timedelta(seconds=int(scan_interval)),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.async_fetch_all()
        except GwmAuthError as err:
            # 交给 HA 走重新认证流程，用户只需重新粘贴 ssoTk
            raise ConfigEntryAuthFailed(str(err)) from err
        except GwmApiError as err:
            raise UpdateFailed(str(err)) from err
