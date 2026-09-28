"""funlab.flaskr.conf 套件。

真正的伺服器參數在子模組：
- waitress_conf（waitress 線程/連線參數）
- gunicorn_conf（gunicorn worker/timeout 參數）
本 __init__ 刻意不匯出任何設定值，避免副本漂移。
"""
