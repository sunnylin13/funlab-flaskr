# funlab-flaskr

Flask 應用程式基礎框架，提供 Plugin 系統整合、路由管理、SSE、身份驗證整合等功能。

## 啟動順序

1. create_app() — 建立 Flask 應用實例
2. PluginManager 載入 — 依 pyproject.toml 的 [tool.finfun.plugins] 配置探索並載入 Plugin
3. 各 Plugin 的 setup(app) 依拓撲順序呼叫（PluginDependencyResolver 確保依賴先行）
4. Blueprint 在 Plugin setup 中使用 pp.register_blueprint(...) 注冊
5. 排程 Plugin（unlab-sched）在最後啟動，確保 DB / SSE 已就緒
6. pp.run() / WSGI server 啟動

## Plugin 整合點

| Plugin | 整合方式 |
|---|---|
| unlab-auth | Blueprint /auth；login_required decorator |
| unlab-sched | APScheduler；依賴 unlab-flaskr PluginManager |
| unlab-sse | SSE endpoint /sse；需 unlab-flaskr event bus |
| 業務 Plugin | 在 setup() 中 pp.register_blueprint(...) |

## 設計規範

- 所有路由集中在各 Plugin Blueprint，flaskr 不直接持有業務路由。
- Plugin 依賴透過 PluginManager.register_dependency() 宣告，避免循環初始化。
- 環境設定透過 unlab.utils.load_config 統一載入，支援 .toml / .yaml。

## 待實作（Wave 2）

- T-flaskr-001：PluginManager 整合（依賴 T-libs-003，已完成）
- T-flaskr-003：Plugin 整合點集中化（目前各 Plugin 自行 register_blueprint，需統一）
