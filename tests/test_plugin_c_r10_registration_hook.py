"""R10（kanban t_e56e99f5）：FunlabFlask 構造完成後明確廣播一次 plugins_registration_complete。

验收：
- hook 恰觸發一次，且在所有 plugin_after_init 之後（＝全部 plugin 註冊完成）。
- context 自動帶 app（HookManager 注入）。
"""
from __future__ import annotations

import os

os.environ.setdefault('QT_API', 'None')
os.environ.setdefault('MPLBACKEND', 'Agg')

CONFIG = """
[FunlabFlask]
TITLE = 'R10 Test App'
APP_NAME = 'r10-test'
APP_LOGO = '/static/logo.svg'
HOME_ENTRY = 'blank.html'
SECRET_KEY = 'pinned-test-secret-key-r10'
PREWARM_ENABLED = false
ENV = { TESTING = true, WSGI = 'flask', PORT = 5998, DEBUG = true }

[CACHE]
CACHE_TYPE = 'SimpleCache'
"""


def test_registration_complete_broadcast_exactly_once(tmp_path, monkeypatch):
    from funlab.core.hook import HookManager

    calls: list[str] = []
    original = HookManager.call_hook

    def spy(self, hook_name, **context):
        calls.append(hook_name)
        return original(self, hook_name, **context)

    monkeypatch.setattr(HookManager, "call_hook", spy)

    from funlab.flaskr.app import FunlabFlask
    cfg = tmp_path / "config.toml"
    cfg.write_text(CONFIG, encoding="utf-8")
    app = FunlabFlask(configfile=str(cfg), envfile=None,
                      import_name="test_r10_app",
                      template_folder="", static_folder=None)

    n = calls.count("plugins_registration_complete")
    assert n == 1, f"plugins_registration_complete 必須恰觸發一次，實際 {n} 次：{calls}"
    # 全部 plugin 註冊完成語意：必須在所有 plugin_after_init 之後
    for i, name in enumerate(calls):
        if name == "plugin_after_init":
            assert i < calls.index("plugins_registration_complete")
    # HookManager 自動注入 app context
    seen = {}

    def probe(context):
        seen.update(context)
    app.hook_manager.register_hook("plugins_registration_complete", probe)
    app.hook_manager.call_hook("plugins_registration_complete")
    # （手動再觸發僅驗證 context 注入；恰一次由上方 calls 計數保證）
    assert seen.get("app") is app
