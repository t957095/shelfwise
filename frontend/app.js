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
const demoBtn = document.getElementById('demo-btn');
const statusSection = document.getElementById('status-section');
const productsGrid = document.getElementById('products-grid');
const productCount = document.getElementById('product-count');
const toastContainer = document.getElementById('toast-container');
const csvPreview = document.getElementById('csv-preview');
const csvPreviewSummary = document.getElementById('csv-preview-summary');
const csvPreviewSamples = document.getElementById('csv-preview-samples');
const csvMaxRows = document.getElementById('csv-max-rows');
const csvPreviewProcess = document.getElementById('csv-preview-process');
const csvPreviewCancel = document.getElementById('csv-preview-cancel');
let pendingCsvFile = null;

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
                <div class="icon">Search</div>
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
    if (demoBtn) {
        demoBtn.addEventListener('click', handleDemo);
    }
    csvFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) previewCsv(e.target.files[0]);
    });
    csvPreviewProcess.addEventListener('click', processPreviewedCsv);
    csvPreviewCancel.addEventListener('click', hideCsvPreview);

    // Image manager modal
    document.getElementById('image-manager-close').addEventListener('click', closeImageManager);
    document.getElementById('image-manager-overlay').addEventListener('click', (e) => {
        if (e.target.id === 'image-manager-overlay') closeImageManager();
    });
    document.getElementById('image-upload-btn').addEventListener('click', uploadManagedImage);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeImageManager();
    });
    document.getElementById('export-csv-btn').addEventListener('click', () => exportPortfolio('csv'));
    document.getElementById('export-json-btn').addEventListener('click', () => exportPortfolio('json'));
    document.getElementById('export-shopify-btn').addEventListener('click', () => exportPortfolio('shopify'));
    document.getElementById('export-amazon-btn').addEventListener('click', () => exportPortfolio('amazon'));
    document.getElementById('export-woocommerce-btn').addEventListener('click', () => exportPortfolio('woocommerce'));
    document.getElementById('export-ebay-btn').addEventListener('click', () => exportPortfolio('ebay'));
    document.getElementById('export-etsy-btn').addEventListener('click', () => exportPortfolio('etsy'));
    document.getElementById('export-bigcommerce-btn').addEventListener('click', () => exportPortfolio('bigcommerce'));
    document.getElementById('export-doordash-btn').addEventListener('click', () => exportPortfolio('doordash'));
    document.getElementById('export-ubereats-btn').addEventListener('click', () => exportPortfolio('ubereats'));
    document.getElementById('export-grubhub-btn').addEventListener('click', () => exportPortfolio('grubhub'));

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

async function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        csvFileInput.files = files;
        try {
            await previewCsv(files[0]);
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
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

async function previewCsv(file) {
    pendingCsvFile = file;
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/api/upload-csv/preview?max_rows=5`, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Preview failed');
    }

    const data = await res.json();
    const upcCol = data.detected_columns?.upc || 'unknown';
    const summary = `Detected UPC column: <strong>${escapeHtml(upcCol)}</strong> · ${data.total_upcs} unique UPCs${data.truncated ? '+' : ''}`;
    csvPreviewSummary.innerHTML = summary;

    csvPreviewSamples.innerHTML = (data.sample || []).map(s => {
        const name = s.seed?.name || 'Unknown product';
        return `<li><strong>${escapeHtml(s.upc)}</strong> — ${escapeHtml(name)}</li>`;
    }).join('');

    csvPreview.style.display = 'block';
    csvPreview.setAttribute('tabindex', '-1');
    csvPreview.focus();
}

function hideCsvPreview() {
    csvPreview.style.display = 'none';
    csvPreviewSamples.innerHTML = '';
    csvFileInput.value = '';
    pendingCsvFile = null;
}

async function processPreviewedCsv() {
    if (!pendingCsvFile) return;
    const file = pendingCsvFile;
    const maxRows = csvMaxRows.value;
    hideCsvPreview();
    setLoading(true);
    await handleFileUpload(file, maxRows);
}

async function handleFileUpload(file, maxRows = '100') {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/api/upload-csv?max_rows=${maxRows}`, {
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

// Demo
async function handleDemo() {
    setLoading(true);
    const res = await fetch(`${API_BASE}/api/demo`);
    const data = await res.json();
    showToast('Demo UPCs submitted', 'info');
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
                <div class="icon">Catalog</div>
                <h3>No products yet</h3>
                <p>Enter UPC codes above or load the demo to get started</p>
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

    const images = (p.images || []).filter(img => img && img.url);
    if (images.length === 0 && p.image_url) {
        images.push({ url: p.image_url, source: 'Best' });
    }

    const mainImage = images[0];
    const thumbnails = images.slice(1, 5);
    const isGeneratedImage = Boolean(mainImage && (mainImage.generated || mainImage.source === 'ShelfWise Review Placeholder'));

    const mainImageHtml = mainImage
        ? `<div class="product-image-shell">
                <img src="${escapeHtml(mainImage.url)}" alt="${escapeHtml(p.name || 'Product image')}" class="product-image" loading="lazy" onclick="openLightbox(${escapeJsString(mainImage.url)}, ${escapeJsString(p.name || 'Product')})" style="cursor: zoom-in;" onerror="this.style.display='none'">
                ${isGeneratedImage ? '<span class="image-status-badge">Review image</span>' : ''}
           </div>`
        : `<div class="product-image placeholder" role="img" aria-label="No image available">No image</div>`;

    const thumbnailsHtml = thumbnails.length > 0
        ? `<div class="product-image-thumbnails" role="list" aria-label="Additional product images">` +
          thumbnails.map((img, i) => `
              <button class="product-thumbnail" role="listitem" aria-label="Product image ${i + 2} from ${escapeHtml(img.source || 'verified source')}" onclick="openLightbox(${escapeJsString(img.url)}, ${escapeJsString(p.name || 'Product')})">
                  <img src="${escapeHtml(img.url)}" alt="" loading="lazy" onerror="this.parentElement.style.display='none'">
              </button>
          `).join('') +
          `</div>`
        : '';

    const attributesHtml = Object.entries(p.attributes || {})
        .slice(0, 4)
        .map(([k, v]) => `<span class="meta-tag"><span class="key">${escapeHtml(k)}:</span> <span class="value">${escapeHtml(String(v))}</span></span>`)
        .join('');

    const citationsHtml = (p.citations || []).slice(0, 3).map(c => `
        <div class="citation-item">
            <span class="citation-source">${escapeHtml(c.source || 'Source')}</span>
            <span class="citation-fields">${escapeHtml(Array.isArray(c.fields) ? c.fields.join(', ') : '')}</span>
            <span class="citation-confidence">${(((c.confidence || 0) * 100)).toFixed(0)}%</span>
        </div>
    `).join('');

    return `
        <article class="product-card" tabindex="0" aria-label="${escapeHtml(p.name || 'Unknown product')}">
            ${mainImageHtml}
            ${thumbnailsHtml}
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
                        Reasoning
                    </button>
                    <button class="btn btn-outline btn-sm" onclick="openImageManager('${p.upc}')" aria-label="Manage images for ${escapeHtml(p.name || p.upc)}">
                        Images
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

function escapeJsString(text) {
    return JSON.stringify(String(text || ''))
        .replace(/&/g, '\\u0026')
        .replace(/</g, '\\u003c')
        .replace(/>/g, '\\u003e')
        .replace(/"/g, '&quot;');
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
            <span class="citation-source">${escapeHtml(c.source || 'Source')}</span>
            <span class="citation-fields">${escapeHtml(Array.isArray(c.fields) ? c.fields.join(', ') : '')}</span>
            <span class="citation-confidence">${(((c.confidence || 0) * 100)).toFixed(0)}%</span>
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

let imageManagerUpc = null;

function openImageManager(upc) {
    const product = products.find(p => p.upc === upc);
    if (!product) return;
    imageManagerUpc = upc;
    renderImageManager(product);
    const overlay = document.getElementById('image-manager-overlay');
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    document.getElementById('image-manager-close').focus();
}

function closeImageManager() {
    const overlay = document.getElementById('image-manager-overlay');
    overlay.classList.remove('active');
    overlay.setAttribute('aria-hidden', 'true');
    imageManagerUpc = null;
    document.getElementById('image-upload-input').value = '';
}

function renderImageManager(product) {
    const list = document.getElementById('image-manager-list');
    const images = (product.images || []).filter(img => img && img.url);
    if (images.length === 0 && product.image_url) {
        images.push({ url: product.image_url, source: 'Primary' });
    }

    if (images.length === 0) {
        list.innerHTML = `<p style="color: var(--text-muted);">No images yet. Upload one below.</p>`;
        return;
    }

    list.innerHTML = images.map((img, i) => `
        <div class="image-manager-item">
            <img src="${escapeHtml(img.url)}" alt="" loading="lazy" onerror="this.parentElement.style.display='none'">
            <div class="image-manager-meta">
                <span class="image-manager-source">${escapeHtml(img.source || 'Verified source')}</span>
                ${img.url === product.image_url ? '<span class="image-manager-primary">Primary</span>' : ''}
            </div>
            <button class="btn btn-danger btn-sm" onclick="deleteManagedImage(${escapeJsString(img.url)})" aria-label="Delete image ${i + 1}">
                Delete
            </button>
        </div>
    `).join('');
}

async function uploadManagedImage() {
    if (!imageManagerUpc) return;
    const input = document.getElementById('image-upload-input');
    const file = input.files[0];
    if (!file) {
        showToast('Select an image first', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_BASE}/api/products/${imageManagerUpc}/images`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Upload failed');
        }
        const data = await res.json();
        const product = products.find(p => p.upc === imageManagerUpc);
        if (product) {
            product.images = data.images;
            product.image_url = data.image_url;
        }
        renderImageManager(product);
        renderProducts();
        input.value = '';
        showToast('Image uploaded', 'info');
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    }
}

async function deleteManagedImage(url) {
    if (!imageManagerUpc || !url) return;
    if (!confirm('Delete this image?')) return;

    try {
        const encoded = encodeURIComponent(url);
        const res = await fetch(`${API_BASE}/api/products/${imageManagerUpc}/images?url=${encoded}`, {
            method: 'DELETE',
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Delete failed');
        }
        const data = await res.json();
        const product = products.find(p => p.upc === imageManagerUpc);
        if (product) {
            product.images = data.images;
            product.image_url = data.image_url;
        }
        renderImageManager(product);
        renderProducts();
        showToast('Image deleted', 'info');
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    }
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
    if (demoBtn) {
        demoBtn.disabled = loading;
    }
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
