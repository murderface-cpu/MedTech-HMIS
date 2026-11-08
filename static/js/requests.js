// The API root is rendered by the server into <meta name="api-root"> so no path is hardcoded here
const API_ROOT = document.querySelector('meta[name="api-root"]').content

function apiUrl(path) {
    return `${API_ROOT}${path}`
}

const api_routes = {
    "patients_list": apiUrl("patients/"),
    "nok_list": apiUrl("nextOfKin/"),
    "visits_list": apiUrl("visits/"),
    "triage_list": apiUrl("triage/"),
}

function removeEmpty(obj) {
    Object.keys(obj).forEach(key => {
        if (obj[key] && typeof obj[key] === 'object') {
        removeEmpty(obj[key]);
        } else if (obj[key] == null || obj[key] === '') {
        delete obj[key];
        }
    });
    return obj;
}

function getCookie(name) {
    const match = document.cookie.split("; ").find(row => row.startsWith(`${name}=`));
    return match ? decodeURIComponent(match.split("=")[1]) : null;
}

// Escape text before placing it inside HTML built with template strings
function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

class RequestError extends Error {
    constructor(status, data) {
        super(RequestError.describe(data) || `Request failed (${status})`);
        this.status = status;
        this.data = data;
    }

    static describe(data) {
        if (!data) return "";
        if (typeof data === "string") return "";
        if (data.detail) return data.detail;
        return Object.entries(data)
            .map(([field, errors]) => `${field.replace(/_/g, " ")}: ${[].concat(errors).join(" ")}`)
            .join("\n");
    }
}

// keepEmpty sends empty values as null, so an edit can clear a field
async function makeRequest (url, method="GET", data={}, {keepEmpty=false}={}) {
    let requestData = {
        method: method,
        credentials: "same-origin",
        cache: "no-cache",
        headers: {
            Accept: "application/json",
        },
    };

    if (method == "POST" || method == "PUT" || method == "PATCH" || method == "DELETE") {
        requestData.headers["X-CSRFToken"] = getCookie("csrftoken");
    }
    if (method == "POST" || method == "PUT" || method == "PATCH") {
        const payload = keepEmpty
            ? Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value === "" || value === undefined ? null : value]))
            : removeEmpty({...data})
        requestData.body = JSON.stringify(payload);
        requestData.headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, requestData);
    const text = await response.text();
    let body = null;
    try {
        body = text ? JSON.parse(text) : null;
    } catch (error) {
        body = text;
    }

    // the session expired: reloading sends the user to the sign-in page
    if (response.status === 401 || (response.status === 403 && body && /credentials/i.test(body.detail || ""))) {
        window.location.reload();
    }
    if (!response.ok) {
        throw new RequestError(response.status, body);
    }
    return body;
}

// Follows DRF pagination and returns every record
async function fetchAll(url) {
    let results = [];
    let next = url;
    while (next) {
        const response = await makeRequest(next, "GET");
        if (Array.isArray(response)) {
            return response;
        }
        results = results.concat(response.results);
        next = response.next;
    }
    return results;
}

function showError(error) {
    alert(error && error.message ? error.message : "Something went wrong. Please try again.");
}

// Converts an API datetime into the value an <input type="date"> expects
function toDateInputValue(value) {
    if (!value) return "";
    const date = new Date(value);
    if (isNaN(date)) return "";
    const pad = n => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatDateTime(value) {
    if (!value) return "";
    const date = new Date(value);
    return isNaN(date) ? value : date.toLocaleString();
}
