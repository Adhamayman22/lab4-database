// The light / dark button.
// The choice is saved in this browser (localStorage) and put on <html> as
// data-theme="light" or "dark"; style.css picks the colours from it.
// A small script in base.html applies the saved choice before the page is
// drawn, so it never flashes in the wrong colours.
// With no saved choice the site follows the system setting.

const THEME_KEY = "theme";
const root = document.documentElement;
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

function currentTheme() {
    if (root.dataset.theme === "light" || root.dataset.theme === "dark") {
        return root.dataset.theme;
    }
    return systemDark.matches ? "dark" : "light";
}

function updateThemeButtons() {
    const theme = currentTheme();
    const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";

    document.querySelectorAll(".theme-toggle").forEach(function (button) {
        button.dataset.current = theme; // CSS shows the sun in dark mode, the moon in light mode
        button.setAttribute("aria-label", label);
        button.title = label;
        button.hidden = false;
    });
}

function setTheme(theme) {
    // Fade all the colours for a moment instead of switching at once.
    root.classList.add("theme-changing");
    root.dataset.theme = theme;

    try {
        localStorage.setItem(THEME_KEY, theme);
    } catch (error) {
        // private window or blocked storage: the choice lasts until the page closes
    }

    updateThemeButtons();
    setTimeout(function () {
        root.classList.remove("theme-changing");
    }, 400);
}

document.querySelectorAll(".theme-toggle").forEach(function (button) {
    button.addEventListener("click", function () {
        setTheme(currentTheme() === "dark" ? "light" : "dark");
    });
});

// If the system changes while nothing was picked, the icon follows it.
systemDark.addEventListener("change", updateThemeButtons);

updateThemeButtons();
