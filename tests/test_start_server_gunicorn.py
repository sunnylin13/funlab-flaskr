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
