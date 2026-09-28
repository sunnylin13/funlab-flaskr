"""FLK-01: 唯一的 Exception handler 必須是 appbase 的 handle_error。

行為面驗證：JSON 請求觸發未捕捉例外時，回應由 appbase.handle_error 產生
（{'error': ...} + 500）。若 flaskr 的死碼 handler 重新生效，會改成回 HTML
trace 頁（不含 'error' JSON 鍵），此測試即失敗。
"""
from __future__ import annotations

import pytest
from flask import Blueprint


@pytest.fixture(scope='session')
def raise_app(tmp_path_factory):
    # 自建 app（同 test_csrf_protection 的 random-key 模式）：session 級
    # csrf_app 可能被其他測試先觸發請求後才轮到本 fixture，届时
    # register_blueprint 会被 Flask 拒绝（"can no longer be called"）。
    from tests.conftest import CSRF_CONFIG_PINNED, _write_config, _make_app
    tmp = tmp_path_factory.mktemp('err_cfg')
    app = _make_app(_write_config(tmp, 'err.toml', CSRF_CONFIG_PINNED),
                    import_name='test_err_handler_app')
    bp = Blueprint('err_probe', __name__, url_prefix='/err-probe')

    @bp.route('/boom')
    def boom():
        raise ValueError('intentional-boom')

    app.register_blueprint(bp)
    return app


def test_json_error_from_appbase_handler(raise_app):
    # appbase.handle_error 以 request.is_json（Content-Type）分流，故探測
    # 請求須帶 application/json Content-Type（PLAN 原版只發 Accept 頭，
    # 實測會落入 HTML 分支——偏離已在交付 comment 如實回報）。
    resp = raise_app.test_client().get('/err-probe/boom',
                                       headers={'Accept': 'application/json',
                                                'Content-Type': 'application/json'})
    assert resp.status_code == 500
    # appbase.handle_error: request.is_json 時回 {'error': str(exc)}
    assert resp.is_json
    assert 'intentional-boom' in resp.get_json()['error']


def test_no_http_client_import_in_app_module():
    import funlab.flaskr.app as m
    src = open(m.__file__, encoding='utf-8').read()
    assert 'http.client' not in src, 'FLK-01: 不得再 import http.client.HTTPException'
    assert 'handle_unexpected_error' not in src, 'FLK-01: 死碼 handler 必須移除'
