// Application menu: page filter, planned-pages toggle, remembered workspaces, the narrow-screen
// drawer, and keeping the current page in step with the tab open on the page.
document.addEventListener("DOMContentLoaded", () => {
    const nav = document.querySelector("#app-nav")
    if (!nav) return

    const HIDE_PLANNED_KEY = "medsafe.hidePlanned"
    const OPEN_WORKSPACES_KEY = "medsafe.openWorkspaces"
    const workspaces = [...nav.querySelectorAll(".nav-workspace")]
    const pageLinks = [...nav.querySelectorAll("a.nav-page")]
    const filterInput = nav.querySelector("[data-nav-filter]")
    const breadcrumb = {
        workspace: document.querySelector("[data-breadcrumb-workspace]"),
        section: document.querySelector("[data-breadcrumb-section]"),
        title: document.querySelector("[data-page-title]"),
    }

    // Workspaces opened by hand stay open on the next page; the current one is always open
    const readOpen = () => {
        try { return JSON.parse(localStorage.getItem(OPEN_WORKSPACES_KEY)) || [] } catch { return [] }
    }
    const remembered = new Set(readOpen())
    workspaces.forEach(workspace => {
        if (remembered.has(workspace.dataset.workspace)) workspace.open = true
        workspace.addEventListener("toggle", () => {
            if (filterInput.value) return
            const open = new Set(readOpen())
            workspace.open ? open.add(workspace.dataset.workspace) : open.delete(workspace.dataset.workspace)
            localStorage.setItem(OPEN_WORKSPACES_KEY, JSON.stringify([...open]))
        })
    })
    nav.querySelector(".nav-workspace[data-current]")?.querySelector("[aria-current='page']")
        ?.scrollIntoView({ block: "nearest" })

    // Planned pages
    const plannedToggle = nav.querySelector("[data-toggle-planned]")
    plannedToggle.checked = !document.documentElement.classList.contains("hide-planned")
    plannedToggle.addEventListener("change", () => {
        document.documentElement.classList.toggle("hide-planned", !plannedToggle.checked)
        localStorage.setItem(HIDE_PLANNED_KEY, plannedToggle.checked ? "0" : "1")
    })

    // Page filter: matches page, section and workspace names; Enter opens the first live match
    const openBeforeFilter = new Map()
    function applyFilter() {
        const query = filterInput.value.trim().toLowerCase()
        if (query && openBeforeFilter.size === 0) {
            workspaces.forEach(workspace => openBeforeFilter.set(workspace, workspace.open))
        }
        let matches = 0
        workspaces.forEach(workspace => {
            let workspaceMatches = 0
            workspace.querySelectorAll(".nav-section").forEach(section => {
                let sectionMatches = 0
                section.querySelectorAll("li").forEach(item => {
                    const haystack = `${item.textContent} ${section.querySelector(".nav-section-label").textContent} ${workspace.dataset.workspace}`.toLowerCase()
                    const hit = !query || haystack.includes(query)
                    item.toggleAttribute("data-filtered-out", !hit)
                    if (hit) sectionMatches++
                })
                section.toggleAttribute("data-filtered-out", sectionMatches === 0)
                workspaceMatches += sectionMatches
            })
            workspace.toggleAttribute("data-filtered-out", workspaceMatches === 0)
            if (query) workspace.open = workspaceMatches > 0
            matches += workspaceMatches
        })
        nav.querySelector("[data-nav-empty]").hidden = matches > 0 || !query
        if (!query && openBeforeFilter.size) {
            openBeforeFilter.forEach((open, workspace) => workspace.open = open)
            openBeforeFilter.clear()
        }
    }
    filterInput.addEventListener("input", applyFilter)
    filterInput.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            const first = pageLinks.find(link => !link.closest("[data-filtered-out]"))
            if (first) first.click()
        } else if (event.key === "Escape") {
            filterInput.value = ""
            applyFilter()
            filterInput.blur()
        }
    })
    document.addEventListener("keydown", event => {
        const typing = event.target.closest("input, textarea, select, [contenteditable]")
        if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
            event.preventDefault()
            openDrawer()
            filterInput.focus()
        }
    })

    // The current page follows the tab shown on the page
    function markCurrent(tab) {
        const link = pageLinks.find(candidate => candidate.dataset.path === window.location.pathname && candidate.dataset.tab === tab)
        if (!link) return
        pageLinks.forEach(candidate => candidate.removeAttribute("aria-current"))
        link.setAttribute("aria-current", "page")
        if (breadcrumb.workspace) {
            breadcrumb.workspace.textContent = link.dataset.workspace
            breadcrumb.section.textContent = link.dataset.sectionLabel
        }
        if (breadcrumb.title) breadcrumb.title.textContent = link.querySelector(".nav-page-label").textContent
    }
    document.addEventListener("tabshown", event => markCurrent(event.detail.tab))

    // A link to another tab of the open page switches tab without reloading
    pageLinks.forEach(link => link.addEventListener("click", event => {
        if (link.dataset.path !== window.location.pathname || !link.dataset.tab) return
        const toggler = document.querySelector(`.section-togglers[data-section="${CSS.escape(link.dataset.tab)}"]`)
        if (!toggler || toggler.disabled) return
        event.preventDefault()
        toggler.click()
        const url = new URL(window.location.href)
        url.searchParams.set("tab", link.dataset.tab)
        window.history.replaceState(null, "", url)
        closeDrawer()
    }))

    // Narrow screens: the menu is a drawer
    const openButton = document.querySelector("[data-action='open-nav']")
    function openDrawer() {
        if (getComputedStyle(openButton).display === "none") return
        document.body.classList.add("nav-open")
        openButton.setAttribute("aria-expanded", "true")
    }
    function closeDrawer() {
        if (!document.body.classList.contains("nav-open")) return
        document.body.classList.remove("nav-open")
        openButton.setAttribute("aria-expanded", "false")
    }
    openButton.addEventListener("click", () => {
        openDrawer()
        filterInput.focus()
    })
    document.querySelector("[data-action='close-nav']").addEventListener("click", () => {
        closeDrawer()
        openButton.focus()
    })
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
            closeDrawer()
            openButton.focus()
        }
    })
})
