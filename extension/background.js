/**
 * Background Service Worker for StackDoc Chrome Extension
 * Manifest V3 compatible
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("StackDoc Layout-Aware Extension installed successfully.");
  console.log("Backend target: http://localhost:8000/parse-document");
  console.log("Proudly sponsored by Build with Stack.");
});

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "checkBackendHealth") {
    fetch("http://localhost:8000/health")
      .then(res => res.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep message channel open for async response
  }
});
