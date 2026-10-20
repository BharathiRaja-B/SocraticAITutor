/**
 * app.js — Shared utilities for all frontend pages.
 * Handles: API calls, auth token management, toast notifications.
 */

// Backend URL — change this if your backend runs on a different port
const API_BASE = "http://127.0.0.1:8000";

// ─── Auth Helpers ─────────────────────────────────────────────────────────────

/** Save login data to localStorage */
function saveAuth(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

/** Get the current JWT token */
function getToken() {
  return localStorage.getItem("token");
}

/** Get the current user object */
function getUser() {
  const raw = localStorage.getItem("user");
  return raw ? JSON.parse(raw) : null;
}

/** Remove auth data (logout) */
function clearAuth() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

/** Redirect to login if not authenticated */
function requireAuth(role = "student") {
  const token = getToken();
  const user = getUser();
  if (!token || !user) {
    window.location.href = "index.html";
    return false;
  }
  if (role === "admin" && user.role !== "admin") {
    window.location.href = "dashboard.html";
    return false;
  }
  return true;
}

// ─── API Fetch Helper ─────────────────────────────────────────────────────────

/**
 * Make an authenticated API call.
 * @param {string} endpoint - e.g. "/chat"
 * @param {string} method   - "GET", "POST", etc.
 * @param {object} body     - JSON body (for POST requests)
 * @returns {Promise<object>} - parsed JSON response
 */
async function api(endpoint, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);

  let response;
  try {
    response = await fetch(`${API_BASE}${endpoint}`, options);
  } catch (networkErr) {
    // fetch() itself threw — backend is unreachable or CORS preflight failed
    throw new Error(
      "Cannot reach the server. Make sure the backend is running on " +
      API_BASE + " and you are opening the frontend via Live Server (not file://)"
    );
  }

  // If unauthorized, clear auth and redirect to login
  if (response.status === 401) {
    clearAuth();
    window.location.href = "index.html";
    return;
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Something went wrong");
  }

  return data;
}

// ─── Toast Notifications ──────────────────────────────────────────────────────

let toastTimer = null;

/**
 * Show a brief toast notification.
 * @param {string} message - text to display
 * @param {"success"|"error"|"info"} type - style variant
 */
function showToast(message, type = "info") {
  // Remove any existing toast
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();
  if (toastTimer) clearTimeout(toastTimer);

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  toastTimer = setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ─── Alert Banner Helpers ─────────────────────────────────────────────────────

function showAlert(id, message, type = "error") {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = message;
  el.className = `alert alert-${type}`;
  el.style.display = "block";
}

function hideAlert(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "none";
}

// ─── Format Helpers ───────────────────────────────────────────────────────────

/** Format an ISO date string to a readable local date */
function formatDate(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Format an ISO date string to a readable local time */
function formatDateTime(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Escape HTML to prevent XSS when inserting user content into the DOM */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}


// /**
//  * app.js — Shared utilities for all frontend pages.
//  * Handles: API calls, auth token management, toast notifications.
//  */

// const API_BASE = "http://localhost:8000";

// // ─── Auth Helpers ─────────────────────────────────────────────────────────────

// /** Save login data to localStorage */
// function saveAuth(token, user) {
//   localStorage.setItem("token", token);
//   localStorage.setItem("user", JSON.stringify(user));
// }

// /** Get the current JWT token */
// function getToken() {
//   return localStorage.getItem("token");
// }

// /** Get the current user object */
// function getUser() {
//   const raw = localStorage.getItem("user");
//   return raw ? JSON.parse(raw) : null;
// }

// /** Remove auth data (logout) */
// function clearAuth() {
//   localStorage.removeItem("token");
//   localStorage.removeItem("user");
// }

// /** Redirect to login if not authenticated */
// function requireAuth(role = "student") {
//   const token = getToken();
//   const user = getUser();
//   if (!token || !user) {
//     window.location.href = "index.html";
//     return false;
//   }
//   if (role === "admin" && user.role !== "admin") {
//     window.location.href = "dashboard.html";
//     return false;
//   }
//   return true;
// }

// // ─── API Fetch Helper ─────────────────────────────────────────────────────────

// /**
//  * Make an authenticated API call.
//  * @param {string} endpoint - e.g. "/chat"
//  * @param {string} method   - "GET", "POST", etc.
//  * @param {object} body     - JSON body (for POST requests)
//  * @returns {Promise<object>} - parsed JSON response
//  */
// async function api(endpoint, method = "GET", body = null) {
//   const headers = { "Content-Type": "application/json" };
//   const token = getToken();
//   if (token) headers["Authorization"] = `Bearer ${token}`;

//   const options = { method, headers };
//   if (body) options.body = JSON.stringify(body);

//   const response = await fetch(`${API_BASE}${endpoint}`, options);

//   // If unauthorized, clear auth and redirect to login
//   if (response.status === 401) {
//     clearAuth();
//     window.location.href = "index.html";
//     return;
//   }

//   const data = await response.json();

//   if (!response.ok) {
//     throw new Error(data.detail || "Something went wrong");
//   }

//   return data;
// }

// // ─── Toast Notifications ──────────────────────────────────────────────────────

// let toastTimer = null;

// /**
//  * Show a brief toast notification.
//  * @param {string} message - text to display
//  * @param {"success"|"error"|"info"} type - style variant
//  */
// function showToast(message, type = "info") {
//   // Remove any existing toast
//   const existing = document.querySelector(".toast");
//   if (existing) existing.remove();
//   if (toastTimer) clearTimeout(toastTimer);

//   const toast = document.createElement("div");
//   toast.className = `toast toast-${type}`;
//   toast.textContent = message;
//   document.body.appendChild(toast);

//   toastTimer = setTimeout(() => {
//     toast.style.opacity = "0";
//     toast.style.transition = "opacity 0.3s";
//     setTimeout(() => toast.remove(), 300);
//   }, 3500);
// }

// // ─── Alert Banner Helpers ─────────────────────────────────────────────────────

// function showAlert(id, message, type = "error") {
//   const el = document.getElementById(id);
//   if (!el) return;
//   el.textContent = message;
//   el.className = `alert alert-${type}`;
//   el.style.display = "block";
// }

// function hideAlert(id) {
//   const el = document.getElementById(id);
//   if (el) el.style.display = "none";
// }

// // ─── Format Helpers ───────────────────────────────────────────────────────────

// /** Format an ISO date string to a readable local date */
// function formatDate(isoString) {
//   if (!isoString) return "—";
//   return new Date(isoString).toLocaleDateString("en-US", {
//     month: "short",
//     day: "numeric",
//     year: "numeric",
//   });
// }

// /** Format an ISO date string to a readable local time */
// function formatDateTime(isoString) {
//   if (!isoString) return "—";
//   return new Date(isoString).toLocaleString("en-US", {
//     month: "short",
//     day: "numeric",
//     hour: "2-digit",
//     minute: "2-digit",
//   });
// }

// /** Escape HTML to prevent XSS when inserting user content into the DOM */
// function escapeHtml(text) {
//   const div = document.createElement("div");
//   div.textContent = text;
//   return div.innerHTML;
// }
