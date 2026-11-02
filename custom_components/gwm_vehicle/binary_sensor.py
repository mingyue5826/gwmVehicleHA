"""Binary sensors for the GWM vehicle integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AIR_SWITCH_ON_WHEN,
    APPT_ON_WHEN,
    DOMAIN,
    FUEL_LOW_ON_WHEN,
    LOCK_ON_WHEN,
    TIRE_ABNORMAL_ON_WHEN,
)
from .coordinator import GwmCoordinator
from .entity import GwmBaseEntity, resolve_path


@dataclass(frozen=True, kw_only=True)
class GwmBinaryDescription(BinarySensorEntityDescription):
    """带取数路径与极性规则的二进制传感器描述。"""

    raw_path: str
    # 命中的原始值视为 on
    on_values: tuple[str, ...] = ("1",)
    # 若设置，则「原始值不在该集合内」视为 on（用于车窗这类开度值）
    closed_values: tuple[str, ...] | None = None


BINARY_SENSORS: tuple[GwmBinaryDescription, ...] = (
    GwmBinaryDescription(
        key="door_lock",
        translation_key="door_lock",
        raw_path="carStatus.drvDoorLockSts",
        device_class=BinarySensorDeviceClass.LOCK,
        on_values=LOCK_ON_WHEN,
    ),
    GwmBinaryDescription(
        key="engine",
        translation_key="engine",
        raw_path="carStatus.engSts",
        device_class=BinarySensorDeviceClass.POWER,
        icon="mdi:engine",
        on_values=("1",),
    ),
    GwmBinaryDescription(
        key="door_fl",
        translation_key="door_fl",
        raw_path="carStatus.drvDoorSts",
        device_class=BinarySensorDeviceClass.DOOR,
        on_values=("1",),
    ),
    GwmBinaryDescription(
        key="door_fr",
        translation_key="door_fr",
        raw_path="carStatus.passDoorSts",
        device_class=BinarySensorDeviceClass.DOOR,
        on_values=("1",),
    ),
    GwmBinaryDescription(
        key="door_rl",
        translation_key="door_rl",
        raw_path="carStatus.rlDoorSts",
        device_class=BinarySensorDeviceClass.DOOR,
        on_values=("1",),
    ),
    GwmBinaryDescription(
        key="door_rr",
        translation_key="door_rr",
        raw_path="carStatus.rrDoorSts",
        device_class=BinarySensorDeviceClass.DOOR,
        on_values=("1",),
    ),
    GwmBinaryDescription(
        key="trunk",
        translation_key="trunk",
        raw_path="carStatus.trunkSts",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car-back",
        on_values=("1",),
    ),
    GwmBinaryDescription(
        key="hood",
        translation_key="hood",
        raw_path="carStatus.hoodSts",
        device_class=BinarySensorDeviceClass.OPENING,
        # 注：MDI 没有 car-engine 这个图标，写成它会渲染成空白
        icon="mdi:engine-outline",
        on_values=("1",),
    ),
    GwmBinaryDescription(
        key="window_fl",
        translation_key="window_fl",
        raw_path="carStatus.drvWinPosnSts",
        device_class=BinarySensorDeviceClass.WINDOW,
        closed_values=("0",),
    ),
    GwmBinaryDescription(
        key="window_fr",
        translation_key="window_fr",
        raw_path="carStatus.passWinPosnSts",
        device_class=BinarySensorDeviceClass.WINDOW,
        closed_values=("0",),
    ),
    GwmBinaryDescription(
        key="window_rl",
        translation_key="window_rl",
        raw_path="carStatus.rlWinPosnSts",
        device_class=BinarySensorDeviceClass.WINDOW,
        closed_values=("0",),
    ),
    GwmBinaryDescription(
        key="window_rr",
        translation_key="window_rr",
        raw_path="carStatus.rrWinPosnSts",
        device_class=BinarySensorDeviceClass.WINDOW,
        closed_values=("0",),
    ),
    GwmBinaryDescription(
        key="fuel_low_alarm",
        translation_key="fuel_low_alarm",
        raw_path="carStatus.fuelLowAlarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:gas-station-off",
        on_values=FUEL_LOW_ON_WHEN,
    ),
    GwmBinaryDescription(
        key="tire_abnormal",
        translation_key="tire_abnormal",
        raw_path="carStatus.tireSts",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:car-tire-alert",
        on_values=TIRE_ABNORMAL_ON_WHEN,
    ),
    # ---- 远程空调（GW.M.GET_AIR_STS）----
    GwmBinaryDescription(
        key="ac_cooling",
        translation_key="ac_cooling",
        raw_path="air.coldSwitch",
        icon="mdi:snowflake",
        on_values=AIR_SWITCH_ON_WHEN,
    ),
    GwmBinaryDescription(
        key="ac_heating",
        translation_key="ac_heating",
        raw_path="air.heatSwitch",
        icon="mdi:fire",
        on_values=AIR_SWITCH_ON_WHEN,
    ),
    GwmBinaryDescription(
        key="ac_appointment",
        translation_key="ac_appointment",
        raw_path="air.hasAppt",
        icon="mdi:calendar-clock",
        on_values=APPT_ON_WHEN,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GwmCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(GwmBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class GwmBinarySensor(GwmBaseEntity, BinarySensorEntity):
    entity_description: GwmBinaryDescription

    def __init__(
        self, coordinator: GwmCoordinator, description: GwmBinaryDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.api.vin}_{description.key}"

    @property
    def _raw_text(self) -> str | None:
        raw = resolve_path(self.coordinator.data, self.entity_description.raw_path)
        if raw is None:
            return None
        return str(raw).strip()

    @property
    def is_on(self) -> bool | None:
        value = self._raw_text
        if value in (None, "", "--"):
            return None
        closed = self.entity_description.closed_values
        if closed is not None:
            return value not in closed
        return value in self.entity_description.on_values

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """保留原始值，方便核对 0/1 极性。"""
        return {"raw_value": self._raw_text}
