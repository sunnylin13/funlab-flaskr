"""FLK-10: 錯誤頁必須轉義 msg。

探針路由必須在 app 處理第一個 request 之前註冊（Flask 禁止 post-first-request
setup），因此這裡自建一個全新的 FunlabFlask app（比照 conftest._make_app，
不共用 session 級 csrf_app，避免測試執行順序造成 register_blueprint 失敗）。
"""
from __future__ import annotations

import os

import pytest
from flask import Blueprint, abort

os.environ.setdefault('QT_API', 'None')
os.environ.setdefault('MPLBACKEND', 'Agg')

PROBE_CONFIG = """
[FunlabFlask]
TITLE = 'XSS Probe App'
APP_NAME = 'xss-probe-test'
APP_LOGO = '/static/logo.svg'
HOME_ENTRY = 'blank.html'
SECRET_KEY = 'pinned-test-secret-key-for-xss-probe'
PREWARM_ENABLED = false
ENV = { TESTING = true, WSGI = 'flask', PORT = 5998, DEBUG = true }

[CACHE]
CACHE_TYPE = 'SimpleCache'
"""


@pytest.fixture()
def probe_app(tmp_path):
    cfg = tmp_path / 'probe_config.toml'
    cfg.write_text(PROBE_CONFIG, encoding='utf-8')

    from funlab.flaskr.app import FunlabFlask
    app = FunlabFlask(configfile=str(cfg), envfile=None,
                      import_name='test_xss_probe_app',
                      template_folder='', static_folder='')
    # 無 DB：去掉 funlab-auth 的 per-request DB loader（同 conftest._make_app）
    app.login_manager._request_callback = None

    bp = Blueprint('xss_probe', __name__, url_prefix='/xss-probe')

    @bp.route('/bad')
    def bad():
        abort(403, description='<script id="xss">x</script>')

    app.register_blueprint(bp)
    return app


def test_abort_description_is_escaped(probe_app):
    resp = probe_app.test_client().get('/xss-probe/bad')
    assert resp.status_code == 403
    assert b'<script id="xss">' not in resp.data
    # markupsafe 跳雙引號轉為 &#34;（PLAN 原文寫 &quot;，語意相同，此處
    # 以實際轉義輸出為準斷言；核心要求 = raw <script> 不得出現）
    assert b'&lt;script id=&#34;xss&#34;&gt;x&lt;/script&gt;' in resp.data


def test_no_safe_filter_in_error_templates():
    import pathlib
    tdir = (pathlib.Path(__file__).resolve().parents[1]
            / 'funlab' / 'flaskr' / 'templates')
    for name in ('error-403.html', 'error-404.html', 'error-500.html'):
        text = (tdir / name).read_text(encoding='utf-8')
        assert '| safe' not in text and '|safe' not in text, f'{name} 仍含 |safe'
