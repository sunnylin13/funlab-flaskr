# 菜單問題快速診斷

如果在 Dark/Light 主題切換後發現菜單不工作，請按以下步驟快速診斷：

---

## 🚀 一鍵診斷 (複制粘貼到瀏覽器 Console)

打開瀏覽器開發工具 (F12) → Console 標籤 → 複制粘貼以下代碼：

```javascript
// ============================================
// FunLab Dark Theme Menu Diagnostic Tool v1.0
// 一鍵診斷主題和菜單問題
// ============================================

console.group("🔍 FunLab Theme Menu Diagnostic Report");

// 1. 主題狀態檢查
console.group("1️⃣ Theme Status");
const currentTheme = document.documentElement.getAttribute("data-bs-theme");
const storedTheme = localStorage.getItem("tabler-theme");
console.log("✓ Current theme (HTML attribute):", currentTheme || "light [default]");
console.log("✓ Stored theme (localStorage):", storedTheme || "light [default]");
console.groupEnd();

// 2. 菜單元素檢查
console.group("2️⃣ Menu Elements");
const sidebar = document.querySelector("aside");
const navbar = document.querySelector(".navbar-collapse");
const navItems = document.querySelectorAll(".nav-link");
const dropdownItems = document.querySelectorAll(".dropdown-item");

console.log("✓ Sidebar found:", sidebar ? "✅ Yes" : "❌ No");
console.log("✓ Navbar collapse found:", navbar ? "✅ Yes" : "❌ No");
console.log("✓ Navigation items found:", navItems.length, "items");
console.log("✓ Dropdown items found:", dropdownItems.length, "items");

if (sidebar) {
    console.log("  - Sidebar HTML:", sidebar.outerHTML.substring(0, 150) + "...");
}
console.groupEnd();

// 3. CSS 變數檢查
console.group("3️⃣ CSS Custom Properties");
const htmlStyle = window.getComputedStyle(document.documentElement);
const cssVars = {
    "color": htmlStyle.getPropertyValue("--bs-body-color").trim(),
    "bg": htmlStyle.getPropertyValue("--bs-body-bg").trim(),
    "surface": htmlStyle.getPropertyValue("--bs-bg-surface").trim(),
    "border": htmlStyle.getPropertyValue("--bs-border-color").trim()
};

console.log("✓ CSS Variables (active):");
Object.entries(cssVars).forEach(([key, val]) => {
    console.log(`  --bs-${key === "color" ? "body-color" : key === "bg" ? "body-bg" : key === "surface" ? "bg-surface" : "border-color"}: ${val || "❌ not set"}`);
});
console.groupEnd();

// 4. 菜單計算樣式檢查
console.group("4️⃣ Menu Computed Styles");
const testMenuLink = document.querySelector(".nav-link:first-of-type") || document.querySelector("a.dropdown-item:first-of-type");
if (testMenuLink) {
    const computed = window.getComputedStyle(testMenuLink);
    console.log("✓ Sample menu link styles:");
    console.log("  color:", computed.color);
    console.log("  background:", computed.backgroundColor);
    console.log("  padding:", computed.padding);
    console.log("  display:", computed.display);
    console.log("  visibility:", computed.visibility);
} else {
    console.log("❌ No menu link found to test");
}
console.groupEnd();

// 5. Bootstrap JS 檢查
console.group("5️⃣ Bootstrap Interaction");
const tablerScript = Array.from(document.scripts).find(s => s.src.includes("tabler") && s.src.includes(".js"));
const bootstrapScript = Array.from(document.scripts).find(s => s.src.includes("bootstrap") && s.src.includes(".js"));

console.log("✓ Tabler JS loaded:", tablerScript ? "✅ Yes (" + tablerScript.src + ")" : "❌ No");
console.log("✓ Bootstrap JS loaded:", bootstrapScript ? "✅ Yes" : "⚠️ May be included in Tabler");

// 測試 dropdown 功能
const dropdownTest = document.querySelector("[data-bs-toggle='dropdown']");
if (dropdownTest) {
    console.log("✓ Dropdown element found (can be toggled)");
    // 嘗試取得 Bootstrap 實例
    try {
        const bsDropdown = bootstrap.Dropdown.getInstance(dropdownTest);
        console.log("  Bootstrap Dropdown instance:", bsDropdown ? "✅ Active" : "⚠️ Not active");
    } catch (e) {
        console.log("  ⚠️ Bootstrap global not available");
    }
}
console.groupEnd();

// 6. 颜色对比度检查 (Dark mode)
console.group("6️⃣ Dark Mode Contrast Check");
if (currentTheme === "dark") {
    const bodyColor = cssVars.color;
    const bodyBg = cssVars.bg;
    
    // 簡單的對比度評估
    console.log("✓ Text color (dark mode):", bodyColor);
    console.log("✓ Background (dark mode):", bodyBg);
    console.log("  💡 Tip: Use WebAIM Contrast Checker to verify WCAG AA compliance");
    console.log("     https://webaim.org/resources/contrastchecker/");
} else {
    console.log("⏭️ Skipped (Not in dark mode)");
}
console.groupEnd();

// 7. 快速修復建議
console.group("7️⃣ Quick Fixes");
const issues = [];

if (!currentTheme && currentTheme !== "dark") {
    issues.push("Light mode 正在使用（可能需要切換到 Dark 測試）");
}
if (!storedTheme) {
    issues.push("localStorage 未設置主題 - 可手動設置：localStorage.setItem('tabler-theme', 'dark')");
}
if (!sidebar && !navbar) {
    issues.push("❌ 找不到菜單元素 - 檢查 HTML 結構");
}
if (navItems.length === 0 && dropdownItems.length === 0) {
    issues.push("❌ 找不到任何菜單項 - 檢查權限或菜單配置");
}

if (issues.length === 0) {
    console.log("✅ 未發現已知問題 - 菜單應該正常工作");
} else {
    console.log("⚠️ Potential Issues:");
    issues.forEach((issue, idx) => console.log(`  ${idx + 1}. ${issue}`));
}
console.groupEnd();

console.log("\n📝 Complete diagnostic report generated above.");
console.log("💡 If issues persist, scroll up to view details.");

console.groupEnd();
```

---

## 🧪 運行後的預期結果

### ✅ 正常情況 (一切正常)

```
✓ Current theme (HTML attribute): dark
✓ Stored theme (localStorage): dark
✓ Sidebar found: ✅ Yes
✓ Navigation items found: 15 items
✓ CSS Variables (active):
  --bs-body-color: rgb(170, 176, 182)
  --bs-body-bg: rgb(10, 14, 39)
✓ Sample menu link styles:
  color: rgb(170, 176, 182)
  background: rgba(0, 0, 0, 0)
✅ 未發現已知問題 - 菜單應該正常工作
```

### ❌ 問題情況 1 - 菜單看不見 (顏色對比問題)

```
✓ color: rgb(0, 0, 0)  ← 黑色文字
✓ background: rgb(10, 14, 39)  ← 深色背景
```

**診斷**：在深色背景上使用黑色文字，對比度完全不足

**修復**：添加 CSS 覆蓋（在 banner.html 的 `<style>` 中）：
```css
html[data-bs-theme="dark"] .nav-link,
html[data-bs-theme="dark"] .dropdown-item {
    color: var(--bs-body-color) !important;
}
```

### ❌ 問題情況 2 - Dropdown 無法展開

```
✓ Dropdown element found (can be toggled)
  Bootstrap Dropdown instance: ⚠️ Not active
```

**診斷**：Bootstrap Dropdown 沒有被初始化

**修復**：確保按順序加載：
1. tabler.min.css
2. tabler.min.js (defer 屬性)

---

## 🔧 根據診斷結果的修復

### 情況 A：主題未被應用

```javascript
// 在 Console 中手動應用
localStorage.setItem('tabler-theme', 'dark');
document.documentElement.setAttribute('data-bs-theme', 'dark');

// 重新整理頁面
location.reload();
```

### 情況 B：菜單找不到

```javascript
// 檢查 g.mainmenu 是否正確輸出
const menuHTML = document.querySelector('aside') || 
                 document.querySelector('[id*="navbar-menu"]');
console.log(menuHTML ? "✅ Menu HTML present" : "❌ Menu missing");
```

### 情況 C：菜單項無法點擊

```javascript
// 檢查是否有覆蓋樣式
const menuLink = document.querySelector('.nav-link');
const styles = window.getComputedStyle(menuLink);
console.log("pointer-events:", styles.pointerEvents);  // 應該是 'auto'
console.log("display:", styles.display);  // 應該不是 'none'
```

---

## 📊 完整檢查清單

執行診斷後，檢查以下項目：

- [ ] **主題應用**：`Current theme` 和 `Stored theme` 相符
- [ ] **菜單存在**：Sidebar 或 Navbar collapse 找到
- [ ] **菜單項數量**：Navigation items ≥ 1
- [ ] **CSS 變數**：所有 `--bs-*` 值都已設置（不是空）
- [ ] **對比度**：文字和背景顏色值完全不同
- [ ] **Bootstrap 互動**：Dropdown instance 已激活
- [ ] **無已知問題**：修復列表為空或為綠色 ✅

---

## 📞 如果故障排除無效

請報告以下信息：

1. **診斷輸出**：上面運行腳本後的完整 console 輸出
2. **瀏覽器**：Chrome 版本 (或其他)
3. **修復步驟**：您已嘗試的修復
4. **屏幕截圖**：Dark 和 Light 模式的菜單截圖

---

**最後更新**：2025-02-27  
**支持的 Tabler 版本**：1.4.0+  
**支持的瀏覽器**：Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
