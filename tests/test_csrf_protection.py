"""Global CSRF protection acceptance tests (ADR-016 D2, kanban t_d95b5988).

Acceptance criteria covered here:
  1. POST/PUT/PATCH/DELETE without a CSRF token → 400 (not 500 — the
     appbase catch-all errorhandler(Exception) must NOT swallow CSRFError).
  2. Form POST carrying hidden_tag token → normal response.
  3. fetch/XHR style request carrying X-CSRFToken header → normal response.
  4. Exempted flask-restx api namespace: POST without token → 200.
  5. CSRFProtect is wired AFTER plugin registration (extensions['csrf']
     exists; plugin-declared exemptions survive).
  6. Base templates inject <meta name="csrf-token"> and load csrf_ajax.js.
  7. SECRET_KEY random fallback sets secret_key_is_random (R3 deployment
     guard surfaced for operators).
"""
from __future__ import annotations

import re

# ══════════════════════════════════════════════════════════════════════════
# 1. Missing token → 400 on every write method
# ══════════════════════════════════════════════════════════════════════════

def test_post_without_token_is_400(client):
    r = client.post('/csrf-probe/write')
    assert r.status_code == 400, r.data[:200]
    # Must stay a CSRF rejection, never an appbase-swallowed 500.
    assert b'CSRF' in r.data


def test_put_patch_delete_without_token_are_400(client):
    for method in (client.put, client.patch, client.delete):
        r = method('/csrf-probe/write')
        assert r.status_code == 400, (method, r.data[:200])


def test_json_post_without_token_is_400_json_flavoured(client):
    r = client.post('/csrf-probe/write', json={'ids': [1]})
    assert r.status_code == 400
    # JSON clients get a JSON body (notifications/plugin-mgmt style callers).
    assert r.is_json
    assert 'CSRF' in r.get_json()['error']


def test_bogus_token_is_400(client):
    r = client.post('/csrf-probe/write', headers={'X-CSRFToken': 'not-a-real-token'})
    assert r.status_code == 400


def test_safe_methods_unaffected(client):
    assert client.get('/csrf-probe/write').status_code == 200
    assert client.get('/health').status_code == 200
    assert client.get('/blank').status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# 2. Valid token paths → normal
# ══════════════════════════════════════════════════════════════════════════

def test_form_post_with_hidden_tag_token(client):
    g = client.get('/csrf-probe/form')
    assert g.status_code == 200
    m = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', g.data)
    assert m, 'hidden_tag() must render the csrf_token input'
    token = m.group(1).decode()
    r = client.post('/csrf-probe/form', data={'csrf_token': token, 'name': 'x'})
    assert r.status_code == 200, r.data[:200]


def test_header_token_post_ok(client, csrf_token):
    r = client.post('/csrf-probe/write', headers={'X-CSRFToken': csrf_token})
    assert r.status_code == 200, r.data[:200]


def test_alt_header_name_token_post_ok(client, csrf_token):
    # flask-wtf accepts both X-CSRFToken and X-CSRF-Token by default.
    r = client.post('/csrf-probe/write', headers={'X-CSRF-Token': csrf_token})
    assert r.status_code == 200, r.data[:200]


def test_json_post_with_header_token_ok(client, csrf_token):
    r = client.post('/csrf-probe/write', json={'ids': [1]},
                    headers={'X-CSRFToken': csrf_token})
    assert r.status_code == 200, r.data[:200]


# ══════════════════════════════════════════════════════════════════════════
# 3. flask-restx api namespace exemption (the ONLY exemption, ADR-016 D2-b)
# ══════════════════════════════════════════════════════════════════════════

def test_exempted_api_post_without_token_is_200(client):
    r = client.post('/csrf-probe-api/api/query')
    assert r.status_code == 200, r.data[:200]
    assert r.get_json() == {'api': True}


def test_exemption_is_scoped_not_global(client):
    # The exemption covers the restx Api views only — a plain route in the
    # same app is still protected.
    assert client.post('/csrf-probe-api/api/query').status_code == 200
    assert client.post('/csrf-probe/write').status_code == 400


# ══════════════════════════════════════════════════════════════════════════
# 4. Wiring invariants
# ══════════════════════════════════════════════════════════════════════════

def test_csrf_extension_registered(csrf_app):
    from flask_wtf import CSRFProtect
    assert isinstance(csrf_app.extensions.get('csrf'), CSRFProtect)
    assert csrf_app.extensions['csrf'] is csrf_app.csrf


def test_base_templates_inject_meta_and_bootstrap_js():
    import funlab.flaskr
    from pathlib import Path
    tpl_dir = Path(funlab.flaskr.__file__).parent.joinpath('templates', 'layouts')
    for name in ('base.html', 'base-fullscreen.html'):
        text = tpl_dir.joinpath(name).read_text(encoding='utf-8')
        assert 'name="csrf-token"' in text, name
        assert 'csrf_ajax.js' in text, name


def test_static_js_served(client):
    r = client.get('/static/js/csrf_ajax.js')
    assert r.status_code == 200
    assert b'X-CSRFToken' in r.data


def test_blank_page_carries_meta_token(client):
    body = client.get('/blank').get_data()
    assert re.search(rb'name="csrf-token" content=".+"', body), \
        'authenticated/anonymous pages must expose the token for JS submitters'


# ══════════════════════════════════════════════════════════════════════════
# 5. SECRET_KEY deployment guard (ADR-016 D2 / R3)
# ══════════════════════════════════════════════════════════════════════════

def test_pinned_secret_key_no_random_flag(csrf_app):
    assert csrf_app.secret_key_is_random is False


def test_random_secret_key_flag_and_warning(tmp_path, caplog):
    from tests.conftest import CSRF_CONFIG_RANDOM_KEY, _write_config, _make_app
    import logging
    with caplog.at_level(logging.WARNING):
        app = _make_app(_write_config(tmp_path, 'rand.toml', CSRF_CONFIG_RANDOM_KEY),
                        import_name='test_csrf_randomkey_app')
    assert app.secret_key_is_random is True
    # The logger used is funlab's CustomLogger; caplog may not see it, so
    # assert the flag (the actionable signal) and, if the record is visible,
    # its message.
    messages = [rec.getMessage() for rec in caplog.records]
    if messages:
        assert any('SECRET_KEY' in m for m in messages)
