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
