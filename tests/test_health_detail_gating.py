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
