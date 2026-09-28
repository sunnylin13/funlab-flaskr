"""FLK-08: 已裁示移除的 demo 圖床目錄不得復活。"""
from __future__ import annotations

import pathlib

REMOVED = ['emails', 'photos', 'tracks', 'products', 'components',
           'brands', 'browsers', 'jobs', 'crypto-currencies']


def test_removed_asset_dirs_stay_gone():
    static = pathlib.Path(__file__).resolve().parents[1] / 'funlab' / 'flaskr' / 'static'
    for d in REMOVED:
        assert not (static / d).exists(), f'demo 圖床目錄 {d} 不該存在（FLK-08 裁示）'
