// Side panel that shows the selected record

function showPreview(rows, actions=[]) {
    const main = document.querySelector("main")
    main.classList.add("split")
    const previewArea = document.querySelector(".preview-area");
    const details = rows.map(([title, value]) => `
        <div class="detail-group">
            <p class="part-title">${escapeHtml(title)}</p>
            <p class="part-content">${escapeHtml(value)}</p>
        </div>`).join("")
    const buttons = actions.map((action, i) => `<button type="button" data-preview-action="${i}">${escapeHtml(action.label)}</button>`).join("")

    previewArea.innerHTML = `
    <div class="img-wrapper">
        <img src="${escapeHtml(previewArea.dataset.userImage)}" alt="">
    </div>
    <div class="details">${details}</div>
    <div class="cta_area">${buttons}</div>
    `;
    actions.forEach((action, i) => {
        previewArea.querySelector(`[data-preview-action="${i}"]`).addEventListener("click", action.onClick)
    })
}

const loadPatientOnPreview = (patient) => {
    const actions = [{ label: "Edit details", onClick: () => triggerEditPatientModal(patient) }]
    if (!patient.visit && document.querySelector("#create_visit_modal")) {
        actions.push({ label: "Create visit", onClick: () => triggerCreateVisitModal(patient) })
    }
    showPreview([
        ["Patient ID:", patient.patient_id],
        ["Full Name:", patient.fullname],
        ["NIN:", patient.nin],
        ["Phone No:", patient.telnumber],
        ["Address:", patient.address],
        ["Gender:", patient.gender],
        ["Age:", patient.age],
        ["Active Visit:", patient.visit ? "Yes" : "No"],
    ], actions)
}


const loadVisitPreview = (visit) => {
    showPreview([
        ["Patient ID:", visit.patient.patient_id],
        ["Visit:", visit.visit_id],
        ["Full Name:", visit.patient.fullname],
        ["NIN:", visit.patient.nin],
        ["Category:", visit.category.name],
        ["Doctor:", visit.Doctor || "Not assigned"],
        ["Speciality:", visit.Speciality],
        ["Billing:", visit.billing_label || "Not set"],
        ["Visit Date:", formatDateTime(visit.visit_date)],
        ["Complete:", visit.complete ? "Yes" : "No"],
    ], [{ label: "Edit details", onClick: () => triggerCreateVisitModal(visit, true) }])
}

const loadTriagePreview = (triage) => {
    showPreview([
        ["Patient ID:", triage.patient.patient_id],
        ["Full Name:", triage.patient.fullname],
        ["NIN:", triage.patient.nin],
        ["Blood Pressure:", triage.blood_pressure],
        ["Heart Rate:", triage.heart_rate],
        ["Respiratory Rate:", triage.respiratory_rate],
        ["Temperature:", triage.temperature],
        ["Updated On:", formatDateTime(triage.updated_on)],
    ], [{ label: "Edit details", onClick: () => triggerCreateTriageModal(triage, true) }])
}
