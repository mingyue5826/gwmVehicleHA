"""Base entity for the GWM vehicle integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_LICENSE_PLATE,
    CONF_MODEL,
    CONF_VEHICLE_NAME,
    DEFAULT_NAME,
    DOMAIN,
)

if TYPE_CHECKING:
    from .coordinator import GwmCoordinator


def resolve_path(data: Any, path: str | None) -> Any:
    """按 "carStatus.remainFuel" 这种点路径取值，取不到返回 None。"""
    if not path or not isinstance(data, dict):
        return None
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
        if node is None:
            return None
    return node


class GwmBaseEntity(CoordinatorEntity["GwmCoordinator"]):
    """所有实体的公共基类：绑定到同一台车。"""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GwmCoordinator) -> None:
        super().__init__(coordinator)
        self._vin: str = coordinator.api.vin
        self._entry: ConfigEntry = coordinator.entry

    # ------------------------------------------------------------------
    # 配置读取（options 优先，回退到 data）
    # ------------------------------------------------------------------
    def config_value(self, key: str, default: str = "") -> str:
        value = self._entry.options.get(key) or self._entry.data.get(key) or default
        return str(value).strip()

    @property
    def vehicle_name(self) -> str:
        return self.config_value(CONF_VEHICLE_NAME, DEFAULT_NAME)

    @property
    def device_info(self) -> DeviceInfo:
        model = self.config_value(CONF_MODEL)
        plate = self.config_value(CONF_LICENSE_PLATE)
        if plate:
            model = f"{model} · {plate}" if model else plate

        return DeviceInfo(
            identifiers={(DOMAIN, self._vin)},
            name=self.vehicle_name,
            manufacturer="长城汽车 GWM",
            model=model or None,
            serial_number=self._vin,
            configuration_url="https://www.gwm.com.cn",
        )

    # ------------------------------------------------------------------
    # 数据便捷访问
    # ------------------------------------------------------------------
    @property
    def car_status(self) -> dict[str, Any]:
        """carStatus 子节点，绝大多数车况字段都在这里。"""
        data = self.coordinator.data or {}
        status = data.get("carStatus")
        return status if isinstance(status, dict) else {}

    @property
    def air_status(self) -> dict[str, Any]:
        """远程空调上一次的设置。"""
        data = self.coordinator.data or {}
        air = data.get("air")
        return air if isinstance(air, dict) else {}

    @property
    def engine_status(self) -> dict[str, Any]:
        """发动机远程启动信息。"""
        data = self.coordinator.data or {}
        engine = data.get("engine")
        return engine if isinstance(engine, dict) else {}

    def raw(self, key: str) -> Any:
        """取 carStatus 里的原始字段值，找不到返回 None。"""
        return self.car_status.get(key)
