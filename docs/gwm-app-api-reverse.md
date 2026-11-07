# 长城汽车 App（GWM）接口逆向分析 — 登录链路与车辆数据获取

分析对象：`抓包/未命名文件夹` 共 108 组请求/响应（编号 803–910），覆盖"输入账号密码点登录 → 首页 → 我的车"全过程。
抓包时间：2026-11-01 21:59–22:00（GMT+8），App 版本 2.1.3 / Android / `GWM-APP-ANDROID-1100018`。

---

## 1. 结论先说

| 项 | 结论 |
|---|---|
| 登录必需 | 是。车辆数据接口靠 `tk`（tokenId）鉴权，`tk` 只能由登录链换取 |
| 登录链长度 | 5 步：密码登录 → SSO 换 token → TSP 登录 → 车辆列表 → token 上报 |
| 最难点 | 第 1 步 `pwd-login` 请求/响应 body 为 **AES(CryptoJS OpenSSL 格式) 密文**，口令硬编码在 APK 内 → 必须反编译 |
| 数据获取 | 主数据走 TSP 接口 `ti.gwm.com.cn:8443/tsp/ead`，**实测不校验 `sign`/`ckey`，只校验 payload 内的 `tk`** |
| 可绕过项 | TSP 的 `sign` 头可任意填/不填；`ckey` 固定 `ea49a50f914b8d38af1c84809d302683` |
| 不可绕过项 | gapp-api 的 `Sign`（SHA256）、gw-app-gateway 的 `bt-auth-sign`（有 appKey 但缺 appSecret） |
| 免签名的换票链 | `GW.M.APP_LOGIN` 用 `ssoId+ssoToken` 直接换 `tk`，**不校验 sign/ckey**，可完全跳过 `loginSSOAccount`(bt-auth) |
| 唯一缺口 | `pwd-login` 的 AES 口令（硬编码 APK 内）→ 拿到它即可实现"账号密码直登" |
| 重要约束 | `tk` 单会话：每次 `GW.M.APP_LOGIN` 会踢掉上一个 `tk` |

---

## 2. 域名分工

| 域名 | 作用 | 鉴权 |
|---|---|---|
| `gapp-api.gwmapp-h.com` | 业务主 API（登录、车辆列表、用户、社区） | `G-TOKEN`(JWT) + `Sign`(SHA256 64hex) |
| `gw-app-gateway.gwmapp-h.com` | 新版网关（车辆安全、远控、服务项、消息中心） | `accessToken`/`tokenId` 头 + `bt-auth-*` 签名 |
| `car-api.gwmapp-h.com` | TSP 代理（APP_LOGIN） | `sign`(SHA1 Base64) + `ckey` |
| `ti.gwm.com.cn:8443` | TSP 车况网关（**核心数据源**） | payload 内 `tk`，`sign` 不校验 |
| `bmp-api.gwmapp-h.com` | 消息未读数 | 同 gapp-api |
| `quickaplus-api.gwm.cn` / `odata.gwm.cn` | 友盟埋点、神策埋点 | 无关，忽略 |

---

## 3. 登录链路（时序）

```
① POST gapp-api /api-guser/v5/user/pwd-login          ← 账号密码（AES 加密体）
        ↓ data 为 G_A(...) 密文，内含 ssoId + ssoToken
② POST gw-app-gateway /app-api/api/v1.0/userAuth/loginSSOAccount
        ↓ 明文返回 accessToken / refreshToken / ssoToken(新) / beanId
③ GET  car-api /tsp/v1/proxy/navinfo/GW.M.APP_LOGIN   ← ssoTk 换 TSP 登录态
        ↓ 返回 tokenId(=TSP tk) / userId / gwid
④ POST gapp-api /gcar/v1/app/android/vehicle/query-vehicle-list
        ↓ 车辆列表（vin、品牌、车型、车牌…）
⑤ POST gapp-api /api-guser/v1/token/submit            ← 兜底上报 token（可省）
```

### 3.1 ① 密码登录

```
POST https://gapp-api.gwmapp-h.com/api-guser/v5/user/pwd-login
G-TOKEN: (登录前为空)
Sign: <sha256 64hex>            ← 登录前也有，说明 Sign 不依赖登录态
TimeStamp: 1793541554000
DeviceId: 0123456789abcdef0123456789abcdef
NoteId: 145765423214576567716671
SourceApp: GWM / SourceType: ANDROID / SourceAppVer: 2.1.3 / SourceAppCode: 2130
AppId: GWM-APP-ANDROID-1100018

G_A(U2FsdGVkX1/6Up3Yml6...,1)      ← 整个 body 是密文文本，长度 1351
```

- `U2FsdGVkX1...` = `"Salted__"` 的 Base64 → **CryptoJS AES-CBC + OpenSSL KDF**（8 字节 salt 前缀，PKCS7 padding）。
- 明文应是 `{"phone":"...","password":"..."}` 结构的 JSON（长度 1351 密文 ≈ 明文 100 字节左右）。
- 响应同格式：`{"code":0,"data":"G_A(U2FsdGVkX19uvnNg...,1)"}`，解密后含 `ssoId`、`ssoToken`、`G-TOKEN`。

### 3.2 ② SSO 换 token（明文，已可读）

```
POST https://gw-app-gateway.gwmapp-h.com/app-api/api/v1.0/userAuth/loginSSOAccount
beanId / tenantId:1 / terminal:GW_APP_GWM / enterPriseId:CC01 / rs:2
appId: 097a7099af30d960 / brand: 10
bt-auth-appkey: 7863128529   bt-auth-nonce: <16hex>   bt-auth-timestamp: <ms>   bt-auth-sign: <sha256>

{"appType":0,"deviceId":"...","phone":"178...","ssoId":"U770...","ssoToken":"0123456789abcdef0123456789abcdef"}
```

响应关键字段：

| 字段 | 值示例 | 用途 |
|---|---|---|
| `accessToken` | `eyZ4pHNpYnXH...`（长串，非 JWT） | 网关类接口 `accessToken` 头 |
| `refreshToken` | `eyFlyTsbPyUU...` | 刷新用 |
| `ssoToken` | `0123456789abcdef0123456789abcdef` | 下一步 TSP 登录 |
| `ssoId` | `U770000000000000000` | 用户 ID（JWT 里也叫 userId） |
| `beanId` | `2800000000000000000` | 全链路都要带 |
| `ptToken` | `0123456789ab...` | 与旧 ssoToken 相同 |

### 3.3 ③ TSP 登录（换 `tk`）

```
GET https://car-api.gwmapp-h.com/tsp/v1/proxy/navinfo/GW.M.APP_LOGIN?p=<urlencode json>
Header: v:1.0  cid:<deviceId>  client:phone  sign:<sha1 base64>  time:<ms>
        ckey:ea49a50f914b8d38af1c84809d302683  token:""
        protocolVer:2.1.2  brandType:GWM

p = {"body":{"pushId":"0","pushKey":"0","ssoid":"U770...","phone":"178...","appType":0,"ssoTk":"996589..."},
     "header":{"brandType":"gwm","cVer":"2.1.3","fn":"GW.M.APP_LOGIN","fv":"0202",
               "mobileId":"<deviceId>","osType":"Android:24031PN0DC","osVer":"12",
               "rs":"2","ts":"<yyyyMMddHHmmssSSS>","tk":"","v":"1.0"}}
```

响应：

```json
{"header":{"c":0,"fn":"GW.M.APP_LOGIN","m":"Success"},
 "body":{"tokenId":"0123456789abcdef0123456789abcdef","hasPwd":"1","hasScyPwd":1,
         "gwid":"2800000000000000000","userId":"0123456789abcdef0123456789abcdef"}}
```

**`tokenId` 就是后续所有 TSP 请求的 `tk` / `token`。**

### 3.4 ④ 车辆列表

```
POST https://gapp-api.gwmapp-h.com/gcar/v1/app/android/vehicle/query-vehicle-list
G-TOKEN: <JWT, RS256>   Sign: <sha256>   beanId / ssoId / DeviceId / TimeStamp / NoteId
{"vehicleVersion":13}
```

`G-TOKEN` 是 JWT，payload 明文可读：
```json
{"nbf":1793541554,"sourceApp":"GWM","sourceType":"ANDROID","appId":"GWM-APP-ANDROID-1100018",
 "exp":1794146354,"iat":1793541554,"userId":"U770000000000000000","deviceId":"0123456789abcdef0123456789abcdef"}
```
有效期 7 天（exp-iat=604800），签名算法标注 `SHA256withRSA`。

响应 `data.acquireVehiclesList[]` 关键字段：`vin`、`licenseNumber`、`brandCode`、`commonModelName`、`vehicleModelCode`、`type`、`defaultVehicle`、`gpsServiceStatus`、`shareId`。

---

## 4. 三套签名机制

| 位置 | 形态 | 已知线索 | 是否必须 |
|---|---|---|---|
| `gapp-api` 头 `Sign` | SHA256 64 hex | 报错文案 `version3 serverSign is not equal appSign`；登录前即存在，与 `body`/`TimeStamp`/`DeviceId`/`NoteId` 相关 | 必须（实测伪造即 4001） |
| `gw-app-gateway` `bt-auth-sign` | SHA256 64 hex | 头里同时给 `bt-auth-appkey: 7863128529`、`bt-auth-nonce`、`bt-auth-timestamp`、`appId: 097a7099af30d960` | 必须（缺失/不符明确报错） |
| `car-api` / `ti.gwm.com.cn` 头 `sign` | SHA1 → Base64（20 字节） | `ckey` 固定 `ea49a50f914b8d38af1c84809d302683` | **不校验（实测）** |

### 4.1 网关报错对照（实测）

| 情况 | 返回 |
|---|---|
| 原样重放（timestamp 已过期） | `{"code":"607005","description":"signature is invalid"}` |
| 删除 `bt-auth-sign` | `{"code":"607012","description":"sign is null"}` |
| 改 `bt-auth-sign` | `{"code":"607099","description":"sign is inconformity"}` |

→ 有 sign **且** 时间窗校验（原样重放仍失败，说明 timestamp 参与签名且有容忍窗口，估计 60s–5min）。

### 4.2 TSP 不校验签名（实测 4 组）

对 `ti.gwm.com.cn:8443/tsp/ead` 用同一 payload 做对照：

| 变体 | 结果 |
|---|---|
| A 原样重放 | 200 Success（数据完整） |
| B 删除 `sign` 头 | 200 Success |
| C `sign` 改 `AAAA` | 200 Success |
| D `time` 改当前时间 | 200 Success |
| E `token` 头删掉（payload 内 `tk` 保留） | 200 Success |
| F payload 内 `tk` 置空 | `c:-101 未知的function访问权限` |
| G payload 内 `tk` 造假 | `c:-101 缓存数据已失效，需要您重新进行登录` |

→ **TSP 只认 payload 里的 `tk`，其余头部形同虚设。** 这让车况轮询实现极简（见第 6 节代码）。

---

## 5. 数据接口清单（按 HA 价值排序）

| # | 接口 | 方法/域名 | 关键 body / query | 返回 |
|---|---|---|---|---|
| 1 | `GW.M.GET_VEHICLE_STATE` | GET `ti.gwm.com.cn:8443/tsp/ead` | `body:{vin}` | 油量、电量、胎压×4、四门、四窗、后备箱、引擎盖、锁、经纬度、总里程、发动机状态、充电状态 |
| 2 | `GW.M.GET_ENGINE_STS` | 同上 | `body:{userId,vin}` | `runTime`（远程启动已运行秒数） |
| 3 | `GW.M.GET_MESSAGE_LIST` | 同上 | `body:{}` | 车机消息条数 |
| 4 | 车辆列表 | POST `gapp-api /gcar/v1/app/android/vehicle/query-vehicle-list` | `{vehicleVersion:13}` | VIN、车牌、车型 |
| 5 | 远控能力配置 | POST `gw-app-gateway /app-api/api/v3.0/vehicle/remote-ctrl/config/query` | `{sendType:0,types:["AIR_CONDITIONER_START"],userId:<tokenId>,vin}` | 该车支持的远控项与参数 |
| 6 | 车辆安全信息 | GET `gw-app-gateway /app-api/api/v3.0/vehicle/security/info?version=1` | — | `securityTime:2592000`（免密有效期 30 天）、`isSecurityPasswordExist` |
| 7 | 服务项 | GET `gw-app-gateway /app-api/api/v3.0/vehicle/service/item/{vin}?userRole=1` | — | TOF 能力码（远程控制/安防/坐席等） |
| 8 | 车辆图片 | GET `gw-app-gateway /app-api/api/v3.0/vehicle/picture/{vin}` | — | 外观色、选装件 |
| 9 | `GW.M.REFRESH_VEHICLE_STATE` | GET `ti.gwm.com.cn:8443/tsp/ead` | `body:{vin}` | 只返回 `transactionId`；**让车机重新上报**，数据靠 #1 再取 |

### 5.1 车况字段样例（`GW.M.GET_VEHICLE_STATE`）

```json
{"vehicleSts":{
  "battSts":{"chgSts":0,"socSts":-1,"finishTime":-1},          // 充电状态（燃油车为空值）
  "carStatus":{"remainFuel":"13","vehTotDistance":"12345",
    "drvTirePress":"228","passTirePress":"226","rlTirePress":"222","rrTirePress":"224",
    "drvTireTemp":"30","passTireTemp":"31","rlTireTemp":"28","rrTireTemp":"29",
    "drvDoorSts":0,"passDoorSts":0,"rlDoorSts":0,"rrDoorSts":0,"trunkSts":0,"hoodSts":"0",
    "drvDoorLockSts":0,
    "drvWinPosnSts":0,"passWinPosnSts":0,"rlWinPosnSts":0,"rrWinPosnSts":0,
    "engSts":"0","engstsValid":"1",
    "lat":"39.908692","lon":"116.397477","uploadTime":1793540666000},
  "chargeSettings":{"mode":"1","socLimit":"0"},
  "lastUpdate":1793540666000,"apptAirSts":0,"vin":"LGWEF5A50NH000001"}}
```

（本车为哈弗 H6 燃油版：`remainFuel=13`、`tankCapacity=0.0`、`socSts=-1`）

---

## 6. 已跑通的取数代码（无需签名）

```python
import json, urllib.parse, urllib.request

TK   = "0123456789abcdef0123456789abcdef"   # 由 3.3 得到
VIN  = "LGWEF5A50NH000001"
BASE = "https://ti.gwm.com.cn:8443/tsp/ead"

def tsp(fn: str, body: dict) -> dict:
    p = {"body": body,
         "header": {"brandType": "gwm", "cVer": "2.1.3", "fn": fn, "fv": "0202",
                    "mobileId": "", "osType": "Android", "osVer": "12",
                    "rs": "2", "ts": "20261101220000000", "tk": TK, "v": "1.0"}}
    url = BASE + "?p=" + urllib.parse.quote(json.dumps(p, separators=(",", ":")))
    hdr = {"v": "1.0", "client": "phone", "ckey": "ea49a50f914b8d38af1c84809d302683",
           "token": TK, "brandType": "GWM"}          # sign / time / cid 均可省略
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20) as r:
        return json.loads(r.read())

print(tsp("GW.M.GET_VEHICLE_STATE", {"vin": VIN}))
print(tsp("GW.M.GET_ENGINE_STS",   {"userId": "0123456789abcdef0123456789abcdef", "vin": VIN}))
```

已实测返回完整车况。`ts` 填固定值也能过（网关不校验时间）。

---

## 7. 卡点：密码登录的 AES 与两处签名

### 7.1 已尝试且失败的推测式爆破

| 尝试 | 范围 | 结果 |
|---|---|---|
| AES-256/128-CBC + MD5 KDF 解密 `pwd-login` 请求体 | 60+ 常见口令（gwm/GWM2020/greatwall/beantech/appId/机型…） | 全部失败 |
| `bt-auth-sign` 猜测 | `{appId,nonce,ts,appkey,path,method,tenantId,terminal}` 的 1–5 阶排列 × 7 种分隔符 × kv/v 两种形态 × md5/sha1/sha256/HMAC(key=appkey/appId) | 0 命中 |
| `Sign`(gapp) 同上 | — | 无有效输入（缺 secret） |

结论：**签名/TLS 层面没有"通用公钥/固定 IV"可推算**——不是 RSA 公钥加密，而是 HMAC/AES 对称密钥，密钥为 APK 内常量。必须拿到 APK 反编译。

### 7.2 下一步（需要 APK）

1. 取包：`adb shell pm path com.gwm.app`（包名待确认）→ `adb pull`，或用 apkpure/应用宝下载 2.1.3。
2. `jadx-gui` 打开，按序搜：
   - `Salted__` / `CryptoJS` / `AES/CBC/PKCS5Padding` → 找 AES 口令与 `G_A` 实现
   - `"Sign"` / `serverSign` / `version3` → 找 gapp 签名拼接与 secret
   - `bt-auth-sign` / `btAuth` / `7863128529` → 找网关签名（appSecret 大概率在同一常量类）
   - `ea49a50f914b8d38af1c84809d302683` → 直接定位 TSP 渠道密钥类
3. 若代码混淆/so 加固：Frida hook 兜底
   ```js
   // 通用：hook 所有 MessageDigest / Mac 的输入输出，打印明文与摘要
   Java.perform(() => {
     const MD = Java.use('java.security.MessageDigest');
     MD.digest.overload('[B').implementation = function (b) {
       const r = this.digest(b);
       console.log('MD ' + this.getAlgorithm() + ' in=' + bytesToStr(b) + ' out=' + bytesToHex(r));
       return r;
     };
   });
   ```
   配合 hook `javax.crypto.Cipher.doFinal` 抓 AES 明文/密钥。

### 7.3 若无 APK 的降级方案

| 方案 | 说明 | 代价 |
|---|---|---|
| 手动粘贴 token | 用户抓一次包，把 `tk` + `vin` 填进 HA 配置，7 天过期后重填 | 无需逆向，但体验差 |
| 只做传感器 | 用 `tk` 轮询 TSP 车况（本文第 6 节代码） | 可以立刻验证集成效果 |
| 半自动登录 | 用 App 内"扫码/分享"类免密入口（未抓到） | 需再抓包确认 |

---

## 8. 对 HACS 集成的建议

**分两阶段：**

1. **阶段一（不需要逆向）**：`tk` + `vin` 手动配置 → 轮询 `GW.M.GET_VEHICLE_STATE` → 建传感器
   - 传感器：剩余油量、总里程、四轮胎压/胎温、四门/四窗/后备箱/引擎盖、车锁、发动机状态、经纬度（device_tracker）、最后上报时间、充电状态
   - 轮询间隔 ≥ 5min（TSP 走车机缓存，`lastUpdate` 与 `uploadTime` 同源，频繁拉取无意义）
   - 令牌失效判定：`header.c == -101` → 抛 `ConfigEntryAuthFailed`

2. **阶段二（逆向完成后）**：把 `tk` 获取自动化，做成标准 `config_flow`（账号密码登录，refreshToken 续期）
   - 登录实现顺序：`pwd-login`(AES) → `loginSSOAccount`(bt-auth) → `GW.M.APP_LOGIN`
   - 远控（可选）：走 `gw-app-gateway`，需要 `securityTime` 免密或 6 位安全密码

**仓储结构建议**（与 HACS 规范一致）：

```
custom_components/gwm/
├── __init__.py        # 轮询 coordinator
├── config_flow.py     # 账号密码 / token 两种模式
├── api.py             # TSP + gateway 客户端（签名集中在 auth.py）
├── auth.py            # AES(G_A) + Sign + bt-auth-sign
├── sensor.py  lock.py  binary_sensor.py  device_tracker.py
└── const.py           # 域名、appId、ckey、字段映射表
```

---

## 9. 附：关键抓包索引

| 编号 | 内容 |
|---|---|
| 803 | `pwd-login` 密码登录（AES） |
| 805 | `loginSSOAccount` SSO 换 token（明文，最具参考价值） |
| 806 | `GW.M.APP_LOGIN` 换 TSP `tokenId` |
| 807 | `query-vehicle-list` 车辆列表 |
| 808 | `vehicle/security/info` 免密有效期 |
| 809 | IM `generateUserSig`（腾讯云 IM，与车控无关） |
| 813 | `token/submit` token 上报 |
| 823/824/825 | 签到、用户信息、积分 |
| 851/861/901 | 我的车 UI 组件配置（无数据价值） |
| 863/902 | TOF 服务能力码列表 |
| 899 | `GW.M.GET_ENGINE_STS` |
| 900 | 远控能力配置查询 |
| 905 | `GW.M.GET_VEHICLE_STATE` **核心车况** |
| 906/910 | `GW.M.GET_MESSAGE_LIST` |
| 804/814/818/893/909 | 友盟埋点、神策埋点，忽略 |
| 848–892 | H5 商城页（`gw-h5-gateway`），与 HA 无关 |

---

## 10. 实测补充（2026-11-01 22:20）

### 10.1 `GW.M.APP_LOGIN` 不校验任何签名

对 `car-api.gwmapp-h.com/tsp/v1/proxy/navinfo/GW.M.APP_LOGIN` 重放：

| 变体 | 结果 |
|---|---|
| A 原样 | 200 Success，返回新 `tokenId` |
| B 删 `sign` | 200 Success |
| C `sign=AAAA` | 200 Success |
| D 删 `sign` + `ckey` | 200 Success |

且 `ssoTk`（抓包中 21:59 的）在 22:23 仍可用 → **可重复换取 `tk`，非一次性**。

**意义：拿到 `ssoId` + `ssoToken` 就能换 `tk`，`loginSSOAccount` 那套 `bt-auth` 签名可以整条跳过。**
即"账号密码直登"只剩一个门槛：`pwd-login` 的 AES 口令。

### 10.2 `tk` 单会话（会互踢）

实验：连续两次 `GW.M.APP_LOGIN`

```
login1 → tk1 = 0123456789abcdef0123456789abcdef   → 取车况 c=0 Success
login2 → tk2 = fedcba9876543210fedcba9876543210   → 取车况 c=0 Success
         tk1 → 取车况 c=-101 缓存数据已失效，需要您重新进行登录
```

结论：

- 同一 `ssoId` 全局只保留**最新一个** `tk`，旧的立即失效。
- 集成里 **不能**在每次轮询前重新 login，否则一直踢自己；必须缓存 `tk`，仅在 `c=-101` 时重登一次。
- 副作用：HA 用你的 `ssoTk` 换 `tk` 会顶掉手机 App 的 TSP 会话（App 车况页可能要求重新登录）。

### 10.3 AES 口令字典爆破结果（失败）

| 轮次 | 候选 | 结果 |
|---|---|---|
| 1 | 60 个常见弱口令 | 0 命中 |
| 2 | 618 个组合（gwm/greatwall/beantech/haval… × 123/@2020…/年份/前缀后缀） | 0 命中 |

→ 口令为随机串或拼接生成，无法字典推算，只能反编译 APK 取常量。

---

## 11. APK 静态分析记录（2.1.3，276MB）

### 11.1 基本信息

| 项 | 值 |
|---|---|
| 包名 | `com.gwm.fusion`（App 内另有 `com.gwm.fusion.test` 校验项） |
| 加固 | **网易易盾**：`lib/arm64-v8a/libDexHelper.so` |
| dex 规模 | `classes.dex` 122MB，但 `string_ids` 仅 1658 条、257 个类 → 业务代码被抽到 dex 尾部数据区 |
| 加密实现 | `lib/arm64-v8a/libsapp_crypto_tool.so`（235KB） |

### 11.2 加密入口（so 导出符号）

```
sapp_init
sapp_AES_ecb_encrypt
sapp_AES_cbc_encrypt
sapp_skb_encrypt / sapp_skb_decrypt
Java_com_sapp_CryptoTool_aesEncryptStringWithBase64
Java_com_sapp_CryptoTool_aesEncryptByteArr
```

→ **AES 加解密走 native**，Java 层的 `G_A()` 只是 JNI 包装。这就是 dex 里搜不到口令的原因。

### 11.3 so 内可疑常量（`.data` 段 0x49040 起）

```
049040  ED7CFD7610BDEEC4396EAD24D906FC9B;ED7CFD7610BDEEC4396EAD24D906FC9B
049090  ab1bc3af2c9cc54c...(244 字节 hex blob)
049010  com.gwm.fusion;com.gwm.fusion.test
```

- 第一行：32 hex 重复两次、分号分隔 → 疑似 key/iv（16B 各一份）。
- 244 字节 blob：非 16 对齐（244 % 16 = 4），疑似加密的密钥表。

### 11.4 已穷举且失败的组合

| 尝试 | 规模 | 结果 |
|---|---|---|
| dex 内高熵串作 CryptoJS passphrase（md5 KDF，AES-128/256，含/不含 salt） | 12,728 | 0 |
| 全 dex ASCII 串（6–64 字符）作 passphrase + md5/sha256 直作 key + hex/base64 解码作 key | 228,779 × 9 种派生 | 0 |
| dex 内 16/32/40/48/64 位 hex 常量直接作 AES key（CBC/ECB，IV=零/自身/md5） | 2,032 × 6 | 0 |
| so 内 244B blob 用 `ED7CFD...` 解（AES-128/256 ECB/CBC） | 5 种 | 全乱码 |

判定：密钥未以明文形式存在于可读数据段，且被二次加密/由设备信息派生 → **静态不可达**。

### 11.5 结论

要拿到 `G_A` 的 AES 密钥，只能动态：

1. 设备侧（MuMu 模拟器 / 真机）装 frida-server；
2. hook `Cipher.getInstance` / `Cipher.init` / `SecretKeySpec.<init>`，直接打印 key 与 IV；
3. 或 hook 易盾的字符串解密函数，还原被抽取的 `const-string`（含 `SECRET_1` / `SECRET_2` / `SECURET_KEY` 的值）。

拿到后即可完整复现 `pwd-login`，实现账号密码自动登录。

---

## 12. Frida 动态调试尝试（2026-11-01 23:20）

### 12.1 环境与足迹（全部落在项目目录内）

| 项 | 位置 | 体积 |
|---|---|---|
| Python 客户端 | `work/venv/`（frida 17.25.0 + frida-tools 14.11.0） | ~90 MB |
| frida-server | `work/frida/frida-server`（x86_64, 17.25.0） | 165 MB |
| 设备侧 | `/data/local/tmp/fri-d`（改名规避特征扫描） | 165 MB |

设备信息：MuMu 12 Nx，`127.0.0.1:7555`，Android 12 (SDK 31)，`ro.product.cpu.abi = x86_64`，SELinux Permissive，`adb root` 直接可用（自带 Magisk）。

### 12.2 工具链验证通过

- `adb root` → uid=0；`setsid` 启动 frida-server 成功（`nohup &` 会被回收）。
- `frida-ps -U` / `-H 127.0.0.1:8899` 均可列出进程。
- 对照测试：attach `com.android.settings` → 脚本正常执行，输出 `Java.available=true`，进程存活。

### 12.3 长城 App 上失败：易盾反调试

```
frida -H 127.0.0.1:8899 -p <pid> -l min.js
→ Failed to attach: agent connection closed unexpectedly
→ 进程 PID 变化（15235 → 15529），即被杀死后自重启
```

即使把 server 改名为 `fri-d`、换端口 8899，仍被拦截 → 检测点不在文件名/端口，而在注入后的内存特征或线程名。

### 12.4 额外硬伤：APK 仅含 arm64-v8a

APK 内 64 个 so **全部位于 `lib/arm64-v8a/`**，无 x86_64；模拟器为 x86_64，App 运行在 ARM 转译层（安装后 lib 目录为 `lib/arm64`）。frida-gum 无法可靠 hook 转译执行的 arm64 代码。

结论：在 MuMu（x86_64 + 易盾）上做 native hook 不可行。可选绕过路径：
1. 真机（arm64）需 root + 过易盾反 frida；
2. Magisk 级 frida 隐藏模块（FridaHide / zygisk-fridahide），需评估是否被易盾针对性检测；
3. **Unicorn 静态模拟** arm64 `sapp_init` + `sapp_AES_cbc_encrypt`（不依赖设备，纯离线，成功率未知）；
4. 放弃自动登录，走 4 值方案。

## 13. 登录参数最小集实测

`GW.M.APP_LOGIN` 的 body **必需 4 个字段**（缺任一即 `c=-52`）：

| 字段 | 缺失时报错 |
|---|---|
| `phone` | 参数phone是必须的 |
| `ssoid` | 参数ssoid是必须的 |
| `appType` | 参数appType是必须的（填 `0`） |
| `ssoTk` | 参数ssoTk是必须的 |

`pushId` / `pushKey` 可省略。

> 更正：早前一轮测试因为校验顺序是 phone → ssoid → appType，看到「参数phone是必须的」就误判了后两个字段可省。加上 `appType: 0` 后恢复正常。

`ssoTk` 可填 `loginSSOAccount` 返回的 `ssoToken`，也可填返回的 `ptToken`，两者都通。

`token/submit`（gapp-api）**不需要**调用 —— 它是设备推送绑定上报，与取数无关。

## 13.1 请求头最小集

TSP 两个接口的请求头只需要：

```
v: 1.0
client: phone
brandType: GWM
```

实测 `mobileId`、`cid`、`ckey`、`time`、`sign`、`protocolVer` 全部可以省略；
`mobileId` 传空串、传随机 UUID 均不影响换票。TSP 取数接口另需 `token: <tk>` 头，
但真正生效的是请求体里的 `header.tk`。

## 14. 凭证寿命实测

| 凭证 | 类型 | 有效期 | 来源 |
|---|---|---|---|
| `accessToken` | JWT | **7 天**（2026-11-01 21:59 → 11-08 21:59） | loginSSOAccount 返回 |
| `refreshToken` | JWT | **30 天**（→ 2026-12-01 21:59） | loginSSOAccount 返回 |
| `ssoTk` / `ptToken` | 32 hex GUID | ≥ **6 天**（2026-11-01 21:59 签发 → 11-07 16:01 实测仍可换 tk），上限未知 | 抓包 / 登录返回 |
| `tokenId`（tk） | 32 hex | 未知，单会话互踢；失效返回 `c=-101` | APP_LOGIN 返回 |

4 值方案中只有 `ssoTk` 会过期；`ssoId` / `phone` / `vin` 永久不变。

---

## 15. HACS 集成（方案 A）落地记录

代码位置：`custom_components/gwm_vehicle/`（仓库根目录另有 `hacs.json`、`README.md`）。

### 15.1 架构

| 文件 | 职责 |
|---|---|
| `api.py` | APP_LOGIN 换 tk、缓存、`-101` 自动重换一次、GET_VEHICLE_STATE 取车况 |
| `coordinator.py` | 轮询调度；`GwmAuthError` → `ConfigEntryAuthFailed`（自动触发重新认证） |
| `config_flow.py` | 4 值表单 + 实跑校验；`reauth` 流程用于 ssoTk 过期后重填 |
| `sensor.py` | 16 个数值实体（含车辆位置） |
| `binary_sensor.py` | 17 个二进制实体 |
| `device_tracker.py` | GPS 位置（在地图上移动，在家/离家由 HA 按 zone.home 判定） |
| `button.py` | 1 个「刷新数据」按钮，诊断分类：下发 `REFRESH_VEHICLE_STATE` 让车机重新上报，再后台轮询 `uploadTime` 判断完成 |
| `const.py` | 端点、请求头最小集、**门窗极性规则** |

共 35 个实体。无第三方依赖（仅用 HA 自带的 aiohttp）。
品牌图在 `brand/`，**全部官方素材**：
- `icon.png`(512×512)：App Store 官方应用图标（长城汽车，红底 + 白色徽标 + GWM），
  原图 1024×1024，经 `itunes.apple.com/search` 的 `artworkUrl512` 取得后降采样。红底在两套主题下都成立，
  所以 `dark_icon.png` 用同一张，不再改色。
- `logo.png`(794×256) / `dark_logo.png`：裁自官网 `https://www.gwm.com.cn/dist/images/home-page/cc_logo-s-20250120.png`
  （1306×421 白色透明 PNG），浅色主题用 `-webkit-mask` 换成 `#14181D`，深色主题保留白色。
- `h6_45.png`/`h6_90.png`：官方车型页车辆渲染图，用作设备头像。

### 15.2 关键实现决策

- **只走最小请求头** `v/client/brandType`，不带 `cid`/`ckey`/`time`/`sign`，避免引入无意义的时效字段。
- **tk 串行化换票**：`asyncio.Lock` + 双重检查，避免并发轮询时重复登录互相踢。
- **只读**：不含任何远控写操作。
- `token/submit` 不调用（与取数无关）。

### 15.3 联调结果（`work/tests/test_integration.py`）

```
[PASS] 时间戳格式为 17 位
[PASS] 拿到 vehicleSts / carStatus（54 字段）
       油量=13L  里程=12345km  位置=(39.908692, 116.397477)
[PASS] 伪造 tk → 自动重换并成功取数，tk 被替换
[PASS] 清空 tk → 自动登录
[PASS] 25 个实体字段路径全部存在于真实响应
```

### 15.4 待确认项

门窗 `0/1` 极性为推断值。每个二进制实体都输出了 `raw_value` 属性便于核对；
若与实际相反，改 `const.py` 的 `LOCK_ON_WHEN` 等元组即可。

---

## 16. 能力边界复核（2026-11-02 06:40）

### 16.1 新增可用只读函数

对 TSP 网关逐个试探（空 body 调用：存在则报参数缺失，不存在则 `HTTP 500 this is a service fallback`）：

| fn | 状态 | 返回 |
|---|---|---|
| `GW.M.GET_VEHICLE_STATE` | ✅ | `vehicleSts`（54 字段 carStatus + battSts/chargeSettings/lastUpdate/apptAirSts） |
| `GW.M.GET_AIR_STS` | ✅ **新发现** | 远程空调设置 |
| `GW.M.GET_ENGINE_STS` | ✅ | `{"runTime":"20"}` |
| `GW.M.REFRESH_VEHICLE_STATE` | ✅ **最有用** | `{"transactionId":"otsp…"}`，指令异步下发 |
| `GW.M.GET_MESSAGE_LIST` | ✅ | 站内消息 |
| `GW.M.APP_LOGIN` | ✅ | tokenId |
| `GW.M.SET_AIR_STS` / `AIR_CONDITIONER_START` / `AIR_START` / `SET_AIR` | ❌ 500 fallback | 控制指令不在 TSP |
| `GW.M.GET_SEAT_STS` / `GET_WINDOW_STS` / `GET_TIRE_STS` / `GET_TRIP_INFO` / `GET_MAINTENANCE_INFO` | ❌ 500 fallback | 字段已含在 carStatus |

### 16.1.1 `GW.M.REFRESH_VEHICLE_STATE` —— App 的「刷新数据」

**之前把「刷新」和「取车况」当成同一个接口，是错的。** 两者分工：

| | `GET_VEHICLE_STATE` | `REFRESH_VEHICLE_STATE` |
|---|---|---|
| 作用 | 读服务端**缓存** | 下发指令，要求 **T-BOX 重新上报** |
| 是否产生新数据 | ❌ 永远只是缓存 | ✅ 车机会上报一遍 |
| 返回 | `vehicleSts`（54 字段） | `{"transactionId":"otsp…"}` |
| 耗时 | < 1 秒 | 异步，车机醒着 10 秒、休眠 1–3 分钟 |

**免签名可用**（实测 2026-11-07）：只带 `token` 请求头即可，`sign`/`ckey`/`time`/`cid` 全部省略也返回 `c=0`。
与 `GET_VEHICLE_STATE` 同一个入口 `ti.gwm.com.cn:8443/tsp/ead`，同一个 TSP 网关。

```python
r = tsp("GW.M.REFRESH_VEHICLE_STATE", {"vin": VIN})
# {"header": {"c": 0, "m": "Success", ...},
#  "body":   {"transactionId": "otsp7c54cd8242d14352ad54554541596097"}}
```

**App 的下半段走不通**：拿到 `transactionId` 后，App 会去
`gw-app-gateway.gwmapp-h.com/app-api/api/v3.0/vehicle/remote-ctrl/result?seqNo=<seq>&vin=<vin>&msgType=remote`
轮询指令执行结果 —— 那是 `bt-auth-sign` 强校验的网关，逆不出来。

**但不需要它**：指令执行成功后服务端缓存必然刷新，`carStatus.uploadTime` 会推进。
所以用「下发 REFRESH → 轮询 GET_VEHICLE_STATE 比较 uploadTime」即可判断完成，等价且全程免签名。

两个实测细节（2026-11-07 16:21 / 16:26）：

1. 刷新瞬间服务端缓存会被**清空**，此时 `GET_VEHICLE_STATE` 返回的 `carStatus` 是空壳
   （`uploadTime`/`remainFuel`/`lat` 全为 `None`）。集成里做了保护：这种情况沿用上一轮数据，
   否则所有实体会瞬间变「未知」。
2. `vehicleSts.lastUpdate` 与 `carStatus.uploadTime` 实测**同值同跳**，都是车机上报时刻（13 位毫秒时间戳）。

### 16.2 `GW.M.GET_AIR_STS` 完整字段

```json
{"temp":26,"engineControl":1,"airVolumeLevel":"4","temperatureLevel":"9",
 "airVolumeMode":"2","coldSwitch":"0","runTime":10,"hasAppt":0,"heatSwitch":"0"}
```

| 字段 | 含义 |
|---|---|
| `temp` | 设定温度 ℃ |
| `engineControl` | 是否连带启动发动机（1=是） |
| `airVolumeLevel` | 风量档位 |
| `temperatureLevel` | 温度档位 |
| `airVolumeMode` | 出风模式 |
| `coldSwitch` / `heatSwitch` | 制冷 / 制热开关 |
| `runTime` | 运行时长（分钟） |
| `hasAppt` | 是否已预约 |

语义：**上一次远程空调的设置**，不是车内实时温度（燃油车空调靠发动机，熄火时无此概念）。

### 16.3 空调控制不可用

控制走 `gapp-api.gwmapp-h.com/app-api/api/v3.0/vehicle/remote-ctrl/*`，强校验 `bt-auth-sign`（SHA256，secret 在 APK native 层）。
抓包中 `remote-ctrl/config/query` 显示本车支持：

```json
{"cmd":"AIR_CONDITIONER_START","cmdContent":{"allowStartEng":1,"temperature":26,"operationTime":600}}
```

即有远程开空调能力，但**下发指令这一侧签名破不了 → 集成只做只读**。

### 16.4 静态车辆信息（品牌/车牌/图片）

都在 `gapp-api` 的车辆列表 `query-vehicle-list`（需 `Sign` 签名，不可调用）。从抓包可见字段：

| 字段 | 值 |
|---|---|
| `brandName` / `showBrandName` | 红标全新哈弗H6 |
| `modelName` | 红标全新哈弗H6_CC6464RM08B_21款-黑色内饰_冠军版 |
| `licenseNumber` | 京A12345 |
| `color` / `colorValue` | 汉密尔顿白 / `#626262` |
| `engineNo` / `engineType` | GW4B15A |
| `imageUrl` / `material45Url` / `material90Url` | CDN 车辆渲染图（可直接下载，无需鉴权） |

图片 CDN 实测可直接 GET，已下载 45°/90° 两张 PNG（329KB / 241KB）随集成内置，
路径 `custom_components/gwm_vehicle/brand/`，通过静态路由 `/{STATIC_URL_PREFIX}/brand/h6_45.png` 暴露为设备头像。

品牌/车型/车牌无法通过接口读取，改为配置项可选字段（`model` / `license_plate`），留空不影响功能。

### 16.5 当前数据能力总表

| 用户关心的项 | 可得 | 来源 |
|---|---|---|
| 里程 | ✅ 12345 km | `carStatus.vehTotDistance` |
| 剩余油量 | ✅ 13 L（**升，非百分比**） | `carStatus.remainFuel` |
| 4 个胎压 | ✅ 228/226/222/224 kPa | `drv/pass/rl/rr TirePress` |
| 4 个胎温 | ✅ 30/31/28/29 ℃ | `drv/pass/rl/rr TireTemp` |
| 车门（4 门） | ✅ 全关 | `*DoorSts` |
| 车锁 | ✅ 已上锁 | `drvDoorLockSts` |
| 车窗、后备箱、引擎盖 | ✅ | `*WinPosnSts` / `trunkSts` / `hoodSts` |
| 发动机状态 | ✅ 熄火 | `carStatus.engSts` |
| 远程启动时长 | ✅ 20 min | `engine.runTime` |
| 空调设定温度 | ✅ 26 ℃ | `air.temp` |
| 空调风量/制冷/制热/预约 | ✅ | `air.*` |
| 空调控制 | ❌ 需签名 | gapp-api |
| 车辆位置 | ✅ (36.66018, 117.26186) | `carStatus.lat/lon` |
| 品牌/车型/车牌 | ⚠️ 配置项手填 | 车辆列表（需签名） |
| 车辆图片 | ✅ 已内置 | CDN 直链 |
