# Dark/Light 主題菜單修復總結

## 📅 修復日期
2026-02-27

## 🔍 診斷發現的問題

### 問題 1：Sidebar 硬編碼 Light 主題 ❌
**症狀**：
```html
<aside class="navbar navbar-vertical navbar-expand-lg" data-bs-theme="light">
```

即使用戶切換到 Dark 模式（`<html data-bs-theme="dark">`），sidebar 仍然強制使用 Light 主題，因為其 `data-bs-theme="light"` 屬性覆蓋了全局設置。

**根本原因**：
[funlab-libs/funlab/core/menu.py](https://github.com/sunnylin13/funlab-libs/blob/f14bd1d/funlab/core/menu.py#L90) 的 `MenuBar._virtical_template` 硬編碼了 `data-bs-theme="{theme}"`，且默認值為 `'light'`。

### 問題 2：菜單鏈接顏色對比度不足 ❌
**症狀**：
```
color: rgb(107, 114, 128)  ← #6b7280 深灰色
background: #111827        ← 深色背景
```

Dark 模式下，菜單鏈接使用深灰色 `#6b7280`（`--tblr-secondary`），在深色背景 `#111827` 上對比度不足，難以閱讀。

**預期顏色**：
```
color: #e5e7eb  ← --tblr-body-color (淺灰色)
background: #111827
```

### 問題 3：Logo 未顯示 ⚠️
用戶報告在 banner 的 logo.svg 圖標未能顯示。

**診斷結果**：
- Logo 文件存在：`/static/logo.svg` ✅
- Logo 為有效的 SVG ✅
- 可能原因：使用 vertical layout 時，logo 由 sidebar 渲染（而非 banner.html）

---

## ✅ 實施的修復

### 修復 1：移除 Sidebar 硬編碼主題
**文件**：`funlab-libs/funlab/core/menu.py`  
**提交**：`f14bd1d` (sunnylin13/funlab-libs)

**更改**：
```python
# 修復前
_virtical_template: ClassVar[str]="""
    <aside class="navbar navbar-vertical navbar-expand-lg" data-bs-theme="{theme}">
    ...
    </aside>
    """

# 修復後
_virtical_template: ClassVar[str]="""
    <aside class="navbar navbar-vertical navbar-expand-lg">
    ...
    </aside>
    """
```

**同時更新 `html()` 方法**：
```python
# 修復前
html = self._virtical_template.format(title=self.title, icon=self.icon, 
                                       href=self.href, theme=self.theme, 
                                       sub_menus=sub_menus)

# 修復後
html = self._virtical_template.format(title=self.title, icon=self.icon, 
                                       href=self.href, sub_menus=sub_menus)
```

**效果**：
- Sidebar 現在會自動繼承 `<html data-bs-theme="dark/light">` 的設置
- Dark/Light 切換立即生效，無需額外配置
- 符合 Tabler 1.4.0 的 CSS 變數繼承機制

---

### 修復 2：添加 Dark Mode 菜單顏色 CSS 覆蓋
**文件**：`funlab-flaskr/funlab/flaskr/templates/includes/banner.html`  
**提交**：`be526ea` (sunnylin13/funlab-flaskr)

**新增 CSS**：
```css
/* Dark mode 菜單顏色修正 - 確保足夠的對比度 */
html[data-bs-theme="dark"] .navbar-vertical .nav-link,
html[data-bs-theme="dark"] .navbar-vertical .dropdown-item,
html[data-bs-theme="dark"] aside .nav-link,
html[data-bs-theme="dark"] aside .dropdown-item {
    color: var(--tblr-body-color) !important;
}

html[data-bs-theme="dark"] .navbar-vertical .nav-link:hover,
html[data-bs-theme="dark"] aside .nav-link:hover {
    background-color: rgba(255, 255, 255, 0.05) !important;
}
```

**效果**：
- Dark 模式下菜單鏈接使用 `--tblr-body-color` (#e5e7eb 淺灰色)
- 在深色背景上對比度提升至 WCAG AA 標準
- Hover 效果更明顯（5% 白色半透明背景）

---

### 修復 3：Logo 顯示檢查
**診斷**：
- Logo 文件存在：`d:\08.dev\funlab\funlab-flaskr\funlab\flaskr\static\logo.svg` ✅
- 配置正確：`config.APP_LOGO = '/static/logo.svg'` ✅
- MenuBar 正確傳遞：`MenuBar(icon=config.APP_LOGO)` ✅

**Layout 差異**：
- **Vertical Layout** (sidebar)：Logo 由 `MenuBar._virtical_template` 渲染在 sidebar 中
- **Horizontal Layout**：Logo 由 `banner.html` 渲染在 navbar 中

**下一步**：用戶需要確認在重啟應用後 logo 是否顯示

---

## 🧪 驗證步驟

### 1. 重啟應用
```powershell
# 停止當前運行的應用
# 重新啟動
cd D:\08.dev\funlab\funlab-start
python run.py
```

### 2. 測試主題切換
1. 打開瀏覽器訪問應用
2. 點擊 Dark/Light 主題切換按鈕
3. **驗證 Sidebar**：
   - 背景顏色應立即改變
   - 菜單鏈接文字顏色應清晰可見
   - 無需刷新頁面

### 3. 運行更新的診斷腳本
打開瀏覽器 Console (F12)，運行：

```javascript
// 更新後的診斷工具（檢查繼承）
console.group("🔍 Theme Inheritance Check");

const htmlTheme = document.documentElement.getAttribute("data-bs-theme");
const sidebarTheme = document.querySelector("aside")?.getAttribute("data-bs-theme");

console.log("✓ HTML theme:", htmlTheme || "light [default]");
console.log("✓ Sidebar theme:", sidebarTheme || "inherited ✅");

if (!sidebarTheme) {
    console.log("✅ PASS: Sidebar correctly inherits theme from <html>");
} else if (sidebarTheme === htmlTheme) {
    console.log("✅ PASS: Sidebar theme matches HTML theme");
} else {
    console.log("❌ FAIL: Sidebar theme conflicts with HTML theme");
}

// 檢查菜單顏色
const navLink = document.querySelector("aside .nav-link");
if (navLink) {
    const color = window.getComputedStyle(navLink).color;
    console.log("✓ Menu link color:", color);
    
    // 預期：Dark mode 應該是淺色 (rgb > 200)
    const rgb = color.match(/\d+/g).map(Number);
    if (htmlTheme === "dark" && rgb[0] > 200) {
        console.log("✅ PASS: Menu color suitable for dark background");
    } else if (htmlTheme === "light" && rgb[0] < 100) {
        console.log("✅ PASS: Menu color suitable for light background");
    } else {
        console.log("⚠️ WARNING: Menu color contrast may be insufficient");
    }
}

console.groupEnd();
```

### 4. 預期結果
```
✓ HTML theme: dark
✓ Sidebar theme: inherited ✅
✅ PASS: Sidebar correctly inherits theme from <html>
✓ Menu link color: rgb(229, 231, 235)
✅ PASS: Menu color suitable for dark background
```

---

## 📊 修復前後對比

| 項目 | 修復前 | 修復後 |
|------|--------|--------|
| **Sidebar 主題** | 硬編碼 `light` | 繼承 `<html>` |
| **主題切換** | 需要刷新頁面 | 立即生效 ✅ |
| **Dark 模式菜單顏色** | `#6b7280` (深灰) | `#e5e7eb` (淺灰) ✅ |
| **對比度 (Dark)** | 不足 | WCAG AA ✅ |
| **Logo 顯示** | 待驗證 | 應正常 ✅ |

---

## 🔗 相關提交

### funlab-libs
- **f14bd1d**: fix: remove hardcoded theme from sidebar to inherit from html element
  - 移除 `data-bs-theme="{theme}"` 硬編碼
  - 更新 `html()` 方法
  - https://github.com/sunnylin13/funlab-libs/commit/f14bd1d

### funlab-flaskr
- **be526ea**: fix: add Dark mode CSS overrides for menu colors
  - 添加 Dark mode 菜單顏色覆蓋
  - 提升對比度至 WCAG AA
  - https://github.com/sunnylin13/funlab-flaskr/commit/be526ea

- **103e44a**: fix: update menu diagnostic tool to use correct Tabler 1.4.0 CSS variables
  - 修正診斷工具查找 `--tblr-*` 變數（而非 `--bs-*`）
  - https://github.com/sunnylin13/funlab-flaskr/commit/103e44a

---

## 💡 技術說明

### Tabler 1.4.0 主題繼承機制
Tabler 1.4.0 使用 CSS 自定義屬性（CSS Custom Properties）實現主題系統：

```css
/* Light mode (default) */
:root, [data-bs-theme="light"] {
    --tblr-body-color: #1f2937;
    --tblr-body-bg: #f9fafb;
    ...
}

/* Dark mode */
[data-bs-theme="dark"] {
    --tblr-body-color: #e5e7eb;
    --tblr-body-bg: #111827;
    ...
}
```

**繼承原理**：
1. 在 `<html data-bs-theme="dark">` 上設置主題
2. 所有子元素自動繼承 CSS 變數值
3. 如果子元素有 `data-bs-theme` 屬性，會覆蓋繼承的值

**我們的修復**：
- 移除 sidebar 的 `data-bs-theme` 屬性 → 允許完整繼承
- 使用 `:root` 的變數 → 自動響應主題切換

---

## 🎯 下一步行動

### 立即驗證（用戶執行）
1. ✅ 重啟應用
2. ✅ 測試 Dark/Light 切換
3. ✅ 運行驗證腳本
4. ✅ 確認 Logo 顯示

### 如果問題持續
請提供以下信息：
1. 驗證腳本輸出結果
2. 瀏覽器 Console 的完整輸出
3. 截圖（Dark 和 Light 模式）
4. 瀏覽器版本

---

**修復完成時間**：2026-02-27  
**狀態**：✅ 已提交和推送所有修復  
**測試狀態**：⏳ 等待用戶驗證
