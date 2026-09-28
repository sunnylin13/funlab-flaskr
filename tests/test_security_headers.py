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
