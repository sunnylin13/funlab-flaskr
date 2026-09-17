"""Shared fixtures for funlab-flaskr CSRF tests (ADR-016 D2).

Builds ONE real ``FunlabFlask`` application (full plugin registration path)
from a minimal TOML config written into a tmp dir, then attaches probe
blueprints used by the tests.  Building the full app is deliberately chosen
over a bare Flask mock: the acceptance criteria concern the *composed* app
(CSRFProtect wired after plugin registration, error-handler precedence,
templates injecting the meta tag).
"""
from __future__ import annotations

import os

import pytest

# Mirror run.py: keep matplotlib/Qt out of plugin imports.
os.environ.setdefault('QT_API', 'None')
os.environ.setdefault('MPLBACKEND', 'Agg')


CSRF_CONFIG_PINNED = """
[FunlabFlask]
TITLE = 'CSRF Test App'
APP_NAME = 'csrf-test'
APP_LOGO = '/static/logo.svg'
HOME_ENTRY = 'blank.html'
SECRET_KEY = 'pinned-test-secret-key-for-csrf-tests'
PREWARM_ENABLED = false
ENV = { TESTING = true, WSGI = 'flask', PORT = 5999, DEBUG = true }

[CACHE]
CACHE_TYPE = 'SimpleCache'
"""

CSRF_CONFIG_RANDOM_KEY = """
[FunlabFlask]
TITLE = 'CSRF Test App (random key)'
APP_NAME = 'csrf-test-random'
APP_LOGO = '/static/logo.svg'
HOME_ENTRY = 'blank.html'
PREWARM_ENABLED = false
ENV = { TESTING = true, WSGI = 'flask', PORT = 5999, DEBUG = true }

[CACHE]
CACHE_TYPE = 'SimpleCache'
"""


def _write_config(tmp_path, name: str, content: str) -> str:
    cfg = tmp_path / name
    cfg.write_text(content, encoding='utf-8')
    return str(cfg)


def _make_app(configfile: str, import_name: str):
    from funlab.flaskr.app import FunlabFlask
    app = FunlabFlask(configfile=configfile, envfile=None,
                      import_name=import_name,
                      template_folder='', static_folder='')
    # The unit-test app has no database (config carries no [DATABASE] to keep
    # the test self-contained).  funlab-auth's request_loader queries the
    # user table on *every* request and would 500 before the CSRF before-hook
    # result matters; these tests only ever run as anonymous users, so drop
    # the per-request DB-backed loader.  (flask_login stores it in the public
    # ``LoginManager.request_loader`` decorator state.)
    app.login_manager._request_callback = None
    return app


@pytest.fixture(scope='session')
def csrf_app(tmp_path_factory):
    """Real FunlabFlask app with global CSRFProtect enabled (pinned SECRET_KEY)."""
    tmp = tmp_path_factory.mktemp('csrf_cfg')
    app = _make_app(_write_config(tmp, 'config.toml', CSRF_CONFIG_PINNED),
                    import_name='test_csrf_app')
    _attach_probes(app)
    return app


def _attach_probes(app) -> None:
    """Attach probe blueprints AFTER app construction.

    A blueprint added post-construction still falls under CSRFProtect because
    enforcement lives in the global before_request hook — this is exactly the
    ADR-016 D2 'fail-closed for future routes' semantics, and the probes give
    us unprotected-by-default write endpoints to assert against without
    depending on the auth-protected business routes.
    """
    from flask import Blueprint, jsonify, render_template_string
    from flask_restx import Api, Namespace, Resource
    from wtforms import StringField
    from flask_wtf import FlaskForm

    class _ProbeForm(FlaskForm):
        name = StringField('name')

    probe = Blueprint('csrf_probe', __name__, url_prefix='/csrf-probe')

    @probe.route('/write', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def write():
        return jsonify(ok=True)

    @probe.route('/form', methods=['GET', 'POST'])
    def form_page():
        form = _ProbeForm()
        if form.validate_on_submit():
            return jsonify(ok=True)
        return render_template_string(
            '<!doctype html><html><body>'
            '<meta name="csrf-token" content="{{ csrf_token() }}">'
            '<form method="post">{{ form.hidden_tag() }}</form>'
            '</body></html>', form=form)

    app.register_blueprint(probe)

    # restx Api with the exemption pattern used by finfun-fundmgr (D2-b).
    restx_bp = Blueprint('csrf_probe_api', __name__, url_prefix='/csrf-probe-api')
    api = Api(restx_bp, doc=None, decorators=[app.csrf.exempt])
    ns = Namespace('api')
    api.add_namespace(ns)

    @ns.route('/query', methods=['GET', 'POST'])
    class QueryAPI(Resource):
        def get(self):
            return {'api': True}

        def post(self):
            # read-only query; POST merely delegates to GET (same as fundmgr)
            return self.get()

    app.register_blueprint(restx_bp)


@pytest.fixture()
def client(csrf_app):
    return csrf_app.test_client()


@pytest.fixture()
def csrf_token(client):
    """Token extracted from a rendered page, as the browser would get it."""
    resp = client.get('/blank')
    assert resp.status_code == 200
    import re
    m = re.search(rb'name="csrf-token" content="([^"]+)"', resp.data)
    assert m, 'base template must inject <meta name="csrf-token"> (ADR-016 D2-c)'
    return m.group(1).decode()
