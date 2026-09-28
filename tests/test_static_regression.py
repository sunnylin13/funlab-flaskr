"""FLK-09: static 暴露防回歸（H1）。

三層斷言：
1) url_map：不得存在 endpoint=='static' 且 rule=='/<path:filename>' 的
   app 級規則（H1 的破口形態）。
2) get_user_data_storage_path 不得位於任何已註冊 static_folder 之下。
3) HTTP 實測：套件根目錄下的敏感檔 404、/static 前端資源 200。
"""
from __future__ import annotations

from pathlib import Path


def _registered_static_dirs(app):
    dirs = []
    if app.static_folder:
        dirs.append(Path(app.static_folder).resolve())
    for bp in app.blueprints.values():
        if bp.static_folder:
            root = (Path(bp.static_folder) if Path(bp.static_folder).is_absolute()
                    else Path(bp.root_path) / bp.static_folder)
            dirs.append(root.resolve())
    return dirs


def test_no_app_level_static_route(csrf_app):
    bad = [rule for rule in csrf_app.url_map.iter_rules()
           if rule.endpoint == 'static' and rule.rule == '/<path:filename>']
    assert not bad, f'app 級 static 規則復活：{bad}'


def test_user_data_not_under_any_static_folder(csrf_app):
    user_data = csrf_app.get_user_data_storage_path('flk09-regression').resolve()
    for static_dir in _registered_static_dirs(csrf_app):
        assert user_data != static_dir
        assert static_dir not in user_data.parents, \
            f'使用者資料目錄 {user_data} 在 static 目錄 {static_dir} 之下'


def test_sensitive_paths_404_static_assets_200(csrf_app):
    client = csrf_app.test_client()
    for path in ('/app.py', '/conf/config.toml',
                 '/_users/nobody/probe.pfx',
                 '/funlab/flaskr/conf/gunicorn_conf.py'):
        assert client.get(path).status_code == 404, f'{path} 不得可下載'
    assert client.get('/static/dist/js/tabler.min.js').status_code == 200


def test_create_app_uses_static_none():
    from funlab.flaskr import app as app_module
    src = open(app_module.__file__, encoding='utf-8').read()
    create_app_src = src[src.index('def create_app'):src.index('def start_server')]
    assert 'static_folder=None' in create_app_src
    assert 'static_folder=""' not in create_app_src
