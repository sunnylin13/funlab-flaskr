"""PW-4: /health 的 degraded 判定排除 late pending 預熱任務。

late=True（run() 之後註冊、永不執行）的 pending 任務永遠不會被執行清空，
若計入 degraded 會把 /health 永久打到 503。本測試以 monkeypatch
funlab.core.prewarm.status() 注入各種 entry，不依賴 libs 側真實的
late 欄位是否存在（本 worktree 基於 late 欄位上線前的 main）。
"""
from __future__ import annotations

import funlab.core.prewarm as prewarm


def _patch_status(monkeypatch, entries):
    monkeypatch.setattr(prewarm, 'status', lambda: dict(entries))


def test_late_pending_does_not_degrade(client, monkeypatch):
    """late 殭屍任務（pending + late=True）→ /health 仍 200 ok。"""
    _patch_status(monkeypatch, {
        'done_task': {'status': 'done', 'attempts': 1, 'late': False},
        'zombie_task': {'status': 'pending', 'attempts': 0, 'late': True},
    })
    resp = client.get('/health', environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'ok'
    # 明細仍原樣揭露 late pending，除的是判定不是可見性
    assert body['prewarm']['zombie_task']['status'] == 'pending'


def test_normal_pending_still_degrades(client, monkeypatch):
    """正常 pending（late=False，會被執行）→ 仍 503 degraded。"""
    _patch_status(monkeypatch, {
        'real_pending': {'status': 'pending', 'attempts': 0, 'late': False},
    })
    resp = client.get('/health', environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert resp.status_code == 503
    assert resp.get_json()['status'] == 'degraded'


def test_pending_without_late_key_still_degrades(client, monkeypatch):
    """libs 舊版 status() 沒有 late 欄位 → 缺欄視同非 late，維持 503。"""
    _patch_status(monkeypatch, {
        'legacy_pending': {'status': 'pending', 'attempts': 0},
    })
    resp = client.get('/health', environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert resp.status_code == 503
    assert resp.get_json()['status'] == 'degraded'
