// Renders API records into tables

function formatCell(record, field) {
    switch (field) {
        case "patient":
            return record.patient ? record.patient.fullname : ""
        case "patientID":
            return record.patient ? record.patient.patient_id : ""
        case "category":
            return record.category ? record.category.name : ""
        case "visit":
        case "complete":
        case "handled":
            return record[field] ? "Yes" : "No"
        case "created_on":
        case "updated_on":
        case "visit_date":
            return formatDateTime(record[field])
        default:
            return record[field] === null || record[field] === undefined ? "" : record[field]
    }
}

function createTableRows (parentElem, data, fields, listener) {
    data.forEach((record, i) => {
        const rowElem = document.createElement("tr");
        rowElem.dataset.row = i
        rowElem.dataset.record_db_id = record["id"]
        fields.forEach(field => {
            const cell = document.createElement("td");
            cell.dataset.value = field
            cell.textContent = formatCell(record, field)
            rowElem.appendChild(cell)
        })

        if (listener) {
            rowElem.style.cursor = "pointer"
            rowElem.addEventListener("click", () => {
                parentElem.querySelectorAll("tr.selected").forEach(row => row.classList.remove("selected"))
                rowElem.classList.add("selected")
                listener(record)
            })
        }

        parentElem.appendChild(rowElem)
    })
}

// Replaces the rows of a table and (re)initialises DataTables on it
function renderTable(tableId, records, fields, listener) {
    const table = document.querySelector(`table#${tableId}`)
    if ($.fn.DataTable.isDataTable(table)) {
        $(table).DataTable().destroy()
    }
    const tableBody = table.querySelector("tbody")
    tableBody.innerHTML = "";
    createTableRows(tableBody, records, fields, listener)
    $(table).DataTable({ order: [], language: tableLanguage(table) })
}

function clearPreview() {
    const previewArea = document.querySelector(".preview-area")
    if (previewArea) {
        previewArea.innerHTML = "";
        document.querySelector("main").classList.remove("split")
    }
}

async function renderPatientData() {
    clearPreview()
    const records = await fetchAll(`${api_routes.patients_list}?page_size=100`)
    renderTable("patientsTable", records, ["patient_id", "fullname", "gender", "age", "visit", "created_on"], loadPatientOnPreview)
}

async function renderVisitData(listener=loadVisitPreview, tableId="visitsTable") {
    clearPreview()
    const records = await fetchAll(`${api_routes.visits_list}?page_size=100`)
    renderTable(tableId, records, ["patientID", "patient", "category", "Speciality", "Doctor", "complete", "visit_date"], listener)
    return records
}

async function rendertriageData() {
    clearPreview()
    const records = await fetchAll(api_routes.triage_list)
    renderTable("triage_table", records, ["patientID", "patient", "blood_pressure", "heart_rate", "respiratory_rate", "temperature", "created_on"], loadTriagePreview)
}

async function renderLabRequestData(url, tableId, listener) {
    const records = await makeRequest(url, "GET")
    renderTable(tableId, records, ["patientID", "visit_id", "patient", "category", "doctor", "handled", "created_on"], listener)
    return records
}
