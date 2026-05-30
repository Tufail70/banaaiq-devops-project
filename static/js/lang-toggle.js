document.addEventListener("DOMContentLoaded", () => {
    const html = document.documentElement;
    const toggle = document.getElementById("lang-toggle");
    const toggleText = document.getElementById("lang-toggle-text");

    if (!toggle || !toggleText) {
        return;
    }

    const currentLang = html.getAttribute("lang") || "en";
    toggleText.textContent = currentLang === "en" ? "العربية" : "English";

    toggle.addEventListener("mouseenter", () => {
        toggleText.textContent = currentLang === "en" ? "العربية" : "English";
    });
});
