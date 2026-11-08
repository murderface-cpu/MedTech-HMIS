// Patients, visits and triage pages

let refreshCurrentPage = () => Promise.resolve()

function initPatientsPage(page) {
    refreshCurrentPage = {
        patients: renderPatientData,
        visits: () => renderVisitData(),
        triage: rendertriageData,
    }[page]

    const createPatient = document.querySelector("#create_patient_modal_activator")
    if (createPatient) {
        createPatient.addEventListener("click", () => openModal("create_patient_modal"))
    }
    const createVisit = document.querySelector("#create_visit_modal_activator")
    if (createVisit) {
        createVisit.addEventListener("click", () => triggerCreateVisitModal(null))
    }
    const createTriage = document.querySelector("#create_triage_modal_activator")
    if (createTriage) {
        createTriage.addEventListener("click", () => triggerCreateTriageModal(null))
    }

    document.querySelectorAll("[data-submit='patient']").forEach(button => button.addEventListener("click", submitPatientData))
    document.querySelectorAll("[data-submit='visit']").forEach(button => button.addEventListener("click", submitVisitData))
    document.querySelectorAll("[data-submit='triage']").forEach(button => button.addEventListener("click", submitTriageData))
    initDoctorFilter()
    initLoadPatientModal()

    refreshCurrentPage().catch(showError)
}

function fieldValues(modal, mapping) {
    const data = {}
    Object.entries(mapping).forEach(([key, selector]) => {
        data[key] = modal.querySelector(selector).value
    })
    return data
}

function setFieldValues(modal, mapping, record) {
    Object.entries(mapping).forEach(([key, selector]) => {
        const value = record[key]
        modal.querySelector(selector).value = value === null || value === undefined ? "" : value
    })
}

function afterSave(modal) {
    closeModal(modal)
    return refreshCurrentPage().catch(showError)
}


// ---------------------------------- Patient ----------------------------------
const PATIENT_FIELDS = {
    firstname: "#firstName",
    middlename: "#middleName",
    lastname: "#lastName",
    nin: "#NIN",
    age: "#age",
    gender: "#gender",
    telnumber: "#phoneNumber",
    alttelnumber: "#AltNumber",
    email: "#email",
    address: "#address",
}
const NOK_FIELDS = {
    firstname: "#NOK_firstName",
    middlename: "#NOK_middleName",
    lastname: "#NOK_lastName",
    relationship: "#NOK_relationship",
    nin: "#NOK_nin",
    telnumber: "#NOK_phoneNumber",
    gender: "#NOK_Gender",
    address: "#NOK_address",
}

function triggerEditPatientModal(patient) {
    const modal = openModal("create_patient_modal", "edit")
    modal.dataset.patient = patient.patient_id
    modal.dataset.patientPk = patient.id
    setFieldValues(modal, PATIENT_FIELDS, patient)
    modal.querySelector("#dateOfBirth").value = toDateInputValue(patient.date_of_birth)
    modal.querySelector("#patient_id").value = patient.patient_id

    makeRequest(`${api_routes.nok_list}${patient.id}/`, "GET")
        .then(nok => {
            modal.dataset.nok = nok.id
            setFieldValues(modal, NOK_FIELDS, nok)
        })
        .catch(error => {
            // 404 means the patient has no next of kin yet
            if (error.status !== 404) showError(error)
        })
}

async function submitPatientData() {
    const modal = document.querySelector("#create_patient_modal")
    if (!validateRequired(modal.querySelectorAll("[data-required]"))) {
        return
    }
    const patientData = fieldValues(modal, PATIENT_FIELDS)
    patientData.date_of_birth = modal.querySelector("#dateOfBirth").value
    if (!patientData.age && !patientData.date_of_birth) {
        validateRequired([modal.querySelector("#age"), modal.querySelector("#dateOfBirth")])
        return
    }
    if (patientData.date_of_birth) {
        // the age is worked out from the date of birth
        patientData.age = ""
    }

    const nokData = fieldValues(modal, NOK_FIELDS)
    const hasNok = [...modal.querySelectorAll("[data-nok-required]")].some(field => field.value !== "")
    if (hasNok && !validateRequired(modal.querySelectorAll("[data-nok-required]"))) {
        return
    }

    try {
        let patient
        if (modal.dataset.action === "edit") {
            patient = await makeRequest(apiUrl(`patients/${encodeURIComponent(modal.dataset.patient)}/update/`), "PATCH", patientData, {keepEmpty: true})
        } else {
            patient = await makeRequest(apiUrl("patients/create/"), "POST", patientData)
        }
        if (hasNok) {
            if (modal.dataset.nok) {
                await makeRequest(apiUrl(`nextOfKin/${modal.dataset.nok}/update/`), "PATCH", nokData, {keepEmpty: true})
            } else {
                await makeRequest(apiUrl("patients/create/nextOfKin/"), "POST", {...nokData, patient: patient.id})
            }
        }
        await afterSave(modal)
    } catch (error) {
        showError(error)
    }
}


// ---------------------------------- Visit ----------------------------------
function fillPatientSummary(modal, patient) {
    modal.dataset.patientPk = patient.id
    modal.dataset.patient = patient.patient_id
    modal.querySelectorAll("[data-field]").forEach(field => {
        const value = patient[field.dataset.field]
        field.value = value === null || value === undefined ? "" : value
    })
    const loader = modal.querySelector(".load_patient_activator")
    if (loader) loader.hidden = true
}

function preparePatientSelection(modal, onSelect) {
    const loader = modal.querySelector(".load_patient_activator")
    loader.hidden = false
    loader.onclick = () => openLoadPatientModal(patient => {
        openModal(modal, "create")
        fillPatientSummary(modal, patient)
        if (onSelect) onSelect(patient)
    })
}

function initDoctorFilter() {
    const speciality = document.querySelector("#visit_specialty")
    if (!speciality) return
    speciality.addEventListener("change", () => {
        const selected = speciality.selectedOptions[0]
        const name = selected && selected.value ? selected.dataset.name : null
        const doctor = document.querySelector("#visit_doctor")
        doctor.querySelectorAll(".doctors_options").forEach(option => {
            const matches = !name || option.dataset.specialities.split("|").includes(name)
            option.hidden = !matches
            if (!matches && option.selected) doctor.value = ""
        })
    })
}

function triggerCreateVisitModal(data, edit=false) {
    const modal = openModal("create_visit_modal", edit ? "edit" : "create")
    modal.querySelector("#visit_date").value = toDateInputValue(new Date())

    if (!data) {
        preparePatientSelection(modal)
        return
    }

    if (edit) {
        modal.dataset.visit = data.id
        fillPatientSummary(modal, data.patient)
        modal.querySelector("#visit_date").value = toDateInputValue(data.visit_date)
        modal.querySelector("#visit_category").value = data.category.id
        modal.querySelector("#visit_specialty").value = data.speciality || ""
        modal.querySelector("#visit_doctor").value = data.doctor || ""
        modal.querySelector("#billing_methods").value = data.billing_type || ""
        if (data.insurance_company) modal.querySelector("#insurance_company").value = data.insurance_company
        if (data.account_company) modal.querySelector("#account_company").value = data.account_company
        updateBillingCompanyFields(modal.querySelector("#billing_methods"))
    } else {
        fillPatientSummary(modal, data)
    }
}

async function submitVisitData() {
    const modal = document.querySelector("#create_visit_modal")
    if (!modal.dataset.patientPk) {
        showError(new Error("Select a patient first."))
        return
    }
    if (!validateRequired(modal.querySelectorAll("[data-required]"))) {
        return
    }

    const billing = modal.querySelector("#billing_methods")
    const kind = billing.selectedOptions[0] ? billing.selectedOptions[0].dataset.kind : null
    const visitData = {
        patient: modal.dataset.patientPk,
        visit_date: modal.querySelector("#visit_date").value,
        category: modal.querySelector("#visit_category").value,
        speciality: modal.querySelector("#visit_specialty").value || null,
        doctor: modal.querySelector("#visit_doctor").value || null,
        billing_type: billing.value || null,
        insurance_company: kind === "insurance" ? modal.querySelector("#insurance_company").value : null,
        account_company: kind === "account" ? modal.querySelector("#account_company").value : null,
    }

    try {
        if (modal.dataset.action === "edit") {
            await makeRequest(apiUrl(`visits/${modal.dataset.visit}/update`), "PATCH", visitData, {keepEmpty: true})
        } else {
            await makeRequest(apiUrl("visits/create/"), "POST", visitData)
        }
        await afterSave(modal)
    } catch (error) {
        showError(error)
    }
}


// ---------------------------------- Triage ----------------------------------
const TRIAGE_FIELDS = {
    blood_pressure: "#blood_pressure",
    heart_rate: "#heart_rate",
    respiratory_rate: "#respiratory_rate",
    temperature: "#temperature",
    weight: "#weight",
    height: "#height",
    oxygen_saturation: "#oxygen_saturation",
    MUAC: "#MUAC",
    sign_symptoms: "#sign_symptoms",
    injury_details: "#injury_details",
}

function displayTriageFormData(data, parentElem) {
    setFieldValues(parentElem, TRIAGE_FIELDS, data)
}

function triggerCreateTriageModal(data, edit=false) {
    const modal = openModal("create_triage_modal", edit ? "edit" : "create")
    if (!data) {
        preparePatientSelection(modal)
        return
    }
    if (edit) {
        modal.dataset.visit = data.visit
        modal.dataset.triage = data.id
        fillPatientSummary(modal, data.patient)
        displayTriageFormData(data, modal)
    } else {
        fillPatientSummary(modal, data)
    }
}

async function submitTriageData() {
    const modal = document.querySelector("#create_triage_modal")
    if (!modal.dataset.patient) {
        showError(new Error("Select a patient first."))
        return
    }
    const bloodPressure = modal.querySelector("#blood_pressure")
    if (!bloodPressure.checkValidity()) {
        bloodPressure.classList.add("error")
        showError(new Error("Enter the blood pressure as systolic/diastolic, for example 120/80."))
        return
    }
    const triageData = fieldValues(modal, TRIAGE_FIELDS)

    try {
        if (modal.dataset.action === "edit") {
            await makeRequest(apiUrl(`triage/${modal.dataset.triage}/update/`), "PATCH", triageData, {keepEmpty: true})
        } else {
            // a triage record belongs to the patient's active visit
            const visits = await makeRequest(apiUrl(`patients/${encodeURIComponent(modal.dataset.patient)}/visit/`), "GET")
            if (visits.length === 0) {
                showError(new Error("This patient has no active visit. Create a visit before recording triage."))
                return
            }
            await makeRequest(apiUrl("triage/create/"), "POST", {...triageData, visit: visits[0].id})
        }
        await afterSave(modal)
    } catch (error) {
        showError(error)
    }
}


// ---------------------------------- Select patient ----------------------------------
let loadPatientState = { page: 1, search: "", onSelect: null }

function openLoadPatientModal(onSelect) {
    loadPatientState = { page: 1, search: "", onSelect }
    const modal = openModal("load_patient_modal")
    modal.querySelector("#load_patient_search").value = ""
    loadPatients()
}

function initLoadPatientModal() {
    const modal = document.querySelector("#load_patient_modal")
    if (!modal) return
    let searchTimer = null
    modal.querySelector("#load_patient_search").addEventListener("input", event => {
        clearTimeout(searchTimer)
        searchTimer = setTimeout(() => {
            loadPatientState.search = event.target.value.trim()
            loadPatientState.page = 1
            loadPatients()
        }, 300)
    })
    modal.querySelector("#loadNextPatients").addEventListener("click", () => {
        loadPatientState.page++
        loadPatients()
    })
    modal.querySelector("#loadPreviousPatients").addEventListener("click", () => {
        loadPatientState.page--
        loadPatients()
    })
}

function loadPatients() {
    const params = new URLSearchParams({ page: loadPatientState.page })
    if (loadPatientState.search) params.set("search", loadPatientState.search)

    makeRequest(`${api_routes.patients_list}?${params}`, "GET")
    .then(response => {
        document.querySelector("#loadNextPatients").disabled = response.next === null
        document.querySelector("#loadPreviousPatients").disabled = response.previous === null
        document.querySelector("#load_patient_empty").hidden = response.results.length > 0

        const tableBody = document.querySelector("table#load_patient_table tbody")
        tableBody.innerHTML = "";
        createTableRows(tableBody, response.results, ["patient_id", "fullname", "gender", "age", "visit", "created_on"], patient => {
            closeModal(document.querySelector("#load_patient_modal"))
            if (loadPatientState.onSelect) loadPatientState.onSelect(patient)
        })
    })
    .catch(showError)
}
