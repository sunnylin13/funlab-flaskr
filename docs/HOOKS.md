# Hook 系統（唯一事實來源）

> 2026-09-27 重寫，合併並取代 docs/plugin_refactore/ 兩檔（導入計畫屬歷史；usage_examples 中不存在的 API 已剔除）。
> 核對基準：`funlab-libs/funlab/core/hook.py`、`funlab-libs/funlab/core/appbase.py`、`funlab-libs/funlab/core/plugin.py`、`funlab-libs/funlab/core/model_hook.py`、`funlab-sched`、grep 全 workspace templates。
> **不在本檔的 hook 名稱 = 不存在，不要憑舊文件引用。**（例：`view_project_sidebar_left/right` 只出現在已廢除的導入計畫草案，原始碼無呼叫點。）

## 1. API

實作：`funlab-libs/funlab/core/hook.py:HookManager`（每 app 一個實例，掛在 `app.hook_manager`）。

```python
app.hook_manager.register_hook(name, callback, priority=100, plugin_name=None)
# 回傳 None；同 priority 者按註冊序；數字小的先執行。

app.hook_manager.call_hook(name, **context) -> list[HookCallResult]
# 依序執行回呼；context 自動補 app（若未給）、request、current_user（在請求情境下）。
# 單一回呼丟例外 → 記 error log、略過該筆、繼續後續（錯誤隔離）。

app.hook_manager.render_hook(name, **context) -> markupsafe.Markup
# call_hook 後把各回呼的非 None 回傳值 str() 串接成 Markup。
# ⚠️ 回呼回傳的 HTML 不做 autoescape——回呼必須自行確保內容安全（不要拼入使用者輸入）。

app.hook_manager.list_hooks(name=None) -> dict[str, list[callback]]  # 除錯用
```

Jinja 側：`appbase.register_jinja_filters` 把模板函數 `call_hook(...)` 綁到 `render_hook`，因此模板中 `{{ call_hook('...') }}` 實際走的是 render 路徑。

## 2. 實際存在的 Hook 名稱

### 2.1 View Hooks（模板呼叫，回傳 HTML 字串）

分佈在 `funlab-flaskr/funlab/flaskr/templates/layouts/base.html` 與 `base-fullscreen.html`（兩版都有）：

| Hook | 位置 |
|---|---|
| `view_layouts_base_html_head` | `<head>` 尾（base.html 約 L50） |
| `view_layouts_base_content_top` | `.page-body` 內、page_body block 前（約 L93） |
| `view_layouts_base_content_bottom` | page_body block 後（約 L95） |
| `view_layouts_base_body_bottom` | `</body>` 前（約 L134） |

context：`app`、`request`、`current_user`（請求情境）。

### 2.2 Controller Hooks（appbase 觸發）

`funlab-libs/funlab/core/appbase.py:register_request_handler`：

| Hook | 觸發點 | 附加 context |
|---|---|---|
| `controller_before_request` | 每個請求進入時（CSRF 檢查之後、路由之前） | — |
| `controller_after_request` | 回應產生後 | `response` |
| `controller_error_handler` | app 層 `Exception` handler 內（HTTPException 直接放行、不觸發） | `error` |

注意：三個都是「旁觀」性質——回傳值被丟棄（call_hook 結果不接），改不了請求/回應流程；要改回應請用 Flask 原生 `after_request`。

### 2.3 Plugin Lifecycle Hooks（funlab-libs 觸發）

`funlab-libs/funlab/core/plugin.py`。context 一律帶 `plugin`（實例）與 `plugin_name`：

| Hook | 觸發點 |
|---|---|
| `plugin_after_init` | `Plugin.__init__` 尾（每個 plugin 構造完成）；SchedService/QuoteService 用它做「等其他 plugin 初始化完再啟動載入」的同步點 |
| ~~`plugin_service_init`~~ | **已移除**（2026-09-30，零生產消費，kanban t_c0ecb5c5；`ServicePlugin.__init__` 不再觸發，改監聽 `plugin_after_init`） |
| `plugin_before_start` / `plugin_after_start` | `Plugin.start()` |
| `plugin_before_stop` / `plugin_after_stop` | `Plugin.stop()` |
| `plugin_before_reload` / `plugin_after_reload` | `Plugin.reload()` |

### 2.4 Model Hooks（opt-in）

`funlab-libs/funlab/core/model_hook.py:ModelHookMixin` — 只有**繼承 mixin 且經 `save()/delete()` 路徑**寫入的 entity 會觸發（必須傳 `app=` 才發 hook）。workspace 內目前無 entity 繼承此 mixin（grep 僅見 mixin 自身），即：**現況不會有任何 model hook 事件**，註冊了也只是預留。

| Hook | context |
|---|---|
| `model_before_save` / `model_after_save` | `model, model_class, session, is_new` |
| `model_after_create` | `model, model_class, session`（is_new 時額外觸發） |
| `model_before_delete` / `model_after_delete` | `model, model_class, session` |

### 2.5 Task Hooks（funlab-sched 觸發）

`funlab-sched/funlab/sched/task.py`：

| Hook | 觸發點 | 附加 context |
|---|---|---|
| `task_before_execute` | 排程任務執行前 | `task, task_name, args, kwargs` |
| `task_after_execute` | 成功後 | `task, task_name, result` |
| `task_error` | 拋例外時 | `task, task_name, error` |

## 3. 註冊時機與慣例

- 在 plugin `__init__`（或 view 的 `_register_hook_examples` 慣例方法）註冊；`plugin_after_init` 可用於「等依賴 plugin 出現」的場合——慣例做法是檢查 `context['plugin_name']` 是否為目標 plugin 名（如 quotesvcs 等 `"pluginmanager"`/`"PluginManagerView"`）。
- priority：慣例 1（最早）/ 5-10（系統性）/ 50（一般功能）/ 100（預設，最晚）。SchedService 用 5 搶先啟動。
- View hook 每次渲染都跑：**不要在 hook 內做 DB 查詢或重計算**。
- 回呼簽名固定 `(context: dict)`；以唯讀方式使用 context。
- 除錯：`app.hook_manager.list_hooks('controller_before_request')` 看註冊清單；`_hooks` 內部結構為 `(priority, callback, plugin_name)` 元組清單（非 dict，舊文件的 `hook['plugin_name']` 寫法是錯的）。

## 4. 最小範例

```python
class MyPlugin(ViewPlugin):
    def __init__(self, app, url_prefix=None):
        super().__init__(app, url_prefix)
        self.app.hook_manager.register_hook(
            "view_layouts_base_content_top",
            self._banner, priority=50, plugin_name=self.name)

    def _banner(self, context) -> str:
        user = context.get('current_user')
        if user is not None and getattr(user, 'is_admin', False):
            return '<div class="alert alert-info">Admin mode</div>'
        return ""   # 回傳 ""/None 等於不插入
```
