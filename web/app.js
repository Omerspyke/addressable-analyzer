let reportData = null;
let reportsListData = null;
let sizeChart = null;

// Init
document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    await loadReport();
});

function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        });
    });
}

async function loadReport() {
    const resp = await fetch('/api/report');
    reportData = await resp.json();
    renderHeader();
    renderDashboard();
    renderDuplicates();
    renderDependencies();
    renderSizes();
    loadReportsList();
}

async function reloadReport() {
    const btn = document.getElementById('reload-btn');
    btn.textContent = 'Reloading...';
    btn.disabled = true;
    try {
        await fetch('/api/reload', { method: 'POST' });
        await loadReport();
    } finally {
        btn.textContent = 'Reload';
        btn.disabled = false;
    }
}

function renderHeader() {
    document.getElementById('project-name').textContent = reportData.project_name || 'Unknown';
    document.getElementById('build-target').textContent = reportData.build_target || '';
    document.getElementById('build-info').textContent =
        `Unity ${reportData.unity_version} | ${reportData.addressables_version} | Built: ${reportData.build_time}`;
}

// === DASHBOARD ===
function renderDashboard() {
    const s = reportData.summary;
    const el = document.getElementById('tab-dashboard');
    el.innerHTML = `
        <div class="cards">
            <div class="card">
                <div class="card-label">Total Bundles</div>
                <div class="card-value">${s.total_bundles}</div>
                <div class="card-sub">${s.remote_bundles} remote / ${s.local_bundles} local</div>
            </div>
            <div class="card">
                <div class="card-label">Total Size</div>
                <div class="card-value">${formatBytes(s.total_size)}</div>
                <div class="card-sub">Remote: ${formatBytes(s.remote_size)} / Local: ${formatBytes(s.local_size)}</div>
            </div>
            <div class="card">
                <div class="card-label">Groups</div>
                <div class="card-value">${s.total_groups}</div>
            </div>
            <div class="card">
                <div class="card-label">Total Assets</div>
                <div class="card-value">${s.total_assets}</div>
            </div>
            <div class="card">
                <div class="card-label">Duplicates</div>
                <div class="card-value ${s.duplicate_count > 0 ? 'severity-high' : ''}">${s.duplicate_count}</div>
            </div>
            <div class="card">
                <div class="card-label">Cross-Dependencies</div>
                <div class="card-value ${s.cross_dependency_count > 0 ? 'severity-medium' : ''}">${s.cross_dependency_count}</div>
                <div class="card-sub">Remote-to-Remote</div>
            </div>
        </div>
        <h3 style="margin-bottom:12px; font-size:14px;">Top 10 Largest Bundles</h3>
        <table>
            <thead><tr><th>Bundle</th><th>Group</th><th>Size</th><th>Type</th></tr></thead>
            <tbody>
                ${reportData.bundles.slice(0, 10).map(b => `
                    <tr>
                        <td>${shortName(b.name)}</td>
                        <td>${b.group}</td>
                        <td>${formatBytes(b.size)}</td>
                        <td><span class="tag ${b.is_remote ? 'tag-remote' : 'tag-local'}">${b.is_remote ? 'Remote' : 'Local'}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// === DUPLICATES ===
function renderDuplicates() {
    const el = document.getElementById('tab-duplicates');
    const dups = reportData.duplicates;

    el.innerHTML = `
        <div class="filter-row">
            <input class="search-box" placeholder="Search duplicates..." oninput="filterDuplicates(this.value)">
            <span style="color:var(--text-dim);font-size:12px">${dups.length} duplicated assets</span>
        </div>
        <table id="dup-table">
            <thead>
                <tr>
                    <th onclick="sortTable('dup-table',0)">Asset</th>
                    <th onclick="sortTable('dup-table',1)">Path</th>
                    <th onclick="sortTable('dup-table',2)" class="sorted-desc">Count</th>
                    <th>Found In Bundles</th>
                </tr>
            </thead>
            <tbody>
                ${dups.map(d => `
                    <tr class="dup-row" data-search="${(d.asset_name + d.asset_path).toLowerCase()}">
                        <td><strong>${d.asset_name}</strong></td>
                        <td style="font-size:11px;color:var(--text-dim)">${d.asset_path}</td>
                        <td class="${severityClass(d.bundle_count)}">${d.bundle_count}</td>
                        <td><div class="bundle-list">${d.bundles.map(b => `<span class="tag">${shortName(b)}</span>`).join(' ')}</div></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function filterDuplicates(query) {
    const q = query.toLowerCase();
    document.querySelectorAll('.dup-row').forEach(row => {
        row.style.display = row.dataset.search.includes(q) ? '' : 'none';
    });
}

// === DEPENDENCIES ===
function renderDependencies() {
    const el = document.getElementById('tab-dependencies');
    const crossDeps = reportData.cross_dependencies;
    const allDeps = [];
    reportData.bundles.forEach(b => {
        b.dependencies.forEach(d => {
            allDeps.push({
                from_bundle: b.name,
                from_group: b.group,
                to_bundle: d.bundle_name,
                is_remote_from: b.is_remote,
                is_cross: crossDeps.some(c => c.from_bundle === b.name && c.to_bundle === d.bundle_name),
            });
        });
    });

    el.innerHTML = `
        <div class="filter-row">
            <input class="search-box" placeholder="Search dependencies..." oninput="filterDeps(this.value)">
            <button class="filter-btn active" onclick="toggleDepFilter(this,'all')">All (${allDeps.length})</button>
            <button class="filter-btn" onclick="toggleDepFilter(this,'cross')">Cross-Remote (${crossDeps.length})</button>
        </div>
        <table id="dep-table">
            <thead>
                <tr>
                    <th>From Bundle</th>
                    <th>From Group</th>
                    <th>Depends On</th>
                    <th>Type</th>
                </tr>
            </thead>
            <tbody>
                ${allDeps.map(d => `
                    <tr class="dep-row ${d.is_cross ? 'dep-cross' : ''}" data-search="${(d.from_bundle+d.to_bundle+d.from_group).toLowerCase()}" data-cross="${d.is_cross}">
                        <td>${shortName(d.from_bundle)}</td>
                        <td>${d.from_group}</td>
                        <td>${shortName(d.to_bundle)}</td>
                        <td>${d.is_cross ? '<span class="tag tag-danger">Remote-Remote</span>' : '<span class="tag">Normal</span>'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

let depFilterMode = 'all';
function toggleDepFilter(btn, mode) {
    depFilterMode = mode;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.dep-row').forEach(row => {
        if (mode === 'cross') {
            row.style.display = row.dataset.cross === 'true' ? '' : 'none';
        } else {
            row.style.display = '';
        }
    });
}

function filterDeps(query) {
    const q = query.toLowerCase();
    document.querySelectorAll('.dep-row').forEach(row => {
        const matchSearch = row.dataset.search.includes(q);
        const matchFilter = depFilterMode === 'all' || row.dataset.cross === 'true';
        row.style.display = (matchSearch && matchFilter) ? '' : 'none';
    });
}

// === BUNDLE SIZES ===
function renderSizes() {
    const el = document.getElementById('tab-sizes');
    const bundles = reportData.bundles;
    const top30 = bundles.slice(0, 30);

    el.innerHTML = `
        <div class="chart-container"><canvas id="size-chart"></canvas></div>
        <div class="filter-row">
            <input class="search-box" placeholder="Search bundles..." oninput="filterSizes(this.value)">
            <span style="color:var(--text-dim);font-size:12px">${bundles.length} bundles</span>
        </div>
        <table id="size-table">
            <thead>
                <tr>
                    <th onclick="sortTable('size-table',0)">Bundle</th>
                    <th onclick="sortTable('size-table',1)">Group</th>
                    <th onclick="sortTable('size-table',2)" class="sorted-desc">Size</th>
                    <th onclick="sortTable('size-table',3)">Assets</th>
                    <th onclick="sortTable('size-table',4)">Deps Size</th>
                    <th>Type</th>
                </tr>
            </thead>
            <tbody>
                ${bundles.map(b => `
                    <tr class="size-row" data-search="${(b.name+b.group).toLowerCase()}">
                        <td>${shortName(b.name)}</td>
                        <td>${b.group}</td>
                        <td data-sort="${b.size}">${formatBytes(b.size)}</td>
                        <td data-sort="${b.asset_count}">${b.asset_count}</td>
                        <td data-sort="${b.dependency_size}">${formatBytes(b.dependency_size)}</td>
                        <td><span class="tag ${b.is_remote ? 'tag-remote' : 'tag-local'}">${b.is_remote ? 'Remote' : 'Local'}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    // Chart
    if (sizeChart) sizeChart.destroy();
    const ctx = document.getElementById('size-chart').getContext('2d');
    sizeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top30.map(b => shortName(b.name)),
            datasets: [{
                label: 'Bundle Size',
                data: top30.map(b => b.size),
                backgroundColor: top30.map(b => b.is_remote ? 'rgba(79,195,247,0.7)' : 'rgba(102,187,106,0.7)'),
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => formatBytes(ctx.raw)
                    }
                }
            },
            scales: {
                x: {
                    ticks: { callback: v => formatBytes(v), color: '#8899aa' },
                    grid: { color: 'rgba(42,58,92,0.5)' }
                },
                y: {
                    ticks: { color: '#8899aa', font: { size: 10 } },
                    grid: { display: false }
                }
            }
        }
    });
}

function filterSizes(query) {
    const q = query.toLowerCase();
    document.querySelectorAll('.size-row').forEach(row => {
        row.style.display = row.dataset.search.includes(q) ? '' : 'none';
    });
}

// === BUILD DIFF ===
async function loadReportsList() {
    const resp = await fetch('/api/reports');
    reportsListData = await resp.json();
    renderDiffSelectors();
}

function renderDiffSelectors() {
    const el = document.getElementById('tab-diff');
    if (!reportsListData || reportsListData.length < 2) {
        el.innerHTML = '<div class="empty-state"><p>Need at least 2 saved reports to compare.</p><p style="margin-top:8px">Click "Reload" after a new Addressables build to save another report.</p></div>';
        return;
    }

    const options = reportsListData.map((r, i) =>
        `<option value="${r.filepath}">${r.filename} (${r.build_target}, ${r.summary.total_bundles || '?'} bundles)</option>`
    ).join('');

    el.innerHTML = `
        <div class="select-row">
            <label>Old:</label>
            <select id="diff-old">${options}</select>
            <label>New:</label>
            <select id="diff-new">${options}</select>
            <button onclick="runDiff()">Compare</button>
        </div>
        <div id="diff-result"></div>
    `;

    // Default: old=second, new=first
    if (reportsListData.length >= 2) {
        document.getElementById('diff-old').selectedIndex = 1;
        document.getElementById('diff-new').selectedIndex = 0;
    }
}

async function runDiff() {
    const oldPath = document.getElementById('diff-old').value;
    const newPath = document.getElementById('diff-new').value;
    const resp = await fetch(`/api/diff?a=${encodeURIComponent(oldPath)}&b=${encodeURIComponent(newPath)}`);
    const diff = await resp.json();
    renderDiffResult(diff);
}

function renderDiffResult(diff) {
    const el = document.getElementById('diff-result');
    if (!diff) { el.innerHTML = '<p>No diff data</p>'; return; }

    let html = '';

    // Summary
    html += '<div class="diff-section"><h3>Summary Changes</h3><div class="cards">';
    const labels = {
        total_bundles: 'Bundles', total_size: 'Total Size', total_assets: 'Assets',
        duplicate_count: 'Duplicates', cross_dependency_count: 'Cross-Deps',
        remote_bundles: 'Remote Bundles', local_bundles: 'Local Bundles'
    };
    for (const [key, label] of Object.entries(labels)) {
        const d = diff.summary_diff[key];
        if (!d) continue;
        const isSize = key.includes('size');
        const deltaStr = d.delta > 0 ? `+${isSize ? formatBytes(d.delta) : d.delta}` : (isSize ? formatBytes(d.delta) : d.delta);
        const cls = d.delta > 0 ? 'delta-positive' : d.delta < 0 ? 'delta-negative' : 'delta-zero';
        html += `<div class="card"><div class="card-label">${label}</div><div class="card-value">${isSize ? formatBytes(d.new) : d.new}</div><div class="card-sub ${cls}">${deltaStr}</div></div>`;
    }
    html += '</div></div>';

    // New duplicates
    if (diff.new_duplicates.length > 0) {
        html += `<div class="diff-section"><h3><span class="severity-high">NEW</span> Duplicates (${diff.new_duplicates.length})</h3><table><thead><tr><th>Asset</th><th>Path</th><th>Count</th></tr></thead><tbody>`;
        diff.new_duplicates.forEach(d => {
            html += `<tr><td>${d.asset_name}</td><td style="font-size:11px">${d.asset_path}</td><td class="severity-high">${d.bundle_count}</td></tr>`;
        });
        html += '</tbody></table></div>';
    }

    // Resolved duplicates
    if (diff.resolved_duplicates.length > 0) {
        html += `<div class="diff-section"><h3><span style="color:var(--green)">RESOLVED</span> Duplicates (${diff.resolved_duplicates.length})</h3><table><thead><tr><th>Asset</th><th>Path</th><th>Was In</th></tr></thead><tbody>`;
        diff.resolved_duplicates.forEach(d => {
            html += `<tr><td>${d.asset_name}</td><td style="font-size:11px">${d.asset_path}</td><td>${d.bundle_count} bundles</td></tr>`;
        });
        html += '</tbody></table></div>';
    }

    // Size changes
    if (diff.size_changes.length > 0) {
        html += `<div class="diff-section"><h3>Bundle Size Changes (${diff.size_changes.length})</h3><table><thead><tr><th>Bundle</th><th>Group</th><th>Old Size</th><th>New Size</th><th>Delta</th></tr></thead><tbody>`;
        diff.size_changes.slice(0, 30).forEach(c => {
            const cls = c.delta > 0 ? 'delta-positive' : 'delta-negative';
            html += `<tr><td>${shortName(c.name)}</td><td>${c.group}</td><td>${formatBytes(c.old_size)}</td><td>${formatBytes(c.new_size)}</td><td class="${cls}">${c.delta > 0 ? '+' : ''}${formatBytes(c.delta)}</td></tr>`;
        });
        html += '</tbody></table></div>';
    }

    // Added/removed bundles
    if (diff.added_bundles.length > 0) {
        html += `<div class="diff-section"><h3><span style="color:var(--green)">ADDED</span> Bundles (${diff.added_bundles.length})</h3><table><thead><tr><th>Bundle</th><th>Group</th><th>Size</th></tr></thead><tbody>`;
        diff.added_bundles.forEach(b => {
            html += `<tr><td>${shortName(b.name)}</td><td>${b.group}</td><td>${formatBytes(b.size)}</td></tr>`;
        });
        html += '</tbody></table></div>';
    }

    if (diff.removed_bundles.length > 0) {
        html += `<div class="diff-section"><h3><span class="severity-high">REMOVED</span> Bundles (${diff.removed_bundles.length})</h3><table><thead><tr><th>Bundle</th><th>Group</th><th>Size</th></tr></thead><tbody>`;
        diff.removed_bundles.forEach(b => {
            html += `<tr><td>${shortName(b.name)}</td><td>${b.group}</td><td>${formatBytes(b.size)}</td></tr>`;
        });
        html += '</tbody></table></div>';
    }

    el.innerHTML = html;
}

// === HELPERS ===
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const neg = bytes < 0;
    bytes = Math.abs(bytes);
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
    return (neg ? '-' : '') + bytes.toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

function shortName(name) {
    // Remove hash suffix from bundle names like "remotebullseyeleague_assets_all_b4533ab43b983dbb3ac83e27257adb5a.bundle"
    return name.replace(/_[a-f0-9]{32}\.bundle$/, '.bundle').replace(/\.bundle$/, '');
}

function severityClass(count) {
    if (count >= 5) return 'severity-high';
    if (count >= 3) return 'severity-medium';
    return 'severity-low';
}

function sortTable(tableId, colIndex) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const th = table.querySelectorAll('th')[colIndex];

    // Toggle direction
    const isDesc = th.classList.contains('sorted-desc');
    table.querySelectorAll('th').forEach(h => { h.classList.remove('sorted-asc', 'sorted-desc'); });
    th.classList.add(isDesc ? 'sorted-asc' : 'sorted-desc');
    const dir = isDesc ? 1 : -1;

    rows.sort((a, b) => {
        const aCell = a.cells[colIndex];
        const bCell = b.cells[colIndex];
        const aVal = aCell.dataset.sort ? parseFloat(aCell.dataset.sort) : aCell.textContent.trim();
        const bVal = bCell.dataset.sort ? parseFloat(bCell.dataset.sort) : bCell.textContent.trim();
        if (typeof aVal === 'number' && typeof bVal === 'number') return (aVal - bVal) * dir;
        return String(aVal).localeCompare(String(bVal)) * dir;
    });

    rows.forEach(r => tbody.appendChild(r));
}
