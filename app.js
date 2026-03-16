/**
 * app.js — SyllabSync Frontend
 */

// ── Configuration ──
const API_BASE = window.location.origin;
let selectedFiles = []; 

// ── DOM References ──
const dropZone      = document.getElementById('dropZone');
const fileInput     = document.getElementById('fileInput');
const fileList      = document.getElementById('fileList');
const analyseRow    = document.getElementById('analyseRow');
const analyseBtn    = document.getElementById('analyseBtn');
const fileCountBadge= document.getElementById('fileCountBadge');
const progressPanel = document.getElementById('progressPanel');

// ── 1. Event Listeners ──

// Open file picker when clicking browse
if (fileInput) {
    fileInput.addEventListener('change', e => addFiles(e.target.files));
}

// Drag and Drop Logic
if (dropZone) {
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        addFiles(e.dataTransfer.files);
    });
}

// ── 2. The Missing "addFiles" Logic ──

function addFiles(files) {
    const pdfs = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    
    pdfs.forEach(f => {
        // Only add if file isn't already in the list
        if (!selectedFiles.find(existing => existing.name === f.name)) {
            selectedFiles.push(f);
        }
    });

    renderFileList();
}

function renderFileList() {
    if (!fileList || !analyseRow) return;

    fileList.innerHTML = '';

    if (selectedFiles.length === 0) {
        fileList.hidden = true;
        analyseRow.hidden = true;
        return;
    }

    fileList.hidden = false;
    analyseRow.hidden = false;

    selectedFiles.forEach((file, idx) => {
        const card = document.createElement('div');
        card.className = 'file-card';
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid #eee;">
                <span>📄 ${file.name}</span>
                <button onclick="removeFile(${idx})" style="color:red; cursor:pointer; background:none; border:none;">✕</button>
            </div>
        `;
        fileList.appendChild(card);
    });

    fileCountBadge.textContent = `${selectedFiles.length} file(s) selected`;
}

// Global helper for the remove button
window.removeFile = function(idx) {
    selectedFiles.splice(idx, 1);
    renderFileList();
};

// ── 3. The "Analyse" Logic ──

async function startAnalysis() {
    if (selectedFiles.length === 0) return;

    analyseBtn.disabled = true;
    analyseBtn.textContent = "Uploading...";
    progressPanel.hidden = false;

    const formData = new FormData();
    // CRITICAL: Name must be 'files' to match FastAPI backend
    selectedFiles.forEach(f => formData.append('files', f));

    try {
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Upload failed");

        const data = await response.json();
        console.log("Job started:", data.job_id);
        
        // Start listening to the SSE progress
        listenToProgress(data.job_id);

    } catch (err) {
        alert("Error: " + err.message);
        analyseBtn.disabled = false;
        analyseBtn.textContent = "Analyse with SyllabSync →";
    }
}

function listenToProgress(jobId) {
    const sse = new EventSource(`${API_BASE}/api/progress/${jobId}`);
    
    sse.onmessage = (e) => {
        const data = JSON.parse(e.data);
        const progressFill = document.getElementById('progressFill');
        const progressLabel = document.getElementById('progressLabel');

        if (progressFill) progressFill.style.width = `${data.progress}%`;
        if (progressLabel) progressLabel.textContent = data.step;

        if (data.status === 'completed') {
            sse.close();
            alert("Analysis Complete!");
            // You can call your renderResults function here
        }
        
        if (data.status === 'failed') {
            sse.close();
            alert("Processing failed: " + data.error);
        }
    };
}

analyseBtn.addEventListener('click', startAnalysis);