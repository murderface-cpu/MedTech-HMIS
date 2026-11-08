document.addEventListener("DOMContentLoaded", () => {

    // section display
    const section_togglers = document.querySelectorAll(".section-togglers")

    function showSection(activator) {
        if (activator.dataset.modal != null || activator.disabled) {
            return
        }
        let sectionToShow = document.querySelector(`#${activator.dataset.section}`)
        if (!sectionToShow) {
            return
        }

        section_togglers.forEach(toggler => {
            toggler.classList.remove("is-active")
            toggler.setAttribute("aria-selected", "false")
        })
        activator.classList.add("is-active")
        activator.setAttribute("aria-selected", "true")

        // close open sections
        let openSections = document.querySelectorAll(".variable-section.inview");
        openSections.forEach(section => section.classList.remove("inview"))

        sectionToShow.classList.add("inview")
        document.dispatchEvent(new CustomEvent("tabshown", { detail: { tab: activator.dataset.section } }))

        // remember the open tab so it stays open after a form is submitted
        if (activator.dataset.section && document.body.dataset.rememberTab !== undefined) {
            document.querySelectorAll("form input[name='tab']")
                .forEach(input => input.value = activator.dataset.section)
            const url = new URL(window.location.href);
            url.searchParams.set("tab", activator.dataset.section);
            window.history.replaceState(null, "", url);
        }
    }

    section_togglers.forEach(
        activator => activator.addEventListener("click", () => showSection(activator))
    )

    // open the tab named in the url (?tab=), or the one marked as default
    const requestedTab = new URLSearchParams(window.location.search).get("tab") || document.body.dataset.initialTab
    const initialToggler = (requestedTab && document.querySelector(`.section-togglers[data-section="${CSS.escape(requestedTab)}"]`))
        || document.querySelector(".section-togglers[data-default]")
    if (initialToggler) {
        showSection(initialToggler)
    }

    const test_togglers = document.querySelectorAll(".test-togglers")
    test_togglers.forEach(
        activator => activator.addEventListener("click", () => {
            let testToShow = document.querySelector(`#${activator.dataset.test}`)

            test_togglers.forEach(toggler => toggler.classList.remove("is-active"))
            activator.classList.add("is-active")

            // close open tests
            let openTests = document.querySelectorAll(".variable-test.inview");
            openTests.forEach(test => test.classList.remove("inview"))

            testToShow.classList.add("inview")
        })
    )

    const section_part_toggler = document.querySelectorAll(".section-part-toggler")
    section_part_toggler.forEach(
        activator => activator.addEventListener("click", () => {
            let sectionToShow = document.querySelector(`#${activator.dataset.section}`)

            // close the open part of the same section
            const scope = sectionToShow.closest(".variable-section") || document
            let openSections = scope.querySelectorAll(".variable-section-part.inview");
            openSections.forEach(section => section.classList.remove("inview"))
            scope.querySelectorAll(".section-part-toggler").forEach(toggler => toggler.classList.toggle("is-active", toggler === activator))

            sectionToShow.classList.add("inview")
        })
    )

    // tables rendered on the server
    document.querySelectorAll("table.datatable").forEach(table => {
        $(table).DataTable({ order: [], language: tableLanguage(table) })
    })

    // rows that open a record
    document.addEventListener("click", event => {
        const row = event.target.closest("tr[data-href]")
        if (row && !event.target.closest("a, button, input, select, textarea, label")) {
            window.location.href = row.dataset.href
        }
    })

    // forms that ask before doing something irreversible
    document.querySelectorAll("form[data-confirm]").forEach(form => {
        form.addEventListener("submit", event => {
            if (!window.confirm(form.dataset.confirm)) {
                event.preventDefault()
            }
        })
    })

    // sidebar
    document.querySelectorAll("[data-action='sign-out']").forEach(button => {
        button.addEventListener("click", () => document.querySelector("#logout_form").submit())
    })
    document.querySelectorAll("[data-action='focus-search']").forEach(button => {
        button.addEventListener("click", () => {
            const search = [...document.querySelectorAll(".dataTables_filter input")]
                .find(input => input.offsetParent !== null)
            if (search) search.focus()
        })
    })

    // a header checkbox that ticks every checkbox of the same name in its form
    document.querySelectorAll("[data-check-all]").forEach(master => {
        master.addEventListener("change", () => {
            master.form.querySelectorAll(`input[type='checkbox'][name='${master.dataset.checkAll}']`)
                .forEach(box => box.checked = master.checked)
        })
    })

    document.querySelectorAll("[data-action='print']").forEach(button => {
        button.addEventListener("click", () => window.print())
    })
})

// Shared wording for every DataTable: a labelled search box and an empty state that says what is missing
function tableLanguage(table) {
    return {
        search: "",
        searchPlaceholder: "Search this table",
        lengthMenu: "Show _MENU_ rows",
        info: "_START_ to _END_ of _TOTAL_",
        infoEmpty: "",
        infoFiltered: "(filtered from _MAX_)",
        zeroRecords: "No records match your search.",
        emptyTable: (table && table.dataset.empty) || "No records yet.",
        paginate: { previous: "Previous", next: "Next" },
    }
}

// Behaviours of the 2026-11 pages: filters that apply at once, live worklists, in-row forms, note templates
document.addEventListener("DOMContentLoaded", () => {
    // a choice that applies as soon as it is made (period, month, insurer)
    document.querySelectorAll("[data-auto-submit]").forEach(control => {
        control.addEventListener("change", () => {
            const form = control.form
            if (!form) return
            // a preset period replaces any custom dates
            if (control.name === "period") form.querySelectorAll("input[type='date']").forEach(input => input.value = "")
            form.requestSubmit ? form.requestSubmit() : form.submit()
        })
    })

    // worklists that refresh themselves, unless someone is typing or a row form is open
    const refresh = parseInt(document.body.dataset.autoRefresh || "0", 10)
    if (refresh > 0) {
        let dirty = false
        document.addEventListener("input", () => { dirty = true })
        setInterval(() => {
            const busy = dirty || document.querySelector(".row-popover[open]") || document.hidden
                || (document.activeElement && document.activeElement.matches("input, select, textarea"))
            if (!busy) window.location.reload()
        }, refresh * 1000)
    }

    // one in-row form open at a time; Escape or a click elsewhere closes it
    const popovers = document.querySelectorAll(".row-popover")
    popovers.forEach(popover => {
        popover.addEventListener("toggle", () => {
            if (!popover.open) return
            popovers.forEach(other => { if (other !== popover) other.open = false })
            const first = popover.querySelector("input:not([type='hidden']), select, textarea")
            if (first) first.focus()
        })
    })
    document.addEventListener("keydown", event => {
        if (event.key !== "Escape") return
        document.querySelectorAll(".row-popover[open]").forEach(popover => {
            popover.open = false
            popover.querySelector("summary").focus()
        })
    })
    document.addEventListener("click", event => {
        document.querySelectorAll(".row-popover[open]").forEach(popover => {
            if (!popover.contains(event.target)) popover.open = false
        })
    })

    // note templates: a select whose chosen wording is added to a field
    document.querySelectorAll("select[data-insert-into]").forEach(select => {
        select.addEventListener("change", () => {
            const field = document.getElementById(select.dataset.insertInto)
            if (!field || !select.value) return
            field.value = field.value.trim() ? `${field.value.trim()}\n${select.value}` : select.value
            field.dispatchEvent(new Event("input", { bubbles: true }))
            field.focus()
            select.value = ""
        })
    })
})
