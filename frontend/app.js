/* Frontend API target */
const API_BASE = "https://ai-doc-analyzer-yr6n.onrender.com";

/* ══════════════════════════════════════════
   DOM REFS
══════════════════════════════════════════ */
const dropzone     = document.getElementById("dropzone");
const fileInput    = document.getElementById("fileInput");
const fileInfo     = document.getElementById("fileInfo");
const fileNameEl   = document.getElementById("fileName");
const clearFileBtn = document.getElementById("clearFile");
const apiKeyInput  = document.getElementById("apiKey");
const analyzeBtn   = document.getElementById("analyzeBtn");
const btnLabel     = document.getElementById("btnLabel");
const btnSpinner   = document.getElementById("btnSpinner");
const results      = document.getElementById("results");
const errorBanner  = document.getElementById("errorBanner");
const errorMsg     = document.getElementById("errorMsg");
const sentimentBadge = document.getElementById("sentimentBadge");
const summaryText  = document.getElementById("summaryText");
const entityGrid   = document.getElementById("entityGrid");

/* ══════════════════════════════════════════
   STATE
══════════════════════════════════════════ */
let selectedFile = null;

/* ══════════════════════════════════════════
   DRAG & DROP
══════════════════════════════════════════ */
["dragenter","dragover"].forEach(evt =>
  dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add("drag-over"); })
);
["dragleave","drop"].forEach(evt =>
  dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove("drag-over"); })
);
dropzone.addEventListener("drop", e => {
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});
dropzone.addEventListener("click", e => {
  // Only trigger if click was NOT on the label/button itself
  if (e.target !== dropzone && !dropzone.contains(e.target)) return;
  if (e.target.tagName === "LABEL") return;
  fileInput.click();
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

/* ══════════════════════════════════════════
   FILE HELPERS
══════════════════════════════════════════ */
function setFile(file) {
  selectedFile = file;
  fileNameEl.textContent = file.name;
  fileInfo.classList.remove("hidden");
  analyzeBtn.disabled = false;
  hideError();
  results.classList.add("hidden");
}

function clearFile() {
  selectedFile = null;
  fileInput.value = "";
  fileInfo.classList.add("hidden");
  analyzeBtn.disabled = true;
  results.classList.add("hidden");
  hideError();
}

clearFileBtn.addEventListener("click", clearFile);

function getFileType(file) {
  const name = file.name.toLowerCase();
  if (name.endsWith(".pdf"))  return "pdf";
  if (name.endsWith(".docx") || name.endsWith(".doc")) return "docx";
  // images
  if (/\.(png|jpg|jpeg|tiff|tif|bmp|webp)$/.test(name)) return "image";
  return null;
}

/* ══════════════════════════════════════════
   ANALYZE
══════════════════════════════════════════ */
analyzeBtn.addEventListener("click", runAnalysis);

async function runAnalysis() {
  if (!selectedFile) return;

  setLoading(true);
  hideError();
  results.classList.add("hidden");

  try {
    // STEP 1: Wake backend
    await fetch("https://ai-doc-analyzer-yr6n.onrender.com/health");

    // STEP 2: Wait for backend to fully start
    await new Promise(resolve => setTimeout(resolve, 20000));

    // STEP 3: Send actual request
    const formData = new FormData();
    formData.append("file", selectedFile);

    const response = await fetch(
      "https://ai-doc-analyzer-yr6n.onrender.com/proxy-analyze",
      {
        method: "POST",
        body: formData
      }
    );

    if (!response.ok) {
      throw new Error("Server error: " + response.status);
    }

    const data = await response.json();
    renderResults(data);

  } catch (err) {
    console.error(err);
    showError("Server is starting. Please click again after a few seconds.");
  } finally {
    setLoading(false);
  }
}

/* ══════════════════════════════════════════
   RENDER
══════════════════════════════════════════ */
function renderResults(data) {
  // ── Sentiment ──────────────────────────
  const s = (data.sentiment || "Neutral").toLowerCase();
  sentimentBadge.textContent = data.sentiment || "Neutral";
  sentimentBadge.className   = `sentiment-badge ${s}`;

  // ── Summary ────────────────────────────
  summaryText.textContent = data.summary || "No summary available.";

  // ── Entities ───────────────────────────
  const groups = [
    { key: "names",         label: "👤 People" },
    { key: "organizations", label: "🏢 Organizations" },
    { key: "dates",         label: "📅 Dates" },
    { key: "locations",     label: "📍 Locations" },
    { key: "amounts",       label: "💰 Amounts" },
  ];

  entityGrid.innerHTML = "";
  groups.forEach(({ key, label }) => {
    const items = data.entities?.[key] || [];
    const group = document.createElement("div");
    group.className = "entity-group";

    const title = document.createElement("div");
    title.className = "entity-group-title";
    title.textContent = label;

    const chips = document.createElement("div");
    chips.className = "entity-chips";

    if (items.length === 0) {
      const empty = document.createElement("span");
      empty.className = "chip empty";
      empty.textContent = "None detected";
      chips.appendChild(empty);
    } else {
      items.forEach((val, i) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = val;
        chip.style.animationDelay = `${i * 40}ms`;
        chips.appendChild(chip);
      });
    }

    group.appendChild(title);
    group.appendChild(chips);
    entityGrid.appendChild(group);
  });

  results.classList.remove("hidden");
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ══════════════════════════════════════════
   UI STATE HELPERS
══════════════════════════════════════════ */
function setLoading(on) {
  analyzeBtn.disabled = on;
  btnLabel.textContent  = on ? "Analyzing…" : "Analyze Document";
  btnSpinner.classList.toggle("hidden", !on);
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorBanner.classList.remove("hidden");
}

function hideError() {
  errorBanner.classList.add("hidden");
}
