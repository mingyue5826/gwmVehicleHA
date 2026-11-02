"""GPS device tracker for the GWM vehicle integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BRAND_IMAGE_45, DOMAIN, STATIC_URL_PREFIX
from .coordinator import GwmCoordinator
from .entity import GwmBaseEntity, resolve_path


def _coord(value) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GwmCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GwmDeviceTracker(coordinator)])


class GwmDeviceTracker(GwmBaseEntity, TrackerEntity):
    _attr_name = None  # 用设备名作为实体名

    def __init__(self, coordinator: GwmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.api.vin}_location"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def entity_picture(self) -> str | None:
        """地图与实体卡上显示车辆渲染图（只给 tracker，避免污染所有实体）。"""
        return f"/{STATIC_URL_PREFIX}/{BRAND_IMAGE_45}"

    @property
    def latitude(self) -> float | None:
        return _coord(resolve_path(self.coordinator.data, "carStatus.lat"))

    @property
    def longitude(self) -> float | None:
        return _coord(resolve_path(self.coordinator.data, "carStatus.lon"))

    @property
    def available(self) -> bool:
        if self.latitude is None or self.longitude is None:
            return False
        if abs(self.latitude) < 0.0001 and abs(self.longitude) < 0.0001:
            return False
        return super().available
