"""GPS device tracker for the GWM vehicle integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BRAND_IMAGE_45, DOMAIN, STATIC_URL_PREFIX
from .coordinator import GwmCoordinator
from .entity import GwmBaseEntity, resolve_path
from .geo import gcj02_to_wgs84


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
    def _wgs84(self) -> tuple[float | None, float | None]:
        """车机给的是 GCJ-02，转成 HA 通用的 WGS-84。

        不转的话车辆会在地图上偏 500 米出头，「距家距离」也跟着虚高
        （实测 493 m vs 实际 113 m）。
        """
        lat = _coord(resolve_path(self.coordinator.data, "carStatus.lat"))
        lon = _coord(resolve_path(self.coordinator.data, "carStatus.lon"))
        if lat is None or lon is None:
            return None, None
        # 车机未定位时上报 (0, 0)，那是「没有坐标」而不是几内亚湾
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            return None, None
        return gcj02_to_wgs84(lat, lon)

    @property
    def latitude(self) -> float | None:
        return self._wgs84[0]

    @property
    def longitude(self) -> float | None:
        return self._wgs84[1]

    @property
    def available(self) -> bool:
        if self._wgs84[0] is None or self._wgs84[1] is None:
            return False
        return super().available
