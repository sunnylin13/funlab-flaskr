# Funlab-Flaskr Web UI 架構指南

## 目錄
- [I. 整體架構概覽](#i-整體架構概覽)
- [II. 模板系統運作細部](#ii-模板系統運作細部)
- [III. 實作案例分析](#iii-實作案例分析)
- [IV. 獨立頁面實作指南](#iv-獨立頁面實作指南)
- [V. 優缺點評估](#v-優缺點評估)

---

## I. 整體架構概覽

### 1.1 分層架構

```
┌─────────────────────────────────────────────────┐
│         Flask Application (funlab-flaskr)        │
├─────────────────────────────────────────────────┤
│  1. Routes & Views (view.py / app.py)            │
│     - Define URL endpoints                       │
│     - Handle GET/POST requests                   │
│     - Perform business logic                     │
├─────────────────────────────────────────────────┤
│  2. Forms (form.py)                              │
│     - Flask-WTF form definitions                 │
│     - Validation rules                          │
│     - Dynamic field handling                    │
├─────────────────────────────────────────────────┤
│  3. Templates (templates/)                       │
│     - Jinja2 template engine                     │
│     - Template inheritance (base.html)           │
│     - Block-based content composition            │
├─────────────────────────────────────────────────┤
│  4. Static Assets (static/)                      │
│     - CSS (Tabler design system)                 │
│     - JavaScript (Vanilla + Recharts)            │
│     - Images & icons                            │
├─────────────────────────────────────────────────┤
│  5. Plugin System (ViewPlugin base class)        │
│     - Plugin loading mechanism                   │
│     - Route registration                        │
│     - Menu integration                          │
└─────────────────────────────────────────────────┘
```

### 1.2 技術棧

| 層級 | 技術 | 版本 | 用途 |
|------|--------|--------|----------|
| **後端 Framework** | Flask | ^3.0.0 | Web application framework |
| **模板引擎** | Jinja2 | Built-in | HTML template rendering |
| **表單庫** | Flask-WTF | ^1.0+ | Form generation & validation |
| **認證** | Flask-Login | ^0.6.3 | User authentication |
| **ORM** | SQLAlchemy | Via funlab-libs | Database abstraction |
| **UI Framework** | Tabler | v1.0.0-beta19 | Bootstrap-based dashboard |
| **圖表庫** | Recharts | React library | Interactive charts |
| **前端** | Vanilla JS | - | Dynamic interactions |

---

## II. 模板系統運作細部

### 2.1 模板繼承結構

```
layouts/base.html [主基礎模板]
   ├── block stylesheets       [頁面特定 CSS]
   ├── block page_header       [頁面標題區]
   ├── block page_body         [主要內容區]
   ├── block page_footer       [頁面底部]
   ├── block modal_dialog      [模態框]
   └── block javascripts       [頁面特定 JS]
         │
         └── includes/
              ├── banner.html              [頂部導航欄]
              ├── banner_scripts.html      [導航 JS]
              ├── scripts.html             [全局 JS 資源]
              └── footer.html              [頁腳]
```

### 2.2 Base.html 模板流程

```html
<!DOCTYPE html>
<html>
  <head>
    <!-- 1. 靜態 CSS 資源 (Tabler + 自定義) -->
    <link href="/static/dist/css/tabler.min.css" rel="stylesheet" />

    <!-- 2. 頁面特定 CSS -->
    {% block stylesheets %}{% endblock %}

    <!-- 3. Hook 系統 -->
    {{ call_hook('view_layouts_base_html_head') }}
  </head>
  <body>
    <div class="page">
      <!-- 3. 主菜單 (條件渲染) -->
      {% if layout=='vertical' %}
        {{ g.mainmenu|safe }}
      {% endif %}

      <!-- 4. 導航欄 -->
      {% block banner %}
        {% include config.BANNER_PAGE | default('includes/banner.html') %}
      {% endblock %}

      <div class="page-wrapper">
        <!-- 5. 頁面標題 -->
        {% block page_header %}{% endblock %}

        <!-- 6. 主要內容 -->
        <div class="page-body">
          {{ call_hook('view_layouts_base_content_top') }}
          {% block page_body %}{% endblock %}
          {{ call_hook('view_layouts_base_content_bottom') }}

          <!-- 7. Flash 消息 -->
          {% for category, message in get_flashed_messages(with_categories=true) %}
            <div class="alert alert-{{ category }}">{{ message }}</div>
          {% endfor %}
        </div>

        <!-- 8. 頁腳 -->
        {% block page_footer %}
          {% include config.FOOTER_PAGE | default('includes/footer.html') %}
        {% endblock %}
      </div>
    </div>

    <!-- 9. 全局 JS 資源 -->
    {% include 'includes/scripts.html' %}

    <!-- 10. 頁面特定 JS -->
    {% block javascripts %}{% endblock %}

    <!-- 11. SSE 客戶端 (實時通知) -->
    {{ sse_client_script|safe }}

    <!-- 12. Hook 系統 (底部) -->
    {{ call_hook('view_layouts_base_body_bottom') }}
  </body>
</html>
```

### 2.3 關鍵模板特性

#### A. Jinja2 過濾器 (Filters)

```jinja2
{# 數值格式化 #}
{{ value|format_value }}

{# 日期格式化 #}
{{ date_obj|common_formatter }}

{# 百分比 #}
{{ 0.1234|format("%.2f") }}%

{# 默認值 #}
{{ value|default('N/A') }}

{# 安全 HTML 渲染 #}
{{ html_content|safe }}
```

#### B. 條件渲染

```jinja2
{# 基於用戶角色 #}
{% if current_user.role == 'supervisor' %}
  <div>全司管理選項</div>
{% elif current_user.role == 'manager' %}
  <div>個人投資組合</div>
{% endif %}

{# 基於認證狀態 #}
{% if current_user.is_authenticated %}
  歡迎 {{ current_user.username }}
{% else %}
  請登入
{% endif %}
```

#### C. 動態包含 (Dynamic Include)

```jinja2
{# 根據配置動態選擇 banner #}
{% with banner_page = config.BANNER_PAGE | default('includes/banner.html') %}
  {% include banner_page %}
{% endwith %}

{# 根據不同頁面切換 footer #}
{% block page_footer %}
  {% with footer_page = config.FOOTER_PAGE | default('includes/footer.html') %}
    {% include footer_page %}
  {% endwith %}
{% endblock %}
```

#### D. Hook 系統

```jinja2
{# Head 部分的 hook（用於注入自定義 CSS/Meta） #}
{{ call_hook('view_layouts_base_html_head') }}

{# 內容頂部 hook #}
{{ call_hook('view_layouts_base_content_top') }}

{# 內容底部 hook #}
{{ call_hook('view_layouts_base_content_bottom') }}

{# Body 底部 hook #}
{{ call_hook('view_layouts_base_body_bottom') }}
```

### 2.4 資料流向

```
Flask View (view.py)
    ↓ render_template(template_name, **context)
Jinja2 Template Engine
    ↓ (處理 blocks, loops, conditions, filters)
HTML 渲染
    ↓ (包含 CSS, JS 資源)
瀏覽器渲染
```

---

## III. 實作案例分析

### 3.1 Finfun-Fundmgr 實作架構

#### 3.1.1 Plugin View 基類

```python
from funlab.core.plugin import ViewPlugin
from flask import Blueprint, render_template

class FundMgrView(ViewPlugin):
    def __init__(self, app: FunlabFlask):
        super().__init__(app)
        # 1. 初始化 API namespace (Flask-RESTX)
        api: Api = Api(self.blueprint,
                      doc='swagger',
                      title='Fund Manager API',
                      version='1.0')
        self.api_namespace = Namespace('api')
        api.add_namespace(self.api_namespace)

        # 2. 註冊路由
        self.register_routes()

        # 3. 延遲初始化（在應用完全啟動後）
        @app.teardown_appcontext
        def init_subscriptions(error):
            if not hasattr(self, '_initialized'):
                self._initialize_subscriptions()
                self._initialized = True
```

#### 3.1.2 路由註冊 (Route Registration)

```python
def register_routes(self):
    # 1. 簡單路由
    @self.blueprint.route('/portfolio', methods=['GET', 'POST'])
    @login_required
    def portfolio(user_email: str = None):
        form = ManagersForm(request.form)

        # 處理表單提交
        if 'submit' in request.form:
            user_email = form.manager_email.data
            account_id = form.account.data
        else:
            user_email = current_user.email
            account_id = None

        # 從資料庫載入數據
        with self.app.dbmgr.session_context() as session:
            manager = load_user(user_email, sa_session=session)
            positions = manager.positions
            returnlog = manager.lastest_returnlog

        # 渲染模板，傳遞上下文
        return render_template('portfolio.html',
                             form=form,
                             manager=manager,
                             positions=positions)

    # 2. API 路由
    @self.api_namespace.route('/manager_accounts', methods=['GET', 'POST'])
    class ManagerAccounts(Resource):
        @login_required
        def get(self):
            manager_email = request.args.get('manager_email')
            accounts = load_manager_accounts(manager_email)
            return jsonify(accounts)

        @login_required
        def post(self):
            # POST 處理
            return self.get()
```

#### 3.1.3 表單處理 (Form Handling)

```python
# form.py
class ManagersForm(FlaskForm):
    manager_email = SelectField('Manager', choices=[], validators=[DataRequired()])
    account = SelectField('Account', choices=[])
    submit = SubmitField('查詢')

class PerformanceForm(FlaskForm):
    manager_email = SelectField('Portfolio', choices=[], validators=[DataRequired()])
    account = SelectField('Account', choices=[])
    fromdate = DateField('From', format="%Y-%m-%d")
    todate = DateField('To', format="%Y-%m-%d")
    submit = SubmitField('Performance Analysis')

# view.py - 使用者表單
form = ManagersForm(request.form)
if form.validate():  # 驗證表單
    user_email = form.manager_email.data
```

#### 3.1.4 動態表單欄位更新

```html
<!-- portfolio.html 中的 JavaScript -->
<script>
document.addEventListener('DOMContentLoaded', function () {
    var managerEmailSelect = document.getElementById('manager_email');
    var accountSelect = document.getElementById('account');

    managerEmailSelect.addEventListener('change', function () {
        var selectedEmail = managerEmailSelect.value;
        var xhr = new XMLHttpRequest();

        // 1. 發送 AJAX 請求到後端 API
        xhr.open('POST', "{{ url_for('fundmgr_bp.api_manager_accounts') }}", true);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');

        xhr.onreadystatechange = function () {
            if (xhr.readyState === 4 && xhr.status === 200) {
                // 2. 解析 JSON 回應
                var data = JSON.parse(xhr.responseText);

                // 3. 動態更新下拉選單
                accountSelect.innerHTML = '';
                var option = document.createElement('option');
                option.value = 'ALL';
                option.text = 'ALL';
                option.selected = true;
                accountSelect.appendChild(option);

                data.forEach(function (account) {
                    var option = document.createElement('option');
                    option.value = account[0];
                    option.text = account[1];
                    accountSelect.appendChild(option);
                });
            }
        };

        xhr.send('manager_email=' + encodeURIComponent(selectedEmail));
    });
});
</script>
```

### 3.1.5 複雜數據處理與渲染

```python
# view.py - Performance 頁面的變數處理
def portfolio():
    # 1. 提取複雜數據
    positions_view = []
    for pos in portfolio_target.positions:
        positions_view.append({
            'symbol': pos.symbol,
            'name': pos.name,
            'price': get_price(pos),  # 實時價格
            'return_rate': pos.return_rate,
            'portion': pos.portion,
            # ... 更多字段
        })

    # 2. 計算衍生數據
    implicit_cash = portfolio_target.implicit_cash
    implicit_exright_value = portfolio_target.implicit_exright_value

    # 3. 渲染到模板
    return render_template('portfolio.html',
                         positions=positions_view,
                         last_returnlog=last_returnlog,
                         implicit_cash=implicit_cash)
```

### 3.1.6 菜單整合

```python
def setup_menus(self):
    top_menu = Menu('Fund Mgr.', expand=True, icon='<svg>...</svg>')
    top_menu.append(menu=[
        MenuItem(title='Portfolio',
                href=f'/{self.name}/portfolio'),
        MenuItem(title='Performance',
                href=f'/{self.name}/performance'),
        MenuItem(title='Benchmark',
                href=f'/{self.name}/benchmark'),
        # ... 更多菜單項
    ])

    self.app.append_mainmenu(menus=top_menu)

    # 用戶菜單
    self.app.insert_usermenu(idx=0, menus=[
        MenuItem(title='Portfolio',
                href=f'/{self.name}/portfolio'),
        MenuItem(title='Broker Settings',
                href=f'/{self.name}/broker_settings')
    ])
```

### 3.2 頁面流程圖

```
portfolio.html (頁面初始化)
    ├─ {% extends "layouts/base.html" %}
    │   (繼承基礎模板)
    │
    ├─ {% block stylesheets %}
    │   (頁面特定 CSS)
    │
    ├─ {% block page_header %}
    │   <form> (ManagersForm)
    │   <script> (動態下拉選單)
    │
    ├─ {% block page_body %}
    │   <div class="page-body">
    │   ├─ <card> (投資組合摘要)
    │   ├─ <table> (持倉列表)
    │   └─ <datagrid> (統計數據)
    │
    └─ {% block javascripts %}
        多個外部 JS (Recharts 圖表, 數據刷新)
```

---

## IV. 獨立頁面實作指南

### 4.1 最小化範本 (Minimal Template)

#### Step 1: 定義頁面模板

**[yourmodule]/templates/mypage.html**

```html
{% extends "layouts/base.html" %}

{% block title %}{{ config.TITLE }} - My Page{% endblock %}

{# 頁面特定 CSS #}
{% block stylesheets %}
<style>
  .custom-card {
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }
</style>
{% endblock %}

{# 頁面標題區 #}
{% block page_header %}
<div class="container-xl">
  <div class="row g-2 align-items-center">
    <div class="col">
      <div class="page-pretitle">My Module</div>
      <h2 class="page-title">My Custom Page</h2>
    </div>
    <div class="col-auto ms-auto d-print-none">
      <a href="{{ url_for('mymodule_bp.another_page') }}" class="btn btn-primary">
        Other Page
      </a>
    </div>
  </div>
</div>
{% endblock %}

{# 主內容區 #}
{% block page_body %}
<div class="container-xl">
  <div class="row row-deck row-cards">
    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Content Title</h3>
        </div>
        <div class="card-body">
          <p>Your content goes here</p>
          {% if items %}
            <ul class="list-group">
            {% for item in items %}
              <li class="list-group-item">{{ item.name }}</li>
            {% endfor %}
            </ul>
          {% else %}
            <p class="text-muted">No items found</p>
          {% endif %}
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{# 頁面特定 JavaScript #}
{% block javascripts %}
<script>
  document.addEventListener('DOMContentLoaded', function() {
    console.log('Page loaded');
    // 初始化頁面邏輯
  });
</script>
{% endblock %}
```

#### Step 2: 定義 View 類

**[yourmodule]/view.py**

```python
from funlab.core.plugin import ViewPlugin
from flask import render_template, request, jsonify
from flask_login import login_required

class MyModuleView(ViewPlugin):
    def __init__(self, app):
        super().__init__(app)
        self.register_routes()
        self.setup_menus()

    def register_routes(self):
        """定義所有路由"""

        @self.blueprint.route('/')
        def index():
            """首頁重定向"""
            return redirect(url_for(f'{self.bp_name}.mypage'))

        @self.blueprint.route('/mypage')
        @login_required
        def mypage():
            """我的自定義頁面"""
            # 1. 業務邏輯：從資料庫或 API 獲取數據
            items = self._load_items()

            # 2. 將數據傳遞給模板
            return render_template('mypage.html',
                                 items=items)

        @self.blueprint.route('/api/items', methods=['GET', 'POST'])
        @login_required
        def api_items():
            """API 端點：返回 JSON 數據"""
            items = self._load_items()
            return jsonify([{'id': i.id, 'name': i.name} for i in items])

    def setup_menus(self):
        """設置菜單"""
        from funlab.core.menu import Menu, MenuItem

        menu = Menu('My Module', expand=True, icon='<svg>...</svg>')
        menu.append(menu=[
            MenuItem(title='My Page',
                    href=f'/{self.name}/mypage'),
            MenuItem(title='Another Page',
                    href=f'/{self.name}/another_page'),
        ])

        self.app.append_mainmenu(menus=menu)

    def _load_items(self):
        """內部方法：載入項目"""
        with self.app.dbmgr.session_context() as session:
            # 從資料庫查詢
            items = session.query(ItemEntity).filter(...).all()
            return items
```

#### Step 3: 註冊 Plugin

**[yourmodule]/__init__.py**

```python
from funlab.core.plugin import Plugin

class MyModule(Plugin):
    """My custom module plugin"""

    @staticmethod
    def get_view_class():
        """返回視圖類"""
        from .view import MyModuleView
        return MyModuleView

    @staticmethod
    def get_entities_registry():
        """返回資料庫實體（可選）"""
        return {}  # 或 entitites_registry
```

---

### 4.2 進階範本：含表單和動態交互

#### portfolio.html (進階範本)

```html
{% extends "layouts/base.html" %}

{% block stylesheets %}
<style>
  /* 自定義樣式 */
  .portfolio-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    border-radius: 8px;
  }

  .stat-card {
    background: white;
    padding: 20px;
    border-left: 4px solid #667eea;
  }
</style>
{% endblock %}

{% block page_header %}
<div class="container-xl">
  <div class="row">
    <div class="col">
      <h1>Portfolio Manager</h1>
    </div>
  </div>
</div>
{% endblock %}

{% block page_body %}
<div class="container-xl">
  {# 表單區 #}
  {% if form %}
  <div class="row mb-4">
    <div class="col">
      <form method="post">
        {{ form.hidden_tag() }}
        <div class="row">
          <div class="col-auto">
            {{ form.manager_email(class_="form-control") }}
          </div>
          <div class="col-auto">
            {{ form.account(class_="form-control") }}
          </div>
          <div class="col-auto">
            {{ form.submit(class_="btn btn-primary") }}
          </div>
        </div>
      </form>
    </div>
  </div>
  {% endif %}

  {# 統計卡片 #}
  <div class="row row-deck row-cards mb-4">
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="stat-card">
        <div class="d-flex align-items-center">
          <span class="h3 mb-0">{{ total_value | format_value }}</span>
        </div>
        <div class="text-muted">Total Value</div>
      </div>
    </div>
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="stat-card">
        <div class="d-flex align-items-center">
          <span class="h3 mb-0" style="color: {% if return_rate > 0 %}green{% else %}red{% endif %}">
            {{ return_rate | format("%.2f") }}%
          </span>
        </div>
        <div class="text-muted">Return Rate</div>
      </div>
    </div>
  </div>

  {# 表格區 #}
  <div class="row">
    <div class="col">
      <div class="card">
        <div class="table-responsive">
          <table class="table table-sm card-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Price</th>
                <th>Volume</th>
                <th>Value</th>
                <th>Return %</th>
              </tr>
            </thead>
            <tbody>
            {% for pos in positions %}
              <tr>
                <td><strong>{{ pos.symbol }}</strong></td>
                <td>{{ pos.price | format("%.2f") }}</td>
                <td>{{ pos.volume }}</td>
                <td>${{ pos.value | format("%.2f") }}</td>
                <td>
                  <span class="badge {% if pos.return_rate > 0 %}bg-success{% else %}bg-danger{% endif %}">
                    {{ pos.return_rate | format("%.2f") }}%
                  </span>
                </td>
              </tr>
            {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block javascripts %}
<script>
// 動態聯動選擇框
document.querySelectorAll('select').forEach(select => {
  select.addEventListener('change', function() {
    console.log('Selection changed:', this.value);
  });
});

// 數據刷新
function refreshData() {
  fetch('/api/portfolio-data')
    .then(r => r.json())
    .then(data => {
      console.log('Data updated:', data);
      // 更新頁面
    });
}

// 自動刷新（每 30 秒）
setInterval(refreshData, 30000);
</script>
{% endblock %}
```

---

### 4.3 頁面架構對比

#### A. 簡單頁面結構

```
Simple Page
├── Header (標題)
├── Content (靜態內容或簡單列表)
└── Footer
```

**適用場景**: 展示頁面、說明文件、關於頁面

#### B. 表單頁面結構

```
Form Page
├── Header (標題)
├── Form (輸入表單)
├── Content (根據表單結果顯示)
└── Scripts (動態表單行為)
```

**適用場景**: 設置頁面、配置頁面、搜尋頁面

#### C. 儀表板頁面結構

```
Dashboard Page
├── Header (標題 + 篩選)
├── Stats Cards (統計卡片)
├── Charts (圖表)
├── Tables (數據表)
└── Scripts (數據刷新, AJAX)
```

**適用場景**: Portfolio、Performance、Analytics

#### D. 複合頁面結構

```
Complex Page
├── Header (標題 + 篩選表單)
├── Tabs/Navigation (導航)
├── Content Area (多個 block)
│  ├── Overview (摘要)
│  ├── Details (詳情)
│  └── Actions (操作)
├── Charts (可互動圖表)
└── Scripts (SSE, WebSocket, 實時更新)
```

**適用場景**: Portfolio、Manager Settings、Advanced Analytics

---

## V. 優缺點評估

### 5.1 優點

#### ✅ 優點 1: 高度可組合的模板系統

**優勢**:
- Block 繼承使頁面復用率高
- 易於維護一致的頁面設計
- 頁面特定內容與基礎模板完全分離

**範例**:
```html
{# 基礎模板定義了頁面結構 #}
base.html: banner + page_header + page_body + footer

{# 具體頁面只需覆蓋需要的 block #}
portfolio.html: 只覆蓋 page_header 和 page_body
performance.html: 只覆蓋 page_header, page_body, javascripts
```

#### ✅ 優點 2: 完整的插件架構

**優勢**:
- Plugin 機制支援模塊化開發
- ViewPlugin 基類提供統一的初始化流程
- 易於在運行時動態加載插件

**實現機制**:
```python
# Plugin 自動註冊路由、菜單、資料庫實體
class FundMgrView(ViewPlugin):
    def __init__(self, app):
        super().__init__(app)
        self.register_routes()      # 自動註冊藍圖
        self.setup_menus()          # 整合到主菜單
        # 資料庫實體通過 entities_registry 自動建表
```

#### ✅ 優點 3: 靈活的表單處理

**優勢**:
- Flask-WTF 提供驗證和安全性
- CSRF 保護自動啟用
- 表單字段可動態生成

**方案**:
```python
# 動態選擇框
form.manager_email = SelectField(choices=get_managers())
form.account = SelectField(choices=[])  # 通過 AJAX 動態加載

# 前端動態更新
xhr.open('POST', '/api/manager_accounts')
```

#### ✅ 優點 4: 豐富的前端生態

**優勢**:
- Tabler 提供專業的 UI 組件
- Recharts 支援複雜的互動圖表
- SSE 實現實時推送通知

**整合範例**:
```html
{# Tabler 卡片 #}
<div class="card">
  <div class="card-body">...</div>
</div>

{# Recharts 圖表 #}
<div id="chart-container"></div>  {# 由 JS 初始化 #}

{# SSE 實時推送 #}
{{ sse_client_script|safe }}
```

#### ✅ 優點 5: Hook 系統的可擴展性

**優勢**:
- 無需修改核心代碼即可擴展功能
- 多個 Plugin 可同時註冊同一 Hook
- 支援優先級管理

**使用場景**:
```python
# Plugin A 在 head 中註冊自定義 CSS
app.hook_manager.register_hook('view_layouts_base_html_head',
                              lambda: '<link href="..."></link>',
                              priority=10)

# Plugin B 在 body 底部註冊 Script
app.hook_manager.register_hook('view_layouts_base_body_bottom',
                              lambda: '<script>...</script>',
                              priority=5)
```

#### ✅ 優點 6: 多使用者支援

**優勢**:
- Flask-Login 內建多使用者認證
- 角色基礎的視圖控制 (@admin_required, @login_required)
- 用戶特定的數據存儲

**實現**:
```python
@blueprint.route('/admin')
@admin_required  # 只有管理員可訪問
def admin_panel():
    return render_template('admin.html')

# 用戶數據隔離
user_data_path = app.get_user_data_storage_path(current_user.username)
```

---

### 5.2 缺點

#### ❌ 缺點 1: 前後端耦合度高

**問題**:
- HTML 渲染完全在服務器端進行
- 無法實現單頁應用 (SPA) 的無刷新用戶體驗
- 頁面交互需要回到服務器

**影響**:
```html
{# 用戶選擇下拉框，需要回到服務器 #}
managerEmailSelect.addEventListener('change', function() {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/manager_accounts', true);
  // ... 需要等待服務器響應
});
```

**解決方案**:
- 使用 AJAX 減少頁面刷新
- 引入前端框架 (Vue.js/React) 進行前後端分離
- 採用混合架構 (e.g., Flask 後端 + React 前端)

#### ❌ 缺點 2: 複雜頁面的 JavaScript 管理

**問題**:
- Vanilla JS 編寫複雜邏輯時容易混亂
- 無模塊化、無包管理
- 難以維護大量 JavaScript 代碼

**實例**:
```javascript
// portfolio.html 中有動態表單、圖表初始化、數據刷新等
// 所有邏輯混在一個 <script> 標籤中
document.addEventListener('DOMContentLoaded', function() {
  // 形成邏輯混亂
  initForm();
  initChart();
  startDataRefresh();
});
```

**解決方案**:
- 模塊化 JavaScript (使用 webpack/vite)
- 引入 TypeScript 增加類型安全
- 使用 Recharts React 組件而非原生 JavaScript

#### ❌ 缺點 3: 移動端適配挑戰

**問題**:
- Tabler 是為桌面優化的
- 複雜表格在手機上難以展示
- 需要額外的響應式設計工作

**範例**:
```html
{# 寬表格在手機上無法正常顯示 #}
<table class="table-responsive">
  <tr>
    <th>Symbol</th><th>Price</th><th>Volume</th>
    <th>Return</th><th>Action</th>
  </tr>
</table>
```

**解決方案**:
- 使用 Bootstrap 的 `table-responsive` 類
- 為移動端設計不同的視圖
- 考慮使用 React Native 開發移動應用

#### ❌ 缺點 4: 性能優化限制

**問題**:
- 每個頁面刷新都需要重新渲染整個 HTML
- 大量數據列表渲染時性能下降
- 無內置懶加載機制

**性能指標**:
```
頁面加載時間: 500ms - 2s (取決於數據量)
首屏加載: 需要等待服務器完整渲染
```

**解決方案**:
- 實現分頁/虛擬滾動
- 使用 CDN 加速靜態資源
- 實現客戶端緩存策略

#### ❌ 缺點 5: 實時性不足

**問題**:
- SSE 實現单向推送（服務器 → 客戶端）
- 無法支援雙向實時通信
- 遇到高延遲時用戶體驗差

**限制**:
```javascript
// SSE 只能單向推送
eventSource.onmessage = function(event) {
  console.log('Received:', event.data);  // 被動接收
};

// 無法實現即時的實時編輯、協作等
```

**解決方案**:
- 升級到 WebSocket 支援雙向通信
- 使用 Socket.IO 或 Django-Channels
- 引入消息隊列 (Redis, RabbitMQ) 進行實時事件分發

#### ❌ 缺點 6: 測試複雜度高

**問題**:
- 集成測試需要測試完整的渲染流程
- 前端測試涉及 DOM 操作和 JavaScript

**測試覆蓋**:
```python
# 需要測試模板渲染、表單驗證、數據傳遞
def test_portfolio_page():
    response = client.get('/fundmgr/portfolio')
    assert response.status_code == 200
    assert b'Portfolio' in response.data
    # 還需要檢查 context 中的數據
    assert 'positions' in response.context
```

**解決方案**:
- 分離業務邏輯和視圖
- 使用 pytest-flask 進行集成測試
- 前端邏輯單元測試使用 Jest/Mocha

---

### 5.3 架構選擇對比表

| 特性 | 傳統 Jinja2 | 前後端分離 | 混合架構 |
|------|-----------|----------|--------|
| **開發速度** | ⭐⭐⭐⭐ 快 | ⭐⭐ 慢 | ⭐⭐⭐ 中等 |
| **頁面加載速度** | ⭐⭐ 中 | ⭐⭐⭐⭐ 快 | ⭐⭐⭐ 中等 |
| **代碼維護性** | ⭐⭐⭐ 中 | ⭐⭐⭐⭐ 高 | ⭐⭐⭐⭐ 高 |
| **實時性能力** | ⭐ 弱 | ⭐⭐⭐⭐⭐ 強 | ⭐⭐⭐⭐ 強 |
| **學習曲線** | ⭐⭐⭐⭐ 低 | ⭐ 高 | ⭐⭐ 中等 |
| **移動端支援** | ⭐⭐ 差 | ⭐⭐⭐⭐⭐ 優 | ⭐⭐⭐⭐ 優 |
| **SEO 友好** | ⭐⭐⭐⭐⭐ 優 | ⭐⭐ 差 | ⭐⭐⭐ 中等 |
| **伺服器成本** | ⭐⭐⭐⭐ 低 | ⭐⭐⭐ 中 | ⭐⭐⭐ 中 |

---

### 5.4 優化建議

#### Level 1: 改進現有架構（短期）

```python
# 1. 優化模板繼承，減少代碼重複
# 創建更多中間層模板
# dashboard.html (針對儀表板頁面)
# table-page.html (針對表格頁面)

# 2. 實現客戶端快取
@app.after_request
def add_cache_headers(response):
    response.cache_control.max_age = 3600
    return response

# 3. 使用 Redis 緩存頻繁查詢
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'redis'})

@app.route('/portfolio')
@cache.cached(timeout=300)  # 5 分鐘緩存
def portfolio():
    ...
```

#### Level 2: 前後端分離（中期）

```
架構變化:
Flask (僅 API) → Swagger/OpenAPI
React/Vue 前端 → 負責 UI 渲染

benefits:
- 前後端獨立開發
- API 可被多個客戶端使用
- 實時性提升
```

#### Level 3: 微服務架構（長期）

```
Flask (整體應用)
    ↓ 演進為
├─ Flask API Gateway
├─ Portfolio Service
├─ Performance Service
├─ Quote Service
├─ Redis (實時數據)
├─ PostgreSQL (持久化)
└─ WebSocket Server (實時推送)
```

---

## 總結

### 最適合的使用場景

✅ **傳統 Jinja2 模板（現有架構）適合**:
- 中小型企業應用
- 內部管理系統
- 快速原型開發
- SEO 重要的站點
- 開發團隊規模小但需要快速迭代

❌ **不適合**:
- 高並發實時應用
- 複雜的前端交互（如實時協作編輯）
- 需要原生移動應用支援
- 超大規模應用

### 推薦的混合方案

```
Flask 後端
├─ 傳統頁面 (Jinja2 模板)
│  └─ 簡單的管理頁面、列表、表單
│
├─ API 端點 (JSON 響應)
│  └─ 複雜交互的 React 組件使用
│
└─ WebSocket 端點
   └─ 實時推送通知和數據更新
```

這種混合方案既保留了傳統架構的優勢，又無需完全重寫整個應用。

---

## 附錄：快速參考

### A. 常用 Jinja2 過濾器

```jinja2
{# 字符串 #}
{{ value|upper }}
{{ value|lower }}
{{ value|title }}
{{ value|truncate(10, '...') }}

{# 列表 #}
{{ items|length }}
{{ items|first }}
{{ items|last }}
{{ items|join(', ') }}

{# 數值 #}
{{ value|int }}
{{ value|float }}
{{ value|round(2) }}

{# 日期 #}
{{ date|strftime('%Y-%m-%d') }}

{# 自定義 #}
{{ value|custom_formatter }}
```

### B. 常用 Tabler CSS 類

```html
{# 容器 #}
<div class="container-xl">      {# 最大寬度容器 #}
<div class="container-fluid">   {# 全寬容器 #}

{# 網格 #}
<div class="row">
  <div class="col-12">           {# 全寬 #}
  <div class="col-6">            {# 50% #}
  <div class="col-lg-3">         {# 大屏 25% #}

{# 卡片 #}
<div class="card">
  <div class="card-header">
  <div class="card-body">
  <div class="card-footer">

{# 按鈕 #}
<button class="btn btn-primary">Primary</button>
<button class="btn btn-secondary">Secondary</button>
<button class="btn btn-danger">Danger</button>

{# 警告 #}
<div class="alert alert-info">Info</div>
<div class="alert alert-success">Success</div>
<div class="alert alert-danger">Danger</div>
```

### C. 建立新頁面的檢查清單

```
☐ 1. 創建 templates/mypage.html
     ☐ 繼承 layouts/base.html
     ☐ 定義 block page_header
     ☐ 定義 block page_body
     ☐ 定義 block stylesheets (如需)
     ☐ 定義 block javascripts (如需)

☐ 2. 在 view.py 中定義路由
     ☐ 使用 @blueprint.route()
     ☐ 添加 @login_required（如需）
     ☐ 從資料庫載入數據
     ☐ 使用 render_template() 返回模板

☐ 3. 可選：創建表單類 (form.py)
     ☐ 继承 FlaskForm
     ☐ 定義字段和驗證器
     ☐ 在 view 中使用表單

☐ 4. 可選：添加菜單項
     ☐ 在 setup_menus() 中添加 MenuItem
     ☐ 設置正確的 href URL

☐ 5. 測試
     ☐ 瀏覽器打開頁面
     ☐ 檢查樣式和佈局
     ☐ 測試表單提交
     ☐ 檢查權限控制
```

