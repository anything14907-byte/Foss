/**
 * StackDoc - Chrome Extension Client Script
 * Communicates with local FastAPI endpoint (http://localhost:8000/parse-document)
 * Powered by Donut Transformer & Build with Stack
 */

const API_BASE_URL = "http://localhost:8000";

// DOM Elements
const statusIndicator = document.getElementById("statusIndicator");
const inputSection = document.getElementById("inputSection");
const loadingSection = document.getElementById("loadingSection");
const errorSection = document.getElementById("errorSection");
const resultSection = document.getElementById("resultSection");

const captureTabBtn = document.getElementById("captureTabBtn");
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const retryBtn = document.getElementById("retryBtn");
const parseAnotherBtn = document.getElementById("parseAnotherBtn");
const copyJsonBtn = document.getElementById("copyJsonBtn");

// Result DOM Elements
const resVendor = document.getElementById("resVendor");
const resDate = document.getElementById("resDate");
const resTotal = document.getElementById("resTotal");
const resConfidence = document.getElementById("resConfidence");
const resSubtotal = document.getElementById("resSubtotal");
const resTax = document.getElementById("resTax");
const resPayment = document.getElementById("resPayment");
const resTime = document.getElementById("resTime");
const itemsCountBadge = document.getElementById("itemsCountBadge");
const lineItemsBody = document.getElementById("lineItemsBody");
const jsonPreview = document.getElementById("jsonPreview");
const errorMessage = document.getElementById("errorMessage");

let lastParsedData = null;

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  checkBackendHealth();
  setupEventListeners();
});

// Check if local FastAPI backend is active
async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (res.ok) {
      statusIndicator.classList.add("online");
      statusIndicator.classList.remove("offline");
      statusIndicator.title = "Local Donut ML Backend Connected";
    } else {
      throw new Error("Backend replied with non-200");
    }
  } catch (err) {
    statusIndicator.classList.add("offline");
    statusIndicator.classList.remove("online");
    statusIndicator.title = "Backend Offline. Ensure FastAPI is running on http://localhost:8000";
  }
}

function setupEventListeners() {
  // Capture Tab Screenshot
  captureTabBtn.addEventListener("click", captureCurrentTab);

  // File Drop Zone
  dropZone.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      uploadAndParse(e.target.files[0]);
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadAndParse(e.dataTransfer.files[0]);
    }
  });

  // Retry
  retryBtn.addEventListener("click", () => {
    showSection(inputSection);
    checkBackendHealth();
  });

  // Parse Another
  parseAnotherBtn.addEventListener("click", () => {
    fileInput.value = "";
    showSection(inputSection);
  });

  // Copy JSON
  copyJsonBtn.addEventListener("click", () => {
    if (lastParsedData) {
      navigator.clipboard.writeText(JSON.stringify(lastParsedData, null, 2)).then(() => {
        copyJsonBtn.textContent = "Copied!";
        setTimeout(() => { copyJsonBtn.textContent = "Copy JSON"; }, 2000);
      });
    }
  });
}

// Capture currently viewed tab / PDF
async function captureCurrentTab() {
  try {
    showSection(loadingSection);
    
    // Check if chrome.tabs is available
    if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.captureVisibleTab) {
      chrome.tabs.captureVisibleTab(null, { format: "png" }, async (dataUrl) => {
        if (!dataUrl) {
          throw new Error("Could not capture tab image. Make sure browser permissions are granted.");
        }
        
        // Convert base64 dataUrl to Blob & File
        const res = await fetch(dataUrl);
        const blob = await res.blob();
        const file = new File([blob], `tab_capture_${Date.now()}.png`, { type: "image/png" });
        await uploadAndParse(file);
      });
    } else {
      throw new Error("Chrome tab capture API not available in current context.");
    }
  } catch (err) {
    showError(err.message || "Failed to capture current tab.");
  }
}

// Upload file to local FastAPI backend
async function uploadAndParse(file) {
  showSection(loadingSection);

  const formData = new FormData();
  formData.append("file", file);
  formData.append("page_number", 1);

  try {
    const response = await fetch(`${API_BASE_URL}/parse-document`, {
      method: "POST",
      headers: {
        "x-stack-project-id": "stack-hackathon-foss-forge"
      },
      body: formData
    });

    if (!response.ok) {
      let errDetail = `HTTP ${response.status}`;
      try {
        const errorJson = await response.json();
        errDetail = errorJson.detail || errDetail;
      } catch (_) {}
      throw new Error(errDetail);
    }

    const data = await response.json();
    lastParsedData = data;
    renderResults(data);
    showSection(resultSection);
    statusIndicator.classList.add("online");
  } catch (err) {
    console.error("Document parsing error:", err);
    showError(
      `Connection or inference error: ${err.message}. ` +
      `Verify the FastAPI server is running locally on http://localhost:8000.`
    );
  }
}

// Render structured layout-extracted data
function renderResults(data) {
  resVendor.textContent = data.vendor_name || "Unknown";
  resDate.textContent = data.date || "N/A";
  
  // Format total
  let totalText = data.total_amount || "0.00";
  if (!totalText.startsWith("$") && !totalText.startsWith("€") && !totalText.startsWith("£")) {
    totalText = `$${totalText}`;
  }
  resTotal.textContent = totalText;
  
  // Confidence
  const confPercent = Math.round((data.confidence_score || 0.95) * 100);
  resConfidence.textContent = `${confPercent}%`;
  
  // Metadata
  resSubtotal.textContent = data.subtotal || "-";
  resTax.textContent = data.tax_amount || "-";
  resPayment.textContent = data.payment_method || "Standard";
  resTime.textContent = data.execution_time_seconds ? `${data.execution_time_seconds}s` : "0.4s";

  // Render Line Items Table
  lineItemsBody.innerHTML = "";
  const items = data.line_items || [];
  itemsCountBadge.textContent = `${items.length} item${items.length === 1 ? '' : 's'}`;

  if (items.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5" style="text-align:center; color:#64748b; padding:12px;">No individual line items parsed</td>`;
    lineItemsBody.appendChild(tr);
  } else {
    items.forEach((item, idx) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${item.line_number || idx + 1}</td>
        <td><strong>${escapeHtml(item.name || "Item")}</strong></td>
        <td>${escapeHtml(String(item.quantity || "1"))}</td>
        <td>${escapeHtml(String(item.unit_price || "-"))}</td>
        <td><strong>${escapeHtml(String(item.total_price || "-"))}</strong></td>
      `;
      lineItemsBody.appendChild(tr);
    });
  }

  // Raw JSON
  jsonPreview.textContent = JSON.stringify(data, null, 2);
}

function showSection(sectionElement) {
  inputSection.classList.add("hidden");
  loadingSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  resultSection.classList.add("hidden");

  sectionElement.classList.remove("hidden");
}

function showError(msg) {
  errorMessage.textContent = msg;
  showSection(errorSection);
  statusIndicator.classList.add("offline");
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
