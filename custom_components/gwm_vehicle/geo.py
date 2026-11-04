"""坐标系转换（GCJ-02 → WGS-84）。

长城车联网（以及绝大多数国内车联网平台）下发的经纬度是 **GCJ-02**（火星坐标、
高德/腾讯/微信地图用的那套），而 Home Assistant 的地图、``zone``、
``device_tracker`` 一律按 **WGS-84** 解释。

直接透传会有两个后果，实测本车都有：

* 车辆在地图上飘出 530 米左右，落到马路对面或别的小区
* ``distance_from_home_km`` 虚高同样的量（实测报 493 米，真实约 113 米）

所以统一在实体出口处转成 WGS-84 再交给 HA。转换只在中国境内生效，
境外坐标原样返回，不影响其他地区的用法。
"""

from __future__ import annotations

import math

__all__ = ["gcj02_to_wgs84", "out_of_china", "wgs84_to_gcj02"]

# 克拉索夫斯基椭球参数（GCJ-02 加密算法固定使用这一组）
_AXIS = 6378245.0
_EE = 0.00669342162296594323


def out_of_china(lat: float, lon: float) -> bool:
    """GCJ-02 只在中国境内做偏移，境外的坐标不该转换。"""
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def _offset_lat(x: float, y: float) -> float:
    ret = (
        -100.0
        + 2.0 * x
        + 3.0 * y
        + 0.2 * y * y
        + 0.1 * x * y
        + 0.2 * math.sqrt(abs(x))
    )
    ret += (
        20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)
    ) * 2.0 / 3.0
    ret += (
        20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)
    ) * 2.0 / 3.0
    ret += (
        160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)
    ) * 2.0 / 3.0
    return ret


def _offset_lon(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (
        20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)
    ) * 2.0 / 3.0
    ret += (
        20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)
    ) * 2.0 / 3.0
    ret += (
        150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)
    ) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lat: float, lon: float) -> tuple[float, float]:
    """WGS-84 → GCJ-02，反解时的正向迭代会用到。"""
    if out_of_china(lat, lon):
        return lat, lon

    dlat = _offset_lat(lon - 105.0, lat - 35.0)
    dlon = _offset_lon(lon - 105.0, lat - 35.0)

    rad = lat / 180.0 * math.pi
    magic = 1 - _EE * math.sin(rad) ** 2
    sqrt_magic = math.sqrt(magic)

    dlat = (dlat * 180.0) / ((_AXIS * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    dlon = (dlon * 180.0) / (_AXIS / sqrt_magic * math.cos(rad) * math.pi)
    return lat + dlat, lon + dlon


def gcj02_to_wgs84(
    lat: float, lon: float, iterations: int = 4
) -> tuple[float, float]:
    """GCJ-02 → WGS-84。

    算法没有解析反函数，用正向变换迭代逼近：每轮把残差补回去，
    4 轮之后误差已小于 1 厘米（实测本车坐标偏移 534 米时收敛到 0.0000001° 内）。
    """
    if out_of_china(lat, lon):
        return lat, lon

    wlat, wlon = lat, lon
    for _ in range(iterations):
        glat, glon = wgs84_to_gcj02(wlat, wlon)
        wlat += lat - glat
        wlon += lon - glon
    return wlat, wlon
