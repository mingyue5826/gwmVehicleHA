/**
 * GWM 车辆状态卡片 (custom:gwm-vehicle-card)
 *
 * 随 gwm_vehicle 集成分发（custom_components/gwm_vehicle/www/），
 * 由集成在启动时自动注册为 Lovelace 资源，无需手动添加。
 *
 * 功能：实车俯视图（可调不透明度）+ 胎压异常红标闪烁 + 车门/窗/盖/后备箱
 *       开启角标 + 引擎/空调状态 + 告警旗 + 油量/里程 + 在家/离家 + 刷新。
 * 实体自动发现：translation_key → entity_id 后缀 → 中文 friendly_name 三级匹配。
 * 零依赖：原生 Web Component，颜色走 HA 主题 CSS 变量（自动适配深浅色）。
 */
const CARD_VERSION = "0.6.1";
const DOMAIN = "gwm_vehicle";
const DEFAULT_IMAGE = `/${DOMAIN}/brand/h6_top.png`;
const DEFAULT_ENGINE_IMAGE = `/${DOMAIN}/brand/h6_engine.png`;
/* 发动机叠加层在车图中的位置（百分比，须与裁剪区域一致） */
const DEFAULT_ENGINE_REGION = { x: 33.5, y: 9, w: 34.5, h: 13.5 };

/* 开门叠加图：从真实「四门打开」俯视图裁出（右侧门为原图，左侧门 CSS 镜像）。
   left/top/w 为占车图宽高的百分比，left 指未镜像时的左边缘。 */
const DOOR_OVERLAY = {
  fl: { file: `/${DOMAIN}/brand/door_front_open.png`, left: 92.95, top: 28.99, w: 46.58, mirror: true },
  fr: { file: `/${DOMAIN}/brand/door_front_open.png`, left: 92.95, top: 28.99, w: 46.58 },
  rl: { file: `/${DOMAIN}/brand/door_rear_open.png`, left: 92.03, top: 49.50, w: 45.65, mirror: true },
  rr: { file: `/${DOMAIN}/brand/door_rear_open.png`, left: 92.03, top: 49.50, w: 45.65 },
};
/* 异常轮胎红色叠加图（同样从真实俯视图裁出，贴住原车轮位置） */
const TIRE_RED_OVERLAY = {
  fl: { file: `/${DOMAIN}/brand/tire_red_fl.png`, left: -0.97, top: 12.84, w: 6.01 },
  fr: { file: `/${DOMAIN}/brand/tire_red_fr.png`, left: 95.42, top: 12.91, w: 5.40 },
  rl: { file: `/${DOMAIN}/brand/tire_red_rl.png`, left: 0.57, top: 75.23, w: 5.71 },
  rr: { file: `/${DOMAIN}/brand/tire_red_rr.png`, left: 93.72, top: 75.23, w: 5.71 },
};

/* 告警图标：加油机（国标油表样式）/ 车胎+感叹号 */
const ICON_FUEL =
  "M19.77 7.23l.01-.01-3.72-3.72L15 4.56l2.11 2.11c-.94.36-1.61 1.26-1.61 2.33 0 1.38 1.12 2.5 2.5 2.5.36 0 .69-.08 1-.21v7.21c0 .55-.45 1-1 1s-1-.45-1-1V14c0-1.1-.9-2-2-2h-1V5c0-1.1-.9-2-2-2H6c-1.1 0-2 .9-2 2v16h10v-7.5h1.5v5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V9c0-.69-.28-1.32-.73-1.77zM12 10H6V5h6v5zm6 0c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1z";
const ICON_TIRE =
  "M10 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zm0 3a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9zm0 2.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM18.6 5h2l-.4 7.4h-1.2L18.6 5zm1 8.6a1.35 1.35 0 1 1 0 2.7 1.35 1.35 0 0 1 0-2.7z";

/* 实体匹配规则：translation_key > entity_id 正则（含 tyre/tire 英式美式两种写法）> 中文 friendly_name。
   ids 用 entity_id 去掉域名后的部分做匹配。 */
const KEY_SPECS = {
  remain_fuel:           { domain: "sensor", ids: "remain_fuel|fuel_level|(^|_)fuel$", zh: "剩余油量|油量" },
  total_distance:        { domain: "sensor", ids: "total_distance|odometer|mileage", zh: "总里程|里程" },
  last_update:           { domain: "sensor", ids: "data_updated_at|last_update|updated_at|last_seen", zh: "数据更新时间|更新时间" },
  position:              { domain: "sensor", ids: "vehicle_position|(^|_)position(_|$)", zh: "车辆位置|经纬度" },
  ac_target_temperature: { domain: "sensor", ids: "ac_target_temperature|target_temperature", zh: "设定温度|目标温度" },
  ac_volume_level:       { domain: "sensor", ids: "ac_fan_level|ac_volume_level|fan_level", zh: "空调-风量|风量" },
  tire_pressure_fl:      { domain: "sensor", ids: "(front_left|left_front).*(tyre|tire).*pressure|(tyre|tire)_pressure_(front_left|fl)", zh: "胎压-左前|左前.*胎压" },
  tire_pressure_fr:      { domain: "sensor", ids: "(front_right|right_front).*(tyre|tire).*pressure|(tyre|tire)_pressure_(front_right|fr)", zh: "胎压-右前|右前.*胎压" },
  tire_pressure_rl:      { domain: "sensor", ids: "(rear_left|left_rear).*(tyre|tire).*pressure|(tyre|tire)_pressure_(rear_left|rl)", zh: "胎压-左后|左后.*胎压" },
  tire_pressure_rr:      { domain: "sensor", ids: "(rear_right|right_rear).*(tyre|tire).*pressure|(tyre|tire)_pressure_(rear_right|rr)", zh: "胎压-右后|右后.*胎压" },
  tire_temp_fl:          { domain: "sensor", ids: "(front_left|left_front).*(tyre|tire).*(temp|temprature|temperature)|(tyre|tire)_temp.*_(front_left|fl)", zh: "轮胎温度-左前|胎温-左前|左前.*温度" },
  tire_temp_fr:          { domain: "sensor", ids: "(front_right|right_front).*(tyre|tire).*(temp|temprature|temperature)|(tyre|tire)_temp.*_(front_right|fr)", zh: "轮胎温度-右前|胎温-右前|右前.*温度" },
  tire_temp_rl:          { domain: "sensor", ids: "(rear_left|left_rear).*(tyre|tire).*(temp|temprature|temperature)|(tyre|tire)_temp.*_(rear_left|rl)", zh: "轮胎温度-左后|胎温-左后|左后.*温度" },
  tire_temp_rr:          { domain: "sensor", ids: "(rear_right|right_rear).*(tyre|tire).*(temp|temprature|temperature)|(tyre|tire)_temp.*_(rear_right|rr)", zh: "轮胎温度-右后|胎温-右后|右后.*温度" },
  door_lock:             { domain: "binary_sensor", ids: "door_lock|central_lock|lock_status", zh: "^车锁|门锁|中控锁" },
  engine:                { domain: "binary_sensor", ids: "(^|_)engine$|engine_status|engine_running", zh: "^发动机$|引擎$" },
  door_fl:               { domain: "binary_sensor", ids: "(front_left|left_front)_door|door_(front_left|fl)", zh: "车门-左前|左前门" },
  door_fr:               { domain: "binary_sensor", ids: "(front_right|right_front)_door|door_(front_right|fr)", zh: "车门-右前|右前门" },
  door_rl:               { domain: "binary_sensor", ids: "(rear_left|left_rear)_door|door_(rear_left|rl)", zh: "车门-左后|左后门" },
  door_rr:               { domain: "binary_sensor", ids: "(rear_right|right_rear)_door|door_(rear_right|rr)", zh: "车门-右后|右后门" },
  trunk:                 { domain: "binary_sensor", ids: "trunk|tailgate|tail_gate", zh: "后备箱|尾门|行李箱" },
  hood:                  { domain: "binary_sensor", ids: "hood|bonnet|engine_hood", zh: "引擎盖|机盖" },
  window_fl:             { domain: "binary_sensor", ids: "(front_left|left_front)_window|window_(front_left|fl)", zh: "车窗-左前|左前窗" },
  window_fr:             { domain: "binary_sensor", ids: "(front_right|right_front)_window|window_(front_right|fr)", zh: "车窗-右前|右前窗" },
  window_rl:             { domain: "binary_sensor", ids: "(rear_left|left_rear)_window|window_(rear_left|rl)", zh: "车窗-左后|左后窗" },
  window_rr:             { domain: "binary_sensor", ids: "(rear_right|right_rear)_window|window_(rear_right|rr)", zh: "车窗-右后|右后窗" },
  fuel_low_alarm:        { domain: "binary_sensor", ids: "(low_fuel|fuel_low)", zh: "低油量|油量低" },
  tire_abnormal:         { domain: "binary_sensor", ids: "(tyre|tire)_abnormal", zh: "胎压异常|胎压报警" },
  ac_cooling:            { domain: "binary_sensor", ids: "ac_cooling|cooling", zh: "空调-制冷|制冷" },
  ac_heating:            { domain: "binary_sensor", ids: "ac_heating|heating", zh: "空调-制热|制热" },
};
const ALL_KEYS = Object.keys(KEY_SPECS);

const TIRE_DEFS = [
  { key: "fl", cn: "左前", p: "tire_pressure_fl", t: "tire_temp_fl" },
  { key: "fr", cn: "右前", p: "tire_pressure_fr", t: "tire_temp_fr" },
  { key: "rl", cn: "左后", p: "tire_pressure_rl", t: "tire_temp_rl" },
  { key: "rr", cn: "右后", p: "tire_pressure_rr", t: "tire_temp_rr" },
];

/* 车图覆盖角标默认位置（占车图宽高百分比，车头朝上）。YAML markers 可覆盖。 */
const DEFAULT_MARKERS = {
  tire_fl:  { x: 7,  y: 14.2, side: "left" },
  tire_fr:  { x: 93, y: 14.2, side: "right" },
  tire_rl:  { x: 11, y: 83.2, side: "left" },
  tire_rr:  { x: 89, y: 83.2, side: "right" },
  door_fl:  { x: 4,  y: 38 },
  door_fr:  { x: 96, y: 38 },
  door_rl:  { x: 4,  y: 61 },
  door_rr:  { x: 96, y: 61 },
  window_fl:{ x: 9,  y: 35 },
  window_fr:{ x: 91, y: 35 },
  window_rl:{ x: 9,  y: 60 },
  window_rr:{ x: 91, y: 60 },
  hood:     { x: 50, y: 10 },
  trunk:    { x: 50, y: 89 },
  engine:   { x: 50, y: 14 },
  ac:       { x: 50, y: 46 },
};

/* 点击热区（占车图宽高百分比）。车图本身是细长线稿，真实可点区域太窄，
   所以热区向外扩到车图之外，并用 z-index 压在覆盖层之上。
   门：以门缝中线为准向两侧各留余量；右侧门用 right 定位（与 DOOR_OVERLAY 一致）。 */
const DOOR_HIT = {
  fl: { left: -7, top: 26, w: 22, h: 24 },
  fr: { right: -7, top: 26, w: 22, h: 24 },
  rl: { left: -7, top: 48, w: 22, h: 24 },
  rr: { right: -7, top: 48, w: 22, h: 24 },
};
/* 发动机热区：比红色叠加层略大一圈，方便点中 */
const ENGINE_HIT = { x: 31, y: 8, w: 39, h: 16 };

function fmtInt(n) {
  return n == null || isNaN(n) ? "--" : Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

class GwmVehicleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._entities = {};
    this._missing = [];
    this._narrow = false;
    this._refreshing = false;
    this._refreshFrom = null;
    this._refreshResult = "";
    this._refreshTimer = null;
    this._ro = null;
    /* 注意：构造函数里不能加属性/子节点（HTML 自定义元素规范），
       否则 Chrome 会判定构造失败，元素直接变成「配置错误」。
       版本标记放到 connectedCallback 里写。 */
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("gwm-vehicle-card: 配置无效");
    }
    this._config = {
      device: config.device || "",
      prefix: config.prefix || "",
      title: config.title || "",
      entities: config.entities || null,
      image: config.image || DEFAULT_IMAGE,
      image_opacity: config.image_opacity != null ? Number(config.image_opacity) : 1,
      car_max_height: Number(config.car_max_height) || 420,
      engine_image: config.engine_image || DEFAULT_ENGINE_IMAGE,
      engine_region: { ...DEFAULT_ENGINE_REGION, ...(config.engine_region || {}) },
      markers: { ...DEFAULT_MARKERS, ...(config.markers || {}) },
      fuel_capacity_l: Number(config.fuel_capacity_l) || 58,
      fuel_low_percent: Number(config.fuel_low_percent) || 10,
      pressure_low: Number(config.pressure_low) || 190,
      pressure_high: Number(config.pressure_high) || 300,
      temp_high: Number(config.temp_high) || 60,
      lock_style: config.lock_style || "both",
      blink: config.blink !== false,
      ac_animation: config.ac_animation !== false,
      show_missing: config.show_missing !== false,
      show_tire_normal: config.show_tire_normal !== false,
      show_tire_summary: config.show_tire_summary === true,
      door_overlay: config.door_overlay !== false,
      tire_overlay: config.tire_overlay !== false,
      door_layout: config.door_layout || {},
      tire_layout: config.tire_layout || {},
    };
    this._entities = {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this._resolveEntities(hass);
    // 刷新状态以按钮实体的 refresh_status 为准（后端才知道车机到底回没回）
    this._syncRefreshState(hass);
    // 兜底：后端属性拿不到时，靠「数据更新时间」自己判断
    if (this._refreshing) {
      const id = this._entities.last_update;
      const now = id ? hass.states[id]?.state : undefined;
      if (now && this._refreshFrom && now !== this._refreshFrom) {
        this._finishRefresh("ok");
      }
    }
    this.render();
  }

  _finishRefresh(result) {
    this._refreshing = false;
    this._refreshResult = result;
    if (this._refreshTimer) { clearTimeout(this._refreshTimer); this._refreshTimer = null; }
    const ttl = result === "ok" ? 6000 : 9000;
    setTimeout(() => {
      if (this._refreshResult === result) { this._refreshResult = ""; this.render(); }
    }, ttl);
  }

  // 按钮实体上的 refresh_status: idle / waiting / done / timeout / failed
  _syncRefreshState(hass) {
    const id = this._entities.refresh;
    if (!id) return;
    const status = hass.states[id]?.attributes?.refresh_status;
    if (!status) return;
    if (status === "waiting") {
      if (!this._refreshing) { this._refreshing = true; this._refreshResult = ""; this.render(); }
      return;
    }
    if (!this._refreshing) return;
    if (status === "done") this._finishRefresh("ok");
    else if (status === "timeout") this._finishRefresh("stale");
    else if (status === "failed") this._finishRefresh("failed");
  }

  getCardSize() {
    return 9;
  }

  static getConfigElement() {
    return document.createElement("gwm-vehicle-card-editor");
  }

  connectedCallback() {
    /* 版本标记写在这里（构造函数里不允许加属性，会构造失败） */
    this.setAttribute("data-gwm-version", CARD_VERSION);
    if (!this._ro) {
      this._ro = new ResizeObserver((entries) => {
        const w = entries[0].contentRect.width;
        const narrow = w > 0 && w < 430;
        if (narrow !== this._narrow) {
          this._narrow = narrow;
          this.render();
        }
      });
      this._ro.observe(this);
    }
    /* 事件只绑一次：HA 可能多次 connected/disconnected，重复绑定会触发多次弹框 */
    if (!this._bound) {
      this._bound = true;
      this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
      this.shadowRoot.addEventListener("pointerdown", (e) => this._onPointerDown(e));
      ["pointerup", "pointercancel", "pointerleave"].forEach((ev) =>
        this.shadowRoot.addEventListener(ev, () => this._cancelLongPress())
      );
      this.shadowRoot.addEventListener("contextmenu", (e) => {
        if (this._lpTimer || this._lpFired) e.preventDefault();
      });
    }
  }

  /* 长按 500ms 触发第二个实体（胎压块：短按=胎压，长按=胎温） */
  _onPointerDown(e) {
    /* 每次按下先清标记：万一上次长按后没有跟上 click，不至于把下一次点击吞掉 */
    this._lpFired = false;
    const el = this._actionTarget(e, "data-long-entity");
    if (!el) {
      this._cancelLongPress();
      return;
    }
    this._cancelLongPress();
    this._lpTimer = setTimeout(() => {
      this._lpTimer = null;
      this._lpFired = true;
      const id = el.getAttribute("data-long-entity");
      if (id) {
        this._fireMoreInfo(id);
        if (navigator.vibrate) navigator.vibrate(15);
      }
    }, 500);
  }

  _cancelLongPress() {
    if (this._lpTimer) {
      clearTimeout(this._lpTimer);
      this._lpTimer = null;
    }
  }

  /* 从事件路径里找带指定属性的最近元素 */
  _actionTarget(e, attr) {
    return e.composedPath().find(
      (n) => n instanceof Element && n.hasAttribute && n.hasAttribute(attr)
    );
  }

  disconnectedCallback() {
    if (this._ro) {
      this._ro.disconnect();
      this._ro = null;
    }
  }

  _onClick(e) {
    /* 长按已经弹过第二个实体，紧随其后的 click 要吞掉，否则会再弹一个 */
    if (this._lpFired) {
      this._lpFired = false;
      return;
    }
    const target = this._actionTarget(e, "data-action");
    if (!target || !this._hass) return;
    const action = target.getAttribute("data-action");

    /* 通用：弹某个实体的 more-info（胎压块、发动机、车门、里程、油量都用它） */
    if (action === "entity") {
      const id = target.getAttribute("data-entity");
      if (id) this._fireMoreInfo(id);
      return;
    }

    if (action === "refresh") {
      // 上一次还在等车机上报，别重复下发（后端也有 60 秒冷却）
      if (this._refreshing) return;
      const btn = this._entities.refresh;
      // 按钮在等车机上报期间是 unavailable，此时点它只会报错
      if (btn && this._hass.states[btn]?.state === "unavailable") {
        this._refreshing = true;
        this.render();
        return;
      }
      const luId = this._entities.last_update;
      this._refreshFrom = luId ? this._hass.states[luId]?.state : null;
      this._refreshing = true;
      this._refreshResult = "";
      this.render();
      if (this._refreshTimer) clearTimeout(this._refreshTimer);
      // 兜底：后端 180 秒后才判超时，这里留点余量
      this._refreshTimer = setTimeout(() => {
        if (this._refreshing) this._finishRefresh("stale");
      }, 200000);
      if (btn) {
        this._hass.callService("button", "press", { entity_id: btn });
      } else {
        // 没找到刷新按钮时，退化为逐个刷新已识别的实体
        const ids = Object.values(this._entities).filter(Boolean);
        if (ids.length) this._hass.callService("homeassistant", "update_entity", { entity_id: ids });
      }
      return;
    }

    if (action === "location") {
      const tracker = this._entities.tracker;
      const pos = this._hass.states[this._entities.position];
      if (tracker) {
        this._fireMoreInfo(tracker);
      } else if (pos && pos.attributes && pos.attributes.latitude) {
        const { latitude: lat, longitude: lon } = pos.attributes;
        window.open(`https://uri.amap.com/marker?position=${lon},${lat}`, "_blank");
      }
      return;
    }

    if (action === "tire" && this._entities.tire_abnormal) {
      this._fireMoreInfo(this._entities.tire_abnormal);
    }
    if (action === "fuel") {
      const id = this._entities.remain_fuel || this._entities.fuel_low_alarm;
      if (id) this._fireMoreInfo(id);
    }
  }

  _fireMoreInfo(entityId) {
    const ev = new Event("hass-more-info", { bubbles: true, composed: true });
    ev.detail = { entityId };
    this.dispatchEvent(ev);
  }

  // ------------------------------------------------------------------
  // 实体自动发现：translation_key > entity_id > 中文 friendly_name
  // ------------------------------------------------------------------
  _resolveEntities(hass) {
    if (!hass || !hass.states) return;
    const conf = this._config;

    // 显式映射优先
    if (conf.entities && Object.keys(conf.entities).length) {
      this._entities = { ...conf.entities };
      return;
    }

    const allIds = Object.keys(hass.states);
    const registry = hass.entities || {};

    // 圈定候选池：设备名 > entity_id 前缀 > 平台过滤 > 全部
    let pool = null;
    if (conf.device && hass.devices) {
      const devIds = Object.values(hass.devices)
        .filter((d) => d && ((d.name || "").includes(conf.device) || (d.name_by_user || "").includes(conf.device)))
        .map((d) => d.id);
      if (devIds.length) {
        pool = allIds.filter((id) => registry[id] && devIds.includes(registry[id].device_id));
      }
    }
    if (pool === null && conf.prefix) {
      pool = allIds.filter((id) => id.startsWith(conf.prefix));
    }
    if (pool === null) {
      const platformPool = allIds.filter((id) => registry[id] && registry[id].platform === DOMAIN);
      pool = platformPool.length ? platformPool : allIds;
    }

    const short = (id) => id.slice(id.indexOf(".") + 1);
    const resolved = {};
    const missing = [];

    for (const [key, spec] of Object.entries(KEY_SPECS)) {
      const candidates = pool.filter((id) => id.startsWith(spec.domain + "."));
      let best = null, bestScore = 0;
      for (const id of candidates) {
        const reg = registry[id] || {};
        const fname = (hass.states[id]?.attributes?.friendly_name) || "";
        let score = 0;
        if (reg.translation_key === key) score = 4;
        else if (short(id) === key || short(id).endsWith("_" + key)) score = 3;
        else if (spec.ids && new RegExp(spec.ids).test(short(id))) score = 2;
        else if (spec.zh && new RegExp(spec.zh).test(fname)) score = 1;
        if (score > bestScore) { best = id; bestScore = score; }
      }
      if (best) resolved[key] = best;
      else missing.push(key);
    }

    // 定位与刷新
    resolved.tracker = pool.find((id) => id.startsWith("device_tracker.")) || "";
    const btnCandidates = pool.filter((id) => id.startsWith("button."));
    resolved.refresh =
      btnCandidates.find((id) => /刷新/.test(hass.states[id]?.attributes?.friendly_name || "")) ||
      btnCandidates.find((id) => short(id) === "refresh" || short(id).endsWith("_refresh")) ||
      btnCandidates[0] || "";

    const sig = JSON.stringify(resolved) + "|" + missing.join();
    if (sig !== this._lastSig) {
      console.info("[gwm-vehicle-card] 实体识别:", resolved, missing.length ? "未识别: " + missing.join(", ") : "全部命中");
      this._lastSig = sig;
    }
    this._entities = resolved;
    this._missing = missing;
  }

  // ------------------------------------------------------------------
  // 渲染
  // ------------------------------------------------------------------
  render() {
    if (!this._config || !this.shadowRoot) return;
    if (!this._hass || !Object.keys(this._entities).length) {
      this.shadowRoot.innerHTML = `<style>${CARD_CSS}</style>
        <ha-card><div class="hint">等待实体数据…<br/>请确认 gwm_vehicle 集成已加载，或在卡片配置中填写 device / prefix / entities。</div></ha-card>`;
      return;
    }

    const m = this._buildModel();
    const blinkCls = this._config.blink ? "blink" : "";

    this.shadowRoot.innerHTML = `<style>${CARD_CSS}</style>
      <ha-card class="${this._narrow ? "narrow" : ""}">
        ${this._headerHtml(m)}
        ${this._flagsHtml(m, blinkCls)}
        ${this._carStageHtml(m, blinkCls)}
        ${this._tireSummaryHtml(m)}
        ${this._footerHtml(m)}
        ${this._metricsHtml(m)}
        ${this._locationHtml(m)}
        ${this._missingHtml()}
      </ha-card>`;

    // 车图就绪后按真实比例修正 stage 宽度
    const img = this.shadowRoot.querySelector(".car-img");
    if (img) {
      if (img.complete) this._fitStage();
      else img.addEventListener("load", () => this._fitStage(), { once: true });
    }
  }

  _buildModel() {
    const hs = this._hass.states;
    const get = (k) => {
      const id = this._entities[k];
      const st = id ? hs[id] : undefined;
      return st ? st.state : undefined;
    };
    const num = (k) => {
      const v = parseFloat(get(k));
      return isNaN(v) ? null : v;
    };
    const on = (k) => get(k) === "on";

    const cfg = this._config;
    /* 车锁极性：集成把原始值 0=已上锁 映射成 on，与 HA「on=未上锁」的约定相反
       （lock 类 device_class：on 表示未上锁）。有 raw_value 时以原始值为准。 */
    const lockRaw = get("door_lock") !== undefined
      ? hs[this._entities.door_lock]?.attributes?.raw_value
      : undefined;
    const unlocked = lockRaw !== undefined && lockRaw !== null
      ? String(lockRaw) !== "0"
      : on("door_lock");

    const tires = TIRE_DEFS.map((d) => {
      const p = num(d.p);
      const t = num(d.t);
      const abnormal =
        (p !== null && (p < cfg.pressure_low || p > cfg.pressure_high)) ||
        (t !== null && t > cfg.temp_high);
      /* 带上实体 id：点击胎压块弹胎压实体的 more-info，长按弹胎温 */
      return {
        ...d, p, t, abnormal,
        pId: this._entities[d.p] || "",
        tId: this._entities[d.t] || "",
      };
    });
    // 全局胎压异常报警但阈值没推断出轮位 → 全部标红提示
    if (on("tire_abnormal") && !tires.some((x) => x.abnormal)) {
      tires.forEach((x) => { x.abnormal = true; x.globalOnly = true; });
    }

    // remain_fuel 是剩余升数；百分比只为进度条与告警阈值服务，按油箱容量换算
    const fuelL = num("remain_fuel");
    const fuelPct = fuelL !== null && cfg.fuel_capacity_l > 0
      ? (fuelL / cfg.fuel_capacity_l) * 100 : null;
    const fuelLow = on("fuel_low_alarm") || (fuelPct !== null && fuelPct <= cfg.fuel_low_percent);
    const acCool = on("ac_cooling");
    const acHeat = on("ac_heating");
    const acTemp = num("ac_target_temperature");
    const acVol = num("ac_volume_level");

    const trackerId = this._entities.tracker;
    const trackerState = trackerId ? hs[trackerId]?.state : undefined;
    const atHome = trackerState === "home";
    const pos = hs[this._entities.position];
    const dist = pos?.attributes?.distance_from_home_km;

    const lu = get("last_update");
    let updateTime = "--";
    if (lu) {
      const d = new Date(lu);
      if (!isNaN(d.getTime())) {
        const p2 = (n) => String(n).padStart(2, "0");
        updateTime = `${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}`;
      }
    }

    let title = cfg.title;
    if (!title) {
      const devId = this._entities.engine && hs[this._entities.engine]
        ? (this._hass.entities?.[this._entities.engine]?.device_id) : null;
      title = (devId && this._hass.devices?.[devId]?.name) || cfg.device || "GWM 车辆";
    }

    return {
      title, tires,
      fuelPct, fuelL, fuelLow,
      mileage: num("total_distance"),
      engineOn: on("engine"),
      acCool, acHeat, acTemp, acVol,
      unlocked,
      doors: { fl: on("door_fl"), fr: on("door_fr"), rl: on("door_rl"), rr: on("door_rr") },
      trunk: on("trunk"),
      hood: on("hood"),
      windows: { fl: on("window_fl"), fr: on("window_fr"), rl: on("window_rl"), rr: on("window_rr") },
      atHome, trackerState, dist,
      updateTime,
    };
  }

  _headerHtml(m) {
    const badge =
      m.unlocked && (this._config.lock_style === "both" || this._config.lock_style === "badge")
        ? `<div class="lock-badge"><svg width="13" height="13" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2a5 5 0 0 1 5 5v3h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h1V7a5 5 0 0 1 5-5zm0 2a3 3 0 0 0-3 3v3h6V7a3 3 0 0 0-3-3z"/></svg><span>未上锁</span></div>`
        : "";
    /* 总里程右对齐到卡片右缘（与左侧车名两端对齐），点击弹里程实体 */
    const mid = this._entities.total_distance || "";
    const hasMileage = m.mileage != null && !isNaN(m.mileage);
    const mileage = hasMileage
      ? `<div class="mileage${mid ? " clickable" : ""}"${
          mid ? ` data-action="entity" data-entity="${mid}"` : ""
        } title="点击查看总里程实体">
          <span class="mileage-label">总里程</span><b>${fmtInt(m.mileage)}</b><i>km</i>
        </div>`
      : "";
    return `<div class="header">
      <div class="title-row">
        <svg class="title-icon" width="20" height="20" viewBox="0 0 24 24"><path fill="currentColor" d="M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11a2 2 0 0 1 2 2v4h-2a2 2 0 0 1-4 0H9a2 2 0 0 1-4 0H3v-4a2 2 0 0 1 2-2zm2.1 0h9.8l-1-3H8.1l-1 3z"/></svg>
        <span class="title">${m.title}</span>
      </div>
      <div class="header-right">${badge}${mileage}</div>
    </div>`;
  }

  _flagsHtml(m, blinkCls) {
    const flags = [];
    const abnormalTires = m.tires.filter((t) => t.abnormal);
    if (abnormalTires.length) {
      const names = abnormalTires.some((t) => t.globalOnly)
        ? "存在异常"
        : abnormalTires.map((t) => t.cn).join("、");
      flags.push(
        `<div class="flag err ${blinkCls}" data-action="tire"><svg width="13" height="13" viewBox="0 0 24 24"><path fill="currentColor" d="${ICON_TIRE}"/></svg><span>胎压异常 · ${names}</span></div>`
      );
    }
    if (m.fuelLow) {
      const fid = this._entities.remain_fuel || this._entities.fuel_low_alarm || "";
      flags.push(
        `<div class="flag warn ${blinkCls}${fid ? " clickable" : ""}"${
          fid ? ` data-action="entity" data-entity="${fid}"` : ""
        }><svg width="13" height="13" viewBox="0 0 24 24"><path fill="currentColor" d="${ICON_FUEL}"/></svg><span>油量低${m.fuelL !== null ? ` · ${Math.round(m.fuelL)} L` : ""}</span></div>`
      );
    }
    return flags.length ? `<div class="flags">${flags.join("")}</div>` : "";
  }

  /* 实车俯视图 + 覆盖角标。胎压异常才显示红色数值标（闪烁），正常不显示。 */
  _carStageHtml(m, blinkCls) {
    const cfg = this._config;
    const mk = cfg.markers;
    const border =
      m.unlocked && (cfg.lock_style === "both" || cfg.lock_style === "border")
        ? "warn-border" : "";

    /* 四轮数据标：胎压/胎温常显，各引一条引导线指到对应车轮。
       三个元素全部绝对定位、以「车图」为坐标基准：
         圆点 = 轮胎中心 (x%, y%)
         线   = 从圆心向车外水平延伸 44px
         值块 = 线外侧再留 6px
       不用任何跨元素测量，所以卡片多宽、车图多大都不会跑偏。 */
    const showNormal = cfg.show_tire_normal !== false;
    const MARK = 44; // 引导线长度
    const GAP = 6;
    const tireMarks = m.tires
      .filter((t) => t.abnormal || (showNormal && (t.p !== null || t.t !== null)))
      .map((t) => {
        const pos = mk["tire_" + t.key] || DEFAULT_MARKERS["tire_" + t.key];
        const x = pos.x;
        const y = pos.y;
        const left = pos.side === "left";
        const pTxt = t.p === null ? "--" : Math.round(t.p);
        const tTxt = t.t === null ? "--" : Math.round(t.t);
        const cls = t.abnormal ? "err" : "ok";
        const lineStyle = left
          ? `left:calc(${x}% - ${MARK}px);width:${MARK}px;top:${y}%`
          : `left:${x}%;width:${MARK}px;top:${y}%`;
        const chipStyle = left
          ? `right:calc(${(100 - x).toFixed(2)}% + ${MARK + GAP}px);top:${y}%`
          : `left:calc(${x}% + ${MARK + GAP}px);top:${y}%`;
        const attr = t.pId ? ` data-action="entity" data-entity="${t.pId}"` : "";
        const attrLong = t.tId ? ` data-long-entity="${t.tId}"` : "";
        return `<span class="tire-line ${cls}" style="${lineStyle}"></span>
          <i class="tire-dot ${cls}" style="left:${x}%;top:${y}%"></i>
          <div class="tire-chip ${cls}${t.abnormal ? " " + blinkCls : ""}${t.pId || t.tId ? " clickable" : ""}"
            style="${chipStyle}"${attr}${attrLong}
            title="${t.cn}轮 · 短按看胎压，长按看胎温">
            <b>${pTxt}<i>kPa</i></b><span>${tTxt}°C</span>
          </div>`;
      })
      .join("");

    /* 发动机启动：红色发动机叠加层（与车图裁剪区域对齐） */
    const er = cfg.engine_region;
    const engineOverlay = m.engineOn
      ? `<img class="engine-overlay ${blinkCls}" src="${cfg.engine_image}" draggable="false" alt=""
          style="left:${er.x}%;top:${er.y}%;width:${er.w}%;height:${er.h}%">`
      : "";

    const badge = (open, name, pos, entId) =>
      open && pos
        ? `<div class="marker${entId ? " clickable" : ""}" style="left:${pos.x}%;top:${pos.y}%"${
            entId ? ` data-action="entity" data-entity="${entId}"` : ""
          }>${name}</div>`
        : "";

    // 空调：制冷蓝 / 制热红 徽标（呼吸动画）
    let acBadge = "";
    if (m.acCool || m.acHeat) {
      const cls = m.acCool ? "cool" : "heat";
      const label = `${m.acCool ? "制冷" : "制热"}${m.acTemp !== null ? " " + Math.round(m.acTemp) + "°C" : ""}`;
      const acId = this._entities.ac_target_temperature || "";
      acBadge = `<div class="ac-pill ${cls} ${cfg.ac_animation ? "pulse" : ""}${acId ? " clickable" : ""}"
        style="left:${mk.ac.x}%;top:${mk.ac.y}%"${
          acId ? ` data-action="entity" data-entity="${acId}"` : ""
        }>${label}</div>`;
    }

    const markers = [
      badge(m.hood, "盖", mk.hood, this._entities.hood),
      badge(m.trunk, "箱", mk.trunk, this._entities.trunk),
      badge(m.windows.fl, "窗", mk.window_fl, this._entities.window_fl),
      badge(m.windows.fr, "窗", mk.window_fr, this._entities.window_fr),
      badge(m.windows.rl, "窗", mk.window_rl, this._entities.window_rl),
      badge(m.windows.rr, "窗", mk.window_rr, this._entities.window_rr),
      acBadge,
    ].join("");

    /* 点击热区：透明、无内容，只把点击映射到实体（比线稿本身好点中）。
       放在 markers 之前，同 z-index 下 markers 后绘制、优先接收点击。 */
    const DOOR_CN = { fl: "左前", fr: "右前", rl: "左后", rr: "右后" };
    const hot = (style, entId, tip) =>
      entId
        ? `<div class="hit" style="${style}" data-action="entity" data-entity="${entId}" title="${tip}"></div>`
        : "";
    const doorHits = Object.entries(DOOR_HIT)
      .map(([k, h]) => {
        const style =
          h.right != null
            ? `right:${h.right}%;top:${h.top}%;width:${h.w}%;height:${h.h}%`
            : `left:${h.left}%;top:${h.top}%;width:${h.w}%;height:${h.h}%`;
        return hot(style, this._entities["door_" + k], DOOR_CN[k] + "车门状态");
      })
      .join("");
    const engineHit = hot(
      `left:${ENGINE_HIT.x}%;top:${ENGINE_HIT.y}%;width:${ENGINE_HIT.w}%;height:${ENGINE_HIT.h}%`,
      this._entities.engine,
      "发动机状态"
    );

    /* 开门：贴真实开门俯视图裁出的门片（左门镜像），比角标直观 */
    const doorOverlays = cfg.door_overlay
      ? Object.entries(m.doors)
          .filter(([, open]) => open)
          .map(([k]) => {
            const o = (cfg.door_layout || {})[k] || DOOR_OVERLAY[k];
            if (!o) return "";
            const pos = o.mirror
              ? `right:${o.left.toFixed(2)}%;`
              : `left:${o.left.toFixed(2)}%;`;
            return `<img class="door-open" src="${o.file}" draggable="false" alt=""
              style="${pos}top:${o.top.toFixed(2)}%;width:${o.w.toFixed(2)}%${o.mirror ? ";transform:scaleX(-1)" : ""}">`;
          })
          .join("")
      : "";

    /* 异常轮胎：红色轮胎叠加层（贴住原车轮位置），没有素材则回落到红点 */
    const tireOverlays = cfg.tire_overlay
      ? m.tires
          .filter((t) => t.abnormal)
          .map((t) => {
            const o = (cfg.tire_layout || {})[t.key] || TIRE_RED_OVERLAY[t.key];
            if (!o) return "";
            return `<img class="tire-red" src="${o.file}" draggable="false" alt=""
              style="left:${o.left.toFixed(2)}%;top:${o.top.toFixed(2)}%;width:${o.w.toFixed(2)}%">`;
          })
          .join("")
      : "";

    return `<div class="stage">
      <div class="car-wrap ${border} ${this._isDarkBg() ? "dark-img" : ""}" style="--car-mh:${cfg.car_max_height}px">
        <img class="car-img" src="${cfg.image}" style="opacity:${cfg.image_opacity}" draggable="false" alt="">
        ${tireOverlays}
        ${doorOverlays}
        ${engineOverlay}
        ${engineHit}
        ${doorHits}
        ${markers}
        ${tireMarks}
      </div>
    </div>`;
  }

  /* 深色主题下黑线条稿需要反色才能看清 */
  _isDarkBg() {
    try {
      let bg = getComputedStyle(this.shadowRoot.host).getPropertyValue("--card-background-color") || "";
      bg = bg.trim();
      let r = 255, g = 255, b = 255;
      const rgb = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (rgb) {
        r = +rgb[1]; g = +rgb[2]; b = +rgb[3];
      } else if (/^#[0-9a-f]{6}$/i.test(bg)) {
        r = parseInt(bg.slice(1, 3), 16); g = parseInt(bg.slice(3, 5), 16); b = parseInt(bg.slice(5, 7), 16);
      }
      return (0.299 * r + 0.587 * g + 0.114 * b) < 128;
    } catch (e) {
      return false;
    }
  }

  /* 车图加载后按真实宽高比约束车图宽度：两侧要留出胎压标注的空间，
     故基准宽度收到 46%（窄卡 42%），高度上限仍由 car_max_height 控制 */
  _fitStage() {
    const img = this.shadowRoot.querySelector(".car-img");
    const wrap = this.shadowRoot.querySelector(".car-wrap");
    if (!img || !wrap || !img.naturalWidth) return;
    const ar = img.naturalWidth / img.naturalHeight;
    const base = this._narrow ? 42 : 46;
    wrap.style.width = `min(${base}%, calc(var(--car-mh, 420px) * ${ar.toFixed(4)}))`;
  }

  /* 全部正常时的一行胎压摘要：让"数据到底有没有取到"一眼可见 */
  _tireSummaryHtml(m) {
    if (!this._config.show_tire_summary) return "";
    if (this._config.show_tire_normal) return "";
    if (m.tires.some((t) => t.abnormal)) return "";
    if (m.tires.every((t) => t.p === null)) return "";
    const p = m.tires.map((t) => (t.p === null ? "--" : Math.round(t.p))).join(" / ");
    const temps = m.tires.map((t) => t.t).filter((v) => v !== null);
    const t = temps.length
      ? temps.map((v) => Math.round(v)).join("/") + "°C"
      : "";
    return `<div class="tire-summary">
      <span>胎压 ${p} kPa</span>${t ? `<span class="sep">·</span><span>胎温 ${t}</span>` : ""}
      <span class="ok-tag">正常</span>
    </div>`;
  }

  /* 窄卡：异常胎压以栅格显示在车图下方（带方位名，避免歧义） */
  _tireGridHtml(m, blinkCls) {
    if (!this._narrow) return "";
    const cells = m.tires
      .filter((t) => t.abnormal)
      .map((t) => {
        const pTxt = t.p === null ? "--" : `${Math.round(t.p)} kPa`;
        const tTxt = t.t === null ? "" : ` · ${Math.round(t.t)}°C`;
        return `<div class="tg-cell">
          <span class="tg-name">${t.cn}</span>
          <span class="tg-val ${blinkCls}">${pTxt}${tTxt}</span>
        </div>`;
      })
      .join("");
    return cells ? `<div class="tire-grid">${cells}</div>` : "";
  }

  _footerHtml(m) {
    const spin = this._refreshing ? "spin" : "";
    const note = this._refreshing
      ? `<span class="refresh-note busy">正在唤醒车机…</span>`
      : this._refreshResult === "ok"
        ? `<span class="refresh-note ok">车机已上报</span>`
        : this._refreshResult === "stale"
          ? `<span class="refresh-note warn">指令已下发 · 车机未响应</span>`
          : this._refreshResult === "failed"
            ? `<span class="refresh-note warn">刷新指令发送失败</span>`
            : "";
    return `<div class="footer">
      <span class="update-time">数据更新于 ${m.updateTime}${note}</span>
      <button class="refresh-btn ${spin}" data-action="refresh" title="让车机重新上报（10 秒 ~ 3 分钟）">
        <svg width="13" height="13" viewBox="0 0 24 24"><path fill="currentColor" d="M12 4V1L7 6l5 5V7a5 5 0 1 1-5 5H5a7 7 0 1 0 7-8z"/></svg>
        刷新
      </button>
    </div>`;
  }

  _metricsHtml(m) {
    const pct = m.fuelPct;
    const pctTxt = m.fuelL === null ? "--" : `${Math.round(m.fuelL)} L`;
    const literTxt = pct === null ? "" : `约 ${Math.round(pct)}%`;
    const barColor = m.fuelLow ? "var(--error-color,#db4437)" : pct !== null && pct < 25 ? "var(--warning-color,#ffa600)" : "var(--success-color,#43a047)";
    const barW = pct === null ? 0 : Math.max(0, Math.min(100, pct));
    const fid = this._entities.remain_fuel || this._entities.fuel_low_alarm || "";
    return `<div class="metric fuel${fid ? " clickable" : ""}"${
      fid ? ` data-action="entity" data-entity="${fid}"` : ""
    } title="点击查看剩余油量实体">
      <div class="metric-top"><span class="metric-label"><svg width="14" height="14" viewBox="0 0 24 24"><path fill="currentColor" d="${ICON_FUEL}"/></svg>剩余油量</span><span class="metric-badge" style="color:${barColor}">${pctTxt}</span></div>
      <div class="bar"><div class="bar-fill" style="width:${barW}%;background:${barColor}"></div></div>
      <div class="metric-val">${literTxt || (pct === null ? "无数据" : "")}</div>
    </div>`;
  }

  _locationHtml(m) {
    const atHome = m.atHome;
    const color = atHome ? "var(--success-color,#43a047)" : "var(--info-color,#039be5)";
    const txt = m.trackerState === undefined || m.trackerState === "unknown" || m.trackerState === "unavailable"
      ? "位置未知"
      : atHome ? "车辆在家" : "车辆离家";
    const dist = m.dist != null && !isNaN(m.dist) ? ` · 距家 ${m.dist} km` : "";
    return `<div class="location" data-action="location">
      <div class="loc-left">
        <svg width="16" height="16" viewBox="0 0 24 24" style="color:${color}"><path fill="currentColor" d="M12 2a7 7 0 0 1 7 7c0 5.2-7 13-7 13S5 14.2 5 9a7 7 0 0 1 7-7zm0 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"/></svg>
        <span>${txt}<span class="loc-sub">${dist}</span></span>
      </div>
      <svg width="14" height="14" viewBox="0 0 24 24" style="color:var(--secondary-text-color,#727272)"><path fill="currentColor" d="M8 4l8 8-8 8V4z"/></svg>
    </div>`;
  }

  _missingHtml() {
    if (!this._config.show_missing || !this._missing.length) return "";
    const zhNames = {
      remain_fuel: "剩余油量", total_distance: "总里程", last_update: "更新时间",
      position: "车辆位置", tire_pressure_fl: "胎压左前", tire_pressure_fr: "胎压右前",
      tire_pressure_rl: "胎压左后", tire_pressure_rr: "胎压右后",
      tire_temp_fl: "胎温左前", tire_temp_fr: "胎温右前", tire_temp_rl: "胎温左后", tire_temp_rr: "胎温右后",
      door_lock: "车锁", engine: "发动机", trunk: "后备箱", hood: "引擎盖",
      ac_target_temperature: "空调温度", ac_volume_level: "空调风量",
      fuel_low_alarm: "低油量报警", tire_abnormal: "胎压异常",
      ac_cooling: "空调制冷", ac_heating: "空调制热",
    };
    const names = this._missing.map((k) => zhNames[k] || k).join("、");
    return `<div class="missing-hint">未识别实体：${names}（在浏览器控制台查看「实体识别」日志，或用 YAML entities 手动指定）</div>`;
  }
}

const CARD_CSS = `
:host { display: block; }
* { box-sizing: border-box; }
.hint { font-size: 13px; color: var(--secondary-text-color,#727272); text-align: center; padding: 16px; line-height: 1.6; }
ha-card {
  padding: 14px 16px;
  background: var(--card-background-color, var(--primary-background-color,#fff));
  border: var(--ha-card-border-width,1px) solid var(--ha-card-border-color, var(--divider-color,#e0e0e0));
  border-radius: var(--ha-card-border-radius,12px);
  color: var(--primary-text-color,#111);
  font-family: inherit;
}
.blink { animation: gwm-blink 1.1s ease-in-out infinite; }
@keyframes gwm-blink { 50% { opacity: .3; } }

.header { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.title-icon { color: var(--info-color,#039be5); flex-shrink: 0; }
.title { font-size: 15px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.header-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; margin-left: auto; }
/* 总里程：右端对齐，前置 label */
.mileage { display: flex; align-items: baseline; gap: 4px; white-space: nowrap; border-radius: 6px;
  padding: 2px 6px; margin-right: -6px; }
.mileage-label { font-size: 11px; color: var(--secondary-text-color,#727272); }
.mileage b { font-size: 13px; font-weight: 600; color: var(--primary-text-color,#111); letter-spacing: -.2px; }
.mileage i { font-style: normal; font-size: 10px; color: var(--secondary-text-color,#727272); }
.mileage.clickable { cursor: pointer; }
.mileage.clickable:hover { background: var(--secondary-background-color,#f5f5f5); }
.lock-badge { display: flex; align-items: center; gap: 5px; border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 500; flex-shrink: 0;
  background: color-mix(in srgb, var(--warning-color,#ffa600) 15%, transparent); color: var(--warning-color,#ffa600); }

.flags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.flag { display: flex; align-items: center; gap: 6px; border-radius: 6px; padding: 5px 10px; font-size: 12px; font-weight: 500; cursor: pointer; }
.flag.err { background: color-mix(in srgb, var(--error-color,#db4437) 14%, transparent); color: var(--error-color,#db4437); border-left: 3px solid var(--error-color,#db4437); }
.flag.warn { background: color-mix(in srgb, var(--warning-color,#ffa600) 16%, transparent); color: var(--warning-color,#ffa600); border-left: 3px solid var(--warning-color,#ffa600); }

.stage { position: relative; display: flex; justify-content: center; padding: 10px 0 6px;
  max-width: 480px; margin: 0 auto; }
.car-wrap { position: relative; width: min(46%, calc(var(--car-mh, 420px) * 0.457)); }
.car-wrap.warn-border { border: 2px dashed var(--warning-color,#ffa600); border-radius: 14px; }
.car-img { display: block; width: 100%; height: auto; }
.car-wrap.dark-img .car-img { filter: invert(1); }

/* 四轮胎压/胎温：圆点落在轮胎中心，引导线向车外延伸，值块在线外侧。
   三者都是绝对定位，坐标全部取自车图百分比 → 永远对得上轮子。 */
.tire-chip { position: absolute; z-index: 5; transform: translateY(-50%);
  display: flex; flex-direction: column; align-items: flex-start; line-height: 1.2;
  border-radius: 8px; padding: 3px 8px; border: 1px solid var(--divider-color,#e0e0e0);
  background: var(--card-background-color,#fff); color: var(--primary-text-color,#212121);
  box-shadow: 0 1px 3px rgba(0,0,0,.07);
  -webkit-touch-callout: none; user-select: none; -webkit-user-select: none; touch-action: manipulation; }
.tire-chip.clickable { cursor: pointer; }
.tire-chip.clickable:hover { border-color: var(--primary-color,#039be5);
  box-shadow: 0 1px 6px rgba(0,0,0,.16); }
.tire-chip.clickable:active { transform: translateY(-50%) scale(.96); }
.tire-chip b { font-size: 13px; font-weight: 600; letter-spacing: -.2px; }
.tire-chip span { font-size: 11px; font-weight: 400; opacity: .78; }
.tire-chip i { font-style: normal; font-size: 9px; font-weight: 400; margin-left: 2px; opacity: .7; }
.tire-chip.err { color: var(--error-color,#db4437);
  border-color: color-mix(in srgb, var(--error-color,#db4437) 55%, transparent);
  background: color-mix(in srgb, var(--error-color,#db4437) 10%, var(--card-background-color,#fff)); }

.tire-line { position: absolute; z-index: 4; height: 0; transform: translateY(-50%); pointer-events: none;
  border-top: 1px solid var(--secondary-text-color,#727272); opacity: .45; }
.tire-line.err { border-top: 2px dashed var(--error-color,#db4437); opacity: 1; }

.tire-dot { position: absolute; z-index: 4; width: 6px; height: 6px; border-radius: 50%;
  background: var(--secondary-text-color,#727272); opacity: .45;
  transform: translate(-50%, -50%); pointer-events: none; }
.tire-dot.err { width: 7px; height: 7px; background: var(--error-color,#db4437); opacity: 1; }

.door-open, .tire-red { position: absolute; z-index: 2; pointer-events: none; }
.car-wrap.dark-img .door-open, .car-wrap.dark-img .tire-red { filter: invert(1) hue-rotate(180deg) saturate(1.15); }

/* 点击热区：完全透明，悬停给淡底衬提示"这里能点"；移动端无 hover，靠 title 无法提示，
   所以热区也覆盖在门缝/发动机这些位置本身合理的位置上 */
.hit { position: absolute; z-index: 2; border-radius: 8px; cursor: pointer;
  -webkit-tap-highlight-color: transparent; }
.hit:hover { background: color-mix(in srgb, var(--primary-color,#039be5) 9%, transparent); }
.marker.clickable, .ac-pill.clickable, .flag.clickable { cursor: pointer; }

.refresh-note { margin-left: 6px; font-size: 11px; }
.refresh-note.busy { color: var(--info-color,#039be5); }
.refresh-note.ok { color: var(--success-color,#43a047); }
.refresh-note.warn { color: var(--warning-color,#ffa600); }
.tire-summary { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 2px;
  font-size: 12px; color: var(--secondary-text-color,#727272); }
.tire-summary .sep { opacity: .5; }
.tire-summary .ok-tag { border-radius: 4px; padding: 0 5px; font-size: 11px; line-height: 16px;
  background: color-mix(in srgb, var(--success-color,#43a047) 16%, transparent); color: var(--success-color,#43a047); }

.engine-overlay { position: absolute; z-index: 1; pointer-events: none; }
.car-wrap.dark-img .engine-overlay { filter: brightness(1.55) saturate(1.15); }

.marker { position: absolute; z-index: 2; transform: translate(-50%, -50%); width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 500;
  background: color-mix(in srgb, var(--warning-color,#ffa600) 88%, transparent); color: #fff; }

.ac-pill { position: absolute; z-index: 2; transform: translate(-50%, -50%); border-radius: 999px; padding: 4px 11px;
  font-size: 12px; font-weight: 500; white-space: nowrap; }
.ac-pill.cool { background: color-mix(in srgb, var(--info-color,#039be5) 82%, transparent); color: #fff; }
.ac-pill.heat { background: color-mix(in srgb, var(--error-color,#db4437) 82%, transparent); color: #fff; }
.ac-pill.pulse { animation: gwm-pulse 2s ease-in-out infinite; }
@keyframes gwm-pulse { 50% { opacity: .65; } }

.tire-grid { display: none; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.narrow .tire-grid { display: grid; }
.narrow .tire-chip { padding: 2px 6px; }
.narrow .tire-chip b { font-size: 11px; }
.narrow .tire-chip span { font-size: 10px; }
.narrow .stage { padding: 8px 0 4px; }
.tg-cell { background: color-mix(in srgb, var(--error-color,#db4437) 12%, var(--card-background-color,#fff)); border-radius: 8px; padding: 7px 10px; display: flex; flex-direction: column; gap: 2px; }
.tg-name { font-size: 11px; color: var(--secondary-text-color,#727272); }
.tg-val { font-size: 12px; font-weight: 500; color: var(--error-color,#db4437); }

.footer { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--divider-color,#e0e0e0); padding-top: 9px; margin-top: 10px; }
.update-time { font-size: 12px; color: var(--secondary-text-color,#727272); }
.refresh-btn { display: flex; align-items: center; gap: 4px; border-radius: 999px; padding: 4px 11px; font-size: 12px; cursor: pointer;
  background: transparent; border: 1px solid var(--divider-color,#e0e0e0); color: var(--primary-text-color,#111); }
.refresh-btn:hover { background: var(--secondary-background-color,#f5f5f5); }
.refresh-btn.spin svg { animation: gwm-spin 1s linear infinite; }
@keyframes gwm-spin { to { transform: rotate(360deg); } }

.metric { background: var(--secondary-background-color,#f5f5f5); border-radius: 8px; padding: 10px 12px; }
.metric.fuel { margin-top: 10px; }
.metric.clickable { cursor: pointer; }
.metric.clickable:hover { filter: brightness(0.96); }
.metric-top { display: flex; justify-content: space-between; align-items: baseline; }
.metric-label { font-size: 12px; color: var(--secondary-text-color,#727272); display: inline-flex; align-items: center; gap: 4px; }
.metric-badge { font-size: 12px; font-weight: 500; }
.metric-val { font-size: 13px; font-weight: 500; margin-top: 5px; }
.bar { height: 8px; border-radius: 4px; background: var(--divider-color,#e0e0e0); margin: 6px 0 0; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width .5s ease; }

.location { display: flex; align-items: center; justify-content: space-between; background: var(--secondary-background-color,#f5f5f5);
  border-radius: 8px; padding: 10px 12px; margin-top: 10px; cursor: pointer; font-size: 13px; }
.location:hover { filter: brightness(0.97); }
.loc-left { display: flex; align-items: center; gap: 8px; }
.loc-sub { color: var(--secondary-text-color,#727272); }

.missing-hint { margin-top: 8px; font-size: 11px; color: var(--warning-color,#ffa600); text-align: center; }
`;

class GwmVehicleCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  setConfig(config) {
    this._config = { ...GwmVehicleCard.getStubConfig(), ...config };
    this.render();
  }
  set hass(hass) {
    this._hass = hass;
    this.render();
  }
  render() {
    if (!this._config || !this.shadowRoot) return;
    if (!customElements.get("ha-form")) {
      this.shadowRoot.innerHTML = `<div style="padding:12px;font-size:13px;color:var(--secondary-text-color,#727272)">GUI 编辑器加载失败，请使用 YAML 配置（见集成 README）。</div>`;
      return;
    }
    const schema = [
      { name: "device", label: "设备名称（留空自动识别）", selector: { text: {} } },
      { name: "title", label: "自定义标题（留空用设备名）", selector: { text: {} } },
      { name: "image", label: "车图 URL（留空用内置俯视图）", selector: { text: {} } },
      { name: "engine_image", label: "发动机叠加层 URL（留空用内置红发动机）", selector: { text: {} } },
      { name: "image_opacity", label: "车图不透明度 0-1（默认 1）", selector: { number: { min: 0, max: 1, step: 0.05, mode: "box" } } },
      { name: "car_max_height", label: "车图最大高度 px（默认 420）", selector: { number: { min: 200, max: 800, step: 10, mode: "box" } } },
      { name: "fuel_capacity_l", label: "油箱容量（升，默认 58）", selector: { number: { min: 1, max: 200, step: 1, mode: "box" } } },
      {
        name: "lock_style", label: "未上锁提示样式",
        selector: { select: { options: [
          { value: "both", label: "虚线边框 + 角标" },
          { value: "border", label: "仅虚线边框" },
          { value: "badge", label: "仅角标" },
        ] } },
      },
      { name: "blink", label: "异常项闪烁", selector: { boolean: {} } },
      { name: "pressure_low", label: "胎压下限 (kPa，默认 190)", selector: { number: { min: 1, max: 500, step: 1, mode: "box" } } },
      { name: "pressure_high", label: "胎压上限 (kPa，默认 300)", selector: { number: { min: 1, max: 500, step: 1, mode: "box" } } },
      { name: "temp_high", label: "胎温上限 (°C，默认 60)", selector: { number: { min: 0, max: 200, step: 1, mode: "box" } } },
    ];
    const form = document.createElement("ha-form");
    form.hass = this._hass;
    form.data = this._config;
    form.schema = schema;
    form.computeLabel = (s) => s.label;
    form.addEventListener("value-changed", (e) => {
      if (!e.detail || !e.detail.value) return;
      this._config = { ...this._config, ...e.detail.value };
      const ev = new Event("config-changed", { bubbles: true, composed: true });
      ev.detail = { config: this._config };
      this.dispatchEvent(ev);
    });
    this.shadowRoot.innerHTML = "";
    this.shadowRoot.appendChild(form);
  }
}

/**
 * 幂等注册自定义元素。
 * 集成升级后资源 URL 带新版本号，HA 会在同一页面内再次加载本脚本；
 * 此时同名元素已存在，直接 define 会抛 NotSupportedError 并中断后续逻辑，
 * 表现就是「明明更新了却还是旧样子」。这里改为探测 + 明确提示硬刷新。
 */
function defineCardElement(tag, ctor) {
  const existing = customElements.get(tag);
  if (!existing) {
    customElements.define(tag, ctor);
    return;
  }
  if (existing === ctor) return;
  console.warn(
    `[gwm-vehicle-card] 页面里已注册旧版 <${tag}>，v${CARD_VERSION} 未生效。` +
      "请按 Ctrl+Shift+R（macOS: Cmd+Shift+R）强制刷新页面。"
  );
}

defineCardElement("gwm-vehicle-card", GwmVehicleCard);
defineCardElement("gwm-vehicle-card-editor", GwmVehicleCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "gwm-vehicle-card",
  name: "GWM 车辆状态卡片",
  description: "长城汽车 GWM 车况总览：实车俯视图、胎压异常、门窗盖状态、油量里程、定位",
  preview: true,
  documentationURL: "https://github.com/your-name/gwm-vehicle-ha",
});

console.info(`%c GWM-VEHICLE-CARD %c v${CARD_VERSION} `, "color:white;background:#185FA5;font-weight:700", "color:#185FA5;background:#E6F1FB");
