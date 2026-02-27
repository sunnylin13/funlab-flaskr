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
