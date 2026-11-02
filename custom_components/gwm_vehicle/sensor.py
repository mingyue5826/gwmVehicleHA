"""Numeric sensors for the GWM vehicle integration."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOCATION_ZERO_EPS
from .coordinator import GwmCoordinator
from .entity import GwmBaseEntity, resolve_path

PRESSURE_KPA = UnitOfPressure.KPA


def _to_number(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if text in ("", "--", "null", "None", "NaN"):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """两点间球面距离（haversine），与 HA 判断在家/离家用的是同一套思路。"""
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True, kw_only=True)
class GwmSensorDescription(SensorEntityDescription):
    """带取数路径的传感器描述。"""

    raw_path: str


SENSORS: tuple[GwmSensorDescription, ...] = (
    GwmSensorDescription(
        key="remain_fuel",
        translation_key="remain_fuel",
        raw_path="carStatus.remainFuel",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
    ),
    GwmSensorDescription(
        key="total_distance",
        translation_key="total_distance",
        raw_path="carStatus.vehTotDistance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
    ),
    GwmSensorDescription(
        key="tire_pressure_fl",
        translation_key="tire_pressure_fl",
        raw_path="carStatus.drvTirePress",
        native_unit_of_measurement=PRESSURE_KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="tire_pressure_fr",
        translation_key="tire_pressure_fr",
        raw_path="carStatus.passTirePress",
        native_unit_of_measurement=PRESSURE_KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="tire_pressure_rl",
        translation_key="tire_pressure_rl",
        raw_path="carStatus.rlTirePress",
        native_unit_of_measurement=PRESSURE_KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="tire_pressure_rr",
        translation_key="tire_pressure_rr",
        raw_path="carStatus.rrTirePress",
        native_unit_of_measurement=PRESSURE_KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="tire_temp_fl",
        translation_key="tire_temp_fl",
        raw_path="carStatus.drvTireTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="tire_temp_fr",
        translation_key="tire_temp_fr",
        raw_path="carStatus.passTireTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="tire_temp_rl",
        translation_key="tire_temp_rl",
        raw_path="carStatus.rlTireTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="tire_temp_rr",
        translation_key="tire_temp_rr",
        raw_path="carStatus.rrTireTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GwmSensorDescription(
        key="last_update",
        translation_key="last_update",
        raw_path="lastUpdate",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check-outline",
    ),
    # ---- 远程空调（GW.M.GET_AIR_STS）----
    GwmSensorDescription(
        key="ac_target_temperature",
        translation_key="ac_target_temperature",
        raw_path="air.temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    GwmSensorDescription(
        key="ac_volume_level",
        translation_key="ac_volume_level",
        raw_path="air.airVolumeLevel",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
    ),
    GwmSensorDescription(
        key="ac_runtime",
        translation_key="ac_runtime",
        raw_path="air.runTime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
    ),
    GwmSensorDescription(
        key="engine_runtime",
        translation_key="engine_runtime",
        raw_path="engine.runTime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:engine-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GwmCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [GwmSensor(coordinator, desc) for desc in SENSORS]
    entities.append(GwmPositionSensor(coordinator))
    async_add_entities(entities)


class GwmSensor(GwmBaseEntity, SensorEntity):
    entity_description: GwmSensorDescription

    def __init__(
        self, coordinator: GwmCoordinator, description: GwmSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.api.vin}_{description.key}"

    @property
    def native_value(self) -> float | Any:
        raw = resolve_path(self.coordinator.data, self.entity_description.raw_path)

        if self.entity_description.device_class is SensorDeviceClass.TIMESTAMP:
            value = _to_number(raw)
            if value is None:
                return None
            # 服务端给的是毫秒时间戳
            return dt_util.utc_from_timestamp(value / 1000)

        return _to_number(raw)


class GwmPositionSensor(GwmBaseEntity, SensorEntity):
    """车辆当前定位。

    ``device_tracker`` 里的「在家/离家」是 Home Assistant 核心算的：
    拿下面的经纬度和 zone.home 的圆心做球面距离，小于 area 半径（默认 100 m）
    就是在家，否则离家。集成这边只负责把车机上报的坐标交出去。
    """

    _attr_translation_key = "position"
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: GwmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.api.vin}_position"

    @property
    def _coords(self) -> tuple[float | None, float | None]:
        lat = _to_number(resolve_path(self.coordinator.data, "carStatus.lat"))
        lon = _to_number(resolve_path(self.coordinator.data, "carStatus.lon"))
        if lat is None or lon is None:
            return None, None
        # 车机未定位时会上报 (0, 0)，那是「没有坐标」而不是「几内亚湾」
        if abs(lat) < LOCATION_ZERO_EPS and abs(lon) < LOCATION_ZERO_EPS:
            return None, None
        return lat, lon

    @property
    def native_value(self) -> str | None:
        lat, lon = self._coords
        if lat is None or lon is None:
            return None
        return f"{lat:.6f}, {lon:.6f}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lat, lon = self._coords
        attrs: dict[str, Any] = {}
        if lat is not None and lon is not None:
            attrs["latitude"] = lat
            attrs["longitude"] = lon

        upload = _to_number(
            resolve_path(self.coordinator.data, "carStatus.uploadTime")
        )
        if upload:
            attrs["located_at"] = dt_util.utc_from_timestamp(
                upload / 1000
            ).isoformat()

        if lat is not None and lon is not None and self.hass is not None:
            home_lat = self.hass.config.latitude
            home_lon = self.hass.config.longitude
            if home_lat is not None and home_lon is not None:
                attrs["distance_from_home_km"] = round(
                    _distance_km(lat, lon, home_lat, home_lon), 2
                )

        return attrs
