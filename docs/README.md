# funlab-flaskr 開發文件

> 本目錄只保留「現行正確知識」。歷史性執行日誌、完成報告、merge checklist、prompt 檔已全數移除（2026-09-27 文件清理）；如需考證歷史，查 git log，不要靠文件。

## 文件索引

| 檔案 | 內容 |
|---|---|
| [UI_ARCHITECTURE.md](UI_ARCHITECTURE.md) | 模板/靜態資源現況結構、Tabler 版本事實、主題切換機制、選單渲染與診斷要點 |
| [HOOKS.md](HOOKS.md) | Hook 系統唯一事實來源：API、實際存在的 hook 名稱與 context、用法 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 三種 WSGI 模式、bind/HOST 規則、static 與使用者資料目錄、安全要點 |
| [IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md) | 待修項目 FLK-01…FLK-11（含完整修正程式碼、測試、驗證指令） |

## 快速事實（以原始碼為準，2026-09-27 核實）

- 應用殼：`funlab/flaskr/app.py:FunlabFlask`（繼承 funlab-libs `funlab/core/appbase.py:_FlaskBase`）。
- 進入點：`create_app()` → `start_server()`；正式服務是 systemd user unit `fund13-web.service`，在 `~/workspaces/fund13/finfun` 以 `run.py` 啟動（waitress、埠 5000）。
- 前端資源**只**由 root_bp 的 `/static` 提供；app 層 `static_folder=None`（見 DEPLOYMENT.md「static 與使用者資料目錄」，此為 H1 安全修復，不可回退）。
- CSRF：全域 `CSRFProtect`（ADR-016 D2）；JS 端由 `static/js/csrf_ajax.js` + base 模板 `<meta name="csrf-token">` 自動帶 `X-CSRFToken`。
- 測試：`cd funlab-flaskr && source ~/.venv/fund13/bin/activate && pytest tests/ -q`（基準現況 18 passed）。
