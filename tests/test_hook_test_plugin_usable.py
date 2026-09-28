"""FLK-07: hook_test_plugin 移到 tests/ 後仍可被載入並產生標記輸出。"""
from __future__ import annotations


def test_hook_markers_render_via_render_hook(csrf_app):
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from hook_test_plugin import HookTestView

    mgr = csrf_app.hook_manager
    # 手動註冊其 view hooks（正式載入路徑靠 entry-point，測試手動掛）
    probe = HookTestView.__new__(HookTestView)  # 跳過 __init__，只取方法
    mgr.register_hook('view_layouts_base_html_head',
                      HookTestView._render_head_marker.__get__(probe),
                      priority=10, plugin_name='hook_test_manual')
    html = str(mgr.render_hook('view_layouts_base_html_head'))
    assert '<!-- hook_test:head -->' in html
