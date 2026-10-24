"""FLK-08: 已裁示移除的 demo 圖床目錄不得復活。

brands、photos 兩目錄各有一檔為 funlab-auth 登入頁執行期依賴
（url_for 動態拼接與絕對路徑引用，flaskr 內靜態 grep 查不到），刪除即壞登入頁：
- funlab-auth/funlab/auth/templates/sign-in.html:90、sign-in-illustration.html:93、
  sign-in-cover.html:89：url_for('root_bp.static', filename='brands/' + provider + '.svg')
- funlab-auth/funlab/auth/templates/sign-in-cover.html:103：
  /static/photos/finances-us-dollars-and-bitcoins-currency-money-4.jpg
故該兩目錄採檔級白名單（見 RESTORED_WHITELIST），其餘目錄維持整目錄不得存在。
未來新增 OAuth provider 時，須同 PR 把對應 brands/<provider>.svg 加入白名單。
"""
from __future__ import annotations

import pathlib

# 維持「目錄不得存在」斷言的 7 目錄
REMOVED = ['emails', 'tracks', 'products', 'components',
           'browsers', 'jobs', 'crypto-currencies']

# 檔級白名單：目錄可存在，但僅限白名單內的檔（relative_to 目錄後的 posix 路徑）。
# 出現白名單以外的任何檔案即視為 demo 圖床復活（含整個 125MB 圖床）→ fail。
RESTORED_WHITELIST = {
    'brands': {'google.svg'},
    'photos': {'finances-us-dollars-and-bitcoins-currency-money-4.jpg'},
}


def test_removed_asset_dirs_stay_gone():
    static = pathlib.Path(__file__).resolve().parents[1] / 'funlab' / 'flaskr' / 'static'
    for d in REMOVED:
        assert not (static / d).exists(), f'demo 圖床目錄 {d} 不該存在（FLK-08 裁示）'
    for d, allowed in RESTORED_WHITELIST.items():
        directory = static / d
        if not directory.exists():
            continue
        extra = sorted(
            p.relative_to(directory).as_posix()
            for p in directory.rglob('*')
            if p.is_file() and p.relative_to(directory).as_posix() not in allowed
        )
        assert not extra, (
            f'{d}/ 出現 FLK-08 白名單以外的檔案（demo 圖床復活？）：{extra}；'
            f'若是新增 OAuth provider 圖示，請同 PR 加入 RESTORED_WHITELIST'
        )
