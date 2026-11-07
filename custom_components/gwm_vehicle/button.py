"""Buttons for the GWM vehicle integration.

两个诊断按钮的分工：

* ``refresh``        —— 下发 ``GW.M.REFRESH_VEHICLE_STATE``，**唤醒车机**重新上报。
                        这是 App 里「刷新数据」的等价操作，慢（10 秒 ~ 3 分钟）但数据是新的。
* ``refresh_cache``  —— 只让 HA 重新拉一遍服务端**缓存**（``GET_VEHICLE_STATE``）。
                        秒回，但车机没上报时拿到的还是旧值。

平时定时轮询走的就是后者，所以第二个按钮主要用于「手动补一次 / 排错」。
"""

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
    async_add_entities(
        [
            GwmVehicleRefreshButton(coordinator),
            GwmCacheRefreshButton(coordinator),
        ]
    )


def _upload_time_iso(coordinator: GwmCoordinator) -> str | None:
    """车机最后一次上报时间（毫秒时间戳）转本地时间字符串。"""
    status = (coordinator.data or {}).get("carStatus")
    if not isinstance(status, dict):
        return None
    stamp = status.get("uploadTime")
    try:
        return dt_util.as_local(dt_util.utc_from_timestamp(int(stamp) / 1000)).isoformat()
    except (TypeError, ValueError):
        return None


class GwmVehicleRefreshButton(GwmBaseEntity, ButtonEntity):
    """让车机重新上报一次整车状态。

    和「等几分钟自己刷新」不是一回事：
    车况平时是车机主动上报的，车熄火后就不再上报，服务端缓存会一直停在
    上一次的值。这个按钮会把 ``GW.M.REFRESH_VEHICLE_STATE`` 下发给 T-BOX，
    要求它立刻上报一遍 —— 也就是 App 里那个「刷新数据」的等价操作。

    指令下发后要等车机响应，实测车机醒着约 10 秒、休眠后 1–3 分钟；期间按钮不会卡住，
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


class GwmCacheRefreshButton(GwmBaseEntity, ButtonEntity):
    """只重新拉一次服务端缓存，不打扰车机。

    等价于 HA 平时每 ``scan_interval`` 秒做的那次轮询：调 ``GET_VEHICLE_STATE``
    读缓存，不向车机下发任何指令。秒回，但**不会**产生新数据 —— 车机没上报过，
    拿到的还是上次那份。

    用处：定时轮询恰好失败（网络抖动 / tk 被顶）后手动补一次；
    或排查「接口返回什么」时快速复现，不用等下一轮。
    想要新数据请用另一个按钮（唤醒车机）。
    """

    _attr_translation_key = "refresh_cache"
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.api.vin}_refresh_cache"
        self._last_at: Any = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "last_refresh_at": dt_util.as_local(self._last_at).isoformat()
            if self._last_at
            else None,
            "last_refresh_ok": self.coordinator.last_update_success,
            # 这次拉到的数据是车机什么时候上报的；和上次一样就说明车机没报新数据
            "data_uploaded_at": _upload_time_iso(self.coordinator),
        }

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_refresh()
        finally:
            self._last_at = dt_util.utcnow()
            self.async_write_ha_state()
