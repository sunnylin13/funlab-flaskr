# Hook 使用範例

本文件提供 Funlab-Flaskr Hook 系統的實用範例與說明，採用繁體中文（台灣用語）。

## 目錄
- [View Hooks](#view-hooks)
- [Controller Hooks](#controller-hooks)
- [Plugin Lifecycle Hooks](#plugin-lifecycle-hooks)
- [Model Hooks](#model-hooks)
- [Task Hooks](#task-hooks)

---

## View Hooks（檢視 Hook）

檢視 Hook 用來在範本的特定位置插入自訂的 HTML 或內容片段。

### 可用的檢視 Hook 點
- `view_layouts_base_html_head`: 在 `<head>` 區塊插入內容
- `view_layouts_base_content_top`: 在頁面內容上方插入
- `view_layouts_base_content_bottom`: 在頁面內容下方插入
- `view_layouts_base_body_bottom`: 在 `</body>` 前插入

### 範例：在所有頁面插入自訂 CSS

```python
class MyPlugin(ViewPlugin):
    def __init__(self, app, url_prefix=None):
        super().__init__(app, url_prefix)
        self.app.hook_manager.register_hook(
            "view_layouts_base_html_head",
            self._inject_custom_css,
            priority=10,
            plugin_name=self.name
        )

    def _inject_custom_css(self, context) -> str:
        return '''
        <style>
            .my-custom-class {
                background-color: #f0f0f0;
            }
        </style>
        '''
```

### 範例：在頁面頂部顯示橫幅（Banner）

```python
def _show_banner(self, context) -> str:
    user = context.get('current_user')
    if user and user.is_admin:
        return '''
        <div class="alert alert-info" role="alert">
            管理員模式：您正以管理員權限瀏覽此頁面
        </div>
        '''
    return ""

# 註冊
self.app.hook_manager.register_hook(
    "view_layouts_base_content_top",
    self._show_banner,
    priority=5,
    plugin_name=self.name
)
```

---

## Controller Hooks（控制器 Hook）

控制器 Hook 用於在請求處理流程中插入自訂邏輯或處理流程前後的動作。

### 可用的控制器 Hook 點
- `controller_before_request`: 在處理請求前執行
- `controller_after_request`: 在處理請求後、回傳回應前執行
- `controller_error_handler`: 發生錯誤時執行

### 範例：請求日誌記錄

```python
def _log_request(self, context) -> None:
    request = context.get('request')
    user = context.get('current_user')

    self.mylogger.info(
        f"Request: {request.method} {request.path} "
        f"User: {user.username if user and user.is_authenticated else 'Anonymous'}"
    )

# 註冊
self.app.hook_manager.register_hook(
    "controller_before_request",
    self._log_request,
    priority=10,
    plugin_name=self.name
)
```

### 範例：添加自訂回應標頭

```python
def _add_custom_headers(self, context) -> None:
    response = context.get('response')
    if response:
        response.headers['X-Custom-Plugin'] = 'MyPlugin'
        response.headers['X-Process-Time'] = str(time.time() - context.get('start_time', time.time()))

# 註冊
self.app.hook_manager.register_hook(
    "controller_after_request",
    self._add_custom_headers,
    priority=10,
    plugin_name=self.name
)
```

### 範例：錯誤通知

```python
def _notify_error(self, context) -> None:
    error = context.get('error')
    request = context.get('request')

    # 發送錯誤通知給管理員
    self.mylogger.error(
        f"Error occurred: {error} "
        f"Path: {request.path} "
        f"Method: {request.method}"
    )

    # 可以在這裡添加發送郵件或 Slack 通知的邏輯

# 註冊
self.app.hook_manager.register_hook(
    "controller_error_handler",
    self._notify_error,
    priority=10,
    plugin_name=self.name
)
```

---

## Plugin Lifecycle Hooks（插件生命週期 Hook）

插件生命週期 Hook 用於在 Plugin 啟動、停止或重載等生命週期事件時執行自訂邏輯。

### 可用的生命週期 Hook 點
- `plugin_before_start`: Plugin 啟動前
- `plugin_after_start`: Plugin 啟動後
- `plugin_before_stop`: Plugin 停止前
- `plugin_after_stop`: Plugin 停止後
- `plugin_before_reload`: Plugin 重載前
- `plugin_after_reload`: Plugin 重載後

### 範例：記錄 Plugin 生命週期

```python
def _log_lifecycle(self, context) -> None:
    plugin = context.get('plugin')
    plugin_name = context.get('plugin_name', 'Unknown')

    self.mylogger.info(f"Plugin lifecycle event: {plugin_name}")

# 註冊所有生命週期 hooks
for hook_name in ['plugin_before_start', 'plugin_after_start',
                  'plugin_before_stop', 'plugin_after_stop',
                  'plugin_before_reload', 'plugin_after_reload']:
    self.app.hook_manager.register_hook(
        hook_name,
        self._log_lifecycle,
        priority=10,
        plugin_name=self.name
    )
```

### 範例：在其他 Plugin 啟動後執行初始化

```python
def _init_after_dependency(self, context) -> None:
    plugin_name = context.get('plugin_name')

    # 等待某個依賴的 Plugin 啟動後才執行初始化
    if plugin_name == 'AuthView':
        self.mylogger.info("AuthView started, initializing dependent features...")
        self._setup_auth_integration()

# 註冊
self.app.hook_manager.register_hook(
    "plugin_after_start",
    self._init_after_dependency,
    priority=10,
    plugin_name=self.name
)
```

---

## Model Hooks（模型 Hook）

模型 Hook 用於在資料庫操作（如儲存、刪除）時插入自訂邏輯。

### 可用的模型 Hook 點
- `model_before_save`: 在儲存資料前執行
- `model_after_save`: 在儲存資料後執行
- `model_after_create`: 在首次建立資料後執行
- `model_before_delete`: 在刪除資料前執行
- `model_after_delete`: 在刪除資料後執行

### 方式一：使用 ModelHookMixin

```python
from funlab.core.model_hook import ModelHookMixin
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(ModelHookMixin, Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)

# 使用方式
user = User(username='john', email='john@example.com')
user.save(session, app)  # 會觸發 model_before_save 和 model_after_save hooks
```

### 方式二：使用 register_model_events

```python
from funlab.core.model_hook import register_model_events

# 為既有的 Model 註冊事件監聽
register_model_events(app, User)

# 之後的所有操作都會自動觸發 hooks
user = User(username='jane', email='jane@example.com')
session.add(user)
session.commit()  # 自動觸發 hooks
```

### 範例：資料變更審計日誌

```python
def _audit_model_changes(self, context) -> None:
    model = context.get('model')
    model_class = context.get('model_class')
    is_new = context.get('is_new', False)

    # 記錄到審計日誌
    audit_log = {
        'model': model_class.__name__,
        'operation': 'create' if is_new else 'update',
        'timestamp': datetime.now(),
        'user': current_user.username if current_user.is_authenticated else 'System'
    }

    self.mylogger.info(f"Audit: {audit_log}")

# 註冊
self.app.hook_manager.register_hook(
    "model_after_save",
    self._audit_model_changes,
    priority=10,
    plugin_name=self.name
)
```

### 範例：資料驗證

```python
def _validate_before_save(self, context) -> None:
    model = context.get('model')
    model_class = context.get('model_class')

    # 自訂驗證邏輯
    if model_class.__name__ == 'Stock' and hasattr(model, 'price'):
        if model.price < 0:
            raise ValueError("Stock price cannot be negative")

# 註冊
self.app.hook_manager.register_hook(
    "model_before_save",
    self._validate_before_save,
    priority=10,
    plugin_name=self.name
)
```

---

## Task Hooks（任務 Hook）

任務 Hook 用於在排程或背景任務執行時觸發自訂處理邏輯。

### 可用的任務 Hook 點
- `task_before_execute`: 任務執行前
- `task_after_execute`: 任務執行後
- `task_error`: 任務發生錯誤時

### 範例：任務執行時間記錄

```python
def _record_task_timing(self, context) -> None:
    task_name = context.get('task_name')
    args = context.get('args', ())
    kwargs = context.get('kwargs', {})

    # 記錄開始時間
    context['start_time'] = time.time()
    self.mylogger.info(f"Task {task_name} starting with args={args}, kwargs={kwargs}")

def _log_task_completion(self, context) -> None:
    task_name = context.get('task_name')
    result = context.get('result')
    start_time = context.get('start_time', time.time())

    duration = time.time() - start_time
    self.mylogger.info(f"Task {task_name} completed in {duration:.2f}s, result={result}")

# 註冊
self.app.hook_manager.register_hook(
    "task_before_execute",
    self._record_task_timing,
    priority=10,
    plugin_name=self.name
)

self.app.hook_manager.register_hook(
    "task_after_execute",
    self._log_task_completion,
    priority=10,
    plugin_name=self.name
)
```

### 範例：任務失敗通知

```python
def _notify_task_error(self, context) -> None:
    task_name = context.get('task_name')
    error = context.get('error')
    args = context.get('args', ())
    kwargs = context.get('kwargs', {})

    # 發送錯誤通知
    message = f"任務 {task_name} 執行失敗: {error}"
    self.mylogger.error(message)

    # 可以在這裡添加發送通知到 Slack、Email 或系統通知的邏輯
    if hasattr(self.app, 'send_user_system_notification'):
        self.app.send_user_system_notification(
            title=f"任務失敗: {task_name}",
            message=str(error),
            target_userid=None  # 發送給所有管理員
        )

# 註冊
self.app.hook_manager.register_hook(
    "task_error",
    self._notify_task_error,
    priority=10,
    plugin_name=self.name
)
```

### 範例：任務執行統計

```python
class TaskStatsPlugin(ViewPlugin):
    def __init__(self, app, url_prefix=None):
        super().__init__(app, url_prefix)
        self.task_stats = {}
        self._register_hooks()

    def _register_hooks(self):
        self.app.hook_manager.register_hook(
            "task_after_execute",
            self._collect_stats,
            priority=10,
            plugin_name=self.name
        )

        self.app.hook_manager.register_hook(
            "task_error",
            self._collect_error_stats,
            priority=10,
            plugin_name=self.name
        )

    def _collect_stats(self, context):
        task_name = context.get('task_name')

        if task_name not in self.task_stats:
            self.task_stats[task_name] = {
                'success_count': 0,
                'error_count': 0,
                'total_time': 0
            }

        start_time = context.get('start_time', 0)
        duration = time.time() - start_time if start_time else 0

        self.task_stats[task_name]['success_count'] += 1
        self.task_stats[task_name]['total_time'] += duration

    def _collect_error_stats(self, context):
        task_name = context.get('task_name')

        if task_name not in self.task_stats:
            self.task_stats[task_name] = {
                'success_count': 0,
                'error_count': 0,
                'total_time': 0
            }

        self.task_stats[task_name]['error_count'] += 1

    def get_stats(self, task_name=None):
        """取得任務統計資料"""
        if task_name:
            return self.task_stats.get(task_name, {})
        return self.task_stats
```

---

## Hook 優先順序

Hook 的執行順序由 `priority` 參數決定，數字越小代表優先權越高（越先執行）。範例：

```python
# priority=1：最高優先權（最先執行）
self.app.hook_manager.register_hook(
    "controller_before_request",
    self._early_hook,
    priority=1,
    plugin_name=self.name
)

# priority=10：一般優先權
self.app.hook_manager.register_hook(
    "controller_before_request",
    self._normal_hook,
    priority=10,
    plugin_name=self.name
)

# priority=100：最低優先權（最後執行）
self.app.hook_manager.register_hook(
    "controller_before_request",
    self._late_hook,
    priority=100,
    plugin_name=self.name
)
```

---

## 除錯技巧

### 檢視已註冊的 Hooks

```python
# 在 Plugin 中檢視特定 hook 點的所有註冊
hooks = self.app.hook_manager._hooks.get('controller_before_request', [])
print(f"Registered hooks: {len(hooks)}")
for hook in hooks:
    print(f"  - {hook['plugin_name']}: {hook['callback'].__name__} (priority={hook['priority']})")
```

### Hook 錯誤隔離

HookManager 會自動隔離 hook 執行中的錯誤：單一 hook 發生例外不會影響其他 hooks 或主要流程。

```python
def _risky_hook(self, context):
    # 即使這裡拋出例外，也不會影響其他 hooks
    raise Exception("Something went wrong")

# 註冊該風險較高的 hook（失敗不會中斷後續處理）
self.app.hook_manager.register_hook(
    "controller_before_request",
    self._risky_hook,
    priority=10,
    plugin_name=self.name
)
```

---

## 最佳實務

- **命名規範**: Hook callback 方法建議使用 `_hookname_action` 格式，例如 `_before_request_log`。
- **優先權**: 建議使用標準優先權值（例如 1 = 最高、10 = 一般、100 = 最低）。
- **錯誤處理**: 在 hook 內部處理可預期的錯誤，避免將例外往外丟出以中斷流程。
- **效能考量**: 檢視（View）hooks 會在每次頁面渲染時執行，應避免放入耗時作業。
- **Context 使用**: 優先以唯讀方式存取 `context`，除非是 before-hook 且有明確需求才修改。
- **日誌記錄**: 使用適當的日誌等級（例如 DEBUG 詳細資訊，INFO 重要事件）。

---

## 參考資料

- [Hook 重構計劃](hook_refactor_plan.md)
- [HookManager 實作](../../funlab-libs/funlab/core/hook.py)
- [HookTestView 測試外掛](../../funlab-flaskr/funlab/flaskr/hook_test_plugin.py)
