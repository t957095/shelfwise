/**
 * ShelfWise Frontend Application
 * Features: SSE live updates, product cards, reasoning trace viewer,
 * multi-format export, drag-and-drop CSV upload, accessibility-first
 */

const API_BASE = window.location.origin;

// State
let currentJobId = null;
let eventSource = null;
let products = [];

// DOM Elements
const upcTextarea = document.getElementById('upc-textarea');
const csvFileInput = document.getElementById('csv-file');
const submitBtn = document.getElementById('submit-btn');

const statusSection = document.getElementById('status-section');
const productsGrid = document.getElementById('products-grid');
const productCount = document.getElementById('product-count');
const toastContainer = document.getElementById('toast-container');

// Initialize
function init() {
    bindEvents();
    loadProducts();
    loadStats();
    setupDragDrop();
    setupKeyboardShortcuts();
    setupSearch();
}

function setupSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        filterProducts(query);
    });
}

function filterProducts(query) {
    if (!query) {
        renderProducts();
        return;
    }
    const filtered = products.filter(p => {
        const name = (p.name || '').toLowerCase();
        const brand = (p.brand || '').toLowerCase();
        const category = (p.category || '').toLowerCase();
        const upc = (p.upc || '').toLowerCase();
        return name.includes(query) || brand.includes(query) || category.includes(query) || upc.includes(query);
    });
    renderFilteredProducts(filtered);
}

function renderFilteredProducts(filtered) {
    productCount.textContent = `(${filtered.length} of ${products.length})`;
    if (filtered.length === 0) {
        productsGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="icon">🔍</div>
                <h3>No matches</h3>
                <p>Try a different search term</p>
            </div>
        `;
        return;
    }
    productsGrid.innerHTML = filtered.map(p => renderProductCard(p)).join('');
}

function sortProducts(sortValue) {
    const [field, direction] = sortValue.split('-');
    const sorted = [...products].sort((a, b) => {
        let valA, valB;
        if (field === 'confidence') {
            valA = a.confidence || 0;
            valB = b.confidence || 0;
        } else if (field === 'name') {
            valA = (a.name || '').toLowerCase();
            valB = (b.name || '').toLowerCase();
        } else {
            return 0;
        }
        if (valA < valB) return direction === 'asc' ? -1 : 1;
        if (valA > valB) return direction === 'asc' ? 1 : -1;
        return 0;
    });
    productsGrid.innerHTML = sorted.map(p => renderProductCard(p)).join('');
    productCount.textContent = `(${sorted.length})`;
}

async function clearPortfolio() {
    if (!confirm('Clear all products and jobs? This cannot be undone.')) return;
    try {
        const res = await fetch(`${API_BASE}/api/clear`, { method: 'POST' });
        if (!res.ok) throw new Error('Clear failed');
        products = [];
        renderProducts();
        loadStats();
        showToast('Portfolio cleared', 'info');
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    }
}

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter or Cmd+Enter to submit
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (!submitBtn.disabled) handleSubmit();
        }
        // / to focus search
        if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
            e.preventDefault();
            const searchInput = document.getElementById('search-input');
            if (searchInput) searchInput.focus();
        }
    });
}

function bindEvents() {
    submitBtn.addEventListener('click', handleSubmit);

    document.getElementById('export-csv-btn').addEventListener('click', () => exportPortfolio('csv'));
    document.getElementById('export-json-btn').addEventListener('click', () => exportPortfolio('json'));
    document.getElementById('export-shopify-btn').addEventListener('click', () => exportPortfolio('shopify'));
    document.getElementById('export-amazon-btn').addEventListener('click', () => exportPortfolio('amazon'));
    document.getElementById('export-woocommerce-btn').addEventListener('click', () => exportPortfolio('woocommerce'));
    document.getElementById('export-ebay-btn').addEventListener('click', () => exportPortfolio('ebay'));
    document.getElementById('export-etsy-btn').addEventListener('click', () => exportPortfolio('etsy'));
    document.getElementById('export-bigcommerce-btn').addEventListener('click', () => exportPortfolio('bigcommerce'));

    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            sortProducts(e.target.value);
        });
    }

    const clearBtn = document.getElementById('clear-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearPortfolio);
    }

    // Close modal on overlay click
    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });

    // Lightbox close
    const lightboxClose = document.getElementById('lightbox-close');
    if (lightboxClose) {
        lightboxClose.addEventListener('click', closeLightbox);
    }
    document.getElementById('lightbox-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeLightbox();
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            closeLightbox();
        }
    });
}

function setupDragDrop() {
    const dropZone = document.getElementById('drop-zone');
    if (!dropZone) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-active'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-active'), false);
    });

    dropZone.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        csvFileInput.files = files;
        handleFileUpload(files[0]);
    }
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Submit UPCs
async function handleSubmit() {
    const text = upcTextarea.value.trim();
    const file = csvFileInput.files[0];

    if (!text && !file) {
        showToast('Enter UPCs or upload a CSV file', 'error');
        return;
    }

    setLoading(true);

    try {
        if (file) {
            await handleFileUpload(file);
        } else {
            const upcs = text.split('\n').map(u => u.trim()).filter(u => u.length > 0);
            if (upcs.length === 0) {
                showToast('No valid UPCs found', 'error');
                setLoading(false);
                return;
            }
            await submitUPCs(upcs);
        }
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
        setLoading(false);
    }
}

async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/api/upload-csv`, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
    }

    const data = await res.json();
    showToast(`Processing ${data.total} UPCs from ${data.filename}`, 'info');
    startJobStream(data.job_id);
}

async function submitUPCs(upcs) {
    const res = await fetch(`${API_BASE}/api/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upcs, auto_scrape: true }),
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Submit failed');
    }

    const data = await res.json();
    showToast(`Processing ${data.total} UPCs`, 'info');
    startJobStream(data.job_id);
}

// SSE Streaming
function startJobStream(jobId) {
    currentJobId = jobId;
    statusSection.style.display = 'block';
    setLoading(true);

    // Close existing connection
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource(`${API_BASE}/api/jobs/${jobId}/stream`);

    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === 'update' || data.type === 'complete') {
            updateStatusDisplay(data.job);
        }

        if (data.type === 'complete') {
            eventSource.close();
            setLoading(false);
            showToast('Processing complete!', 'success');
            loadProducts();
        }

        if (data.type === 'error') {
            eventSource.close();
            setLoading(false);
            showToast(data.message, 'error');
        }
    };

    eventSource.onerror = () => {
        eventSource.close();
        setLoading(false);
        showToast('Connection lost. Refresh to see results.', 'error');
    };
}

function updateStatusDisplay(job) {
    document.getElementById('status-total').textContent = job.total || 0;
    document.getElementById('status-queued').textContent = job.queued || 0;
    document.getElementById('status-running').textContent = job.running || 0;
    document.getElementById('status-completed').textContent = job.completed || 0;
    document.getElementById('status-failed').textContent = job.failed || 0;

    const total = job.total || 1;
    const done = (job.completed || 0) + (job.failed || 0);
    const pct = Math.round((done / total) * 100);

    document.getElementById('progress-fill').style.width = `${pct}%`;
    document.getElementById('progress-text').textContent = `${done} of ${total} complete (${pct}%)`;

    // Update running status styling
    const runningEl = document.getElementById('status-running').parentElement;
    if (job.running > 0) {
        runningEl.classList.add('running');
    } else {
        runningEl.classList.remove('running');
    }
}

// Load products
async function loadProducts() {
    try {
        const res = await fetch(`${API_BASE}/api/products`);
        const data = await res.json();
        products = data.products || [];
        renderProducts();
    } catch (err) {
        showToast('Failed to load products', 'error');
    }
}

function renderProducts() {
    productCount.textContent = `(${products.length})`;

    if (products.length === 0) {
        productsGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="icon">📦</div>
                <h3>No products yet</h3>
                <p>Enter UPC codes above to get started</p>
            </div>
        `;
        return;
    }

    productsGrid.innerHTML = products.map(p => renderProductCard(p)).join('');
}

async function loadStats() {
    try {
        const res = await fetch(`${API_BASE}/api/stats`);
        const data = await res.json();

        document.getElementById('stat-total').textContent = data.total_products;
        document.getElementById('stat-avg-confidence').textContent = `${(data.avg_confidence * 100).toFixed(0)}%`;
        document.getElementById('stat-high').textContent = data.confidence_distribution.high;
        document.getElementById('stat-medium').textContent = data.confidence_distribution.medium;
        document.getElementById('stat-low').textContent = data.confidence_distribution.low;

        // Category tags
        const catContainer = document.getElementById('category-tags');
        const cats = Object.entries(data.category_breakdown || {})
            .sort((a, b) => b[1] - a[1])
            .slice(0, 8);
        catContainer.innerHTML = cats.length > 0
            ? '<span style="color: var(--text-muted); font-size: 0.8rem; width: 100%; margin-bottom: 4px;">Categories:</span>' +
              cats.map(([cat, count]) => `<span class="meta-tag"><span class="key">${escapeHtml(cat)}</span> <span class="value">${count}</span></span>`).join('')
            : '';

        // Source tags
        const srcContainer = document.getElementById('source-tags');
        const srcs = Object.entries(data.source_coverage || {})
            .sort((a, b) => b[1] - a[1])
            .slice(0, 8);
        srcContainer.innerHTML = srcs.length > 0
            ? '<span style="color: var(--text-muted); font-size: 0.8rem; width: 100%; margin-bottom: 4px;">Data Sources:</span>' +
              srcs.map(([src, count]) => `<span class="meta-tag"><span class="key">${escapeHtml(src)}</span> <span class="value">${count}</span></span>`).join('')
            : '';
    } catch (err) {
        // Silently fail - stats are non-critical
    }
}

function renderProductCard(p) {
    const confidence = p.confidence || 0;
    const confidenceClass = confidence >= 0.7 ? 'confidence-high' :
                           confidence >= 0.4 ? 'confidence-medium' : 'confidence-low';
    const confidenceLabel = confidence >= 0.7 ? 'High' :
                           confidence >= 0.4 ? 'Medium' : 'Low';

    const imageHtml = p.image_url
        ? `<img src="${escapeHtml(p.image_url)}" alt="${escapeHtml(p.name || 'Product image')}" class="product-image" loading="lazy" onclick="openLightbox('${escapeHtml(p.image_url)}', '${escapeHtml(p.name || 'Product')}')" style="cursor: zoom-in;" onerror="this.style.display='none'">`
        : `<div class="product-image placeholder" role="img" aria-label="No image available">📦</div>`;

    const attributesHtml = Object.entries(p.attributes || {})
        .slice(0, 4)
        .map(([k, v]) => `<span class="meta-tag"><span class="key">${escapeHtml(k)}:</span> <span class="value">${escapeHtml(String(v))}</span></span>`)
        .join('');

    const citationsHtml = (p.citations || []).slice(0, 3).map(c => `
        <div class="citation-item">
            <span class="citation-source">${escapeHtml(c.source)}</span>
            <span class="citation-fields">${escapeHtml(c.fields.join(', '))}</span>
            <span class="citation-confidence">${(c.confidence * 100).toFixed(0)}%</span>
        </div>
    `).join('');

    return `
        <article class="product-card" tabindex="0" aria-label="${escapeHtml(p.name || 'Unknown product')}">
            ${imageHtml}
            <div class="product-content">
                <div class="product-header">
                    <h3 class="product-name">${escapeHtml(p.name || 'Unknown Product')}</h3>
                    <span class="confidence-badge ${confidenceClass}" aria-label="Confidence: ${confidenceLabel}">${confidenceLabel}</span>
                </div>
                ${p.brand ? `<p class="product-brand">${escapeHtml(p.brand)}</p>` : ''}
                ${p.category ? `<p class="product-category">${escapeHtml(p.category)}</p>` : ''}
                <p class="product-description">${escapeHtml(p.description || '')}</p>
                ${attributesHtml ? `<div class="product-meta">${attributesHtml}</div>` : ''}
                ${citationsHtml ? `
                    <div class="citations-section">
                        <div class="citations-title">Data Sources</div>
                        <div class="citation-list">${citationsHtml}</div>
                    </div>
                ` : ''}
                <div class="product-actions">
                    <button class="btn btn-outline btn-sm" onclick="showReasoningTrace('${p.upc}')" aria-label="View reasoning trace for ${escapeHtml(p.name || p.upc)}">
                        🧠 Reasoning
                    </button>
                    ${p.source_url ? `<a href="${escapeHtml(p.source_url)}" target="_blank" rel="noopener" class="btn btn-outline btn-sm">🔗 Source</a>` : ''}
                </div>
            </div>
        </article>
    `;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Reasoning Trace Modal
function showReasoningTrace(upc) {
    const product = products.find(p => p.upc === upc);
    if (!product) return;

    const modal = document.getElementById('modal-overlay');
    const modalBody = document.getElementById('modal-body');
    const modalTitle = document.getElementById('modal-title');

    modalTitle.textContent = `Reasoning Trace: ${product.name || product.upc}`;

    const traceHtml = (product.reasoning_trace || []).map((step, i) => `
        <div class="trace-item step-${(i % 3) + 1}">
            <strong>Step ${i + 1}:</strong> ${escapeHtml(step)}
        </div>
    `).join('');

    const citationsHtml = (product.citations || []).map(c => `
        <div class="citation-item" style="margin-bottom: 8px;">
            <span class="citation-source">${escapeHtml(c.source)}</span>
            <span class="citation-fields">${escapeHtml(c.fields.join(', '))}</span>
            <span class="citation-confidence">${(c.confidence * 100).toFixed(0)}%</span>
            ${c.note ? `<div style="color: var(--text-muted); margin-top: 4px; font-size: 0.8rem;">${escapeHtml(c.note)}</div>` : ''}
        </div>
    `).join('');

    modalBody.innerHTML = `
        <div style="margin-bottom: 24px;">
            <h4 style="color: var(--text-secondary); margin-bottom: 12px; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em;">Processing Steps</h4>
            <div class="trace-list">${traceHtml || '<p style="color: var(--text-muted);">No reasoning trace available</p>'}</div>
        </div>
        <div>
            <h4 style="color: var(--text-secondary); margin-bottom: 12px; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em;">Source Citations</h4>
            <div class="citation-list">${citationsHtml || '<p style="color: var(--text-muted);">No citations available</p>'}</div>
        </div>
        <div style="margin-top: 24px; padding: 16px; background: var(--bg-tertiary); border-radius: var(--radius-sm);">
            <h4 style="color: var(--text-secondary); margin-bottom: 8px; font-size: 0.9rem;">Final Confidence Score</h4>
            <div style="font-size: 2rem; font-weight: 800; color: ${product.confidence >= 0.7 ? 'var(--success)' : product.confidence >= 0.4 ? 'var(--warning)' : 'var(--danger)'};">
                ${(product.confidence * 100).toFixed(1)}%
            </div>
            <div style="color: var(--text-muted); font-size: 0.85rem; margin-top: 4px;">
                Based on ${(product.citations || []).length} source(s) with weighted agreement
            </div>
        </div>
    `;

    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.getElementById('modal-close').focus();
}

function closeModal() {
    const modal = document.getElementById('modal-overlay');
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
}

function openLightbox(url, caption) {
    const overlay = document.getElementById('lightbox-overlay');
    const img = document.getElementById('lightbox-image');
    const cap = document.getElementById('lightbox-caption');
    img.src = url;
    img.alt = caption;
    cap.textContent = caption;
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
}

function closeLightbox() {
    const overlay = document.getElementById('lightbox-overlay');
    overlay.classList.remove('active');
    overlay.setAttribute('aria-hidden', 'true');
    document.getElementById('lightbox-image').src = '';
}

// Export
async function exportPortfolio(format) {
    try {
        const res = await fetch(`${API_BASE}/api/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ format }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Export failed');
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = res.headers.get('content-disposition')?.match(/filename="(.+)"/)?.[1] || `shelfwise-${format}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        showToast(`Exported as ${format.toUpperCase()}`, 'success');
    } catch (err) {
        showToast(`Export error: ${err.message}`, 'error');
    }
}

// Loading state
function setLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.textContent = loading ? 'Processing...' : 'Submit UPCs';
}

// Auto-refresh products periodically when job is running
setInterval(() => {
    if (currentJobId && submitBtn.disabled) {
        loadProducts();
        loadStats();
    }
}, 3000);

// Start
init();
