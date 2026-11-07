"""Buttons for the GWM vehicle integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GwmCoordinator
from .entity import GwmBaseEntity

STATUS_TEXT = {
    "idle": "未请求",
    "waiting": "已下发，等待车机上报",
    "done": "已完成",
    "timeout": "超时，车机未响应",
    "failed": "下发失败",
}


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GwmCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GwmRefreshButton(coordinator)])


class GwmRefreshButton(GwmBaseEntity, ButtonEntity):
    """让车机重新上报一次整车状态。

    和「等几分钟自己刷新」不是一回事：
    车况平时是车机主动上报的，车熄火后就不再上报，服务端缓存会一直停在
    上一次的值。这个按钮会把 ``GW.M.REFRESH_VEHICLE_STATE`` 下发给 T-BOX，
    要求它立刻上报一遍 —— 也就是 App 里那个「刷新数据」的等价操作。

    指令下发后要等车机响应，实测 1–3 分钟；期间按钮不会卡住，
    进度看这个实体的 ``refreshing`` / ``refresh_status`` 属性。
    """

    _attr_translation_key = "refresh"
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.api.vin}_refresh"

    @property
    def available(self) -> bool:
        return super().available and not self.coordinator.refresh_busy

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        requested = self.coordinator.refresh_requested_at
        status = self.coordinator.refresh_status
        return {
            # 机器可读（idle / waiting / done / timeout / failed），前端卡片按它渲染进度
            "refresh_status": status,
            "refresh_status_text": STATUS_TEXT.get(status, status),
            "refreshing": self.coordinator.refresh_busy,
            "transaction_id": self.coordinator.refresh_seq,
            "requested_at": dt_util.as_local(requested).isoformat()
            if requested
            else None,
        }

    async def async_press(self) -> None:
        if not await self.coordinator.async_request_vehicle_refresh():
            return
        self.async_write_ha_state()
