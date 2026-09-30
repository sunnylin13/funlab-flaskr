# funlab-flaskr 改善方案（IMPROVEMENT_PLAN）

> 撰寫日期：2026-09-27（fund13-dev-arch）。讀者：fund13-dev-coder。
> 每個技術主張都已在原始碼核實並尽量以實跑探針確認（探針：`~/.hermes/profiles/fund13-dev-arch/cache/scratch/probe_flaskr_plan.py`、`probe_flaskr_plan2.py`，只用 tmp config、不碰正式庫）。
> 引用格式：`相對路徑:符號名`（行號約 Lxx，以 2026-09-27 working tree 為準）。
> **現況前提**：H1 static 暴露已熱修入庫（`create_app` 改 `static_folder=None`，commit 878ac68）、H4 憑證已停止追蹤（commit 524f08e）且 git 歷史已清除（見 FLK-11 實施狀態）。本文件不重複已修事项，只做防回歸。
> **實施狀態（2026-09-28 對帳）**：FLK-01～FLK-07/09/10 已合併 main（878ac68 H1、ba9a4b3 FLK-01、6ea52af FLK-02/03/06/10、2c29a20 B2、6a894e5 FLK-05）；FLK-08 依 Q5 裁示刪除 125MB 孤立 assets（備份 backups/flaskr_flk08_orphan_assets_20260928/，退回窗口至 2026-12-28）；FLK-11 已執行 git 歷史清除（main 61ffcb1→5a69723，13 憑證 blob 不可達，GitHub purge ticket #4800915 追蹤 server-side 肅清）。已部署正式服務。測試基線現況 **43 passed**（/health 503 為 QA3 OBS-1 既有環境態，非新缺陷）。本文 (a) 段描述【修復前】缺陷。

## 總覽表

| 編號 | 摘要 | 優先級 | 目標檔 |
|---|---|---|---|
| FLK-01 | `from http.client import HTTPException` 用錯類別；flaskr 的 `@errorhandler(Exception)` 是被 appbase 覆蓋的死碼 | P1 | `funlab/flaskr/app.py` |
| FLK-02 | `/health` 匿名可取得全部 plugin 內部狀態（跨網段亦可） | P1 | `funlab/flaskr/app.py`（route `health`） |
| FLK-03 | `/conf_data` 頁面把 `SECRET_KEY` 明文渲染進 HTML | P1 | `funlab/flaskr/app.py`（route `conf_data`） |
| FLK-04 | `start_server` gunicorn 分支 `logging` 未匯入 → `NameError`，gunicorn 模式完全不可用；套件亦未宣告 gunicorn 相依 | P1 | `funlab/flaskr/app.py`、`pyproject.toml` |
| FLK-05 | 程式衛生：`import sys` 在模組尾端、`conf/__init__.py` 是 waitress_conf 的重製副本、`main()` 的 `if not args` 語意 | P2 | `funlab/flaskr/app.py`、`funlab/flaskr/conf/__init__.py` |
| FLK-06 | 全站回應無 `X-Frame-Options`/`X-Content-Type-Options`/`Referrer-Policy`/CSP 標頭（實測全空） | P1 | `funlab/flaskr/app.py` |
| FLK-07 | `hook_test_plugin.py` 留在正式套件（未掛 entry-point、純死重量） | P2 | `funlab/flaskr/hook_test_plugin.py` |
| FLK-08 | static 185MB，其中約 125MB demo 資源（emails/photos/tracks 等）零引用 | P2（須 hermes-admin 決策） | `funlab/flaskr/static/`、`pyproject.toml` |
| FLK-09 | 防回歸：`tests/conftest.py` 仍以 `static_folder=''` 建測試 app（重新暴露套件根目錄）＋補 static 防回歸測試 | P1 | `tests/conftest.py`、新增 `tests/test_static_regression.py` |
| FLK-10 | `error-403/404/500.html` 以 `{{ msg | safe }}` 輸出錯誤訊息（潛伏反射 XSS 模式） | P2 | `funlab/flaskr/templates/error-*.html` |
| FLK-11 | H4 殘餘風險處理指引：公倉歷史中的券商憑證（作廢重發＋歷史清理僅供裁示） | P1（流程） | git 歷史／券商憑證 |

優先級定義：P0=立即修（資料遺失/服務掛）；P1=本輪必修（安全/功能破口）；P2=排程修（衛生/優化）。

---

## FLK-01（P1）http.client.HTTPException 用錯類別＋死碼 Exception handler

### (a) 問題與影響
- `funlab/flaskr/app.py:3` 寫 `from http.client import HTTPException`。`http.client.HTTPException` 是 HTTP **用戶端**解析錯誤類別，與 Flask/Werkzeug 的 `werkzeug.exceptions.HTTPException` 完全不同系。
- `funlab/flaskr/app.py:handle_unexpected_error`（約 L325-332）以該類別做 `isinstance` 判斷——即使生效也永遠為 False。
- 更關鍵：它是**死碼**。`_FlaskBase.__init__` 先呼叫 `self.register_routes()`（appbase.py 約 L225），之後才 `self.register_request_handler()`（約 L228）。兩邊都用 `@self.errorhandler(Exception)` 註冊在 app 層，Flask 同一 `(None, Exception)` 鍵**後註冊者覆蓋前者**，生效的是 `funlab-libs/funlab/core/appbase.py:handle_error`（約 L403，正確 import `werkzeug.exceptions.HTTPException`）。
- 影響：誤導後續維護者以為 flaskr 的 trace 頁邏輯生效；萬一有人「修好」它（先註冊順序對調），會把 appbase 統一的錯誤處理（含 `controller_error_handler` hook、JSON 錯誤回應）覆蓋掉，且 `traceback.format_exception(error)` 的舊簽名與 trace 頁 `{{ trace_info }}` 輸出（見 FLK-10 的 `|safe` 問題串）會把堆疊直接丟給瀏覽器。

### (b) 優先級：P1（死碼＋錯誤 import，屬誤導性缺陷；無即時資安曝露因為不生效）

### (c) 目標檔/函式
`funlab-flaskr/funlab/flaskr/app.py`：模組 import 區、`FunlabFlask.register_routes` 內 `handle_unexpected_error`。

### (d) 完整修正後程式碼
模組頂部 import 區整段替換（刪 L3 `http.client` 與 L5 `traceback`——`traceback` 只被死碼使用）：

```python
from __future__ import annotations
import argparse
from pathlib import Path
from werkzeug.routing import BuildError

from flask import (Blueprint, Flask, redirect, render_template, url_for, current_app)
from flask_login import current_user
from funlab.core.auth import policy_required
from funlab.core.menu import MenuItem, MenuDivider
from funlab.core.config import Config
from funlab.core.appbase import _FlaskBase
from funlab.core.notification import INotificationProvider
from funlab.core.policy import is_admin, is_authenticated_user
from funlab.utils import vars2env
from funlab.flaskr.plugin_mgmt_view import PluginManagerView
```

`register_routes` 內四個 error handler 區整段替換（刪除 `handle_unexpected_error`；保留 403/404/500 專屬 handler；未捕捉例外統一由 `appbase.handle_error` 處理）：

```python
        # Error handlers. 未捕捉例外的統一處理在 funlab-libs 的
        # _FlaskBase.register_request_handler:handle_error（含
        # controller_error_handler hook 與 JSON 錯誤回應）；flaskr 只補
        # 特定狀態碼的頁面。這裡不可再註冊 @self.errorhandler(Exception)：
        # register_request_handler() 在本方法之後執行，後註冊者會覆蓋前者，
        # flaskr 端重複註冊只會產生死碼。
        @self.errorhandler(403)
        def access_deny_error(error):
            return render_template('error-403.html', msg=str(error)), 403

        @self.errorhandler(404)
        def not_found_error(error):
            return render_template('error-404.html', msg=str(error)), 404

        @self.errorhandler(500)
        def internal_error(error):
            return render_template('error-500.html', msg=str(error)), 500

        # Need to call flask's register_blueprint for all route, after route defined
        self.register_blueprint(self.blueprint)
```

### (e) 完整 pytest 測試
新增 `funlab-flaskr/tests/test_error_handler_single.py`（沿用 `tests/conftest.py` 的 `csrf_app` fixture）：

```python
"""FLK-01: 唯一的 Exception handler 必須是 appbase 的 handle_error。

行為面驗證：JSON 請求觸發未捕捉例外時，回應由 appbase.handle_error 產生
（{'error': ...} + 500）。若 flaskr 的死碼 handler 重新生效，會改成回 HTML
trace 頁（不含 'error' JSON 鍵），此測試即失敗。
"""
from __future__ import annotations

import pytest
from flask import Blueprint


@pytest.fixture(scope='session')
def raise_app(csrf_app):
    bp = Blueprint('err_probe', __name__, url_prefix='/err-probe')

    @bp.route('/boom')
    def boom():
        raise ValueError('intentional-boom')

    csrf_app.register_blueprint(bp)
    return csrf_app


def test_json_error_from_appbase_handler(raise_app):
    resp = raise_app.test_client().get('/err-probe/boom',
                                       headers={'Accept': 'application/json'})
    assert resp.status_code == 500
    # appbase.handle_error: request.is_json 時回 {'error': str(exc)}
    assert resp.is_json
    assert 'intentional-boom' in resp.get_json()['error']


def test_no_http_client_import_in_app_module():
    import funlab.flaskr.app as m
    src = open(m.__file__, encoding='utf-8').read()
    assert 'http.client' not in src, 'FLK-01: 不得再 import http.client.HTTPException'
    assert 'handle_unexpected_error' not in src, 'FLK-01: 死碼 handler 必須移除'
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_error_handler_single.py -v
# 預期：2 passed（修 code 前 test_no_http_client_import_in_app_module 與 JSON 斷言失敗：
# 目前 JSON 500 也由 appbase 產生，故主要靠 src 斷言把關；handler 覆蓋順序改動後
# JSON 斷言防止回歸）
pytest tests/ -q   # 預期：既有 18 passed 不減少（加新增檔後全數 passed）
```

### (g) 風險與禁止事項
- 風險：刪掉死碼不影響現行行為（本就不生效）；但若未來有人希望在 flaskr 層攔 Exception，必須改 funlab-libs 的 `handle_error`，不可在 flaskr 再註冊。
- 禁止：不可順手改 `appbase.py`（屬 funlab-libs 倉，另案）；不可在此 PR 動 templates（FLK-10 獨立處理）；不可動 `conftest.py`（FLK-09 獨立處理）。

---

## FLK-02（P1）/health 匿名資訊洩漏

### (a) 問題與影響
- `funlab/flaskr/app.py:health`（約 L239-269）匿名回全部 plugin 的 `healthy/error_count/last_error` 與 prewarm 狀態。
- 實跑佐證（tmp app 探針）：匿名 `GET /health` → 200，keys `['plugins','prewarm','status']`；`REMOTE_ADDR=10.9.9.9`（非回環）同樣 200 全量內容。正式服務現況：`curl http://127.0.0.1:5000/health` 回 `{"status":"ok","plugins":{"auth":...,"sse":...,"sched":...,"quote":...,"fundmgr":...,"option":...},...}`，等於對公网（服務監聽 0.0.0.0:5000）揭露內部架構、plugin 清單與最近錯誤訊息（`last_error` 可能含路徑/連線字串）。
- 既有消費端：`finfun/docs/FRESH_ENV_SETUP_UV_LINUX.md` 約 L147 以 `curl http://127.0.0.1:5000/health` 驗收 —— 修正必須保留「從 127.0.0.1 存取時回明細」。

### (b) 優先級：P1（轻中度資訊洩漏，公開監聽下可被偵察）

### (c) 目標檔/函式
`funlab-flaskr/funlab/flaskr/app.py`：`register_routes` 內的 `health()`。

### (d) 完整修正後程式碼
`register_routes` 內 `@self.blueprint.route('/health')` 起至該函式結束（約 L239-269）整段替換：

```python
        @self.blueprint.route('/health')
        def health():
            """健康檢查。

            明細（plugins/prewarm 逐項狀態）只在以下條件回傳：
            - 來源為回環位址（127.0.0.1/::1，本机 curl 驗收流程沿用），或
            - HEALTH_DETAIL='admin' 且當前使用者為 admin，或
            - HEALTH_DETAIL='open'（明確選擇公開發布）。
            其餘情況只回 {'status': 'ok'|'degraded'}。
            HEALTH_DETAIL 預設 'local'。
            """
            from flask import jsonify, request as req
            import funlab.core.prewarm as prewarm

            plugin_health = {}
            for name, plugin in self.plugins.items():
                try:
                    h = plugin.health
                    plugin_health[name] = {
                        'healthy': bool(getattr(h, 'is_healthy', False)),
                        'error_count': int(getattr(h, 'error_count', 0)),
                        'last_error': getattr(h, 'last_error', None),
                    }
                except Exception as exc:
                    plugin_health[name] = {
                        'healthy': False,
                        'error_count': 1,
                        'last_error': str(exc),
                    }

            prewarm_status = prewarm.status()
            all_plugins_healthy = all(v.get('healthy', False) for v in plugin_health.values()) if plugin_health else True
            has_prewarm_pending = any(v.get('status') == 'pending' for v in prewarm_status.values())
            system_ok = all_plugins_healthy and not has_prewarm_pending

            mode = str(self.config.get('HEALTH_DETAIL', 'local')).lower()
            loopback = req.remote_addr in ('127.0.0.1', '::1')
            admin = bool(getattr(current_user, 'is_authenticated', False)) and is_admin(current_user)
            show_detail = (mode == 'open') or loopback or (mode == 'admin' and admin)

            if show_detail:
                payload = {
                    'status': 'ok' if system_ok else 'degraded',
                    'plugins': plugin_health,
                    'prewarm': prewarm_status,
                }
            else:
                payload = {'status': 'ok' if system_ok else 'degraded'}
            return jsonify(payload), (200 if system_ok else 503)
```

### (e) 完整 pytest 測試
新增 `funlab-flaskr/tests/test_health_detail_gating.py`：

```python
"""FLK-02: /health 明細只給回環或授權來源。"""
from __future__ import annotations


def _get(client, remote_addr):
    return client.get('/health', environ_base={'REMOTE_ADDR': remote_addr})


def test_loopback_gets_full_detail(client):
    resp = _get(client, '127.0.0.1')
    assert resp.status_code in (200, 503)
    body = resp.get_json()
    assert set(body.keys()) >= {'status', 'plugins', 'prewarm'}


def test_nonloopback_anonymous_gets_status_only(client):
    resp = _get(client, '10.9.9.9')
    assert resp.status_code in (200, 503)
    assert list(resp.get_json().keys()) == ['status']


def test_nonloopback_body_has_no_plugin_names(client):
    resp = _get(client, '192.168.9.9')
    assert b'plugins' not in resp.data
    assert b'prewarm' not in resp.data
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_health_detail_gating.py -v
# 預期：3 passed（修正前 nonloopback 雨條失敗：回鍵含 plugins/prewarm）
```

### (g) 風險與禁止事項
- 風險：外部監控若依賴非回環位址讀明細會看到精簡版。**2026-09-27 實查**：本機 crontab 與 scripts/、備份腳本均無對 /health 的輪詢引用（grep 零命中）→ 現況改動無已知監控依賴；若日後接外部監控，用本機 curl 或設 `HEALTH_DETAIL='open'`。交付時在 PR description 註明。
- 注意：TestClient 的預設 `REMOTE_ADDR` 是 `127.0.0.1`，所以既有的 `/health` 測試（若之後有人加）預設走明細分支，這是預期行為。
- 禁止：不要在這個 handler 加認證 redirect（health 必須可匿名探活）；不可把 503 條件語意改掉（監控依賴它）。

---

## FLK-03（P1）/conf_data 把 SECRET_KEY 明文渲染進 HTML

### (a) 問題與影響
- `funlab/flaskr/app.py:conf_data`（約 L223-226）把 `self.config` 整個傳進 `conf-data.html`，模板的 `render_value` 巨集逐鍵輸出。
- 實跑佐證（探針 P2）：以真實 config 渲染 `conf-data.html`，結果 `SECRET_KEY_label: true, secret_value_leaked: true`——測試用金鑰值原樣出現在 HTML。
- `SECRET_KEY` 不只是 session 簽章：`funlab/flaskr/app.py:create_app`（約 L359）與 appbase 用它做 `vars2env` 的 env 檔加解密金鑰（finfun/config.toml 註解 ADR-016 D2/R3 同旨）。路由雖有 `@policy_required(is_admin)`，但：管理頁 HTML 會被瀏覽器歷史/日誌/螢幕共享留存，且任何对该页的 XSS/代理記錄都會直接拿走主金鑰。
- 另注意 `conf-data.html` 的 `render_value` 輸出未標 `|safe`（Jinja 預設 escape），本項只是洩漏不是 XSS。

### (b) 優先級：P1（主金鑰洩漏面，限 admin 但影響級高）

### (c) 目標檔/函式
`funlab-flaskr/funlab/flaskr/app.py`：新增模組層輔助 `_mask_sensitive`，改 `conf_data()` 路由。

### (d) 完整修正後程式碼
在 `class FunlabFlask` 定義之前插入輔助函式（模組級、可單測）：

```python
import re

# 機密欄位名稱偵測（FLK-03）：渲染設定頁前先遮罩。
# 注意用「包含」而非「等於」：SECRET_KEY / XXX_PASSWORD / DB_TOKEN 都要命中；
# 刻意不含裸 'KEY' 以外的一般詞，避免把 HOME_ENTRY 等一般鍵誤遮。
_SENSITIVE_KEY_RE = re.compile(
    r'(SECRET|PASSWORD|PASSWD|PASSPHRASE|TOKEN|APIKEY|API_KEY|ACCESS_KEY|'
    r'PRIVATE_KEY|CREDENTIAL|CERT_PASS|KEYSTORE)', re.IGNORECASE)


def _mask_sensitive(mapping):
    """遞迴遮罩 dict 中機密鍵的值（不回傳原 dict）。"""
    masked = {}
    for key, value in dict(mapping).items():
        if isinstance(value, dict):
            masked[key] = _mask_sensitive(value)
        elif _SENSITIVE_KEY_RE.search(str(key)):
            masked[key] = '***masked***'
        else:
            masked[key] = value
    return masked
```

`conf_data` 路由整段替換：

```python
        @self.blueprint.route('/conf_data')
        @policy_required(is_admin)
        def conf_data():
            # FLK-03: 設定頁絕不輸出金鑰/密碼值；遞迴遮罩後再渲染。
            return render_template('conf-data.html',
                                   app_conf=_mask_sensitive(self.config),
                                   all_conf=_mask_sensitive(self._config.as_dict()))
```

### (e) 完整 pytest 測試
新增 `funlab-flaskr/tests/test_confdata_masking.py`：

```python
"""FLK-03: 設定頁遮罩機密值（直接測 _mask_sensitive；路由級需 DB/admin，
用单元級把關 + 一條渲染級斷言）。"""
from __future__ import annotations

from funlab.flaskr.app import _mask_sensitive


def test_mask_plain_and_nested():
    src = {
        'SECRET_KEY': 'top-secret',
        'TITLE': 'ok',
        'DATABASE': {'password': 'p@ss', 'url': 'sqlite:///x.db'},
        'DEEP': {'X_DB_TOKEN': 'tok', 'HOME': '/'},
    }
    out = _mask_sensitive(src)
    assert out['SECRET_KEY'] == '***masked***'
    assert out['TITLE'] == 'ok'
    assert out['DATABASE']['password'] == '***masked***'
    assert out['DATABASE']['url'] == 'sqlite:///x.db'
    assert out['DEEP']['X_DB_TOKEN'] == '***masked***'
    assert out['DEEP']['HOME'] == '/'


def test_mask_does_not_mutate_source():
    src = {'SECRET_KEY': 's'}
    _mask_sensitive(src)
    assert src['SECRET_KEY'] == 's'


def test_config_mapping_supported():
    # Flask config 是 dict 子類，dict(mapping) 可直接處理
    from werkzeug.datastructures import MultiDict  # noqa: F401  (import smoke)
    out = _mask_sensitive({'HOME_ENTRY': 'blank.html', 'SECRET_KEY': 'x'})
    assert out == {'HOME_ENTRY': 'blank.html', 'SECRET_KEY': '***masked***'}
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_confdata_masking.py -v
# 預期：3 passed（修正前 ImportError: cannot import name '_mask_sensitive'）
```

### (g) 風險與禁止事項
- 風險：admin 若習慣在設定頁抄密碼會失靈（屬預期取捨；真需讀值走伺服器本機 config 檔）。`_mask_sensitive` 逐層拷貝，超大 config 也只是 O(n)，可忽略。
- 禁止：不要把遮罩做在模板巨集裡（绕過 route 的其他渲染路徑會漏）；不要在 log 端「解除遮罩」；funlab-libs `appbase.py` 約 L352-353 的 DB URL 遮罩 bug 是另一案（證據包 L2），**本 PR 不要順手改跨倉檔案**，只在 PR description 提示。

---

## FLK-04（P1）gunicorn 模式 NameError：`logging` 未匯入，選 gunicorn 必掛

### (a) 問題與影響
- `funlab/flaskr/app.py:start_server` 的 gunicorn 分支在 `GunicornApplication.__init__`（約 L396）使用 `logging.getLogger('gunicorn.error')`，但模組頂部**沒有** `import logging`（只在 `__init__` 方法內與 `main()` 內區域 import；封閉作用域取不到）。
- 實跑佐證（探針 P3，以 stub 模組避免真啟動）：`NameError: cannot access free variable 'logging' where it is not associated with a value in enclosing scope`，堆疊框在 `__init__`（app.py L396）。即 config 設 `WSGI='gunicorn'` 時 100% 崩潰，錯誤訊息也不會是 ImportError，極難排查。
- 連帶：開發 venv 未裝 gunicorn（`python -c "import gunicorn"` → ModuleNotFoundError），而 `conf/gunicorn_conf.py` 存在、`pyproject.toml` 未宣告 gunicorn/gevent 相依——選了 gunicorn 也缺執行件。正式機實際採 waitress（systemd unit fund13-web.service → run.py → WSGI='waitress'），故非 P0。

### (b) 優先級：P1（宣告支援的功能完全不可用；修正成本低）

### (c) 目標檔/函式
`funlab-flaskr/funlab/flaskr/app.py:start_server`；`funlab-flaskr/pyproject.toml`。

### (d) 完整修正後程式碼
1) 在模組頂部 import 區（FLK-01 修正後的版本）加一行：

```python
from __future__ import annotations
import argparse
import logging
from pathlib import Path
from werkzeug.routing import BuildError

from flask import (Blueprint, Flask, redirect, render_template, url_for, current_app)
from flask_login import current_user
from funlab.core.auth import policy_required
from funlab.core.menu import MenuItem, MenuDivider
from funlab.core.config import Config
from funlab.core.appbase import _FlaskBase
from funlab.core.notification import INotificationProvider
from funlab.core.policy import is_admin, is_authenticated_user
from funlab.utils import vars2env
from funlab.flaskr.plugin_mgmt_view import PluginManagerView
```

2) `start_server` 整段替換（gunicorn 分支補 ImportError 的明確訊息已有，flask 分支移除區域名單避免陰影；其餘行為保持不變）：

```python
def start_server(app:Flask):
    config:Config = app.config
    wsgi = config.get('WSGI', 'flask')
    supported_wsgi = ('waitress', 'gunicorn', 'flask')
    if wsgi not in supported_wsgi:
        raise Exception(f'Not supported WSGI. Only {supported_wsgi} is supported.')
    if wsgi == 'waitress':
        try:
            from waitress import serve
            from funlab.flaskr.conf import waitress_conf
        except ImportError as e:
            raise Exception("If use waitress as WSGI server, please install needed packages: pip install waitress") from e
        kwargs = {name: getattr(waitress_conf, name) for name in dir(waitress_conf) if not name.startswith('__')}
        kwargs.pop('multiprocessing', None)  # dummy for import multiprocessing statement
        host = config.get('HOST', '0.0.0.0')
        port = config.get('PORT', 5000)
        kwargs['host'] = host
        kwargs['port'] = port
        app.mylogger.info(f"\nStart Waitress server at {host}:{port}")
        serve(app, **kwargs)
    elif wsgi == 'gunicorn':
        try:
            # https://stackoverflow.com/questions/70396641/how-to-run-gunicorn-inside-python-not-as-a-command-line
            try:
                from gunicorn.app.wsgiapp import WSGIApplication  # pylint: disable=import-error
            except ImportError as e:
                raise Exception("If use gunicorn as WSGI server, please install needed packages: pip install gunicorn gevent") from e
            from funlab.flaskr.conf import gunicorn_conf
        except ImportError as e:
            raise Exception("Use gunicorn as WSGI server, but not found package, please install: pip install gunicorn") from e
        class GunicornApplication(WSGIApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                gunicorn_logger = logging.getLogger('gunicorn.error')
                app.logger.handlers = gunicorn_logger.handlers
                app.logger.setLevel(gunicorn_logger.level)
                super().__init__()

            def load_config(self):
                config = {key: value for key, value in self.options.items()
                        if key in self.cfg.settings and value is not None}
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application
        kwargs = {name: getattr(gunicorn_conf, name) for name in dir(gunicorn_conf) if not name.startswith('__')}
        kwargs.pop('multiprocessing', None)  # dummy for import multiprocessing statement
        host = config.get('HOST', '0.0.0.0')
        port = config.get('PORT', 5000)
        kwargs['bind'] = f"{host}:{port}"
        app.mylogger.info(f"Start Gunicorn server at {host}:{port}")
        GunicornApplication(app, kwargs).run()
    else:  # development, use flask embeded server
        log_file = './funlab.log'
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.DEBUG)
        app.logger.addHandler(handler)
        app.run(port=config['PORT'], use_reloader=False)
```

3) `pyproject.toml` 的 `[dependency-groups]` 整段替換（gunicorn 列為選用群組，不進主相依——正式機走 waitress，不該被迫裝）：

```toml
[dependency-groups]
dev = ["pytest>=8.3.0,<10"]
gunicorn = ["gunicorn>=22.0,<24", "gevent>=24.2"]
```

### (e) 完整 pytest 測試
新增 `funlab-flaskr/tests/test_start_server_gunicorn.py`（用 stub 模組，不真啟動伺服器）：

```python
"""FLK-04: gunicorn 分支不得因 logging 未匯入而 NameError。"""
from __future__ import annotations

import sys
import types

import pytest


class _SentinelStop(Exception):
    pass


class _StubWSGIApplication:
    """極簡 WSGIApplication 替身：只還原 run() 前會走到的初始化路徑。"""

    class _Cfg:
        settings = {'bind': None, 'workers': None, 'worker_class': None}

        def set(self, key, value):
            pass

    def __init__(self, *args, **kwargs):
        self.cfg = _StubWSGIApplication._Cfg()
        # 真實 WSGIApplication.__init__ 會解析參數；這裡模擬到 load_config 即可
        self.load_config()

    def load_config(self):
        pass

    def run(self):
        raise _SentinelStop('run() reached without NameError')


@pytest.fixture()
def stub_gunicorn(monkeypatch):
    gmod = types.ModuleType('gunicorn')
    app_mod = types.ModuleType('gunicorn.app')
    wsgiapp_mod = types.ModuleType('gunicorn.app.wsgiapp')
    wsgiapp_mod.WSGIApplication = _StubWSGIApplication
    app_mod.wsgiapp = wsgiapp_mod
    gmod.app = app_mod
    monkeypatch.setitem(sys.modules, 'gunicorn', gmod)
    monkeypatch.setitem(sys.modules, 'gunicorn.app', app_mod)
    monkeypatch.setitem(sys.modules, 'gunicorn.app.wsgiapp', wsgiapp_mod)


def test_gunicorn_branch_no_nameerror(csrf_app, stub_gunicorn):
    from funlab.flaskr.app import start_server
    # csrf_app 是 session 級 fixture：只存取本次要改的鍵，結束即還原，
    # 避免污染其他依賴 csrf_app.config 的測試。
    saved = {k: csrf_app.config.get(k) for k in ('WSGI', 'HOST', 'PORT')}
    csrf_app.config.update(WSGI='gunicorn', HOST='127.0.0.1', PORT=5999)
    try:
        with pytest.raises(_SentinelStop):
            start_server(csrf_app)
    finally:
        csrf_app.config.update(saved)
    # 修正前此處是 NameError（cannot access free variable 'logging'），
    # pytest.raises(_SentinelStop) 會直接失敗。


def test_flask_branch_filehandler_usable(csrf_app):
    # 保鑣測試：flask 分支的 logging.FileHandler 路徑不因模組級 import 整理而壞
    import logging as _logging
    from funlab.flaskr import app as app_mod
    assert getattr(app_mod, 'logging', None) is _logging or 'logging' in dir(app_mod)
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_start_server_gunicorn.py -v
# 預期：2 passed（修正前 test_gunicorn_branch_no_nameerror 失敗於 NameError）
```

### (g) 風險與禁止事項
- 風險：無行為變更（waitress/flask 分支逐行保持）。若日後要真的啟用 gunicorn，另行評估 `conf/gunicorn_conf.py` 的 `workers = cpu_count()*2+1`（本機 20 核 → 41 個 gevent worker，對單人系統過量；SSE 長連線會各 worker 佔一組記憶體與 APScheduler——**多 worker 與程序內排程/SSE 狀態不相容**，啟用前必須先由 dev-arch 設計黏滞/單 worker 策略）。
- 禁止：本 PR 不可改 `conf/gunicorn_conf.py` 的 workers 數（屬 FLK-04b，待裁示）；不可把 gunicorn 加進主 dependencies（拖垮 waitress 部署）；不可在本機改 `finfun/config.toml` 的 WSGI 值重啟服務。

---

## FLK-05（P2）程式衛生：`import sys` 尾置、conf/__init__ 副本、`if not args`

### (a) 問題與影響
- `funlab/flaskr/app.py:main`（約 L428-429）用 `sys.argv`，但 `import sys` 在檔案**最尾端** L440（`if __name__` 前一行）。模組 import 後 `sys` 恰好已是全域，所以「僥倖能跑」；實跑佐證（探針 P2）：`sys_in_header_before_main: false`。一旦有人把檔拆段或靜態檢查（flake8 F821/E402）就會爆。
- `funlab/flaskr/conf/__init__.py` 整個內容是 `waitress_conf.py` 的複製貼上（`ident/threads/backlog/channel_timeout/connection_limit/url_prefix/trusted_proxy` 全套）。後果：`from funlab.flaskr.conf import *` 或有人误讀 `conf` 套件本身時拿到一份幽靈 waitress 設定；`waitress_conf` 的真實來源不明確。
- `main()` 的 `if not args:` 把「傳入空 list」當「未傳」（應為 `if args is None:`）。

### (b) 優先級：P2

### (c) 目標檔/函式
`funlab-flaskr/funlab/flaskr/app.py`（import 區＋main 首行＋檔尾）；`funlab/flaskr/conf/__init__.py`。

### (d) 完整修正後程式碼
1) app.py：頂部改照 FLK-04 的版本再加 `import sys`（完整頂部如下，取代 FLK-04 頂部）：

```python
from __future__ import annotations
import argparse
import logging
from pathlib import Path
import sys
from werkzeug.routing import BuildError

from flask import (Blueprint, Flask, redirect, render_template, url_for, current_app)
from flask_login import current_user
from funlab.core.auth import policy_required
from funlab.core.menu import MenuItem, MenuDivider
from funlab.core.config import Config
from funlab.core.appbase import _FlaskBase
from funlab.core.notification import INotificationProvider
from funlab.core.policy import is_admin, is_authenticated_user
from funlab.utils import vars2env
from funlab.flaskr.plugin_mgmt_view import PluginManagerView
```

2) app.py：`main()` 與檔尾整段替換（並刪除原 L440 的 `import sys`）：

```python
def main(args=None):
    from funlab.utils import log
    mylogger = log.get_logger(__name__, level=logging.INFO)
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Programing by 013 ...")
    parser.add_argument("-c", "--configfile", dest="configfile", default='config.toml', help="specify config.toml name and path")
    parser.add_argument("-e", "--envfile", dest="envfile", default='.env', help="specify .env file name and path")
    args = parser.parse_args(args)
    configfile=args.configfile
    envfile=args.envfile
    mylogger.progress("Web server starting ...", key="main_webserver")
    start_server(create_app(configfile=configfile, envfile=envfile))
    mylogger.end_progress(f"progress state:{mylogger._progress_states}", key='main_webserver')


if __name__ == "__main__":
    sys.exit(main())
```

3) `funlab/flaskr/conf/__init__.py` 內容整檔替換為：

```python
"""funlab.flaskr.conf 套件。

真正的伺服器參數在子模組：
- waitress_conf（waitress 線程/連線參數）
- gunicorn_conf（gunicorn worker/timeout 參數）
本 __init__ 刻意不匯出任何設定值，避免副本漂移。
"""
```

### (e) 完整 pytest 測試
新增 `funlab-flaskr/tests/test_module_hygiene.py`：

```python
"""FLK-05: import sys 必須在模組頭；main([]) 不得回讀 sys.argv。"""
from __future__ import annotations

import pytest


def test_sys_imported_in_module_header():
    import funlab.flaskr.app as m
    src = open(m.__file__, encoding='utf-8').read()
    header = src.split('class FunlabFlask')[0]
    assert 'import sys' in header


def test_main_with_empty_args_list_is_parse_args_not_sys_argv(monkeypatch):
    import funlab.flaskr.app as m
    from funlab.flaskr.app import main

    def _boom(**kw):
        raise RuntimeError('create_app-called')

    monkeypatch.setattr(m, 'create_app', _boom)
    monkeypatch.setattr(m.sys, 'argv', ['prog', '--nonexistent-flag'])
    # 傳空 list：應走 argparse 預設值並直達 create_app；
    # 若 main 誤讀 sys.argv，argparse 會因 --nonexistent-flag 丟 SystemExit(2)。
    with pytest.raises(RuntimeError, match='create_app-called'):
        main([])


def test_conf_init_exports_no_server_settings():
    import funlab.flaskr.conf as c
    for name in ('threads', 'backlog', 'channel_timeout', 'connection_limit',
                 'url_prefix', 'trusted_proxy', 'ident'):
        assert not hasattr(c, name), f'conf/__init__ 不应再带出 {name}'
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_module_hygiene.py -v
# 預期：3 passed（修正前第 1、2 條 FAIL；第 3 條 FAIL 於 conf/__init__ 帶出 threads 等）
python -c "import funlab.flaskr.conf as c; assert not hasattr(c,'threads')"
# 預期：無輸出（conf/__init__ 不再帶出 waitress 參數）
```

### (g) 風險與禁止事項
- 風險：`conf/__init__.py` 若有外部程式碼 `from funlab.flaskr.conf import threads`（grep 全 workspace 僅見 `from funlab.flaskr.conf import waitress_conf/gunicorn_conf` 的合法用法，無此依賴）。
- 禁止：不要動 `waitress_conf.py`/`gunicorn_conf.py` 內容；不要順手重排其他 import（減少 diff 面積）。

---

## FLK-06（P1）無安全回應標頭（clickjacking/sniffing）

### (a) 問題與影響
- 實跑佐證（探針 P5）：`GET /blank`（200）的回應標頭中 `X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy`、`Content-Security-Policy` **全部為 None**。grep 全 workspace（funlab-libs/funlab-flaskr/funlab-auth 的 .py）無任何設定這些標頭的程式碼。
- 服務預設 bind 0.0.0.0:5000（start_server L376/L411 的預設 HOST），正式機即監聽所有介面 → 任何網站可用 iframe 嵌本應用作 clickjacking（登入後操作）；無 nosniff 時舊瀏覽器可能 sniff 上傳內容。
- 既有 CSP 狀況：無。模板大量使用 inline `<script>`（settings.html、banner_scripts.html）與外部 CDN（rsms.me Inter 字體），直接上強制 CSP 會斷版。

### (b) 優先級：P1

### (c) 目標檔/函式
`funlab-flaskr/funlab/flaskr/app.py`：新增 `_init_security_headers()`，在 `__init__` 尾端呼叫。

### (d) 完整修正後程式碼
1) `FunlabFlask.__init__` 中 `self._init_csrf_protection(CSRFError)` 之後加一行呼叫（該段整段替換）：

```python
        # Wire global CSRF protection now that (and only now that) all
        # plugins have had their chance to register exemptions.
        self._init_csrf_protection(CSRFError)
        # FLK-06: 基本安全標頭（不依賴 CSRF 設定，獨立常駐）
        self._init_security_headers()
        mylogger.end_progress("FunlabFlask created.", key='funlabflask')
```

2) 新增方法（放在 `_init_csrf_protection` 之後）：

```python
    def _init_security_headers(self) -> None:
        """FLK-06: 為所有回應掛上基本安全標頭。

        - X-Frame-Options: SAMEORIGIN — 防 clickjacking。模板目前無
          iframe 自我嵌入需求；如日後有特定頁面允許嵌入，用
          config['X_FRAME_OPTIONS_ALLOW'] 逐頁放行的後續案再議。
        - X-Content-Type-Options: nosniff
        - Referrer-Policy: same-origin
        - Content-Security-Policy：預設**不發**（模板含大量 inline script
          與 rsms.me 字體 CDN，強制 CSP 需先整理模板）。部署者可設
          config['CSP_HEADER']（整條 CSP 字串）或保守的
          config['CSP_REPORT_ONLY']（僅報告不封鎖）啟用。
        """
        @self.after_request
        def _add_security_headers(response):
            response.headers.setdefault('X-Frame-Options',
                                        self.config.get('X_FRAME_OPTIONS', 'SAMEORIGIN'))
            response.headers.setdefault('X-Content-Type-Options', 'nosniff')
            response.headers.setdefault('Referrer-Policy',
                                        self.config.get('REFERRER_POLICY', 'same-origin'))
            csp = self.config.get('CSP_HEADER')
            if csp:
                response.headers['Content-Security-Policy'] = csp
            csp_ro = self.config.get('CSP_REPORT_ONLY')
            if csp_ro:
                response.headers['Content-Security-Policy-Report-Only'] = csp_ro
            return response
```

### (e) 完整 pytest 測試
新增 `funlab-flaskr/tests/test_security_headers.py`：

```python
"""FLK-06: 基本安全標頭存在且值正確；CSP 預設不發。"""
from __future__ import annotations


def test_basic_headers_present(client):
    resp = client.get('/blank')
    assert resp.status_code == 200
    assert resp.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['Referrer-Policy'] == 'same-origin'


def test_csp_not_sent_by_default(client):
    resp = client.get('/blank')
    assert 'Content-Security-Policy' not in resp.headers
    assert 'Content-Security-Policy-Report-Only' not in resp.headers
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_security_headers.py -v
# 預期：2 passed（修正前 KeyError: 'X-Frame-Options'）
```

### (g) 風險與禁止事項
- 風險：`X-Frame-Options: SAMEORIGIN` 會擋掉外部 iframe 嵌入本頁（若使用者有把頁面嵌進別站的用法，要改 `DENY`→`ALLOWALL` 需明確裁示）；`after_request` 順序：appbase 已有一個 `after_request`（call_hook），Flask 依註冊序跑，本標頭與其互不衝突。SSE 長連線回應也會帶這些標頭，無副作用。
- 禁止：本輪**不要**預設啟用強制 CSP（會斷 inline script）；不可在 hook（controller_after_request）裡做標頭（hook 失敗會被 HookManager 吞掉，標頭應硬性送達）。

---

## FLK-07（P2）hook_test_plugin.py 不該留在正式套件

### (a) 問題與影響
- `funlab/flaskr/hook_test_plugin.py:HookTestView` 註冊 20 個 hook 做日誌/標記，純驗證用途。
- 實跑佐證：(1) `pyproject.toml` 無 `[project.entry-points."funlab_plugin"]`（全 workspace 掛 funlab_plugin 的是 funlab-auth/sse/sched 與 finfun-* 六倉，funlab-flaskr 不在內）；(2) tmp app 探針 `plugins_loaded: []`、`HookTestView_active: false`——它**永遠不會被載入**，是隨 wheel 出貨的死程式碼；(3) 舊文件把它列為「既有外掛清單」一員（已於本次文件清理移除）。
- 影響：wheel 體積/稽核雜訊；誤導讀者以為它是示範範本掛得上（實際上掛得上與否取決於使用者自己建 entry-point，放 tests/ 更貼近用途）。

### (b) 優先級：P2

### (c) 目標檔
`funlab-flaskr/funlab/flaskr/hook_test_plugin.py` → 移到 `funlab-flaskr/tests/hook_test_plugin.py`。

### (d) 完整修正後程式碼
檔案內容**一字不改**，僅移動位置（git mv）。移動後如 import 路徑有相對引用問題——它只 import `funlab.core.plugin`，無需改寫。若要在測試內直接實例化並驗證 hook 標記，新增：

```python
# tests/test_hook_test_plugin_usable.py
"""FLK-07: hook_test_plugin 移到 tests/ 後仍可被載入並產生標記輸出。"""
from __future__ import annotations


def test_hook_markers_render_via_render_hook(csrf_app):
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from hook_test_plugin import HookTestView

    mgr = csrf_app.hook_manager
    # 手動註冊其 view hooks（正式載入路徑靠 entry-point，測試手動掛）
    probe = HookTestView.__new__(HookTestView)  # 跳過 __init__，只取方法
    mgr.register_hook('view_layouts_base_html_head',
                      HookTestView._render_head_marker.__get__(probe),
                      priority=10, plugin_name='hook_test_manual')
    html = str(mgr.render_hook('view_layouts_base_html_head'))
    assert '<!-- hook_test:head -->' in html
```
（若嫌 `__new__` 取法彆扭，可接受直接把該檔保留在 tests/ 且不加自動化測試，僅以 FLK-07 的 import 冒煙測試代替；兩種都可，不得兩者皆缺。）

### (e) 完整 pytest 測試
見上（單檔）；另加一條防回歸：

```python
# 續 tests/test_hook_test_plugin_usable.py
def test_package_no_longer_ships_hook_test_plugin():
    import funlab.flaskr as pkg, pathlib
    pkg_dir = pathlib.Path(pkg.__file__).parent
    assert not (pkg_dir / 'hook_test_plugin.py').exists()
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && git mv funlab/flaskr/hook_test_plugin.py tests/hook_test_plugin.py
source ~/workspaces/fund13/.venv/bin/activate && pytest tests/test_hook_test_plugin_usable.py -v
# 預期：2 passed
python -c "import funlab.flaskr.hook_test_plugin" 2>&1 | grep ModuleNotFoundError
# 預期：ModuleNotFoundError（正式套件不再包含該模組）
```

### (g) 風險與禁止事項
- 風險：workspace 內無 import 引用（grep 佐證僅自身）；若 dev-coder 在別處發現引用，停下回報，不要自行決定保留位置。
- 禁止：不要刪檔（保留測試用途）；不要順手改其內部 hook 註冊清單。

---

## FLK-08（P2，須 hermes-admin 決策）static 185MB 瘦身

### (a) 問題與影響（實測數字，2026-09-27 `du -sh`）
- `funlab/flaskr/static` 共 **185M**：`emails 108M`、`dist 57M`（Tabler 執行件，必要）、`photos 9.9M`、`tracks 3.7M`、`avatars 2.4M`、`components 1.2M`、`products 892K`、`brands 328K`、`illustrations 280K`、其餘零頭。
- 引用掃描（grep，templates+全部 plugin 倉的 .html/.py/.js/.css，不含 docs/）：
  - `emails/ photos/ tracks/ products/ components/ brands/ browsers/ jobs/ crypto-currencies/`：**0 個引用**（含 dist 內 CSS 也無 `url()` 引用）。
  - `avatars/`：僅 `templates/tabler_index_demo.html` 引用（該 demo 頁本身無路由掛載，僅存檔參考）。
  - `illustrations/ favicon/ dist/ js/`：有實際引用（`conf-data.html`、base 模板、notification include）。
- 打包面：`pyproject.toml` wheel 只 `exclude = ["**/*.jpg", "**/*.png"]`——emails/photos 目錄裡的 png 被排除了，但 **svg 與其他檔仍進 wheel**；且來源樹本身拖累 clone/安裝與稽核（git `.git` 137M）。
- 舊檔 `DEMO_ASSETS_DECISION.md`（已於本次清理刪除）曾裁示「全部保留」，但其掃描只覆蓋 demo.* 八個檔，未覆蓋 emails/photos 等 125MB，屬**裁示範圍不足**，非抵觸。

### (b) 優先級：P2（無安全/功能影響；純成本）

### (c) 目標
`funlab-flaskr/funlab/flaskr/static/{emails,photos,tracks,products,components,brands,browsers,jobs,crypto-currencies}/`（刪除候選，合計約 125MB）；`templates/tabler_index_demo.html` 與 `static/avatars/`（連動裁示）。

### (d) 完整修正後程式碼
無程式碼。刪除指令（供裁示後執行，**本輪 dev-coder 不可執行**）：

```bash
cd ~/workspaces/fund13/funlab-flaskr/funlab/flaskr/static
git rm -r --quiet emails photos tracks products components brands browsers jobs crypto-currencies
# 若連帶裁示移除 demo 頁：
git rm -f ../../funlab/flaskr/templates/tabler_index_demo.html && git rm -r avatars
```

`pyproject.toml` 的 wheel 段建議同步替換（把整個 static 的圖床類排除改為白名單式，防日後再混入）：

```toml
[tool.hatch.build.targets.wheel]
packages = ["funlab"]
exclude = [
    "**/*.map",
    "funlab/flaskr/static/dist/libs/**/dist/**/*.map",
    "**/*.md",
]
```

### (e) 完整 pytest 測試
刪除後跑既有的 `tests/test_static_regression.py`（FLK-09 產出）即可；另補一條引用守衛：

```python
# tests/test_no_orphan_asset_dirs.py
"""FLK-08: 已裁示移除的 demo 圖床目錄不得復活。"""
from __future__ import annotations

import pathlib

REMOVED = ['emails', 'photos', 'tracks', 'products', 'components',
           'brands', 'browsers', 'jobs', 'crypto-currencies']


def test_removed_asset_dirs_stay_gone():
    static = pathlib.Path(__file__).resolve().parents[1] / 'funlab' / 'flaskr' / 'static'
    for d in REMOVED:
        assert not (static / d).exists(), f'demo 圖床目錄 {d} 不該存在（FLK-08 裁示）'
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr
# 刪除前先跑一次引用守衛（應 FAIL 在存在的目錄），刪除後：
du -sh funlab/flaskr/static        # 預期 ≈ 60M（dist+必要資源）
source ~/workspaces/fund13/.venv/bin/activate && pytest tests/test_no_orphan_asset_dirs.py -v   # 9 項通過
# 人工巡檢：啟動 dev app（WSGI=flask，本機 5999）開 /blank /conf_data /about 與
# finfun 首頁，確認無 404 圖損（用瀏覽器 DevTools Network 過濾 404）。
```

### (g) 風險與禁止事項
- 風險：無法核實「瀏覽器外部書籤/舊邮件模板外部引用」這類靜態掃描看不到的引用（见「疑點」）；git 歷史體積不會因删檔縮小（要縮 .git 需歷史清理，那是 FLK-11 同級的 admin 決策）。
- 禁止：**未獲 hermes-admin 明確核准前不得刪除任何 static 目錄**；不可用 `git filter-repo` 順道瘦身（那會重寫歷史，與 FLK-11 綁定裁示）；本項與 FLK-09 的 static 測試不得互相依賴合併順序（先 FLK-09）。

---

## FLK-09（P1）防回歸：static 暴露（測試基礎設施自己先破口）

### (a) 問題與影響
- H1 熱修後 `create_app()` 用 `static_folder=None`（app.py 約 L357，working tree 未 commit）。但 **`tests/conftest.py:_make_app`（L55-67）仍以 `static_folder=''` 直接構造 `FunlabFlask`**，Flask 會把套件根目錄掛成 app 級 static 路由。
- 實跑佐證：以 conftest 同參數構造後——`static_folder` 解析成 `'/home/.../funlab-flaskr/'`，`app.url_map` 出現規則 `('static', '/<path:filename>')`。也就是測試 app 可匿名下載 `_users/**.pfx`、`funlab/flaskr/conf/config.toml`、任何 `.py`。測試本身不測這些路徑所以「綠」，但一旦有人照提示加 static 回歸測試，會測在一個本來就破口的 fixture 上。
- 本項同時交付任務要求的**防回歸測試**：斷言 app 級 `static` endpoint/規則不存在、`get_user_data_storage_path` 不在任何 static_folder 之下、並實際以 HTTP 404/200 探測。

### (b) 優先級：P1（fixture 級破口＋H1 的防線需要測試固化）

### (c) 目標檔
`funlab-flaskr/tests/conftest.py`（`_make_app`）；新增 `funlab-flaskr/tests/test_static_regression.py`。

### (d) 完整修正後程式碼
1) `tests/conftest.py` 的 `_make_app` 整段替換：

```python
def _make_app(configfile: str, import_name: str):
    from funlab.flaskr.app import FunlabFlask
    # FLK-09: 必須與 create_app() 一致用 static_folder=None。
    # 舊值 '' 會讓 Flask 把套件根目錄掛成 app 級 /<path:filename> 路由，
    # 測試 app 因此可匿名下載 _users/、conf/、*.py（H1 破口在測試裡復活）。
    app = FunlabFlask(configfile=configfile, envfile=None,
                      import_name=import_name,
                      template_folder='', static_folder=None)
    # The unit-test app has no database (config carries no [DATABASE] to keep
    # the test self-contained).  funlab-auth's request_loader queries the
    # user table on *every* request and would 500 before the CSRF before-hook
    # result matters; these tests only ever run as anonymous users, so drop
    # the per-request DB-backed loader.  (flask_login stores it in the public
    # ``LoginManager.request_loader`` decorator state.)
    app.login_manager._request_callback = None
    return app
```

2) 新增 `funlab-flaskr/tests/test_static_regression.py`：

```python
"""FLK-09: static 暴露防回歸（H1）。

三層斷言：
1) url_map：不得存在 endpoint=='static' 且 rule=='/<path:filename>' 的
   app 級規則（H1 的破口形態）。
2) get_user_data_storage_path 不得位於任何已註冊 static_folder 之下。
3) HTTP 實測：套件根目錄下的敏感檔 404、/static 前端資源 200。
"""
from __future__ import annotations

from pathlib import Path


def _registered_static_dirs(app):
    dirs = []
    if app.static_folder:
        dirs.append(Path(app.static_folder).resolve())
    for bp in app.blueprints.values():
        if bp.static_folder:
            root = (Path(bp.static_folder) if Path(bp.static_folder).is_absolute()
                    else Path(bp.root_path) / bp.static_folder)
            dirs.append(root.resolve())
    return dirs


def test_no_app_level_static_route(csrf_app):
    bad = [rule for rule in csrf_app.url_map.iter_rules()
           if rule.endpoint == 'static' and rule.rule == '/<path:filename>']
    assert not bad, f'app 級 static 規則復活：{bad}'


def test_user_data_not_under_any_static_folder(csrf_app):
    user_data = csrf_app.get_user_data_storage_path('flk09-regression').resolve()
    for static_dir in _registered_static_dirs(csrf_app):
        assert user_data != static_dir
        assert static_dir not in user_data.parents, \
            f'使用者資料目錄 {user_data} 在 static 目錄 {static_dir} 之下'


def test_sensitive_paths_404_static_assets_200(csrf_app):
    client = csrf_app.test_client()
    for path in ('/app.py', '/conf/config.toml',
                 '/_users/nobody/probe.pfx',
                 '/funlab/flaskr/conf/gunicorn_conf.py'):
        assert client.get(path).status_code == 404, f'{path} 不得可下載'
    assert client.get('/static/dist/js/tabler.min.js').status_code == 200


def test_create_app_uses_static_none():
    from funlab.flaskr import app as app_module
    src = open(app_module.__file__, encoding='utf-8').read()
    create_app_src = src[src.index('def create_app'):src.index('def start_server')]
    assert 'static_folder=None' in create_app_src
    assert 'static_folder=""' not in create_app_src
```

### (e) 完整 pytest 測試
即 (d) 之 2)（檔名 `tests/test_static_regression.py`，位置 `funlab-flaskr/tests/`）。

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_static_regression.py -v
# 預期：4 passed（修 conftest 前：test_sensitive_paths_404... FAIL 於 /app.py==200）
pytest tests/ -q
# 預期：全數 passed；確認 conftest 改 static_folder=None 不影響既有 CSRF 測試
# （CSRF 測試不依賴 app 級 static；/blank 模板引用的 /static/... 走 root_bp，不受影響）
```

### (g) 風險與禁止事項
- 風險：若某個既有測試暗中依賴 app 級 static（目前 grep 無證據），會在本改動下轉紅——那是該測試要修，不是回退理由。
- 禁止：不可回退 `create_app` 的 `static_folder=None`；不可把 `/_users/` 加進 static allowlist「解決」問題（正解是它永遠不在任何 static 路由下）。
- 交付順序：本項先行合併，FLK-08（static 瘦身）在其後，避免回歸測試失去錨點。

---

## FLK-10（P2）error-*.html 的 `{{ msg | safe }}`（潛伏反射 XSS）

### (a) 問題與影響
- `templates/error-404.html` 約 L38、`error-403.html` 約 L38、`error-500.html` 約 L37-40 以 `{{ msg | safe }}`（500 另有 `{{ trace_info }}`）輸出錯誤內容。
- flaskr 的 403/404/500 handler 都傳 `msg=str(error)`。實跑佐證（探針 P2）：目前 404 路徑內容**不會**被反射進 `str(error)`（Werkzeug 的 NotFound 訊息不含 path），故當下不可利用；但只要任何路由改用 `abort(400/403/500, description=<含使用者輸入>)`，該輸入就會以 `|safe` 原樣注入錯誤頁——這是把「轉義與否」寄託在每個未來呼叫者的自覺上。
- `trace_info` 現況只有（FLK-01 要移除的）死碼 handler 會傳；appbase 的有效 handler 傳 `error=error`，模板未用 `error` 變數，故 trace 不外現。移除死碼後 `trace_info` 永遠未定義 → 區塊不渲染。

### (b) 優先級：P2（現況不可利用，模式危險）

### (c) 目標檔
`funlab-flaskr/funlab/flaskr/templates/error-403.html`、`error-404.html`、`error-500.html`。

### (d) 完整修正後程式碼
error-404.html 與 error-403.html 的對應段（各自 `empty-subtitle` 之後）替換為：

```html
          {% if msg %}
          <p class="empty-subtitle text-muted">Reason: <span class="text-danger">{{ msg }}</span></p>
          {% endif %}
```

error-500.html 的 page_body 內訊息段（原 L36-41）替換為：

```html
          {% if msg %}
          <p>Reason: <span class="text-danger">{{ msg }}</span></p>
          {% endif %}
```

（即三個模板、共去掉全部 `| safe` 與 500 頁的 trace 區塊。錯誤細節只留在伺服器 log，由 appbase handler 的 `exc_info=True` 記錄。）

### (e) 完整 pytest 測試
新增 `funlab-flaskr/tests/test_error_templates_escape.py`：

```python
"""FLK-10: 錯誤頁必須轉義 msg。"""
from __future__ import annotations

from flask import Blueprint, abort


def _probe_app(csrf_app):
    bp = Blueprint('xss_probe', __name__, url_prefix='/xss-probe')

    @bp.route('/bad')
    def bad():
        abort(403, description='<script id="xss">x</script>')

    csrf_app.register_blueprint(bp)
    return csrf_app


def test_abort_description_is_escaped(csrf_app):
    app = _probe_app(csrf_app)
    resp = app.test_client().get('/xss-probe/bad')
    assert resp.status_code == 403
    assert b'<script id="xss">' not in resp.data
    assert b'&lt;script id=&quot;xss&quot;&gt;' in resp.data


def test_no_safe_filter_in_error_templates():
    import pathlib
    tdir = (pathlib.Path(__file__).resolve().parents[1]
            / 'funlab' / 'flaskr' / 'templates')
    for name in ('error-403.html', 'error-404.html', 'error-500.html'):
        text = (tdir / name).read_text(encoding='utf-8')
        assert '| safe' not in text and '|safe' not in text, f'{name} 仍含 |safe'
```

### (f) 驗證指令與預期輸出
```bash
cd ~/workspaces/fund13/funlab-flaskr && source ~/workspaces/fund13/.venv/bin/activate
pytest tests/test_error_templates_escape.py -v
# 預期：2 passed（修正前第 1 條 FAIL：raw <script> 出現在回應）
```

### (g) 風險與禁止事項
- 風險：error-403.html 約 L42 有 `{% if msg=='No Login manager plugin is installled.' %}` 的條件文案（既有行為，字串比對不受去 safe 影響，保留原樣）。
- 禁止：不要在錯誤頁加回 trace（除錯請開 `flask` dev 模式或讀 log）；不可只在某個模板改（三個要一致）。

---

## FLK-11（P1，流程項）H4 殘餘風險：公倉歷史中的券商憑證

### (a) 現況（事實，勿重複執行）
- `sunnylin13/funlab-flaskr` 為 **public** 倉；歷史 commit 曾含 4 檔券商憑證：`funlab/flaskr/_users/**`（Sino/Yuanta/Fubon pfx/p12、Capital pfx）。現行 HEAD 已停止追蹤（commit 524f08e：git rm --cached + .gitignore `*.p12`、`funlab/flaskr/_users/`）。**後續演進（2026-09-28）**：使用者先裁示不改寫歷史，後裁示直接清除歷史替代轉 private——已執行 filter-repo＋force push（main 61ffcb1→5a69723，13 憑證 blob 不可達，遠端 fresh clone 命中 0）；GitHub server-side purge ticket **#4800915** 開立中（force-push 後舊完整 SHA 直取可能仍命中快取，待 GitHub 端肅清後複測 404）。倉庫維持 public＝使用者最終裁示（風險接受結案，憑證不作廢重發，見 kanban t_d9230d35）。殘餘防線＝.gitignore 規則＋本文此節防再發指引。

### (b) 處置優先序（不可顛倒）
1. **作廢重發（最高優先，屬使用者/hermes-admin 待辦，非 coder 工作）**：向元大/富邦/新光/Sinotrade 四家申請憑證作廢並重發。憑證一旦外流，歷史清理與否都不影響「已洩漏」事實——重發前，洩漏處於「可利用」狀態。重發後以 `get_user_data_storage_path` 新目錄重新匯入（該 API 現況寫入 `funlab/flaskr/_users/<user>/`，與 git 無關，屬執行動作，執行人=使用者）。
2. 監控選項：若暫不重發，至少確認券商端憑證用途限 IP/需密碼，並留意異常登入通知（使用者裁示範圍）。
3. **歷史清理——僅供裁示的步驟，未經 hermes-admin 決策不得執行**。倉為 public 且已被外部拉取的可能性無法排除，重寫歷史只防「未來 clone 取得」，不追討既有副本；且 5 個 funlab-* 倉皆 public，若要清理應一次全做。

### (c) 歷史清理建議程序（hermes-admin 核准後才可用）
```bash
# 前提：(1) 已備份（完整 mirror clone）；(2) 已確認無人在舊 HEAD 上有未合併分支；
# (3) 所有協作者知悉要重新 clone。
pip install git-filter-repo
cd ~/workspaces/fund13/funlab-flaskr
git clone --mirror git@github.com:sunnylin13/funlab-flaskr.git ../flaskr-mirror-backup   # 先備份
git filter-repo --path funlab/flaskr/_users/ --invert-path --force
git push --force --mirror origin    # 會使所有既有 clone 的歷史失效
# 之後：所有協作者作廢舊 clone 重新 clone；GitHub 側舊 blob 需另開 support ticket 才會從
# cache/objects 徹底移除（filter-repo 後仍短時間可達）。
```
（跨倉批次：對含憑證的其他 funlab-* public 倉重複同一程序——先盤點 `git log --all --name-only | grep -E '\.(pfx|p12)$'`。）

### (d) dev-coder 在此項下的可做/不可做
- 可做：跑**唯讀盤點**（`git log --all --name-only` 找憑證路徑清單）、驗證 `.gitignore` 現況（已含 `*.pfx *.p12 funlab/flaskr/_users/`）、確認 working tree 的 `_users/` 未被追蹤（`git ls-files funlab/flaskr/_users/` 應為空）。
- 禁止（硬性）：不可執行 `git filter-repo`、`git push --force`、`git commit`、`git push`、重啟 fund13-web；不可在回報/文件中貼出憑證檔名以外的內容（檔名清單本身可貼，公倉歷史裡本就可見）。

---

## 附錄：其他已核實、未列號觀察

- `funlab/flaskr/app.py:start_server` 的 flask dev 分支寫死 `./funlab.log`（CWD 相依）並 `use_reloader=False`：僅開發用，暫不動。
- waitress `connection_limit=1000` + gevent/gunicorn 41 workers 等參數屬容量議題，單人系統無虞，不動。
- `PluginManagerView` 在 public 模式跳過註冊（app.py 約 L153-158 `_is_security_component_enabled`）——現況行為正確，文件化於 DEPLOYMENT.md。
- `hook_usage_examples.md`（已刪）所述 `register_model_events` 在 funlab-libs **不存在**（grep 0 命中）、`enhanced_plugin.py` 不存在——新 HOOKS.md 已不含幽靈 API。
- `/notifications/*` 三條路由都有 `policy_required(is_authenticated_user)`＋全域 CSRF，現況可；無改善項。
- `conf/config.toml` 的 `SECRET_KEY = '...'` 硬編碼僅存在於套件內附的**範例** config（repo 內 `funlab/flaskr/conf/config.toml` 未含金鑰；finfun 正式 config 走 `ENV_VAR:SECRET_KEY`）。無新增風險。
