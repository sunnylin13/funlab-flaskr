# Tabler UI 升級執行日誌

> **升級目標**: Tabler 1.0.0-beta20 → Tabler @tabler/core 1.4.0
> **開始日期**: 2026-02-27
> **項目位置**: `funlab-flaskr` 
> **分支策略**: feature/ui-upgrade/* 多分支並行工作流

---

## 升級進度追蹤

### Phase 1: 繪製基線（Baseline Establishment） ✅ 

**目標**: 建立 Playwright 視覺迴歸測試基線

**搭配分支**: `feature/ui-upgrade/playwright-baseline`

| 步驟 | 任務 | 狀態 | 時間戳 | 備註 |
|------|------|------|--------|------|
| 1.1 | 安裝 Playwright 與瀏覽器 | ✅ Done | 2026-02-27 | pnpm install @playwright/test@1.53.2 |
| 1.2 | 建立基線測試配置 (baseline.spec.ts) | ✅ Done | 2026-02-27 | 6 個匿名路由測試配置 |
| 1.3 | 生成基線截圖 (1440×900 fullpage) | ✅ Done | 2026-02-27 | 6 頁 PNG 圖像輸出 |
| 1.4 | 提交 Node 依賴與測試配置 | ✅ Done | 2026-02-27 | package.json, pnpm-lock.yaml |

**基線覆蓋頁面**:
- Home (redirect) → `/`
- Login → `/auth/login`
- Register → `/auth/register`
- Blank → `/blank`
- About → `/about`
- 404 Error → `/nonexistent`

**輸出物**:
- 6 × 基線 PNG (docs/upgrade/baseline-screens/)
- Playwright 配置檔 (playwright.config.ts)
- package.json 含 @playwright/test 依賴

---

### Phase 2: 核心資產更新（Core Assets Replacement） ✅

**目標**: 將 Tabler 1.0.0-beta20 資產完全替換為 1.4.0 版本

**搭配分支**: `feature/ui-upgrade/core-assets`

| 步驟 | 任務 | 狀態 | 時間戳 | 備註 |
|------|------|------|--------|------|
| 2.1 | 建立資產複製目錄結構 | ✅ Done | 2026-02-27 | `.gitignore` 更新 Node 規則 |
| 2.2 | 複製 CSS 檔案 (css/) | ✅ Done | 2026-02-27 | 65+ CSS 檔案，包括主題與 RTL |
| 2.3 | 複製 JS 檔案 (js/) | ✅ Done | 2026-02-27 | tabler.min.js, tabler-theme.js 等 |
| 2.4 | 複製圖片資源 (img/) | ✅ Done | 2026-02-27 | 160+ 支付/社交 SVG 圖標 |
| 2.5 | 複製第三方函式庫 (libs/) | ✅ Done | 2026-02-27 | apexcharts, tom-select, dropzone 等 |
| 2.6 | 提交資產變更 | ✅ Done | 2026-02-27 | 1585 檔案, +356,653 insertions |

**提交資訊**:
- 分支: `feature/ui-upgrade/core-assets`
- 提交 SHA: `1ab8a41`
- 檔案統計: 1585 files changed, 356,653 insertions(+), 56,783 deletions(-)

**變更內容摘要**:
- 全新 CSS 濾系統 (colors, themes, marketing, social, props)
- 升級 JS 框架 (tabler.esm.js, tabler-theme.js)
- 完整第三方元件更新 (15+ 流行庫)
- 新增社交媒體圖標集 (40+ SVG)

---

### Phase 3: 分支整合（Branch Integration） ✅

**目標**: 整合資產更新至上游分支

**搭配分支**: `feature/ui-upgrade/tabler-1.4.0`

| 序號 | 合併操作 | 狀態 | 時間戳 | 衝突 | 備註 |
|------|---------|------|--------|------|------|
| 3.1 | core-assets → tabler-1.4.0 | ✅ Done | 2026-02-27 | ✅ None | Fast-forward 合併 |
| 3.2 | tabler-1.4.0 → templates | ✅ Done | 2026-02-27 | ✅ None | Fast-forward 合併 |

**合併狀態**:
```
tabler-1.4.0 (1ab8a41)
    ↓ (fast-forward)
templates (HEAD: 現在位置)
```

---

### Phase 4: 模板更新（Template Reference Update） ✅

**目標**: 更新 Jinja2 樣板以使用 1.4.0 資產路徑與快取破壞參數

**搭配分支**: `feature/ui-upgrade/templates`

| 步驟 | 任務 | 狀態 | 時間戳 | 檔案 | 備註 |
|------|------|------|--------|------|------|
| 4.1 | 更新 base.html CSS 參考 | ✅ Done | 2026-02-27 | base.html | 快取破壞: 1692870487 → 1.4.0 |
| 4.2 | 更新 base.html JS 參考 | ✅ Done | 2026-02-27 | base.html | demo-theme.min.js 快取更新 |
| 4.3 | 更新 scripts.html 庫參考 | ✅ Done | 2026-02-27 | scripts.html | apexcharts, jsvectormap, tabler.min.js |
| 4.4 | 更新 base-fullscreen.html | ✅ Done | 2026-02-27 | base-fullscreen.html | 套用相同的快取破壞更新 |
| 4.5 | 提交樣板變更 | ✅ Done | 2026-02-27 | — | 提交 SHA: da8faec |

**更新的資源參考**:

#### CSS 檔案 (base.html)
| 檔案名 | 路徑 | 狀態 | 快取破壞 |
|-------|------|------|---------|
| tabler.min.css | /static/dist/css/ | ✅ 1.4.0 | 1.4.0 |
| tabler-flags.min.css | /static/dist/css/ | ✅ 1.4.0 | 1.4.0 |
| tabler-payments.min.css | /static/dist/css/ | ✅ 1.4.0 | 1.4.0 |
| tabler-vendors.min.css | /static/dist/css/ | ✅ 1.4.0 | 1.4.0 |
| demo.min.css | /static/dist/css/ | ✅ 1.4.0 | 1.4.0 |

#### JavaScript 檔案 (base.html, scripts.html)
| 檔案名 | 路徑 | 類型 | 快取破壞 |
|-------|------|------|---------|
| tabler.min.js | /static/dist/js/ | Core | 1.4.0 |
| demo.min.js | /static/dist/js/ | Demo | 1.4.0 |
| demo-theme.min.js | /static/dist/js/ | Theme | 1.4.0 |
| apexcharts.min.js | /static/dist/libs/apexcharts/ | Lib | 1.4.0 |
| jsvectormap.min.js | /static/dist/libs/jsvectormap/ | Lib | 1.4.0 |

**提交資訊**:
```
提交: da8faec (HEAD -> feature/ui-upgrade/templates)
檔案: 3 changed, 19 insertions(+), 19 deletions(-)
訊息: chore: update Tabler asset references to 1.4.0 with new cache-busting parameters
```

**未解決項目**:
- `funlab/flaskr/app.py`: 2 行註解新增 (保留中)
- `funlab/flaskr/plugin_mgmt_view.py`: 修改中 (保留中)
- `docs/` 資料夾: 未追蹤檔案 (Playwright 成品)

---

## 待完成階段

### Phase 5: 視覺迴歸驗證（Visual Regression Validation）⏳

**目標**: 運行 Playwright 基線對比測試，確保新資產不破壞 UI

**預期工作**:
- 執行 Playwright 測試對比（baseline vs. current）
- 評估視覺差異（預期主要為配色、排版微調）
- 記錄不相容性（如有）

**停止點**: 未執行（需要應用啟動環境確認）

---

### Phase 6: Demo 檔案決策（Demo Assets Evaluation）⏳

**目標**: 決定保留或移除 Demo 相關資源

**候選檢視**:
- `demo.min.css` / `demo.css`
- `demo.min.js` / `demo.js`
- `demo-theme.min.js` / `demo-theme.js`

**決策標準**:
- ☐ 若有自定義樣式依賴: 保留並文件化
- ☐ 若無相依性: 可評估移除以簡化資源
- ☐ 預設: 保留 (向後相容)

**現況**: 已保留在模板引用中（1.4.0 核心仍包含）

---

### Phase 7: cleanup 分支整合（Final Integration）⏳

**目標**: 整合所有工作至 cleanup 分支並準備主線合併

**預期操作**:
1. 建立或更新 `feature/ui-upgrade/cleanup` 分支
2. 合併 templates → cleanup
3. 最終視覺驗證
4. 準備 cleanup → main (或 develop) 合併

**停止點**: 未開始

---

## 技術詳細資訊

### 發現的相容性項目

#### ✅ 完全相容
- **Bootstrap 5 基礎**: Tabler 1.4.0 基於 BS 5.3，所有 BS5 類別仍有效
- **Jinja2 語法**: 不需要樣板引擎更新
- **CSS 預編譯**: 兩版本均為編譯輸出，無 SCSS 相依性
- **JavaScript 模組**: tabler.min.js 向後相容 API

#### 🟡 需要評估
- **Demo 主題系統**: 1.4.0 中主題邏輯已重構 (demo-theme.js → tabler-theme.js)
  - 目前仍在使用 demo-theme.min.js
  - 若要遷移至新系統需額外工作
- **第三方庫升級**: apexcharts, tom-select 等均已升級
  - 配置 API 應向後相容
  - 建議逐項驗證自定義整合

#### ⚠️ 提醒事項
- **快取破壞參數**: 從舊時間戳 (1692870487) 更新為版本號 (1.4.0)
  - 瀏覽器舊快取將被移除
  - 首次載入後所有資源重新下載
- **RTL 支援**: 1.4.0 新增完整 RTL 樣式表
  - 語言偵測系統應自動使用 (若已實作)
  - 或需在 HTML `<html>` 標籤加上 `dir="rtl"`

---

## 手動驗證檢查清單

準備環境測試時，請確認:

- [ ] Flask 應用成功啟動 (`python run.py`)
- [ ] 登入頁加載（CSS 樣式套用正確）
- [ ] 儀表板頁加載（圖表庫初始化成功）
- [ ] 無 404 錯誤訊息於 console
- [ ] 下拉選單、日期選擇器等互動元件可用
- [ ] 行動裝置檢視正常（響應式樣式）
- [ ] 深色模式切換有效（若使用 demo-theme）

---

## 相關文檔

- [UI Refactor & Upgrade Plan](./UI_REFACTOR_AND_UPGRADE_PLAN.md) - 詳細設計文檔
- [Tabler 1.4.0 官方 README](../tabler--tabler-core-1.4.0/README.md)
- [Git 提交歷史](../../../.git/logs/HEAD)

---

**最後更新**: 2026-02-27 16:45 UTC
**近期更新者**: Copilot AI Agent
**下一步**: 啟動 Flask 應用並執行 Phase 5 視覺迴歸驗證
