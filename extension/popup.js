/**
 * StackDoc - Chrome Extension Client Script
 * Communicates with local FastAPI endpoint (http://localhost:8000/parse-document)
 * Supports Donut VLM & PyMuPDF Layout Engine with Canvas Box Visualizer.
 * Powered by Build with Stack.
 */

const API_BASE_URL = "http://localhost:8000";

// DOM Elements
const statusIndicator = document.getElementById("statusIndicator");
const demoBadge = document.getElementById("demoBadge");
const engineBadge = document.getElementById("engineBadge");

const inputSection = document.getElementById("inputSection");
const loadingSection = document.getElementById("loadingSection");
const errorSection = document.getElementById("errorSection");
const resultSection = document.getElementById("resultSection");

const captureTabBtn = document.getElementById("captureTabBtn");
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const modeSelect = document.getElementById("modeSelect");
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

// Canvas Overlay Elements
const layoutBoxContainer = document.getElementById("layoutBoxContainer");
const layoutCanvas = document.getElementById("layoutCanvas");
const toggleBoxesBtn = document.getElementById("toggleBoxesBtn");

let lastParsedData = null;
let showBoxes = true;

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
      const data = await res.json();
      statusIndicator.classList.add("online");
      statusIndicator.classList.remove("offline");
      statusIndicator.title = "StackDoc ML Backend Connected";
      if (data.demo_mode) {
        demoBadge.classList.remove("hidden");
        demoBadge.title = "Server running in STACKDOC_DEMO_MODE=1";
      }
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
  captureTabBtn.addEventListener("click", captureCurrentTab);
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

  retryBtn.addEventListener("click", () => {
    showSection(inputSection);
    checkBackendHealth();
  });

  parseAnotherBtn.addEventListener("click", () => {
    fileInput.value = "";
    showSection(inputSection);
    demoBadge.classList.add("hidden");
    engineBadge.classList.add("hidden");
  });

  copyJsonBtn.addEventListener("click", () => {
    if (lastParsedData) {
      navigator.clipboard.writeText(JSON.stringify(lastParsedData, null, 2)).then(() => {
        copyJsonBtn.textContent = "Copied!";
        setTimeout(() => { copyJsonBtn.textContent = "Copy JSON"; }, 2000);
      });
    }
  });

  if (toggleBoxesBtn) {
    toggleBoxesBtn.addEventListener("click", () => {
      showBoxes = !showBoxes;
      toggleBoxesBtn.textContent = showBoxes ? "Hide Overlay" : "Show Overlay";
      if (lastParsedData && lastParsedData.boxes) {
        renderCanvasBoxes(lastParsedData.boxes, showBoxes);
      }
    });
  }
}

// Capture currently viewed tab / PDF
async function captureCurrentTab() {
  try {
    showSection(loadingSection);
    
    if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.captureVisibleTab) {
      chrome.tabs.captureVisibleTab(null, { format: "png" }, async (dataUrl) => {
        if (!dataUrl) {
          throw new Error("Could not capture tab image. Make sure browser permissions are granted.");
        }
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

  const selectedMode = modeSelect ? modeSelect.value : "auto";
  const formData = new FormData();
  formData.append("file", file);
  formData.append("page_number", 1);

  const url = `${API_BASE_URL}/parse-document?mode=${encodeURIComponent(selectedMode)}`;

  try {
    const response = await fetch(url, {
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
  if (data.confidence !== null && data.confidence !== undefined) {
    const confPercent = Math.round(data.confidence * 100);
    resConfidence.textContent = `${confPercent}%`;
  } else {
    resConfidence.textContent = "N/A";
  }
  
  // Metadata
  resSubtotal.textContent = data.subtotal || "-";
  resTax.textContent = data.tax_amount || "-";
  resPayment.textContent = data.payment_method || "Standard";

  const latencyVal = data.latency_seconds !== undefined ? data.latency_seconds : data.execution_time_seconds;
  resTime.textContent = latencyVal ? `${latencyVal}s` : "-";

  // Badges
  if (data.demo_cached) {
    demoBadge.classList.remove("hidden");
  } else {
    demoBadge.classList.add("hidden");
  }

  if (data.engine) {
    engineBadge.textContent = data.engine === "layout" ? "Layout Engine" : "Donut VLM";
    engineBadge.classList.remove("hidden");
  } else {
    engineBadge.classList.add("hidden");
  }

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
        <td><strong>${escapeHtml(item.name || item.description || "Item")}</strong></td>
        <td>${escapeHtml(String(item.quantity || "1"))}</td>
        <td>${escapeHtml(String(item.unit_price || "-"))}</td>
        <td><strong>${escapeHtml(String(item.line_total || item.total_price || "-"))}</strong></td>
      `;
      lineItemsBody.appendChild(tr);
    });
  }

  // Canvas visualizer for coordinate layout boxes
  try {
    if (data.boxes && layoutBoxContainer && layoutCanvas) {
      layoutBoxContainer.classList.remove("hidden");
      renderCanvasBoxes(data.boxes, showBoxes);
    } else if (layoutBoxContainer) {
      layoutBoxContainer.classList.add("hidden");
    }
  } catch (e) {
    console.warn("Failed to render canvas boxes:", e);
  }

  // Raw JSON
  jsonPreview.textContent = JSON.stringify(data, null, 2);
}

// Safely draw coordinate layout bounding boxes onto canvas
function renderCanvasBoxes(boxes, visible) {
  if (!layoutCanvas) return;
  const ctx = layoutCanvas.getContext("2d");
  ctx.clearRect(0, 0, layoutCanvas.width, layoutCanvas.height);

  if (!visible) return;

  // Background page mock
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(0, 0, layoutCanvas.width, layoutCanvas.height);
  ctx.strokeStyle = "#475569";
  ctx.strokeRect(5, 5, layoutCanvas.width - 10, layoutCanvas.height - 10);

  // Normalize page bounds (approx 612x792 standard letter size)
  const scaleX = (layoutCanvas.width - 20) / 612.0;
  const scaleY = (layoutCanvas.height - 20) / 792.0;
  const offsetX = 10;
  const offsetY = 10;

  function drawBox(bbox, label, color) {
    if (!bbox || bbox.length < 4) return;
    const x = offsetX + bbox[0] * scaleX;
    const y = offsetY + bbox[1] * scaleY;
    const w = Math.max(8, (bbox[2] - bbox[0]) * scaleX);
    const h = Math.max(6, (bbox[3] - bbox[1]) * scaleY);

    ctx.fillStyle = color.replace(")", ", 0.25)").replace("rgb", "rgba");
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x, y, w, h);

    if (label) {
      ctx.fillStyle = color;
      ctx.font = "9px sans-serif";
      ctx.fillText(label, x + 2, Math.max(10, y - 2));
    }
  }

  if (boxes.vendor && boxes.vendor.bbox) {
    drawBox(boxes.vendor.bbox, "Vendor", "rgb(99, 102, 241)");
  }
  if (boxes.date && boxes.date.bbox) {
    drawBox(boxes.date.bbox, "Date", "rgb(56, 189, 248)");
  }
  if (boxes.total && boxes.total.bbox) {
    drawBox(boxes.total.bbox, "Total", "rgb(52, 211, 153)");
  }
  if (boxes.line_items && Array.isArray(boxes.line_items)) {
    boxes.line_items.forEach((item, idx) => {
      drawBox(item.bbox, `Item ${idx+1}`, "rgb(168, 85, 247)");
    });
  }
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
