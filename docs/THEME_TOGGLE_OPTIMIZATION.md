# Dark/Light 主题切換優化與菜單問題診斷

**日期**: 2025-02-27  
**狀態**: 最佳化進行中  
**提交**: (待提交優化)  

---

## 🎯 核心改進

### 改進 1：移除不必要的頁面重新加載 ✅ 已完成

**原問題**：
- 舊版實現在設置主題後仍調用 `window.location.href`，導致整個頁面重新加載
- 不必要的重新加載浪費頻寬、增加延遲、破壞用戶體驗

**優化方案**：
```javascript
// ❌ 舊方式 - 導致頁面重新加載
window.location.href = window.location.pathname + "?" + searchParams.toString();

// ✅ 新方式 - 不重新加載，但更新URL
window.history.replaceState({path: newUrl}, "", newUrl);
```

**優勢**：
- ✅ 主題立即切換（無延遲）
- ✅ 頁面狀態保持（表單輸入、滾動位置等）
- ✅ 瀏覽器歷史正確更新（可書籤、可分享URL）
- ✅ URL 參數同步（`?theme=dark`），便於持久化

**修改檔案**：
- `funlab/flaskr/templates/includes/banner_scripts.html` (已完成)

---

## 🔍 菜單問題診斷

### 菜單問題的可能原因

菜單在 Vertical 佈局中由 `g.mainmenu|safe` 渲染，使用 Tabler/Bootstrap 標準 CSS class。理論上主題切換應該自動工作。

| 可能原因 | 症狀 | 診斷方法 |
|---------|------|---------|
| **CSS 變數未正確應用** | 菜單顏色不變 | 檢查 `<aside>` 元素的計算樣式 |
| **文字對比度問題** | Dark 模式下菜單看不清 | 檢查 `--bs-body-color` 和菜單背景色 |
| **過時的 CSS class** | 菜單在 1.4.0 後樣式破壞 | 確認 `navbar-nav`, `sidebar-nav` 等 class 在 1.4.0 中仍有效 |
| **Dropdown 交互失效** | 菜單子項無法展開 | 檢查 Bootstrap JS 是否正確初始化 |
| **Z-index 衝突** | 菜單被其他元素覆蓋 | 檢查 Devtools 中的堆疊順序 |

---

## 🧪 診斷步驟

### A. 視覺檢查 (在瀏覽器中執行)

1. **打開開發工具** (F12)

2. **檢查菜單元素**：
   - Elements 標籤 → 找到 `<aside>` 或 `<div class="navbar-collapse">` 菜單容器
   - 檢查是否包含 `class="sidebar-nav"` 或 `class="navbar-nav"`

3. **檢查計算樣式**：
   - 右鍵菜單項 → Inspect Element
   - 在 Styles 面板檢查：
     ```
     color: var(--bs-body-color)
     background-color: var(--bs-body-bg) 或 var(--bs-bg-surface)  
     ```
   - 如果看到 `!important` 或硬編碼的顏色值，即表有問題

4. **切換主題並觀察變化**：
   - 點擊 Dark 主題按鈕
   - 观察 `<html data-bs-theme="dark">` 是否設置
   - 菜單顏色是否立即改變（不需要刷新）

### B. 控制台診斷腳本

在瀏覽器 Console (F12 → Console) 中執行以下命令：

```javascript
// 檢查主題狀態
console.log("Current theme:", document.documentElement.getAttribute("data-bs-theme"));
console.log("Stored theme:", localStorage.getItem("tabler-theme"));

// 檢查菜單元素
const sidebar = document.querySelector("aside.sidebar") || 
                document.querySelector("div.sidebar-nav") ||
                document.querySelector("div[id='navbar-menu']");
console.log("Menu element found:", sidebar ? "✅ Yes" : "❌ No");

// 檢查菜單計算樣式
if (sidebar) {
    const computedStyle = window.getComputedStyle(sidebar);
    console.log("Menu color:", computedStyle.color);
    console.log("Menu background:", computedStyle.backgroundColor);
    console.log("Menu border:", computedStyle.border);
}

// 檢查 Bootstrap CSS 變數  
const htmlStyle = window.getComputedStyle(document.documentElement);
console.log("--bs-body-color:", htmlStyle.getPropertyValue("--bs-body-color"));
console.log("--bs-body-bg:", htmlStyle.getPropertyValue("--bs-body-bg"));
console.log("--bs-bg-surface:", htmlStyle.getPropertyValue("--bs-bg-surface"));

// 測試主題切換
function testThemeToggle() {
    localStorage.setItem("tabler-theme", "dark");
    document.documentElement.setAttribute("data-bs-theme", "dark");
    console.log("Testing Dark mode...");
}
testThemeToggle();
```

**預期輸出示例**（Dark 模式）：
```
Current theme: dark ✅
Stored theme: dark ✅
Menu element found: ✅ Yes
Menu color: rgb(170, 176, 182)  [淺灰色，適合深色背景]
Menu background: rgb(10, 14, 39)  [深色背景]
--bs-body-color: rgb(170, 176, 182) ✅
--bs-body-bg: rgb(10, 14, 39) ✅
--bs-bg-surface: rgb(14, 18, 46) ✅
```

### C. 網路檢查

檢查 Tabler CSS 是否已正確加載 Tabler 1.4.0：

```javascript
// 檢查是否加載了 1.4.0 版本
const stylesheets = Array.from(document.styleSheets);
const tablerCSS = stylesheets.find(sheet => 
    sheet.href && sheet.href.includes("tabler.min.css")
);

if (tablerCSS) {
    console.log("Tabler CSS loaded:", tablerCSS.href);
    
    // 嘗試讀取 CSS 規則（如果允許 CORS）
    try {
        const rules = tablerCSS.cssRules || [];
        const darkRules = Array.from(rules).filter(rule => 
            rule.selectorText && rule.selectorText.includes("[data-bs-theme")
        );
        console.log("Dark theme CSS rules found:", darkRules.length > 0 ? "✅ Yes" : "❌ No");
    } catch (e) {
        console.log("CORS 限制，無法讀取 CSS 規則");
    }
}
```

---

## 🔧 可能的修復方案

### 如果菜單顏色不變（最可能的問題）

**原因**：菜單 HTML 可能使用了不支援 CSS 變數的舊 class 名稱

**解決方案**：在 `banner.html` 中添加一個強制刷新菜單樣式的腳本

```html
<script>
// 強制菜單樣式更新（當主題改變時）
function updateMenuStyle() {
    const menuItems = document.querySelectorAll(
        ".sidebar-nav a, .navbar-nav a, .dropdown-item"
    );
    menuItems.forEach(item => {
        // 強制重新計算樣式
        item.style.color = "";  // 清除 inline style，讓 CSS 變數生效
    });
}

// 監聽主題變更
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.attributeName === "data-bs-theme") {
            console.log("Theme changed, updating menu styles...");
            updateMenuStyle();
        }
    });
});

observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-bs-theme"]
});

// 初始化
updateMenuStyle();
</script>
```

### 如果菜單下拉無法展開（Dropdown 交互失效）

**可能原因**：Bootstrap JS 在主題切換後需要重新初始化

**解決方案**：確保 tabler.min.js 已在頁面中加載

```html
<!-- 在 scripts.html 中驗證 -->
<script src="/static/dist/js/tabler.min.js?1.4.0" defer></script>
```

### 如果只有某個特定元素有問題

**診斷方法**：在 DevTools 中檢查該元素的 CSS

```javascript
// 取得特定元素的所有相關 CSS
const element = document.querySelector(".your-problematic-element");
const computed = window.getComputedStyle(element);

// 檢查是否有 !important 覆蓋
const rulesArray = [];
for (let i = 0; i < document.styleSheets.length; i++) {
    try {
        const sheet = document.styleSheets[i];
        const rules = sheet.cssRules || sheet.rules;
        for (let j = 0; j < rules.length; j++) {
            const rule = rules[j];
            if (rule.selectorText && element.matches(rule.selectorText)) {
                rulesArray.push(rule.cssText);
            }
        }
    } catch (e) {
        // CORS 限制
    }
}

console.log("Applicable CSS rules:", rulesArray);
```

---

## 📊 菜單架構概覽

### 菜單在頁面中的位置

```mermaid
graph TD
    A["base.html") --> B{"layout == vertical?"}
    B -->|Yes| C["aside#navbar-menu<br/>(Sidebar Menu)<br/>g.mainmenu"]
    B -->|No| D["navbar-collapse<br/>(Horizontal Menu)<br/>g.mainmenu"]
    C --> E["navbar-nav<br/>menu items"]
    D --> E
```

### 菜單 CSS class 對應

| HTML元素 | CSS Class | Tabler 版本 | 備註 |
|---------|-----------|-----------|------|
| `<aside>` | `sidebar`, `sidebar-sticky` | 1.0.0-beta20 → 1.4.0 | ✅ 仍有支援 |
| `<nav>` | `navbar`, `navbar-expand-md` | 1.0.0-beta20 → 1.4.0 | ✅ 仍有支援 |
| `<ul>` | `navbar-nav`, `nav` | 1.0.0-beta20 → 1.4.0 | ✅ 仍有支援 |
| `<a>` | `nav-link`, `dropdown-toggle` | 1.0.0-beta20 → 1.4.0 | ✅ 仍有支援 |
| 下拉菜單 | `dropdown-menu`, `show` | 1.0.0-beta20 → 1.4.0 | ✅ Bootstrap 5 標準 |

**結論**：Tabler 1.4.0 保留了所有菜單相關的 CSS class，應該不會有結構性的破裂。

---

## 💡 最佳實踐建議

### 1. **立即反應的主題切換** (已實現 ✅)

菜單應在用戶點擊主題按鈕時立即改變，無需重新加載頁面：

```javascript
// ✅ 正確做法（已在 banner_scripts.html 中實現）
localStorage.setItem("tabler-theme", "dark");
document.documentElement.setAttribute("data-bs-theme", "dark");
window.history.replaceState({}, "", newUrl);  // 更新 URL 而不刷新
```

### 2. **避免 Flash of Wrong Color (FOWC)**

在 HTML `<head>` 中添加內聯腳本，在 CSS 加載前應用主題：

```html
<head>
    <!-- 必須在任何 CSS 之前 -->
    <script>
        const theme = localStorage.getItem('tabler-theme') || 'light';
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-bs-theme', 'dark');
        }
    </script>
    <!-- 現在加載 CSS -->
    <link href="/static/dist/css/tabler.min.css?1.4.0" rel="stylesheet" />
</head>
```

### 3. **確保菜單可訪問性**

在 Dark 模式下確保菜單項的文字對比度達到 WCAG AA 標準：

```javascript
// 測試對比度（使用 axe-core 或 Lighthouse）
function checkContrast(element) {
    const bg = window.getComputedStyle(element).backgroundColor;
    const fg = window.getComputedStyle(element).color;
    // 計算相對亮度和對比度比例
    // 需要使用專業工具如 WebAIM 對比度檢查器
}
```

---

## 📋 驗證清單

### 主題切換功能驗證

- [ ] 點擊 Dark 按鈕 → 頁面立即變深色（無頁面重新加載）
- [ ] 點擊 Light 按鈕 → 頁面立即變淺色（無頁面重新加載）
- [ ] 刷新頁面後主題保持不變 → 檢查 localStorage
- [ ] URL 包含 `?theme=dark` 或 `?theme=light` 參數
- [ ] 在 Dark 模式下菜單項清晰可見
- [ ] 菜單下拉功能正常（展開/收合）
- [ ] 菜單在 Mobile 響應式佈局下正常

### 菜單功能驗證

- [ ] 菜單項在 Light 模式下可點擊且清晰
- [ ] 菜單項在 Dark 模式下可點擊且清晰
- [ ] 菜單下拉菜單展開/收合
- [ ] 菜單項懸停樣式正確
- [ ] 菜單項活躍狀態（active）正確顯示
- [ ] Admin 菜單項在非 admin 用戶下隱藏
- [ ] 菜單寬度在 Vertical 和 Horizontal 佈局間切換無問題

### 跨瀏覽器驗證

- [ ] Chrome/Edge (Chromium) ✅
- [ ] Firefox
- [ ] Safari (macOS/iOS)

---

## 🔗 相關資源

- [Tabler 1.4.0 主題文檔](https://tabler.io/)
- [Bootstrap 5.3 黑暗模式](https://getbootstrap.com/docs/5.3/customize/color-modes/)
- [MDN - CSS Custom Properties (CSS Variables)](https://developer.mozilla.org/en-US/docs/Web/CSS/--*)

---

**下一步**：執行上述診斷步驟，將結果報告後可進一步優化或修復菜單問題。

