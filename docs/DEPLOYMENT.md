# funlab-flaskr 部署指南（現況版）

> 2026-09-27 依 `funlab/flaskr/app.py:start_server`、`conf/*.py`、正式 systemd unit 實態重寫。

## 1. 啟動鏈

```
systemd user unit: fund13-web.service
  WorkingDirectory = ~/workspaces/fund13/finfun
  ExecStart = <workspace>/.venv/bin/python run.py
  finfun/run.py → funlab.flaskr.app.create_app(config.toml, .env) → start_server(app)
```

`create_app()` 依 config 的 `ENV` 選擇 `[ENV.X]` 節展開為 app config（finfun 用 `{{ENV.PRODUCTION}}`＋`SECRET_KEY='{{ENV_VAR:SECRET_KEY}}'`，金鑰值在 gitignored 的 `.env`）。

## 2. 三種 WSGI 模式（start_server 實際行為）

| `WSGI=` | 伺服器 | 參數來源 | 現況 |
|---|---|---|---|
| `waitress` | `waitress.serve` | `conf/waitress_conf.py`（threads=cpu*2+1、backlog、channel_timeout=60、connection_limit=1000…）＋ config 的 HOST/PORT 覆蓋 | **正式機採用**（fund13-web.service，埠 5000） |
| `gunicorn` | 行程內 `WSGIApplication` 子類 | `conf/gunicorn_conf.py`（workers=cpu*2+1、worker_class=gevent、timeout=30…）＋ `bind=HOST:PORT` | **目前不可用**：`logging` 未匯入 → NameError（IMPROVEMENT_PLAN FLK-04）；且 venv 未裝 gunicorn。修復前勿設定 |
| `flask`（預設） | Flask 內建 dev server | `app.run(port=PORT, use_reloader=False)`，log 寫 CWD 的 `./funlab.log` | 僅開發 |

HOST 規則：`HOST` 未設時 waitress/gunicorn 都預設 **0.0.0.0**（全部介面）。要限本機請在 config 的 `[ENV.X]` 設 `HOST='127.0.0.1'`，或在防火層擋外網。

`WSGI` 寫錯值 → `raise Exception('Not supported WSGI...')`，fail-fast，正確。

### 多 worker 注意事項（啟用 gunicorn 前必讀）

`conf/gunicorn_conf.py` 的 `workers = cpu_count()*2+1` 在 20 核機器＝41 個 gevent worker。本框架的排程（funlab-sched APScheduler）、通知 provider（PollingNotificationProvider 記憶體佇列）、prewarm 都是 **process-local** 狀態——多 worker 會造成排程重複執行與通知只送達單 worker。現行 waitress 單程序多线程正好規避。若要 gunicorn 化，先由 dev-arch 出「排程/SSE 狀態外置」設計，不要只調小 workers。

## 3. static 與使用者資料目錄（安全紅線）

- **app 層 `static_folder=None`**（`create_app()` 明確傳 None）。前端資源唯一來源是 root_bp 的 `Blueprint(static_folder='static')` → URL `/static/*`；各 plugin blueprint 有自己的 `/fs名/static/*`。
  - 教訓（勿回退）：舊值 `static_folder=""` 讓 Flask 把**套件根目錄**掛在 URL `/`，可匿名下載 `_users/*.pfx`、`conf/config.toml`、所有 `*.py`。防回歸測試：`tests/test_static_regression.py`（IMPROVEMENT_PLAN FLK-09）。
- **使用者資料**：`FunlabFlask.get_user_data_storage_path(username)` → `<套件根>/_users/<username小寫去空格>/`（券商憑證、ca 檔等；消費端：funlab-auth、fundmgr、quotesvcs）。紅線：
  1. 該目錄**永遠不得**位於任何 static_folder 之下；
  2. `.gitignore` 已擋 `*.pfx`、`*.p12`、`funlab/flaskr/_users/`——倉庫是 public，歷史中的憑證處置見 IMPROVEMENT_PLAN FLK-11（作廢重發優先）。

## 4. 安全要點清單

1. `SECRET_KEY` 必須釘選（config 直給或 `ENV_VAR:` 引用）。隨機金鑰時啟動會 log WARNING（ADR-016 D2/R3），CSRF/session 重啟即失效。
2. 全域 CSRFProtect：所有 POST/PUT/PATCH/DELETE 預設要 token；豁免只允許 flask-restx 唯讀 API 在構造期 `app.csrf.exempt`（ADR-016 D2 timing：CSRFProtect 於 plugin 註冊完成後 init）。
3. `/health`：匿名可探活；明細（plugins/prewarm）目前也全開——收斂方案見 FLK-02。外部監控驗收指令慣例：`curl http://127.0.0.1:5000/health`（期待 `status: ok`）。
4. `/conf_data`（admin only）目前會渲染含 `SECRET_KEY` 的完整 config——修案 FLK-03；在其前不要截圖/記錄該頁。
5. 安全回應標頭目前全缺（XFO/nosniff/Referrer-Policy/CSP），修案 FLK-06；上反向代理（HTTPS terminate）前這組標頭＋`SESSION_COOKIE_SECURE` 要一併處理。
6. `PluginManagerView`（內建外掛管理 UI）只在 authorization 啟用時註冊（`_is_security_component_enabled`）；public 模式自動跳過，屬預期。
7. 錯誤頁細節：appbase 的 Exception handler 把未捕捉例外記 log（exc_info）後回 error-500 頁或 JSON；模板不得輸出 `|safe` 訊息（FLK-10）。

## 5. 開發/測試環境

```bash
cd ~/workspaces/fund13/funlab-flaskr
source ~/workspaces/fund13/.venv/bin/activate
pytest tests/ -q                 # 基準：18 passed（2026-09-27）
python run.py -c funlab/flaskr/conf/config.toml   # 用套件範例 config（ENV.TEST: waitress :5001）
```

- 跑 app 前需要 `QT_API=None`、`MPLBACKEND=Agg`（run.py/tests/conftest.py 都已代辦）。
- 範例 `conf/config.toml` 的 DB 是 sqlite（`:memory:`/`test.db`）；正式庫經 finfun/config.toml 的 `[DATABASE.X]`。
- Plugin 探索走 entry-points group `funlab_plugin`＋`.plugin_cache/`；改過 plugin 套件後設 `RESCAN_PLUGINS=true` 或刪 cache。
