/**
 * AI Content Detector - Frontend Client Logic
 * Handles file dropzone, previews, AJAX uploads, circular gauge animations,
 * and live dashboard filtering & deletion.
 */

document.addEventListener('DOMContentLoaded', () => {
    initDropzoneAndUpload();
    initGaugeAnimation();
    initDashboard();
    initCopyReport();
});

// ============================================================
// 1. DROPZONE & UPLOAD HANDLING (index.html)
// ============================================================
function initDropzoneAndUpload() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const previewContainer = document.getElementById('previewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const videoPreview = document.getElementById('videoPreview');
    const previewFileName = document.getElementById('previewFileName');
    const previewFileSize = document.getElementById('previewFileSize');
    const btnChangeFile = document.getElementById('btnChangeFile');
    const btnAnalyze = document.getElementById('btnAnalyze');
    const scannerOverlay = document.getElementById('scannerOverlay');
    const scannerStatusText = document.getElementById('scannerStatusText');

    if (!dropzone || !fileInput) return;

    let selectedFile = null;

    // Click on dropzone opens native file picker
    dropzone.addEventListener('click', () => fileInput.click());

    // Drag & drop visual events
    ['dragenter', 'dragover'].forEach(evtName => {
        dropzone.addEventListener(evtName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('drag-active');
        });
    });

    ['dragleave', 'drop'].forEach(evtName => {
        dropzone.addEventListener(evtName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('drag-active');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFileSelection(files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFileSelection(fileInput.files[0]);
        }
    });

    if (btnChangeFile) {
        btnChangeFile.addEventListener('click', () => {
            fileInput.value = '';
            fileInput.click();
        });
    }

    function handleFileSelection(file) {
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/webm'];
        const ext = file.name.split('.').pop().toLowerCase();
        const allowedExts = ['jpg', 'jpeg', 'png', 'webp', 'mp4', 'webm'];

        if (!allowedExts.includes(ext) && !allowedTypes.includes(file.type)) {
            showToast('Unsupported format! Please choose JPG, PNG, WEBP, MP4, or WEBM.', 'error');
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            showToast('File too large! Maximum allowed upload size is 50MB.', 'error');
            return;
        }

        selectedFile = file;

        // Display File Metadata
        previewFileName.textContent = file.name;
        previewFileSize.textContent = formatBytes(file.size);

        // Display Media Preview
        const isVideo = file.type.startsWith('video/') || ['mp4', 'webm'].includes(ext);
        const objectUrl = URL.createObjectURL(file);

        if (isVideo) {
            imagePreview.style.display = 'none';
            imagePreview.src = '';
            videoPreview.style.display = 'block';
            videoPreview.src = objectUrl;
        } else {
            videoPreview.style.display = 'none';
            videoPreview.src = '';
            imagePreview.style.display = 'block';
            imagePreview.src = objectUrl;
        }

        dropzone.style.display = 'none';
        previewContainer.style.display = 'block';
    }

    // Trigger analysis
    if (btnAnalyze) {
        btnAnalyze.addEventListener('click', async () => {
            if (!selectedFile) {
                showToast('Please select a file to analyze.', 'error');
                return;
            }

            // Disable buttons & show animated scanning beam
            btnAnalyze.disabled = true;
            if (btnChangeFile) btnChangeFile.disabled = true;
            scannerOverlay.classList.add('active');

            // Rotating status steps
            const scanMessages = [
                'Inspecting high-frequency noise & pixel residuals...',
                'Checking EXIF authenticity & generator fingerprints...',
                'Evaluating texture uniformity & diffusion artifacts...',
                'Synthesizing multi-signal confidence score...'
            ];
            let msgIdx = 0;
            const statusInterval = setInterval(() => {
                msgIdx = (msgIdx + 1) % scanMessages.length;
                if (scannerStatusText) scannerStatusText.textContent = scanMessages[msgIdx];
            }, 1200);

            const formData = new FormData();
            formData.append('file', selectedFile);

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    body: formData
                });

                clearInterval(statusInterval);
                const data = await response.json();

                if (response.ok && data.success) {
                    showToast('Scan complete! Redirecting to report...', 'success');
                    setTimeout(() => {
                        window.location.href = data.data.redirect_url;
                    }, 400);
                } else {
                    throw new Error(data.error || 'Failed to analyze content.');
                }
            } catch (err) {
                clearInterval(statusInterval);
                scannerOverlay.classList.remove('active');
                btnAnalyze.disabled = false;
                if (btnChangeFile) btnChangeFile.disabled = false;
                showToast(`Analysis Error: ${err.message}`, 'error');
            }
        });
    }
}


// ============================================================
// 2. CIRCULAR GAUGE & NUMBER ANIMATION (result.html)
// ============================================================
function initGaugeAnimation() {
    const gaugeContainer = document.getElementById('gaugeContainer');
    const gaugeCircle = document.getElementById('gaugeProgressCircle');
    const gaugeNumber = document.getElementById('gaugeNumber');

    if (!gaugeContainer || !gaugeCircle || !gaugeNumber) return;

    const targetScore = parseFloat(gaugeContainer.dataset.score || '0');
    const radius = 85;
    const circumference = 2 * Math.PI * radius; // ~534.07

    gaugeCircle.style.strokeDasharray = circumference;
    gaugeCircle.style.strokeDashoffset = circumference;

    // Color code stroke
    let strokeColor = '#10b981'; // Green for Real
    if (targetScore >= 69.5) {
        strokeColor = '#ef4444'; // Red for AI
    } else if (targetScore >= 30.5) {
        strokeColor = '#f59e0b'; // Amber for Uncertain
    }
    gaugeCircle.style.stroke = strokeColor;

    // Trigger stroke animation
    setTimeout(() => {
        const offset = circumference - (targetScore / 100) * circumference;
        gaugeCircle.style.strokeDashoffset = offset;
    }, 150);

    // Number count-up animation
    const duration = 1600; // ms
    const startTime = performance.now();

    function updateCounter(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Easing out cubic
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const currentScore = (easeOut * targetScore).toFixed(1);

        gaugeNumber.textContent = currentScore;

        if (progress < 1) {
            requestAnimationFrame(updateCounter);
        } else {
            gaugeNumber.textContent = targetScore.toFixed(1);
        }
    }

    requestAnimationFrame(updateCounter);
}


// ============================================================
// 3. DASHBOARD & HISTORY MANAGEMENT (history.html)
// ============================================================
function initDashboard() {
    const tableBody = document.getElementById('historyTableBody');
    if (!tableBody) return;

    const statTotal = document.getElementById('statTotal');
    const statAi = document.getElementById('statAi');
    const statReal = document.getElementById('statReal');
    const statWeek = document.getElementById('statWeek');
    const emptyState = document.getElementById('emptyState');
    const searchInput = document.getElementById('searchInput');
    const filterPills = document.querySelectorAll('#filterPills .filter-btn');

    let currentTypeFilter = 'all';
    let currentLabelFilter = 'all';
    let currentSearch = '';

    // Load initial data
    loadScans();

    // Filter pill click listener
    filterPills.forEach(btn => {
        btn.addEventListener('click', () => {
            filterPills.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const filterType = btn.dataset.filterType;
            const filterVal = btn.dataset.val;

            if (filterType === 'type') {
                currentTypeFilter = filterVal;
                currentLabelFilter = 'all';
            } else if (filterType === 'label') {
                currentLabelFilter = filterVal;
                currentTypeFilter = 'all';
            }
            loadScans();
        });
    });

    // Search input with debounce
    let searchTimeout = null;
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentSearch = e.target.value.trim();
                loadScans();
            }, 300);
        });
    }

    async function loadScans() {
        try {
            const url = new URL('/api/history', window.location.origin);
            if (currentTypeFilter !== 'all') url.searchParams.set('type', currentTypeFilter);
            if (currentLabelFilter !== 'all') url.searchParams.set('label', currentLabelFilter);
            if (currentSearch) url.searchParams.set('search', currentSearch);

            const res = await fetch(url);
            const data = await res.json();

            if (res.ok) {
                renderStats(data.stats);
                renderTable(data.scans);
            }
        } catch (err) {
            console.error('Failed to load history:', err);
            showToast('Failed to load history data.', 'error');
        }
    }

    function renderStats(stats) {
        if (!stats) return;
        if (statTotal) statTotal.textContent = stats.total || 0;
        if (statAi) statAi.textContent = stats.ai_count || 0;
        if (statReal) statReal.textContent = stats.real_count || 0;
        if (statWeek) statWeek.textContent = stats.this_week || 0;
    }

    function renderTable(scans) {
        if (!scans || scans.length === 0) {
            tableBody.innerHTML = '';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (emptyState) emptyState.style.display = 'none';

        tableBody.innerHTML = scans.map(scan => {
            const isVideo = scan.file_type === 'video';
            const score = scan.ai_score;
            let scoreColor = '#10b981';
            let badgeClass = 'badge-real';
            if (score >= 69.5) {
                scoreColor = '#ef4444';
                badgeClass = 'badge-ai';
            } else if (score >= 30.5) {
                scoreColor = '#f59e0b';
                badgeClass = 'badge-uncertain';
            }

            // Thumbnail display
            const thumbHtml = isVideo
                ? `<div style="width: 48px; height: 48px; border-radius: 8px; background: #000; display: flex; align-items: center; justify-content: center; color: var(--primary-light);">
                     <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                   </div>`
                : `<img src="${scan.file_path}" class="table-thumb" alt="Thumb" onerror="this.src='data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'48\' height=\'48\' fill=\'%23334155\'><rect width=\'48\' height=\'48\'/></svg>'">`;

            return `
                <tr id="scan-row-${scan.id}">
                    <td>${thumbHtml}</td>
                    <td>
                        <div style="font-weight: 600; color: #fff; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(scan.original_filename)}">
                            ${escapeHtml(scan.original_filename)}
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${scan.filename.substring(0, 12)}...</div>
                    </td>
                    <td>
                        <span class="type-pill ${scan.file_type}">${scan.file_type}</span>
                    </td>
                    <td>
                        <div class="mini-score-wrap">
                            <span style="font-weight: 700; font-size: 0.92rem; color: ${scoreColor}; min-width: 44px;">
                                ${score}%
                            </span>
                            <div class="mini-score-bar">
                                <div class="mini-score-fill" style="width: ${Math.min(100, Math.max(5, score))}%; background-color: ${scoreColor};"></div>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge ${badgeClass}" style="font-size: 0.75rem; padding: 0.25rem 0.65rem;">
                            ${escapeHtml(scan.label)}
                        </span>
                    </td>
                    <td class="mono" style="font-size: 0.82rem; color: var(--text-secondary);">
                        ${scan.created_at || 'Recently'}
                    </td>
                    <td style="text-align: right;">
                        <div style="display: inline-flex; align-items: center; gap: 0.4rem;">
                            <a href="/result/${scan.id}" class="btn-icon-action" title="View Detailed Report">
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            </a>
                            <button type="button" class="btn-icon-action delete" title="Delete Record" onclick="deleteScanRecord(${scan.id})">
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Expose deleteScanRecord globally so inline button can invoke it
    window.deleteScanRecord = async function(scanId) {
        if (!confirm('Are you sure you want to delete this scan record and its file?')) {
            return;
        }

        try {
            const res = await fetch(`/api/history/${scanId}`, {
                method: 'DELETE'
            });
            const data = await res.json();

            if (res.ok && data.success) {
                const row = document.getElementById(`scan-row-${scanId}`);
                if (row) {
                    row.style.opacity = '0';
                    row.style.transform = 'scale(0.95)';
                    setTimeout(() => {
                        row.remove();
                        loadScans(); // Refresh counters & table
                    }, 200);
                }
                showToast('Scan record deleted.', 'success');
            } else {
                throw new Error(data.error || 'Failed to delete record.');
            }
        } catch (err) {
            showToast(`Deletion failed: ${err.message}`, 'error');
        }
    };
}


// ============================================================
// 4. COPY REPORT SUMMARY (result.html)
// ============================================================
function initCopyReport() {
    const btnCopy = document.getElementById('btnCopyReport');
    if (!btnCopy) return;

    btnCopy.addEventListener('click', () => {
        const title = document.title;
        const score = document.getElementById('gaugeNumber')?.textContent || '0';
        const badge = document.getElementById('resultBadge')?.textContent.trim() || '';
        const summary = document.querySelector('.result-summary-box')?.textContent.trim() || '';

        const textToCopy = `AI Content Detector Report:\n- Verdict: ${badge} (${score}% AI probability)\n- Summary: ${summary}\n- Generated by AI Content Detector`;

        navigator.clipboard.writeText(textToCopy).then(() => {
            showToast('Summary copied to clipboard!', 'success');
        }).catch(() => {
            showToast('Could not copy automatically.', 'error');
        });
    });
}


// ============================================================
// 5. UTILITIES (Toast, formatting, escaping)
// ============================================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';

    let iconSvg = '';
    if (type === 'success') {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `${iconSvg} <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
