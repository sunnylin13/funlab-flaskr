"""[QA2-補測 t_d721078d] Wave2 diff 缺口——funlab-flaskr。

覆蓋點（covfinal 基線未打的 app.py diff 行）：
- FLK-06 after_request：CSP_HEADER 啟用分支（135-137）、CSP_REPORT_ONLY 分支（138-140）
- FLK-03 /conf_data 路由本體：遮罩後渲染（280）
"""
from __future__ import annotations

import funlab.core.auth as auth_mod
from types import SimpleNamespace


def test_csp_header_and_report_only_emitted(csrf_app):
    """config 設定 CSP_HEADER／CSP_REPORT_ONLY 後，兩條頭都要出現在回應（137, 140）。"""
    csrf_app.config['CSP_HEADER'] = "default-src 'self'"
    csrf_app.config['CSP_REPORT_ONLY'] = "default-src 'none'"
    try:
        resp = csrf_app.test_client().get('/blank')
        assert resp.headers.get('Content-Security-Policy') == "default-src 'self'"
        assert resp.headers.get('Content-Security-Policy-Report-Only') == "default-src 'none'"
    finally:
        csrf_app.config.pop('CSP_HEADER', None)
        csrf_app.config.pop('CSP_REPORT_ONLY', None)


def test_csp_headers_absent_by_default(csrf_app):
    """預設不發 CSP（模板含大量 inline script 的妥協，FLK-06 註解）。"""
    csrf_app.config.pop('CSP_HEADER', None)
    csrf_app.config.pop('CSP_REPORT_ONLY', None)
    resp = csrf_app.test_client().get('/blank')
    assert 'Content-Security-Policy' not in resp.headers
    assert 'Content-Security-Policy-Report-Only' not in resp.headers


def test_conf_data_admin_renders_masked(csrf_app, monkeypatch):
    """admin 命中 /conf_data：渲染成功且機密值已被遮罩（280 路由本體）。"""
    monkeypatch.setattr(auth_mod, 'current_user',
                        SimpleNamespace(is_authenticated=True, is_admin=True))
    csrf_app.config['SECRET_KEY'] = 'should-never-appear'
    resp = csrf_app.test_client().get('/conf_data')
    assert resp.status_code == 200
    assert b'should-never-appear' not in resp.data
    assert b'***masked***' in resp.data
