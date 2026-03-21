---
title: "Funlab Hook 系統導入計畫"
description: "針對 funlab_plugin 與 funlab_sched_task 的 Hook 系統導入與相容性改善計畫"
version: "1.0.0"
status: "draft"
lastUpdated: "2026-02-14"
---

# Funlab Hook 系統導入計畫

## 0. 目標與原則

### 0.1 目標
- 引入 Hook 系統，提供可擴充的 view/controller/model/lifecycle 擴展點。
- 保持既有插件行為不變，採取 opt-in 方式導入。
- 支援逐步執行與記錄，確保可追蹤與回溯。

### 0.2 原則
- 不影響既有插件：未註冊 Hook 的插件，行為不變。
- Hook 失敗不阻塞核心流程：錯誤隔離與記錄。
- 尊重現有 lazy load 與 SecurityPlugin 行為。
- 採階段式導入：先 view hooks，再擴展 controller/model。

---

## 1. 架構盤點與分析

### 1.1 核心外掛基礎類別
- 盤點 ViewPlugin/SecurityPlugin/ServicePlugin 與 Enhanced 版本生命週期與指標功能。
- 核對目前使用的基底類別與繼承規範。
	- 來源: funlab-libs/funlab/core/plugin.py
	- 來源: funlab-libs/funlab/core/enhanced_plugin.py

### 1.2 插件管理流程
- 盤點 entry points 探測、lazy load、註冊到 Flask 的流程。
- 檢查 SecurityPlugin 特殊處理與 login_manager 規則。
	- 來源: funlab-libs/funlab/core/plugin_manager.py
	- 來源: funlab-libs/funlab/core/appbase.py

### 1.3 既有外掛清單

#### funlab_plugin
- AuthView (SecurityPlugin) -> funlab-auth/funlab/auth/view.py
- SchedService (ServicePlugin) -> funlab-sched/funlab/sched/service.py
- FundMgrView (ViewPlugin) -> finfun-fundmgr/finfun/fundmgr/view.py
- OptionView (ViewPlugin) -> finfun-option/finfun/option/view.py
- QuoteService (ServicePlugin) -> finfun-quotesvcs/finfun/quotesvcs/service.py
- PluginManagerView (ViewPlugin, built-in) -> funlab-flaskr/funlab/flaskr/plugin_mgmt_view.py
- HookTestView (ViewPlugin, test) -> funlab-flaskr/funlab/flaskr/hook_test_plugin.py

#### funlab_sched_task
- BookKeepingTask -> finfun-fundmgr/finfun/fundmgr/task.py
- FetchDailyPriceTask -> finfun-finfetch/finfun/finfetch/task.py
- FetchReturnIndexTask -> finfun-finfetch/finfun/finfetch/task.py
- FetchRevenueTask -> finfun-finfetch/finfun/finfetch/task.py
- FetchFinstmtTask -> finfun-finfetch/finfun/finfetch/task.py
- FetchExdividendsTask -> finfun-finfetch/finfun/finfetch/task.py
- FetchCompInfoTask -> finfun-finfetch/finfun/finfetch/task.py
- FetchWarrantInfoTask -> finfun-finfetch/finfun/finfetch/task.py
- CalcQuantTask -> finfun-quantanlys/finfun/quantanlys/task.py
- CalcQuantV2Task -> finfun-quantanlys/finfun/quantanlys/task.py

### 1.4 模板 Hook 佈點參考
- layouts/base.html
- layouts/base-fullscreen.html
- includes/scripts.html

---

## 2. Hook 系統設計規格

### 2.1 Hook 類型
- View Hooks: 由模板呼叫，用於插入 HTML。
- Controller Hooks: 控制器流程前後。
- Model Hooks: 資料模型儲存前後。
- Lifecycle Hooks: Plugin start/stop/reload。

### 2.2 HookManager API (草案)
- register_hook(hook_name, callback, priority=100, plugin_name=None)
- call_hook(hook_name, **context)
- render_hook(hook_name, **context) -> HTML

### 2.3 上下文規範
- 必須提供 request, current_user, app 等核心資訊（視 hook 類型）。
- 允許插件於 context 中補充資料，但不可覆寫核心鍵值。

### 2.4 優先級與錯誤隔離
- 數字越小越早執行。
- Hook 失敗需記錄 log，不阻斷核心流程。

---

## 3. 佈點策略與初始 Hook 清單

### 3.1 View Hooks (Phase 1)
- view_layouts_base_html_head
- view_layouts_base_body_bottom
- view_layouts_base_content_top
- view_layouts_base_content_bottom
- view_project_sidebar_left
- view_project_sidebar_right

### 3.2 Controller Hooks (Phase 2)
- controller_before_request
- controller_after_request
- controller_error_handler

### 3.3 Model Hooks (Phase 3)
- model_before_save
- model_after_save
- model_after_create

### 3.4 Lifecycle Hooks (Phase 3)
- plugin_before_start
- plugin_after_start
- plugin_before_stop
- plugin_after_stop
- plugin_before_reload
- plugin_after_reload

### 3.5 Task Hooks (Phase 3)
- task_before_execute
- task_after_execute
- task_error

---

## 4. 相容性分析與改善建議

### 4.1 funlab_plugin

#### AuthView
- 相容性風險: login_manager 規則不可破壞。
- 改善建議: 支援 controller_before_request hook 以注入安全檢查。

#### SchedService
- 相容性風險: service thread 啟動不受影響。
- 改善建議: lifecycle hooks 記錄啟停狀態。

#### FundMgrView
- 相容性風險: blueprint/menus 不應變更。
- 改善建議: view hooks 可掛載 dashboard 小工具。

#### OptionView
- 相容性風險: 路由與模板不改變。
- 改善建議: view hooks 支援自訂頁面區塊。

#### QuoteService
- 相容性風險: background service 啟動時序。
- 改善建議: lifecycle hook + metrics hook 強化監控。

#### PluginManagerView
- 相容性風險: admin API 不變。
- 改善建議: view hook 插入管理頁 UI 擴充區。

### 4.2 funlab_sched_task

#### BookKeepingTask
- 相容性風險: 不改變排程觸發。
- 改善建議: 任務執行前後 hook 記錄。

#### FetchDailyPriceTask
- 相容性風險: 外部資料源流程不改動。
- 改善建議: hook 收集執行耗時與結果。

#### FetchReturnIndexTask
- 相容性風險: 不影響 scheduler 設定。
- 改善建議: hook 注入額外日誌。

#### FetchRevenueTask
- 相容性風險: 不改變資料表寫入。
- 改善建議: hook 支援錯誤重試策略。

#### FetchFinstmtTask
- 相容性風險: 不改變工作流程。
- 改善建議: hook 整合健康狀態上報。

#### FetchExdividendsTask
- 相容性風險: 不影響排程。
- 改善建議: hook 允許額外資料校驗。

#### FetchCompInfoTask
- 相容性風險: 不影響資料抓取。
- 改善建議: hook 支援執行結果通知。

#### FetchWarrantInfoTask
- 相容性風險: 不影響排程。
- 改善建議: hook 記錄 API 成功率。

#### CalcQuantTask
- 相容性風險: 計算流程不改動。
- 改善建議: hook 記錄計算指標。

#### CalcQuantV2Task
- 相容性風險: 不影響 V2 算法。
- 改善建議: hook 支援性能分析。

---

## 5. 分階段執行計畫與查核點

### Phase 0: 盤點與設計
- [x] 完成架構盤點與插件清單確認
- [x] 完成 Hook 設計規格草案
- [x] 完成 view hook 初始清單
- [x] 完成相容性風險清單

### Phase 1: HookManager + View Hooks
- [x] 實作 HookManager (register/call/render)
- [x] 在模板中插入 view hooks
- [x] 建立基礎 hook 測試插件
- [x] 驗證 funlab_plugin 無回歸

### Phase 2: Controller Hooks
- [x] 在 request pipeline 中加入 controller hooks
- [x] 定義統一 context 結構
- [x] 驗證 AuthView 與 login 管理無回歸

### Phase 3: Model/Lifecycle Hooks
- [x] 加入 plugin lifecycle hook 觸發
- [x] 添加 model hooks 的呼叫規範
- [x] 增加 task execution hooks 支援
- [x] 驗證 sched_task 執行流程 (通過端到端測試)
- [x] 驗證 sched_task 執行流程

### Phase 4: Plugin/Task Opt-in
- [x] 切換 funlab.core.plugin 預設導出至 Enhanced Plugin
- [x] 驗證 Enhanced 版本仍可觸發 plugin_after_init/plugin_service_init
- [x] 每個 plugin 提供 hook 註冊範例
- [x] 每個 sched_task 提供 hook 使用範例
- [x] 產出插件開發指南更新版

### Phase 5: Hardening
- [ ] 效能壓測 (hook overhead)
- [ ] 記錄 hook error isolation
- [ ] 完成回歸測試與修正

---

## 6. 驗證清單

### 6.0 無回歸驗證定義
- 核心目標: 既有 funlab_plugin 與 funlab_sched_task 的行為、介面、資料流程不因 Hook 導入而改變。
- 驗證重點: 載入、路由、登入、背景服務、管理介面、錯誤與效能。

### 6.0.1 無回歸驗證步驟 (最低限度)
- 啟動應用並確認 funlab_plugin entry points 探測完成。
- 走訪主要 UI 頁面並確認載入正常 (例如 home/about/插件管理頁)。
- 驗證 AuthView 登入流程與 login_manager 行為一致。
- 驗證 PluginManagerView 狀態 API 可回傳資料。
- 驗證 ServicePlugin 啟動流程無異常日誌。
- 驗證 funlab_sched_task 任務可被 sched service 載入。

### 6.1 funlab_plugin 驗證
- [x] entry points 探測正常
- [x] blueprint 註冊不受影響
- [x] login_manager 行為不變
- [x] plugin reload/health/metrics API 正常

### 6.2 funlab_sched_task 驗證
- [x] scheduler 正常載入任務
- [x] 任務執行可使用 hook
- [x] 任務失敗不影響 scheduler

### 6.3 UI 驗證
- [ ] 基礎模板渲染正確
- [x] view hooks 內容插入正常

---

## 7. 逐步執行與記錄

### 執行紀錄格式
- 日期:
- 執行項目:
- 變更內容:
- 驗證結果:
- 風險與解法:

### 執行紀錄
- 2026-02-14
	- 執行項目: Phase 0 盤點與設計
	- 變更內容: 補齊架構/插件/任務清單與文件來源路徑; 更新 Phase 0 完成狀態
	- 驗證結果: 文件更新完成
	- 風險與解法: 無
- 2026-02-14
	- 執行項目: Phase 1 HookManager + View Hooks
	- 變更內容: 新增 HookManager; 在 base/layouts 佈點 view hooks; 註冊 call_hook Jinja 全域
	- 驗證結果: 尚未執行實際回歸測試
	- 風險與解法: 待補基礎 hook 測試插件
- 2026-02-14
	- 執行項目: Phase 1 HookManager + View Hooks
	- 變更內容: 新增 HookTestView 測試插件並加入 funlab_plugin entry point
	- 驗證結果: 尚未執行實際回歸測試
	- 風險與解法: 測試插件尚未驗證是否能被載入
- 2026-02-14
  - 執行項目: Phase 1 完成驗證
  - 變更內容: 使用者完成無回歸驗證並確認通過
  - 驗證結果: funlab_plugin 載入、路由、登入、管理介面正常
  - 風險與解法: Phase 1 完成，準備進入 Phase 2
- 2026-02-14
  - 執行項目: Phase 2 Controller Hooks
  - 變更內容: 在 appbase.py 加入 before_request/after_request/errorhandler hooks; 更新 HookTestView 測試 controller hooks
  - 驗證結果: 尚未驗證
  - 風險與解法: 需驗證 AuthView 行為不受影響
- 2026-02-14
  - 執行項目: Phase 2 完成驗證
  - 變更內容: 使用者完成 AuthView 與 login 管理回歸驗證
  - 驗證結果: AuthView 登入、權限、session 行為正常
  - 風險與解法: Phase 2 完成，準備進入 Phase 3
- 2026-02-14
  - 執行項目: Phase 3 完成驗證與測試
  - 驗證結果: 成功 ✓ - 通過 test_hooks.py 端到端測試驗證:
    - HookManager 正確運作
    - plugin_after_init hooks 在 ViewPlugin 初始化時被正確觸發
    - Hook 監聽器正確接收 hook 事件
    - 應用完整啟動：所有 5 個 plugins 成功加載
    - task lifecycle hooks (_execute_with_hooks) 已整合於 SchedTask
  - 日誌輸出: 「Triggering plugin_after_init hook for test」成功輸出
  - Phase 3 完流程完成，所有關鍵功能已實現並驗證
- 2026-02-14
  - 執行項目: Enhanced Plugin 切換與回歸測試
  - 變更內容: funlab.core.plugin 預設導出改為 EnhancedViewPlugin/EnhancedSecurityPlugin/EnhancedServicePlugin; Enhanced 版本加入 plugin_after_init/plugin_service_init 觸發
  - 驗證結果: 使用 PYTHONPATH=funlab-libs 執行 test_hooks.py; Enhanced 版本啟用成功 (enhanced_active: True); plugin_after_init hook 觸發成功
  - 風險與解法: 尚未重新執行完整 UI/登入/排程回歸測試，待 Phase 4 完整驗證
- 2026-02-14
  - 執行項目: Enhanced 版本啟動與任務載入驗證
  - 變更內容: 以 finfun/run.py 啟動服務並確認 plugin 初始化與 sched_task 載入流程
  - 驗證結果: 5 個 plugins 全數載入成功; SchedService 10 個任務載入成功; 觀察到 plugin_after_init/plugin_service_init 記錄
  - 風險與解法: 尚未執行任務實際執行與 UI/view hooks 插入驗證
- 2026-02-14
  - 執行項目: task hook 實際執行驗證
  - 變更內容: 更新 test_hooks.py 增加 DummyTask 並以 _execute_with_hooks 驗證 task_before_execute/task_after_execute
  - 驗證結果: DummyTask 回傳 ok; events 捕獲 before/after
  - 風險與解法: 尚未驗證 task_error 與 scheduler 失敗隔離
- 2026-02-14
  - 執行項目: task_error hook 驗證
  - 變更內容: 更新 test_hooks.py 增加 ErrorTask 並觸發 RuntimeError
  - 驗證結果: error hook 捕獲 error:Error; 例外可被呼叫端捕捉
  - 風險與解法: scheduler 失敗隔離仍待以實際排程執行驗證
- 2026-02-14
  - 執行項目: scheduler 失敗隔離驗證
  - 變更內容: 新增 ErrorTask 並以 date trigger 執行一次; 以 finfun/run.py 短暫啟動
  - 驗證結果: ErrorTask 觸發 RuntimeError; SchedService 記錄錯誤後仍完成啟動並繼續服務
  - 風險與解法: 測試任務為 ErrorTask，驗證完成後已移除 entry point
- 2026-02-14
  - 執行項目: UI/view hooks 插入驗證
  - 變更內容: 檢視 layouts/base.html 與 layouts/base-fullscreen.html 的 call_hook 插入點
  - 驗證結果: 已確認 view_layouts_base_html_head/content_top/content_bottom/body_bottom 插入點
  - 風險與解法: 仍需實際頁面渲染回歸測試
- 2026-02-14
  - 執行項目: Phase 4 plugin/task hook 範例
  - 變更內容: AuthView/SchedService/FundMgrView/OptionView/QuoteService/PluginManagerView 加入 HOOK_EXAMPLES 註冊; SchedTask 加入 HOOK_EXAMPLES 範例註冊
  - 驗證結果: 以設定開關啟用時才註冊 hooks，預設不影響既有行為
  - 風險與解法: 待更新插件開發指南說明 HOOK_EXAMPLES 設定方式
- 2026-02-14
  - 執行項目: 插件開發指南更新
  - 變更內容: 新增 HOOK_EXAMPLES 啟用說明與範例註冊方式
  - 驗證結果: 文件更新完成
  - 風險與解法: 無
- 2026-02-14
  - 執行項目: OptionView Option A + Option B 完整迁移案例
  - 變更內容:
    1. Option A: 建立 finfun-option/finfun/option/conf/plugin.toml，設置 [OptionView] HOOK_EXAMPLES = true
    2. Option B: 將 OptionView 改為繼承 EnhancedViewPlugin (from funlab.core.plugin import EnhancedViewPlugin)
    3. 文檔: 新增 OPTIONVIEW_MIGRATION_CASE_STUDY.md (包含分階段遷移指南、驗證清單、後續應用模板)
    4. 文檔: 新增 OPTIONVIEW_MIGRATION_TECHNICAL_SUPPLEMENT.md (技術說明：自動別名機制、架構演變、預期運行流程)
  - 驗證結果: 執行 test_optionview_migration.py，所有 10 項測試通過 (4/4 組)
    - ✅ OptionView 正確繼承 EnhancedViewPlugin
    - ✅ 所有必要方法可用 (__init__, register_routes, setup_menus, _register_hook_examples)
    - ✅ plugin.toml 配置正確加載 (HOOK_EXAMPLES = true)
    - ✅ 導入路徑驗證通過 (自動別名機制正常工作)
  - 風險與解法: 無 (向後相容，自動升級，可選配置)
  - 後續應用: 可直接複製此案例流程到 FundMgrView, QuoteService 等其他插件迁移
- 需更新 Plugin 開發指引，補充 hook 用法。
