// Doctor's workspace: select an active visit, then record findings and place orders for it

const doctorState = { visit: null }

const visitId = () => doctorState.visit.id

function formValues(form) {
    const values = {}
    form.querySelectorAll("[name]").forEach(field => {
        values[field.name] = typeof field.value === "string" ? field.value.trim() : field.value
    })
    return values
}

function fillForm(form, record) {
    form.querySelectorAll("[name]").forEach(field => {
        const value = record ? record[field.name] : null
        field.value = value === null || value === undefined ? "" : value
    })
}

function fillSelect(select, records, label, extra=() => ({})) {
    const placeholder = select.querySelector("option[value='']")
    select.innerHTML = ""
    if (placeholder) select.appendChild(placeholder)
    records.forEach(record => {
        const option = document.createElement("option")
        option.value = record.id
        option.textContent = label(record)
        Object.entries(extra(record)).forEach(([key, value]) => option.dataset[key] = value)
        select.appendChild(option)
    })
}

// Renders records with one function per column; adds a delete button when onDelete is given
function renderRecords(tableId, records, columns, {onSelect=null, onDelete=null, canDelete=() => true}={}) {
    const table = document.querySelector(`table#${tableId}`)
    if ($.fn.DataTable.isDataTable(table)) {
        $(table).DataTable().destroy()
    }
    const body = table.querySelector("tbody")
    body.innerHTML = ""
    records.forEach(record => {
        const row = document.createElement("tr")
        columns.forEach(column => {
            const cell = document.createElement("td")
            const value = column(record)
            cell.textContent = value === null || value === undefined ? "" : value
            row.appendChild(cell)
        })
        if (onDelete) {
            const cell = document.createElement("td")
            if (canDelete(record)) {
                const button = document.createElement("button")
                button.type = "button"
                button.textContent = "Remove"
                button.addEventListener("click", () => {
                    if (window.confirm("Remove this record?")) onDelete(record)
                })
                cell.appendChild(button)
            }
            row.appendChild(cell)
        }
        if (onSelect) {
            row.style.cursor = "pointer"
            row.addEventListener("click", event => {
                if (event.target.closest("button")) return
                body.querySelectorAll("tr.selected").forEach(selected => selected.classList.remove("selected"))
                row.classList.add("selected")
                onSelect(record)
            })
        }
        body.appendChild(row)
    })
    $(table).DataTable({ order: [], language: tableLanguage(table) })
}

async function guarded(action) {
    try {
        return await action()
    } catch (error) {
        showError(error)
    }
}

// ------------------------------------------------------------------ visits

async function loadVisits() {
    clearPreview()
    const mine = document.querySelector("#my_patients_only")
    const filter = mine && mine.checked ? "&mine=1" : ""
    const records = await fetchAll(`${api_routes.visits_list}?page_size=100${filter}`)
    renderTable("visitsTable", records, ["patientID", "patient", "category", "Speciality", "Doctor", "complete", "visit_date"], selectVisit)
}

function setVisitTabs(enabled) {
    document.querySelectorAll(".section-togglers[data-needs-visit]").forEach(toggler => {
        toggler.disabled = !enabled
        toggler.classList.toggle("disabled", !enabled)
    })
}

function showVisitPreview(visit) {
    showPreview([
        ["Patient ID:", visit.patient.patient_id],
        ["Full Name:", visit.patient.fullname],
        ["Gender:", visit.patient.gender],
        ["Age:", visit.patient.age],
        ["Visit:", visit.visit_id],
        ["Category:", visit.category.name],
        ["Doctor:", visit.Doctor || "Not assigned"],
        ["Billing:", visit.billing_label || "Not set"],
        ["Visit Date:", formatDateTime(visit.visit_date)],
    ], [{ label: "Complete visit", onClick: completeVisit }])
}

function selectVisit(visit) {
    doctorState.visit = visit
    setVisitTabs(true)
    showVisitPreview(visit)
    loadTriage()
    loadAllergies()
    findingBooks.forEach(book => book.load())
    loadDiagnosis()
    loadPrescriptions()
    loadLabRequests()
    document.querySelectorAll("[data-service-category]").forEach(section => loadServiceOrders(section))
    document.querySelectorAll("[data-department]").forEach(section => loadDepartmentRequests(section))
}

async function completeVisit() {
    if (!window.confirm(`Mark visit ${doctorState.visit.visit_id} as complete? It will leave the active visits list.`)) return
    await guarded(async () => {
        await makeRequest(apiUrl(`visits/${visitId()}/update`), "PATCH", { complete: true })
        doctorState.visit = null
        setVisitTabs(false)
        document.querySelector(".section-togglers[data-section='assigned_patients']").click()
        await loadVisits()
    })
}

// ------------------------------------------------------------------ triage and allergies

const TRIAGE_FIELDS = ["blood_pressure", "heart_rate", "respiratory_rate", "temperature", "weight", "height",
    "oxygen_saturation", "MUAC", "sign_symptoms", "injury_details"]

async function loadTriage() {
    const form = document.querySelector("#doctor_triage_form")
    form.reset()
    doctorState.triage = null
    try {
        doctorState.triage = await makeRequest(apiUrl(`visit/${visitId()}/triage/`))
    } catch (error) {
        if (error.status !== 404) showError(error)
    }
    const triage = doctorState.triage
    TRIAGE_FIELDS.forEach(field => {
        form.querySelector(`#${field}`).value = triage && triage[field] !== null ? triage[field] : ""
    })
    document.querySelector("#triage_date").textContent = triage
        ? `Recorded ${formatDateTime(triage.created_on)}` : "No triage recorded for this visit yet"
}

async function saveTriage(event) {
    event.preventDefault()
    const form = event.target
    const data = { visit: visitId() }
    TRIAGE_FIELDS.forEach(field => data[field] = form.querySelector(`#${field}`).value.trim())
    await guarded(async () => {
        if (doctorState.triage) {
            await makeRequest(apiUrl(`triage/${doctorState.triage.id}/update/`), "PATCH", data, { keepEmpty: true })
        } else {
            await makeRequest(apiUrl("triage/create/"), "POST", data)
        }
        await loadTriage()
    })
}

async function loadAllergies() {
    resetAllergyForm()
    const records = await guarded(() => makeRequest(apiUrl(`allergy/${encodeURIComponent(doctorState.visit.patient.patient_id)}/patient/`)))
    renderRecords("allergies_table", records || [], [
        record => record.name,
        record => record.comment,
        record => formatDateTime(record.created_on),
    ], {
        onSelect: record => {
            const form = document.querySelector("#allergy_form")
            fillForm(form, record)
            form.dataset.recordId = record.id
            document.querySelector("#allergy_form_reset").hidden = false
        },
        onDelete: record => guarded(async () => {
            await makeRequest(apiUrl(`allergy/${record.id}/delete/`), "DELETE")
            await loadAllergies()
        }),
    })
}

function resetAllergyForm() {
    const form = document.querySelector("#allergy_form")
    form.reset()
    delete form.dataset.recordId
    document.querySelector("#allergy_form_reset").hidden = true
}

async function saveAllergy(event) {
    event.preventDefault()
    const form = event.target
    const data = { ...formValues(form), patient: doctorState.visit.patient.id }
    await guarded(async () => {
        if (form.dataset.recordId) {
            await makeRequest(apiUrl(`allergy/${form.dataset.recordId}/update/`), "PATCH", data, { keepEmpty: true })
        } else {
            await makeRequest(apiUrl("allergy/create/"), "POST", data)
        }
        await loadAllergies()
    })
}

// ------------------------------------------------------------------ clinical findings

// A visit can have several records of each kind: browse them, edit one, or start a new one
class VisitRecordBook {
    constructor(form, resource) {
        this.form = form
        this.resource = resource
        this.records = []
        this.index = 0
        form.addEventListener("submit", event => {
            event.preventDefault()
            this.save()
        })
        form.querySelector("[data-record='previous']").addEventListener("click", () => this.show(this.index - 1))
        form.querySelector("[data-record='next']").addEventListener("click", () => this.show(this.index + 1))
        form.querySelector("[data-record='new']").addEventListener("click", () => this.show(this.records.length))
    }

    async load(selectId=null) {
        const records = await guarded(() => makeRequest(apiUrl(`${this.resource}/${visitId()}/visit/`)))
        this.records = (records || []).sort((a, b) => new Date(a.created_on) - new Date(b.created_on))
        const selected = this.records.findIndex(record => record.id === selectId)
        this.show(selected >= 0 ? selected : Math.max(this.records.length - 1, 0))
    }

    show(index) {
        this.index = Math.min(Math.max(index, 0), this.records.length)
        const record = this.records[this.index] || null
        fillForm(this.form, record)
        this.form.querySelector("[data-record-date]").textContent = record
            ? `Record ${this.index + 1} of ${this.records.length}, ${formatDateTime(record.created_on)}`
            : "New record"
        this.form.querySelector("[data-record='previous']").disabled = this.index === 0
        this.form.querySelector("[data-record='next']").disabled = this.index >= this.records.length
    }

    async save() {
        const record = this.records[this.index]
        const data = { ...formValues(this.form), visit: visitId() }
        await guarded(async () => {
            const saved = record
                ? await makeRequest(apiUrl(`${this.resource}/${record.id}/update/`), "PATCH", data, { keepEmpty: true })
                : await makeRequest(apiUrl(`${this.resource}/create/`), "POST", data)
            await this.load(saved.id)
        })
    }
}

let findingBooks = []

// ------------------------------------------------------------------ diagnosis

async function loadDiagnosis() {
    const records = await guarded(() => makeRequest(apiUrl(`diagnosis/${visitId()}/visit/`)))
    renderRecords("diagnosis_table", records || [], [
        record => record.diagnosis,
        record => record.notes,
        record => record.created_by,
        record => formatDateTime(record.created_on),
    ], {
        onDelete: record => guarded(async () => {
            await makeRequest(apiUrl(`diagnosis/${record.id}/delete/`), "DELETE")
            await loadDiagnosis()
        }),
    })
}

async function saveDiagnosis(event) {
    event.preventDefault()
    const form = event.target
    await guarded(async () => {
        await makeRequest(apiUrl("diagnosis/create/"), "POST", { ...formValues(form), visit: visitId() })
        form.reset()
        await loadDiagnosis()
    })
}

// ------------------------------------------------------------------ prescriptions

async function loadDrugs() {
    const drugs = await guarded(() => fetchAll(apiUrl("drugs/")))
    const select = document.querySelector("#prescription_drug")
    fillSelect(select, drugs || [], drug => `${drug.name} (${drug.category})`, drug => ({ stock: drug.stock_available }))
    select.addEventListener("change", () => {
        const option = select.selectedOptions[0]
        document.querySelector("#prescription_stock").textContent = option && option.value
            ? `In stock: ${option.dataset.stock}` : ""
    })
}

async function loadPrescriptions() {
    const records = await guarded(() => makeRequest(apiUrl(`prescriptions/${visitId()}/visit/`)))
    renderRecords("prescription_table", records || [], [
        record => record.drug_name,
        record => record.dosage,
        record => record.duration,
        record => record.quantity,
        record => record.quantity_issued,
        record => record.stock_available,
        record => record.unit_price,
        record => record.amount,
        record => record.prescribed_by,
    ], {
        onDelete: record => guarded(async () => {
            await makeRequest(apiUrl(`prescriptions/${record.id}/delete/`), "DELETE")
            await loadPrescriptions()
        }),
        canDelete: record => !record.quantity_issued,
    })
}

async function savePrescription(event) {
    event.preventDefault()
    const form = event.target
    await guarded(async () => {
        await makeRequest(apiUrl("prescriptions/create/"), "POST", { ...formValues(form), visit: visitId() })
        form.reset()
        document.querySelector("#prescription_stock").textContent = ""
        await loadPrescriptions()
    })
}

// ------------------------------------------------------------------ procedures, theatre, dental, eye

async function initServiceOrders(section) {
    const category = section.dataset.serviceCategory
    const services = await guarded(() => fetchAll(apiUrl(`services/?category=${encodeURIComponent(category)}`)))
    fillSelect(section.querySelector("select[name='service']"), services || [], service => `${service.name} (${service.fee})`)
    section.querySelector("[data-service-form]").addEventListener("submit", async event => {
        event.preventDefault()
        const form = event.target
        await guarded(async () => {
            await makeRequest(apiUrl("visitservices/create/"), "POST", { ...formValues(form), visit: visitId() })
            form.reset()
            await loadServiceOrders(section)
        })
    })
}

async function loadServiceOrders(section) {
    const category = section.dataset.serviceCategory
    const records = await guarded(() => makeRequest(apiUrl(`visitservices/${visitId()}/visit/?category=${encodeURIComponent(category)}`)))
    renderRecords(`services_table_${category}`, records || [], [
        record => record.service_name,
        record => record.quantity,
        record => record.price,
        record => record.total,
        record => record.notes,
        record => record.ordered_by,
        record => formatDateTime(record.created_on),
    ], {
        onDelete: record => guarded(async () => {
            await makeRequest(apiUrl(`visitservices/${record.id}/delete/`), "DELETE")
            await loadServiceOrders(section)
        }),
    })
}

// ------------------------------------------------------------------ cardiology and radiology

async function initDepartmentRequests(section) {
    const department = section.dataset.department
    const services = await guarded(() => fetchAll(apiUrl(`services/?category=${encodeURIComponent(department)}`)))
    fillSelect(section.querySelector("select[name='service']"), services || [], service => `${service.name} (${service.fee})`)
    section.querySelector("[data-department-form]").addEventListener("submit", async event => {
        event.preventDefault()
        const form = event.target
        await guarded(async () => {
            await makeRequest(apiUrl("departmentrequests/create/"), "POST", { ...formValues(form), department, visit: visitId() })
            form.reset()
            await loadDepartmentRequests(section)
        })
    })
}

function showDepartmentReport(section, record) {
    const report = section.querySelector("[data-department-report]")
    const rows = record.status === "completed"
        ? [
            ["Examination", record.service_name],
            ["Findings", record.result],
            ["Reference range", record.reference_range],
            ["Comments", record.comments],
            ["Reported by", `${record.reported_by || ""} ${formatDateTime(record.reported_on)}`],
        ]
        : [["Examination", record.service_name], ["Status", "Awaiting report from the department"]]
    report.innerHTML = rows.map(([title, value]) => `<dt>${escapeHtml(title)}</dt><dd>${escapeHtml(value)}</dd>`).join("")
    report.hidden = false
}

async function loadDepartmentRequests(section) {
    const department = section.dataset.department
    section.querySelector("[data-department-report]").hidden = true
    const records = await guarded(() => makeRequest(apiUrl(`departmentrequests/${visitId()}/visit/?department=${encodeURIComponent(department)}`)))
    renderRecords(`department_table_${department}`, records || [], [
        record => record.service_name,
        record => record.price,
        record => record.status,
        record => record.requested_by,
        record => formatDateTime(record.created_on),
        record => formatDateTime(record.reported_on),
    ], {
        onSelect: record => showDepartmentReport(section, record),
        onDelete: record => guarded(async () => {
            await makeRequest(apiUrl(`departmentrequests/${record.id}/delete/`), "DELETE")
            await loadDepartmentRequests(section)
        }),
        canDelete: record => record.status === "pending",
    })
}

// ------------------------------------------------------------------ laboratory

const labState = { request: null, selected: new Map() }

async function loadLabRequests() {
    document.querySelector("#lab_request_details").hidden = true
    await guarded(() => renderLabRequestData(apiUrl(`lab/requests/${visitId()}/visit/`), "doctor_lab_requests", showLabRequest))
}

function labResultText(test) {
    if (test.parameters && test.parameters.length) {
        return test.parameters.map(parameter => `${parameter.name}: ${parameter.result ?? ""} ${parameter.units || ""}`.trim()).join("; ")
    }
    return test.result || "Pending"
}

async function showLabRequest(labRequest) {
    labState.request = labRequest
    const tests = await guarded(() => makeRequest(apiUrl(`lab/tests/${labRequest.id}/request/`)))
    labState.requestTests = tests || []
    document.querySelector("#lab_request_details").hidden = false
    document.querySelector("#edit_lab_request").hidden = labRequest.handled
    renderRecords("lab_request_tests", labState.requestTests, [
        test => test.name,
        test => test.price,
        test => labResultText(test),
        test => test.dafault_range,
    ])
}

function updateSelectedTests() {
    const list = document.querySelector("#selected_tests ul")
    list.innerHTML = ""
    labState.selected.forEach(test => {
        const item = document.createElement("li")
        item.innerHTML = `
            <h4 class="test_name">${escapeHtml(test.name)}</h4>
            <p class="test_description">${escapeHtml(test.description)}</p>
            <div class="test_price">
                <span>${escapeHtml(test.currency)}</span>
                <input type="number" min="0" step="any" class="test_price_value" value="${escapeHtml(test.price)}">
            </div>
            <button type="button" class="action" title="Remove test"><i class="fa fa-trash"></i></button>`
        item.querySelector(".test_price_value").addEventListener("change", event => test.price = event.target.value)
        item.querySelector(".action").addEventListener("click", () => {
            labState.selected.delete(test.test)
            updateSelectedTests()
        })
        list.appendChild(item)
    })
    document.querySelector("#test_count").textContent = labState.selected.size
}

async function searchLabTests(search="") {
    const tests = await guarded(() => makeRequest(apiUrl(`lab/tests/?s=${encodeURIComponent(search)}`)))
    const list = document.querySelector("#request-test-list")
    list.innerHTML = ""
    ;(tests || []).forEach(test => {
        const item = document.createElement("li")
        item.innerHTML = `
            <h4 class="test_name">${escapeHtml(test.name)}</h4>
            <p class="test_description">${escapeHtml(test.description)}</p>
            <p class="test_description">Normal range: ${escapeHtml(test.dafault_range)}</p>
            <p class="test_price">${escapeHtml(test.currency)} ${escapeHtml(test.price)}</p>`
        item.addEventListener("click", () => {
            if (!labState.selected.has(test.id)) {
                labState.selected.set(test.id, { ...test, test: test.id })
                updateSelectedTests()
            }
        })
        list.appendChild(item)
    })
}

function startLabRequest(editing) {
    labState.editing = editing
    labState.selected = new Map()
    if (editing) {
        labState.requestTests.forEach(test => labState.selected.set(test.test, { ...test }))
    }
    document.querySelector("#lab_request_mode").textContent = editing
        ? `Editing request of ${formatDateTime(labState.request.created_on)}` : "Selected tests"
    document.querySelector("#place_request_activator").textContent = editing ? "Update request" : "Place request"
    updateSelectedTests()
    const search = document.querySelector("#doctor_search_lab_tests_field")
    search.value = ""
    searchLabTests()
    search.focus()
}

async function placeLabRequest() {
    if (!labState.selected.size) {
        showError(new Error("Select at least one test."))
        return
    }
    const selectedTests = [...labState.selected.values()].map(test => ({ test: test.test, price: test.price }))
    await guarded(async () => {
        if (labState.editing) {
            await makeRequest(apiUrl(`lab/requests/${labState.request.id}/update/`), "PATCH", { selectedTests })
        } else {
            const category = document.querySelector("#laboratory_section").dataset.requestCategory
            await makeRequest(apiUrl("lab/requests/create/"), "POST", { visit_pk: visitId(), category, selectedTests })
        }
        labState.selected = new Map()
        updateSelectedTests()
        document.querySelector("#lab_results_activator").click()
        await loadLabRequests()
    })
}

function initLaboratory() {
    // the part togglers in scripts.js switch the view; these only prepare it
    document.querySelector("#create_lab_request_activator").addEventListener("click", () => startLabRequest(false))
    document.querySelector("#edit_lab_request").addEventListener("click", () => {
        document.querySelector("#create_lab_request_activator").click()
        startLabRequest(true)
    })
    document.querySelector("#place_request_activator").addEventListener("click", placeLabRequest)
    document.querySelector("#lab_test_search_form").addEventListener("submit", event => event.preventDefault())
    let searchTimer = null
    document.querySelector("#doctor_search_lab_tests_field").addEventListener("input", event => {
        clearTimeout(searchTimer)
        searchTimer = setTimeout(() => searchLabTests(event.target.value.trim()), 250)
    })
}

// ------------------------------------------------------------------ page

function initDoctorPage() {
    setVisitTabs(false)
    findingBooks = [
        new VisitRecordBook(document.querySelector("#general_findings_form"), "generalfindings"),
        new VisitRecordBook(document.querySelector("#paedeatrics_form"), "paedeatricnotes"),
        new VisitRecordBook(document.querySelector("#gyn_form"), "gynnotes"),
    ]
    document.querySelector("#doctor_triage_form").addEventListener("submit", saveTriage)
    document.querySelector("#allergy_form").addEventListener("submit", saveAllergy)
    document.querySelector("#allergy_form_reset").addEventListener("click", resetAllergyForm)
    document.querySelector("#diagnosis_form").addEventListener("submit", saveDiagnosis)
    document.querySelector("#prescription_form").addEventListener("submit", savePrescription)
    document.querySelectorAll("[data-service-category]").forEach(section => initServiceOrders(section))
    document.querySelectorAll("[data-department]").forEach(section => initDepartmentRequests(section))
    initLaboratory()
    loadDrugs()

    const mine = document.querySelector("#my_patients_only")
    if (mine) mine.addEventListener("change", () => guarded(loadVisits))
    guarded(loadVisits)
}
