// Switch between the tabs (To-Do / Library, and Books / Authors) without
// reloading the page: the content changes in place, like the tabs of a phone app.
//
// - The pill under the active tab slides to the new one (CSS transition on
//   data-active, see .tabs-indicator in style.css).
// - The new panel slides in from the side we are moving to.
// - The address changes too (/todos, /library, /library?view=authors), so
//   Refresh and the Back button keep working.
// Without JavaScript the tabs are normal links and everything still works.

const mainTabs = document.querySelector('[data-tabs="main"]');
const libraryTabs = document.querySelector('[data-tabs="library"]');
const panels = document.querySelector(".panels");

function setActiveTab(nav, name) {
    nav.dataset.active = name;

    nav.querySelectorAll(".tab").forEach(function (tab) {
        if (tab.dataset.tab === name) {
            tab.setAttribute("aria-current", "page");
        } else {
            tab.removeAttribute("aria-current");
        }
    });
}

function tabNames(nav) {
    return Array.from(nav.querySelectorAll(".tab")).map(function (tab) {
        return tab.dataset.tab;
    });
}

// Hide the old panel and show the new one with a short slide.
// direction > 0: the new tab is on the right, so it comes from the right.
function swapPanels(container, attribute, from, to, direction) {
    const oldPanel = container.querySelector("[" + attribute + '="' + from + '"]');
    const newPanel = container.querySelector("[" + attribute + '="' + to + '"]');

    if (!oldPanel || !newPanel) {
        return false;
    }

    oldPanel.hidden = true;
    newPanel.hidden = false;

    newPanel.classList.remove("enter-forward", "enter-back");
    void newPanel.offsetWidth; // restart the animation if it already ran
    newPanel.classList.add(direction > 0 ? "enter-forward" : "enter-back");

    return true;
}

// A normal click only: Ctrl/Cmd/Shift/middle click still opens a new tab.
function isPlainClick(event) {
    return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey;
}

function currentAddress() {
    return location.pathname + location.search;
}


if (mainTabs && panels) {
    const order = tabNames(mainTabs);

    // Where each tab was last time, so coming back keeps its filter or view.
    const lastAddress = {};
    mainTabs.querySelectorAll(".tab").forEach(function (tab) {
        lastAddress[tab.dataset.tab] = tab.getAttribute("href");
    });
    lastAddress[mainTabs.dataset.active] = currentAddress();

    function showMainTab(name, addToHistory) {
        const current = mainTabs.dataset.active;
        if (name === current) {
            return;
        }

        lastAddress[current] = currentAddress();
        setActiveTab(mainTabs, name);
        swapPanels(panels, "data-panel", current, name, order.indexOf(name) - order.indexOf(current));

        const tab = mainTabs.querySelector('[data-tab="' + name + '"]');
        document.title = tab.dataset.title + " - Workspace";

        if (addToHistory) {
            history.pushState({ tab: name }, "", lastAddress[name]);
        }

        window.scrollTo(0, 0);
    }

    mainTabs.addEventListener("click", function (event) {
        const tab = event.target.closest(".tab");
        if (!tab || !isPlainClick(event)) {
            return;
        }

        event.preventDefault();
        showMainTab(tab.dataset.tab, true);
    });

    window.showMainTab = showMainTab;
}


if (libraryTabs) {
    const order = tabNames(libraryTabs);
    const container = libraryTabs.closest(".card");

    function showLibraryView(name, addToHistory) {
        const current = libraryTabs.dataset.active;
        if (name === current) {
            return;
        }

        setActiveTab(libraryTabs, name);
        swapPanels(container, "data-subpanel", current, name, order.indexOf(name) - order.indexOf(current));

        if (addToHistory) {
            const tab = libraryTabs.querySelector('[data-tab="' + name + '"]');
            history.pushState({ tab: "library", view: name }, "", tab.getAttribute("href"));
        }
    }

    libraryTabs.addEventListener("click", function (event) {
        const tab = event.target.closest(".tab");
        if (!tab || !isPlainClick(event)) {
            return;
        }

        event.preventDefault();
        showLibraryView(tab.dataset.tab, true);
    });

    window.showLibraryView = showLibraryView;
}


// Back / Forward: show the tab that matches the address.
window.addEventListener("popstate", function () {
    const onLibrary = location.pathname.indexOf("/library") === 0;

    if (window.showMainTab) {
        window.showMainTab(onLibrary ? "library" : "todos", false);
    }

    if (onLibrary && window.showLibraryView) {
        const view = new URLSearchParams(location.search).get("view");
        window.showLibraryView(view === "authors" ? "authors" : "books", false);
    }
});
