"""Buttons for the GWM vehicle integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GwmCoordinator
from .entity import GwmBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GwmCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GwmRefreshButton(coordinator)])


class GwmRefreshButton(GwmBaseEntity, ButtonEntity):
    """手动触发一次车况拉取。

    车况是车机上报到服务器的，接口本身要 5–20 秒，点了之后实体不会立刻变，
    得等这一轮请求返回。之所以还要做，是因为刚锁车/关窗后想马上核对结果。
    """

    _attr_translation_key = "refresh"
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.api.vin}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
