# funlab-flaskr UI 架構（現況版）

> 2026-09-27 依現行 `templates/`、`static/`、funlab-libs 原始碼重寫。取代已刪除的 UI_ARCHITECTURE_GUIDE.md / THEME_TOGGLE_OPTIMIZATION.md / DARK_LIGHT_*.md / MENU_DIAGNOSTIC_TOOL.md（那些是修復過程紀錄；結論已合併到本檔，錯誤的舊敘述不保留）。

## 1. 分層結構

```
瀏覽器
 └─ Jinja2 模板（funlab/flaskr/templates/）
     ├─ layouts/base.html            ← 主版面（sidebar＋navbar＋hooks 佈點）
     ├─ layouts/base-fullscreen.html ← 無選單版面（登入頁等）
     ├─ includes/（banner、banner_scripts、scripts、settings、footer、
     │            notification_init、password_scripts、logo）
     └─ error-403/404/500/maintenance、blank、about、conf-data、plugin_management
 └─ 選單 HTML：funlab-libs/funlab/core/menu.py 以 Python 字串模板產生，
     經 before_request 注入 g.mainmenu / g.usermenu（appbase.py:register_request_handler）
 └─ 靜態資源：root_bp 的 /static（app 層無 static 路由，見 DEPLOYMENT.md）
```

- 頁面模板走 `{% extends "layouts/base.html" %}`，以 block 覆寫 `stylesheets / page_header / page_body / page_footer / modal_dialog / javascripts`。
- 動態包含點：`config.BANNER_PAGE`（預設 `includes/banner.html`）、`config.FOOTER_PAGE`（預設 `includes/footer.html`）。
- 模板可用 `call_hook(...)`（Jinja global，綁到 `hook_manager.render_hook`，見 HOOKS.md）與 funlab-libs `jinja_filters` 註冊的過濾器。
- 業務頁面不在本倉：由各 plugin 倉（finfun-fundmgr 等）的 templates 目錄 extend `layouts/base.html`，以各自 blueprint 的 `static` 提供資源（例：`/fundmgr/static/...`）。

## 2. Tabler 版本事實（以 static 內實際檔案為準）

| 事實 | 證據 |
|---|---|
| 執行件是 **Tabler v1.4.0** | `static/dist/js/tabler.min.js` 檔頭 `Tabler v1.4.0`；CSS 全部走 `--tblr-*` 變數前綴（非 `--bs-*`，這是 Tabler 自訂設計） |
| 模板註解的 `@version 1.0.0-beta19/beta20` 是**過期殘留**，不是真實版本 | base.html L4、includes/scripts.html L5 等 |
| `static/dist/js/demo-theme.min.js` 是 **beta20 舊檔**（1.0.0-beta20 檔頭） | 只在 `base-fullscreen.html` 被載入 |
| `static/dist/js/tabler-theme.min.js` 是 1.4.0 版主題初始化 | base.html `<head>` 載入 |
| 快取參數 `?1.4.0` 由模板手寫在 URL 尾（非 build 產物） | base.html L28-33 等 |
| `templates/tabler_index_demo.html` 是 Tabler demo 存檔頁，無路由掛載 | app.py 無對應 route；僅它引用 `static/avatars/` |

## 3. 主題切換機制（現況）

儲存：`localStorage`，鍵 `tabler-theme`（light/dark）、`tabler-theme-base/font/primary/radius`。

載入與套用的三條路徑：

1. **base.html 主版面**：`<head>` 載入 `tabler-theme.min.js`（1.4.0）→ 讀 URL 參數 `?theme=...`（優先）或 localStorage → 把值寫成 `<html data-bs-theme=...>` 等 `data-bs-*` 屬性。head 內載入是刻意的（防 FOUC）。
2. **base-fullscreen.html**：`<body>` 開頭載入舊版 `demo-theme.min.js`（beta20）→ 寫在 `<body data-bs-theme=...>` 而非 `<html>`。與主版面不一致，是已知瑕疵（Tabler CSS 同時支援 html/body 兩種掛點，所以目前可用；統一化列在改進候補）。
3. **navbar 切換鈕**（includes/banner.html 的 `#enable-dark-theme`/`#enable-light-theme`）：連結本體是 `?theme=dark|light`；includes/banner_scripts.html 的 JS 攔截點擊 → 直接改 `document.documentElement` 的 `data-bs-theme` + 寫 localStorage + 改 URL SearchParams，**不重新載入頁面**（這是舊 THEME_TOGGLE_OPTIMIZATION 的最終定案）。同步勾選 settings 面板 radio。

**Settings 面板**（includes/settings.html）：offcanvas 表單，radio 變更即套用＋寫 localStorage；「Reset」清 `tabler-*` 鍵。初始值由面板內嵌 script 與 `tabler-theme.min.js` 共同維護。

**Dark 模式下選單對比**：includes/banner.html 內含 `html[data-bs-theme="dark"] .navbar-vertical ...` 的 CSS 覆蓋（menu 修復的最終形態——**不是**在 sidebar 上硬編 `data-bs-theme="light"`，舊修復前形態已移除；現行 funlab-libs `menu.py:MenuBar._virtical_template` 不含任何 `data-bs-theme`，選單因此正常繼承全域主題。改 menu.py 時不得把它加回去）。

### 選單問題診斷要點（合併自 MENU_DIAGNOSTIC_TOOL.md 的長存部分）

1. 主題變數看 `--tblr-*`（不是 `--bs-*`）：DevTools 查 `getComputedStyle(document.documentElement).getPropertyValue('--tblr-body-bg')`。
2. 先確認主題掛點：`document.documentElement.dataset.bsTheme`（主版面）；fullscreen 頁看 `document.body.dataset.bsTheme`。
3. 選單消失/無反應：查 `g.mainmenu` 是否渲染出 `<aside class="navbar navbar-vertical">`；查 localStorage `tabler-theme` 是否與 DOM 屬性同步；`?theme=dark` 強制可排除 localStorage 干擾。
4. 對比不足：確認 banner.html 的 dark 覆蓋 CSS 有載入（被自訂 BANNER_PAGE 取代時會一起失去覆蓋）。

## 4. 通知與 CSRF 的前端接點

- CSRF：`base.html`/`base-fullscreen.html` head 注入 `<meta name="csrf-token">`，`static/js/csrf_ajax.js`（`defer`）monkey-patch `fetch`/`XMLHttpRequest`，僅對**同原位址**的非 GET 請求補 `X-CSRFToken` 標頭。所有 JS 提交者免改。
- 通知：`includes/notification_init.html` 載入 `_notifications.css` + `window.FUNLAB_CONFIG`（含 `sseEnabled`）＋ SSE 或輪詢 JS（`/static/js/polling_notifications.js` 或 SSE plugin 的 `/sse/static/...`）。provider 由 `app.set_notification_provider()` 決定（預設 appbase 的 in-memory PollingNotificationProvider）。

## 5. Hook 佈點（模板側）

`call_hook(...)` 出現處（grep templates 佐證）：`layouts/base.html` L50/L93/L95/L134 與 `layouts/base-fullscreen.html` L41/L55/L57/L67。名稱與 API 契約見 HOOKS.md。

## 6. 修改指南（給 coder 的硬規則）

1. 新頁面一律 extends `layouts/base.html`；不要在頁面裡重發 base 的 `<head>` 資源清單。
2. 要插 JS/CSS 到全部頁面 → 用 view hook（見 HOOKS.md），不要改 base.html。
3. 新靜態資源放所屬 plugin 的 static 目錄（`/fsplugin名/static/...`）；funlab-flaskr 的 `static/` 只放框架層資源。**絕對不要**把任何使用者資料放進 static 子樹（見 DEPLOYMENT.md）。
4. 升級 Tabler：整組換 `static/dist/`，同步模板尾碼 `?x.y.z`；檢查 `--tblr-*` 變數與 `data-bs-theme` 掛點相容性；`demo-theme.min.js` 若保留需換同版本。
5. 錯誤頁改動注意 `|safe` 限制（IMPROVEMENT_PLAN FLK-10）。
