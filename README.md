# 长城汽车 GWM — Home Assistant 集成

把长城汽车（哈弗 / WEY / 坦克 / 欧拉）的车况接入 Home Assistant。

> 本项目通过**逆向长城汽车 App 2.1.3 的接口**实现，非官方集成。接口随时可能变更。

## 能做什么

| 类型 | 实体 |
|---|---|
| 传感器 | 剩余油量、总里程、胎压-左前/右前/左后/右后、轮胎温度-左前/右前/左后/右后、车辆位置、数据更新时间、空调-设定温度、空调-风量、空调-运行时长、发动机-远程启动时长 |
| 二进制传感器 | 车锁、发动机、车门-左前/右前/左后/右后、后备箱、引擎盖、车窗-左前/右前/左后/右后、低油量报警、胎压异常、空调-制冷、空调-制热、空调-预约 |
| 设备追踪 | 车辆 GPS 位置 |
| 按钮 | 刷新数据（唤醒车机）：下发指令让车机重新上报，等同 App 里的「刷新数据」 |
| 按钮 | 刷新数据（仅重新拉取）：只重读服务端缓存，不打扰车机，秒回 |

共 36 个实体。品牌图在 `brand/`：`icon.png`(512×512，红底，取自 App Store 官方应用图标)、
`logo.png`(794×256，裁自长城官网 1306×421 透明 logo) 及对应 `dark_icon.png`/`dark_logo.png`，
全部使用官方素材，没有自己画；
设备头像用内置的车辆渲染图（`brand/h6_45.png`、`h6_90.png`，来自官方车型页）。

**只读**。不含任何远控指令。车辆列表、远控、空调控制都在需要签名的 `gapp-api` / `gw-app-gateway` 网关后面，目前无法调用。

> 空调与发动机那几个带「设定/时长」字样的实体读的是**车端上一次的设置值**（远程空调的设定温度、
> 风量档、运行时长，以及发动机远程启动时长），不是车内实时温度 —— 这辆车的空调由发动机带动，
> 熄火时不存在「车内温度」这个量。之所以做成传感器而不是配置项，见下面「为什么不把设置项放进配置」。

## 安装

### HACS（推荐）

1. HACS → 集成 → 右上角菜单 → 自定义存储库
2. 仓库地址填本仓库，类别选「集成」
3. 搜索「长城汽车 GWM」安装
4. 重启 Home Assistant

### 手动

把 `custom_components/gwm_vehicle` 整个目录复制到 Home Assistant 配置目录的 `custom_components/` 下，重启。

## 配置

设置 → 设备与服务 → 添加集成 → 搜索「长城汽车」。

必填 4 个值，全部来自抓包；另有 2 个可选字段（车型、车牌）只影响设备信息展示，接口不返回，可留空。

### 怎么拿到这 4 个值

1. 在手机上装抓包工具（推荐 **Reqable** 或 **HttpCanary**），装好它的 CA 证书
2. 打开长城汽车 App 并登录
3. 在抓包记录里找 `car-api.gwmapp-h.com` 的 **`GW.M.APP_LOGIN`** 请求
4. 该请求的 URL 形如：

   ```
   /tsp/v1/proxy/navinfo/GW.M.APP_LOGIN?p=%7B%22body%22%3A%7B...%22ssoid%22%3A%22U770...%22...
   ```

   把 `p` 参数 URL 解码后是一段 JSON：

   ```json
   {"body":{"ssoid":"U770000000000000000","phone":"13800138000","appType":0,
            "ssoTk":"0123456789abcdef0123456789abcdef"}, "header":{...}}
   ```

   | 表单字段 | 取自 |
   |---|---|
   | SSO ID | `ssoid` |
   | 手机号 | `phone` |
   | ssoTk | `ssoTk` |
   | VIN | 见下 |

5. **VIN**：在车辆列表接口 `gapp-api.gwmapp-h.com/gcar/v1/app/android/vehicle/query-vehicle-list` 的响应里找 `vin` 字段（17 位，字母数字）。

> 如果先打开过 App 车况页，`ssoTk` 一般就在这个请求里；实在找不到，`loginSSOAccount` 响应里的 `ssoToken` 和 `ptToken` 也都能填进 ssoTk 字段。
>
> 同一个响应里还能顺手拿到 `brandName`（品牌）、`modelName`（车型）、`licenseNumber`（车牌）——集成不自动读取（该接口需要签名），需要的话填到可选项里。

## 已知限制

### 1. tokenId 是单会话，会顶掉手机 App

Home Assistant 换票后，手机 App 的车况页会话会被作废，App 里可能提示重新登录。

这是服务端的限制，绕不开。集成内部只在必要时换票（缓存 tk，失效才重登），已经把影响降到最低。

### 2. ssoTk 会过期，需要重新抓包

| 凭证 | 有效期 |
|---|---|
| `tokenId` | 自动续，用户无感 |
| `ssoTk` | 实测 ≥ 6 天（同批登录签发的 accessToken 为 7 天、refreshToken 为 30 天） |

**过期后怎么办**：Home Assistant 会自动弹出「需要重新认证」，只要把新的 `ssoTk` 粘进去即可，其他配置不用重填。

### 3. 数据新鲜度取决于车机上报

车况由车上 T-Box 主动上报，熄火后就不再上报，服务端缓存会一直停在上一次的值。
**定时轮询（默认 5 分钟）只是读缓存，不会让车机上报新数据** —— 想立刻拿到最新状态，
需要点「刷新数据（唤醒车机）」按钮，它会把 `GW.M.REFRESH_VEHICLE_STATE` 下发给车机，要求立刻上报一遍。
另有一个「刷新数据（仅重新拉取）」，只重读服务端缓存，不唤醒车机，秒回 —— 数据新旧不变，
用于刚好轮询失败时手动补一次。

下发后车机需要时间响应：醒着时约 10 秒，休眠后 1–3 分钟，无信号/地库则可能一直没响应（3 分钟超时）。
按钮不会卡住，进度看它的 `refreshing` / `refresh_status` 属性；刷新期间按钮暂不可用，
联动 60 秒冷却，避免反复唤醒车机耗电瓶。

`数据更新时间` 传感器显示的是车机最后一次上报的时间，刷新成功后它会跟着跳。

### 4. 门窗状态的 0/1 极性

`车锁`、`车门`、`车窗`等实体的开关判断基于抓包推断，未经官方文档确认：

| 字段 | 假设 |
|---|---|
| `drvDoorLockSts` | 0 = 已上锁，1 = 未上锁 |
| `drvDoorSts` 等 | 0 = 关闭，1 = 打开 |
| `drvWinPosnSts` 等 | 0 = 关闭，非 0 = 打开 |

车门极性已由用户在实车核对确认（0 = 关闭）。车锁按同一套约定推断。每个二进制传感器都带一个 `raw_value` 属性，可用于核对。**若显示与实际相反**，改 `custom_components/gwm_vehicle/const.py`：

```python
LOCK_ON_WHEN = ("0",)   # 若 0 其实是未上锁，改成 ("1",)
```

改完重启 Home Assistant。

### 5. 「在家 / 离家」是 Home Assistant 自己算的

设备追踪实体只提供车辆的经纬度（来自 `carStatus.lat/lon`）。「在家」还是「离家」由 HA 核心判断：
拿这个坐标和 `zone.home` 的圆心算球面距离，小于该区域的半径就是**在家**，否则**离家**。

默认半径 100 m，觉得太灵敏就去 **设置 → 区域与地点 → 家** 改半径。集成不参与这个判断。

> 车辆位置传感器（`sensor.*_position`）把同一份坐标也暴露成传感器：
> 状态是 `纬度, 经度`，属性里有 `latitude`、`longitude`、`located_at`（车机定位上报时间）
> 和 `distance_from_home_km`（距家的直线距离）。

### 6. 为什么不把设置项放进配置

「空调-设定温度」「空调-风量」「空调-运行时长」「发动机-远程启动时长」这几个值看着像设置项，
但它们是**车端记住的上次操作值**，不是 Home Assistant 的偏好设置。控制接口没逆出来，
HA 这边写不回去；做成配置项只会出现「HA 里填 20 分钟、车里实际 30 分钟」的两套数据打架。

所以保留为传感器。等以后远控接口能用，它们会直接并进 `climate` / `button` 实体，不需要迁移配置。

## 为什么不做账号密码自动登录

理论上可以用「手机号 + 密码」直接登录，彻底免掉手工抓包。但登录接口的请求体是 **CryptoJS AES-CBC + OpenSSL KDF** 加密的（`Salted__` 前缀，`U2FsdGVkX1...`），密钥硬编码在 native 库 `libsapp_crypto_tool.so` 中，且 App 用网易易盾加固 + Frida 反调试。

已尝试并失败的路子：700+ 次口令字典爆破、229k 个 dex 字符串 × 9 种密钥派生、2k 个 hex 常量直作 AES key、Frida 动态 hook（attach 即被易盾杀进程）。

如果后续拿到密钥，只需扩展 `api.py`，实体层不用改。

## 文件结构

```
custom_components/gwm_vehicle/
├── __init__.py          # 配置项生命周期 + 静态图片路由
├── api.py               # API 客户端 + tk 缓存/自动重换
├── coordinator.py       # 轮询调度
├── config_flow.py       # 配置表单 + 重新认证
├── entity.py            # 实体基类
├── sensor.py            # 数值传感器 + 车辆位置
├── binary_sensor.py     # 二进制传感器
├── device_tracker.py    # 地图定位
├── button.py            # 下发改刷新指令 + 后台轮询车机是否上报
├── frontend.py          # 前端卡片自动注册（静态路径 + Lovelace 资源表）
├── www/
│   └── gwm-vehicle-card.js  # 车辆状态卡片（custom:gwm-vehicle-card）
├── const.py             # 常量 + 极性规则
├── brand/               # 品牌图（icon/logo + 深色版）+ 车辆渲染图（45°/侧面俯视 h6_top.png）
├── manifest.json
├── strings.json
└── translations/
```

## 车辆状态卡片（前端）

集成自带一张 Lovelace 卡片 `custom:gwm-vehicle-card`（文件在
`custom_components/gwm_vehicle/www/gwm-vehicle-card.js`，随 HACS 一起安装）。

**装完重启 HA 即可用，无需手动添加资源**——集成启动时会自动：

1. 把卡片 js 注册为 HTTP 静态路径 `/gwm_vehicle-card/gwm-vehicle-card.js`
2. 写进 Lovelace 资源表（URL 带 `?v=版本号`，升级后浏览器自动丢弃旧缓存）
3. 若你的 Lovelace 是 YAML 模式（资源表只读），自动退回 `add_extra_js_url`
4. 从 HACS 之外手工装过旧版卡片的，会自动识别旧地址并去重迁移
5. 删除集成的最后一个配置条目时，自动从资源表移除卡片

卡片内容（全部素材随集成内置在 `brand/`，无需外链）：

| 元素 | 素材 / 实现 | 说明 |
|---|---|---|
| 车图 | `brand/h6_top.png` | 俯视线稿，车头朝上；深色主题自动反色；可换图、调不透明度与最大高度 |
| 胎压 / 胎温 | **四个轮胎常显胎压+胎温两行标注，各引一条水平引导线指到车轮中心**（版式对齐车机 App） | 端点以车图百分比定位，卡片任意宽度都不会跑偏；异常轮改红框红字闪烁 + 红色虚线 + 红胎叠加 |
| 车门打开 | **真实开门俯视图裁下的门片**（`door_front_open.png` / `door_rear_open.png`，左侧门自动镜像） | `door_overlay: false` 可退回「门」字角标 |
| 车窗 / 引擎盖 / 后备箱 | 琥珀「窗/盖/箱」角标 | 位置 `markers` 可调 |
| 发动机启动 | 红色发动机叠加层 `brand/h6_engine.png` | `engine_image`/`engine_region` 可配 |
| 空调 | 制冷蓝 / 制热红胶囊徽标（呼吸动画） | 含设定温度 |
| 未上锁 | 虚线琥珀边框 + 锁形角标（`lock_style` 可选） | 已按集成 `raw_value` 正确判断极性 |
| 其余 | 告警旗（加油机/车胎图标）、总里程、油量进度条、定位（点击弹地图）、更新时间 + 刷新 | 刷新会提示「车机是否已上报新数据」 |

总里程在标题行**右端对齐**（左侧车名、右侧里程，两端撑满），带 `总里程` 前置标签。

四个轮胎的胎压与胎温**默认常显**在车图两侧（`224 kPa` / `27°C` 两行），
每个标注都有一条水平引导线，**线端点落在车轮中心**（坐标取自车图百分比，与卡片宽度无关），
只有轮胎异常时才变红闪烁。`show_tire_normal: false` 可退回「仅异常时显示」；
车图下方那行文字摘要默认关闭（`show_tire_summary: true` 可开）。

实体自动识别按 **translation_key → entity_id 正则（`tyre`/`tire` 两种写法都认）→
中文 friendly_name** 三级匹配；卡片底部会提示未识别实体，浏览器控制台可看完整识别日志。

### 可点击区域

点任意可交互元素会直接弹出该实体的 HA 标准 more-info 弹窗，不用跳转别处。

| 点击位置 | 弹出实体 |
|---|---|
| 标题行右侧「总里程 xxx km」 | `sensor.*odometer`（总里程） |
| 四个胎压标注块 | **短按** → 该轮胎压；**长按 0.5 秒** → 该轮胎温 |
| 车图四个车门位置 | 对应 `door_fl` / `door_fr` / `door_rl` / `door_rr` |
| 车头发动机位置 | `engine`（发动机启动状态） |
| 车顶「盖 / 箱 / 窗」角标 | 引擎盖 / 后备箱 / 对应车窗 |
| 空调胶囊「制冷 xx°C」 | `ac_target_temperature` |
| 油量告警旗 / 油量进度条整块 | `remain_fuel`（剩余油量） |
| 胎压异常告警旗 | `tire_abnormal` |
| 底部定位条 | `device_tracker`（没有则打开高德地图） |

车门和发动机的点击区是**透明热区**，范围比线稿本身大一圈（车图很细，门缝只有几像素宽），
桌面端鼠标移上去会有淡色底衬；移动端直接点即可。长按胎压块时手机会有轻微震动反馈。

### 车锁极性说明

集成把原始值 `0=已上锁` 映射成实体 `on`，这与 HA 对 `lock` 类 binary_sensor
「on = 未上锁」的约定相反。卡片会优先读实体的 `raw_value` 属性来判断，
因此不会把已上锁的车误报成「未上锁」。

### 使用

编辑仪表盘 → 添加卡片 → 手动，粘贴：

```yaml
type: custom:gwm-vehicle-card
```

多辆车时用设备名区分：

```yaml
type: custom:gwm-vehicle-card
device: 哈弗H6          # 匹配设备名（包含即可）
```

### 全部配置项

```yaml
type: custom:gwm-vehicle-card
device: ""                # 设备名匹配（推荐多车时用）；留空自动识别
prefix: ""                # 或按 entity_id 前缀匹配
title: ""                 # 自定义标题；留空用设备名
entities: {}              # 显式指定实体，如 {remain_fuel: sensor.xxx}，优先级最高
image: /gwm_vehicle/brand/h6_top.png  # 车图 URL
image_opacity: 1          # 车图不透明度 0~1
car_max_height: 420       # 车图最大高度 px
markers: {}               # 位置覆盖，如 {tire_fl: {x: 7, y: 14.2, side: left}}（占车图百分比，x 同时是引导线终点）
engine_image: /gwm_vehicle/brand/h6_engine.png   # 发动机红色叠加图
engine_region: {x: 33.5, y: 9, w: 34.5, h: 13.5} # 发动机叠加区域（占车图百分比）
door_overlay: true        # 开门时贴真实门片（false 退回「门」字角标）
door_layout: {}           # 门片位置覆盖，如 {fr: {left: 92.95, top: 28.99, w: 46.58}}
tire_overlay: true        # 胎压异常时贴红色轮胎
tire_layout: {}           # 红胎位置覆盖
show_tire_normal: true    # 正常轮胎也显示胎压/胎温标注（默认开启；false = 仅异常时显示）
show_tire_summary: false  # 车图下方一行文字摘要（默认关闭，两侧标注已含全部读数）
fuel_capacity_l: 58       # 油箱容量（升），把剩余升数换算成百分比（进度条/阈值用）
fuel_low_percent: 10      # 无低油报警时的油量告警阈值（%）
pressure_low: 190         # 胎压下限 kPa（低于判异常，红色）
pressure_high: 300        # 胎压上限 kPa
temp_high: 60             # 胎温上限 °C
lock_style: both          # 未上锁提示：both 虚线边框+角标 / border 仅边框 / badge 仅角标
blink: true               # 异常项是否闪烁
ac_animation: true        # 空调徽标呼吸动画
```

### YAML 模式 Lovelace

资源表不可写时集成会走 `add_extra_js_url` 兜底，一般无需手动配置；若要手动声明：

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /gwm_vehicle-card/gwm-vehicle-card.js?v=0.3.0
      type: module
```

## 排错

打开 Home Assistant 日志（设置 → 系统 → 日志）搜索 `gwm_vehicle`。

| 现象 | 原因 |
|---|---|
| 提示「ssoTk 无效或已过期」 | 重新抓包填新的 ssoTk |
| 提示「VIN 无效」 | VIN 填错，或该车不在账号下 |
| 实体长期 `未知` | 车机未上报，或车辆熄火休眠 |
| 提示「无法连接」 | 网络问题，或接口变更 |
| 点了「刷新数据」实体没马上变 | 正常，指令下发后要等车机响应（10 秒 ~ 3 分钟），看按钮的 `refresh_status` 属性 |
| 按钮变灰、点不了 | 正在等车机上报（最长 3 分钟），或处于 60 秒冷却期 |
| `refresh_status` = 超时，车机未响应 | 车在地库/无信号，或 T-BOX 离线；等车机下次自然上报即可 |
