"""Constants for the GWM (Great Wall Motor) vehicle integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "gwm_vehicle"

# ---------------------------------------------------------------------------
# API endpoints (reverse engineered from GWM App 2.1.3)
# ---------------------------------------------------------------------------
# 换取 TSP tokenId（取数门票）。该接口不校验任何签名，但 tokenId 是单会话的：
# 每次调用都会签发新 tk 并作废旧的，因此必须缓存，只在失效时重登。
APP_LOGIN_URL = (
    "https://car-api.gwmapp-h.com/tsp/v1/proxy/navinfo/GW.M.APP_LOGIN"
)
# TSP 数据网关。只认请求体里的 header.tk，请求头 sign/ckey/time 可全部省略。
TSP_EAD_URL = "https://ti.gwm.com.cn:8443/tsp/ead"

FN_APP_LOGIN = "GW.M.APP_LOGIN"
FN_GET_VEHICLE_STATE = "GW.M.GET_VEHICLE_STATE"
# 远程空调（含预约空调）上一次的设置：设定温度、风量档、制冷/制热、运行时长
FN_GET_AIR_STS = "GW.M.GET_AIR_STS"
# 发动机远程启动的运行时长（分钟）
FN_GET_ENGINE_STS = "GW.M.GET_ENGINE_STS"

# TSP 请求头最小集（实测 mobileId / cid / ckey / time 均可省略）
TSP_HEADERS = {
    "v": "1.0",
    "client": "phone",
    "brandType": "GWM",
}

# 请求体 header 里的固定字段
PAYLOAD_HEADER = {
    "brandType": "gwm",
    "cVer": "2.1.3",
    "fv": "0202",
    "osType": "Android",
    "osVer": "12",
    "rs": "2",
    "v": "1.0",
}

APP_TYPE = 0

REQUEST_TIMEOUT = 25

# 业务返回码
CODE_OK = 0
CODE_TOKEN_INVALID = -101

# ---------------------------------------------------------------------------
# Config keys
# ---------------------------------------------------------------------------
CONF_SSO_ID = "sso_id"
CONF_PHONE = "phone"
CONF_SSO_TOKEN = "sso_token"
CONF_VIN = "vin"
CONF_VEHICLE_NAME = "vehicle_name"
CONF_SCAN_INTERVAL = "scan_interval"
# 下面两项接口拿不到（车辆列表接口在需要签名的 gapp-api 上），由用户手填
CONF_MODEL = "model"
CONF_LICENSE_PLATE = "license_plate"

DEFAULT_NAME = "长城汽车"
DEFAULT_SCAN_INTERVAL = 300  # 5 分钟
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 3600

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# ---------------------------------------------------------------------------
# 原始值语义映射
# ---------------------------------------------------------------------------
# 说明：以下 0/1 极性来自对抓包的分析推断，未经官方确认。
# 若某实体显示与实际相反，只需在这里调整对应元组即可。
ON_WHEN_ONE = ("1",)          # 门/窗/盖：0=关闭 1=打开
ON_WHEN_NOT_ZERO = ("1", "2", "3", "4", "5", "6", "7", "8", "9")
LOCK_ON_WHEN = ("0",)         # 车锁：0=已上锁 1=未上锁
FUEL_LOW_ON_WHEN = ("1",)     # 低油报警：1=报警
TIRE_ABNORMAL_ON_WHEN = ("1", "2", "3")  # 胎压异常状态
AIR_SWITCH_ON_WHEN = ("1",)   # 空调制冷/制热开关：1=开启
APPT_ON_WHEN = ("1",)         # 预约空调：1=已预约

# ---------------------------------------------------------------------------
# 静态资源
# ---------------------------------------------------------------------------
# 车辆官方渲染图（45° / 正面），随集成内置，用于实体与设备头像。
BRAND_IMAGE_45 = "brand/h6_45.png"
BRAND_IMAGE_90 = "brand/h6_90.png"
# 品牌图（HA 2025.1+ 会自动识别 custom_components/<domain>/brand/ 目录）
BRAND_ICON = "brand/icon.png"
BRAND_LOGO = "brand/logo.png"
# HA 静态文件路由前缀（在 __init__.py 里注册，指向集成目录）
STATIC_URL_PREFIX = "gwm_vehicle"

# ---------------------------------------------------------------------------
# 前端卡片（custom_components/<domain>/www/ 下，随 HACS 一起下载）
# ---------------------------------------------------------------------------
# 卡片 js 文件名
CARD_JS_FILENAME = "gwm-vehicle-card.js"
# 通过 HA HTTP 静态路径对外暴露的 URL（frontend.py 注册）
# 用独立前缀 <domain>-card，避免与 STATIC_URL_PREFIX 的目录路由重叠冲突
CARD_URL_PATH = f"/{DOMAIN}-card/{CARD_JS_FILENAME}"
# 仪表盘里 type: custom:gwm-vehicle-card
CARD_ELEMENT_NAME = "gwm-vehicle-card"
# 用户此前手工添加过的资源地址：自动识别并迁移/去重，避免卡片被加载两次
CARD_LEGACY_URL_PREFIXES = (
    "/local/community/gwm-vehicle-card/",
    "/local/gwm_vehicle/",
    "/local/gwm-vehicle-card.js",
    "/hacsfiles/gwm-vehicle-card/",
)

# ---------------------------------------------------------------------------
# 定位
# ---------------------------------------------------------------------------
# 车机未定位时上报 (0, 0)，按无效处理
LOCATION_ZERO_EPS = 0.0001
