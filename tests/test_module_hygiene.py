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
