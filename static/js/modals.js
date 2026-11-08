document.addEventListener("DOMContentLoaded", () => {

    // buttons that open a modal named in data-modal
    document.querySelectorAll(".modal-activators").forEach(
        activator => activator.addEventListener("click", () => openModal(activator.dataset.modal))
    )

    document.querySelectorAll(".modal").forEach(modal => {
        modal.querySelectorAll("[data-close-modal]").forEach(
            button => button.addEventListener("click", () => closeModal(modal))
        )
        // modals saved through javascript must not reload the page when Enter is pressed
        modal.querySelectorAll("form:not([method])").forEach(
            form => form.addEventListener("submit", event => event.preventDefault())
        )
    })

    // Escape closes the open dialog
    document.addEventListener("keydown", event => {
        const open = document.querySelector(".modal.inview")
        if (event.key === "Escape" && open) closeModal(open)
    })

    // Billing: show the company field that matches the selected billing mode
    document.querySelectorAll("#billing_methods").forEach(select => {
        select.addEventListener("change", () => updateBillingCompanyFields(select))
        updateBillingCompanyFields(select)
    })
})

function updateBillingCompanyFields(select) {
    const option = select.selectedOptions[0]
    const kind = option ? option.dataset.kind : null
    const scope = select.closest(".modal") || document
    scope.querySelectorAll("[data-billing-kind]").forEach(field => {
        field.classList.toggle("visibility-hidden", field.dataset.billingKind !== kind)
    })
}

function openModal(modalOrId, action="create") {
    const modalToOpen = typeof modalOrId === "string" ? document.querySelector(`#${modalOrId}`) : modalOrId;

    // close open modals
    document.querySelectorAll(".modal.inview").forEach(modal => modal.classList.remove("inview"));

    modalToOpen.classList.add("inview");
    modalToOpen.dataset.action = action

    const title = modalToOpen.querySelector(".modal-title")
    if (title && title.dataset[`${action}Title`]) {
        title.textContent = title.dataset[`${action}Title`]
    }

    // move focus into the dialog, and remember where to return it on close
    modalToOpen.returnFocus = document.activeElement
    const first = modalToOpen.querySelector(".modal-body input:not([type=hidden]):not([type=file]), .modal-body select, .modal-body textarea") || modalToOpen.querySelector("[data-close-modal]")
    if (first) first.focus({ preventScroll: true })
    return modalToOpen
}

function closeModal(modal) {
    // forget the record the modal was editing
    Object.keys(modal.dataset).forEach(attribute => delete modal.dataset[attribute])
    modal.querySelectorAll("form").forEach(form => form.reset())
    modal.querySelectorAll(".error").forEach(elem => elem.classList.remove("error"))
    modal.querySelectorAll("[data-billing-kind]").forEach(field => field.classList.add("visibility-hidden"))
    modal.classList.remove("inview");
    if (modal.returnFocus && document.contains(modal.returnFocus)) modal.returnFocus.focus()
    modal.returnFocus = null
}

// Marks empty required fields; returns true when all are filled in
function validateRequired(fields) {
    let valid = true
    fields.forEach(field => {
        const empty = field.value === "" || field.value === undefined || field.value === null
        field.classList.toggle("error", empty)
        if (empty) valid = false
    })
    return valid
}
