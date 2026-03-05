// API Cyber Dashboard

// Global state
let currentUser = null;
let charts = {};
let selectedDeviceId = null;
let deviceAgents = [];

// Counter animation helper
function animateCounter(elementId, targetValue) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const target = parseInt(targetValue, 10) || 0;
    const current = parseInt(el.textContent, 10) || 0;
    if (current === target) return;
    const duration = 400;
    const start = performance.now();
    const step = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(current + (target - current) * eased);
        if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

// Pagination & sorting state per table
const tableState = {
    events: { skip: 0, limit: 25, sortBy: 'occurred_at', sortOrder: 'desc', total: 0 },
    tasks:  { skip: 0, limit: 25, sortBy: 'started_at',  sortOrder: 'desc', total: 0 },
    users:  { skip: 0, limit: 25, sortBy: 'created_at',  sortOrder: 'desc', total: 0 },
};

// ==================== METRICS LABELS ====================
const METRIC_LABELS = {
    cpu: {
        icon: 'fa-microchip',
        title: 'Procesador',
        color: '#4682B4',
        metrics: {
            'usage_percent': { label: 'Uso CPU', format: 'percent', primary: true },
            'frequency_mhz': { label: 'Frecuencia', format: 'mhz' },
            'load_1m': { label: 'Carga (1 min)', format: 'decimal' },
            'load_5m': { label: 'Carga (5 min)', format: 'decimal' },
            'load_15m': { label: 'Carga (15 min)', format: 'decimal' }
        }
    },
    memory: {
        icon: 'fa-memory',
        title: 'Memoria RAM',
        color: '#28A745',
        metrics: {
            'usage_percent': { label: 'Uso RAM', format: 'percent', primary: true },
            'total_gb': { label: 'Total', format: 'gb' },
            'available_gb': { label: 'Disponible', format: 'gb' },
            'used_gb': { label: 'En uso', format: 'gb' },
            'swap_usage_percent': { label: 'Uso Swap', format: 'percent' },
            'swap_total_gb': { label: 'Swap total', format: 'gb' },
            'swap_used_gb': { label: 'Swap usado', format: 'gb' }
        }
    },
    disk: {
        icon: 'fa-hard-drive',
        title: 'Almacenamiento',
        color: '#B22222',
        metrics: {
            'root_usage_percent': { label: 'Uso (/)', format: 'percent', primary: true },
            'root_total_gb': { label: 'Total (/)', format: 'gb' },
            'root_free_gb': { label: 'Libre (/)', format: 'gb' },
            'root_used_gb': { label: 'Usado (/)', format: 'gb' },
            'read_bytes_total': { label: 'Lectura total', format: 'bytes' },
            'write_bytes_total': { label: 'Escritura total', format: 'bytes' }
        }
    },
    network: {
        icon: 'fa-network-wired',
        title: 'Red',
        color: '#17A2B8',
        metrics: {
            'bytes_sent_total': { label: 'Enviados', format: 'bytes', primary: true },
            'bytes_recv_total': { label: 'Recibidos', format: 'bytes' },
            'packets_sent_total': { label: 'Paquetes TX', format: 'number' },
            'packets_recv_total': { label: 'Paquetes RX', format: 'number' },
            'connections_established': { label: 'Conexiones', format: 'number' },
            'connections_listening': { label: 'Escuchando', format: 'number' }
        }
    }
};

function formatMetricValue(value, format) {
    if (value === null || value === undefined) return '-';
    switch(format) {
        case 'percent':
            return `${value.toFixed(1)}%`;
        case 'gb':
            return `${value.toFixed(2)} GB`;
        case 'mhz':
            return `${Math.round(value)} MHz`;
        case 'bytes':
            return formatBytes(value);
        case 'decimal':
            return value.toFixed(2);
        case 'number':
            return Math.round(value).toLocaleString('es-ES');
        default:
            return typeof value === 'number' ? value.toFixed(2) : value;
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

function getMetricLabel(metricType, metricName) {
    const config = METRIC_LABELS[metricType];
    if (!config) return metricName;

    // Buscar coincidencia exacta
    if (config.metrics[metricName]) {
        return config.metrics[metricName].label;
    }

    // Buscar patrones de disco con otros puntos de montaje
    if (metricType === 'disk') {
        if (metricName.endsWith('_usage_percent')) {
            const mount = metricName.replace('_usage_percent', '');
            return `Uso (${mount})`;
        }
        if (metricName.endsWith('_total_gb')) {
            const mount = metricName.replace('_total_gb', '');
            return `Total (${mount})`;
        }
        if (metricName.endsWith('_free_gb')) {
            const mount = metricName.replace('_free_gb', '');
            return `Libre (${mount})`;
        }
        if (metricName.endsWith('_used_gb')) {
            const mount = metricName.replace('_used_gb', '');
            return `Usado (${mount})`;
        }
    }

    // Buscar patrones de CPU por núcleo
    if (metricType === 'cpu' && metricName.startsWith('core_')) {
        const match = metricName.match(/core_(\d+)_usage/);
        if (match) return `Núcleo ${match[1]}`;
    }

    // Fallback: humanizar el nombre
    return metricName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function getMetricFormat(metricType, metricName) {
    const config = METRIC_LABELS[metricType];
    if (config && config.metrics[metricName]) {
        return config.metrics[metricName].format;
    }
    // Inferir formato del nombre
    if (metricName.includes('percent')) return 'percent';
    if (metricName.includes('_gb')) return 'gb';
    if (metricName.includes('_mhz') || metricName.includes('frequency')) return 'mhz';
    if (metricName.includes('bytes')) return 'bytes';
    if (metricName.startsWith('core_')) return 'percent';
    return 'decimal';
}

document.addEventListener('DOMContentLoaded', () => {
    if (!API.isAuthenticated()) {
        window.location.href = ROOT_PATH + '/';
        return;
    }

    initSidebar();
    initMobileMenu();
    initNavigation();
    initAutoRefresh();
    initFilters();
    loadUserInfo();
    loadDashboard();
});

// Sidebar Toggle
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    const toggleBtn = document.getElementById('sidebarToggle');

    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('expanded');
    }

    toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        mainContent.classList.toggle('expanded');
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });
}

// Mobile Menu
function initMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const menuBtn = document.getElementById('mobileMenuBtn');

    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('sidebar-open');
            overlay.classList.toggle('active');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', () => {
            closeMobileMenu();
        });
    }
}

function closeMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.remove('sidebar-open');
    overlay.classList.remove('active');
}

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            closeMobileMenu();
            switchPage(page);
        });
    });

    document.getElementById('logoutBtn').addEventListener('click', () => {
        AutoRefresh.stopAll();
        API.clearToken();
        window.location.href = ROOT_PATH + '/';
    });
}

// Auto Refresh
function initAutoRefresh() {
    const toggle = document.getElementById('autoRefreshToggle');
    const saved = localStorage.getItem('autoRefresh') !== 'false';
    toggle.checked = saved;

    toggle.addEventListener('change', () => {
        localStorage.setItem('autoRefresh', toggle.checked);
        if (toggle.checked) {
            startAutoRefresh();
        } else {
            AutoRefresh.stopAll();
        }
    });

    if (saved) {
        startAutoRefresh();
    }
}

function startAutoRefresh() {
    AutoRefresh.start('dashboard', loadDashboard, 30000);
}

// Debounce utility
function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// Sync search value between desktop (th) and mobile inputs
function syncSearch(table, value) {
    const mobileInput = document.querySelector(`.mobile-search-input[data-table="${table}"]`);
    if (mobileInput && mobileInput.value !== value) mobileInput.value = value;
}

// Reset page to 0 on filter change, then reload
function onFilterChange(table, loadFn) {
    tableState[table].skip = 0;
    loadFn();
}

// Filters
function initFilters() {
    document.getElementById('agentStatusFilter')?.addEventListener('change', loadAgents);
    document.getElementById('metricsDeviceStatusFilter')?.addEventListener('change', loadMetricsPage);

    // Desktop search inputs (debounced) — inside <th>
    document.getElementById('eventSearchInput')?.addEventListener('input', debounce(() => {
        syncSearch('events', document.getElementById('eventSearchInput').value);
        onFilterChange('events', loadEvents);
    }, 300));
    document.getElementById('userSearchInput')?.addEventListener('input', debounce(() => {
        syncSearch('users', document.getElementById('userSearchInput').value);
        onFilterChange('users', loadUsers);
    }, 300));

    // Mobile search inputs — sync with desktop
    document.querySelectorAll('.mobile-search-input').forEach(input => {
        input.addEventListener('input', debounce(() => {
            const table = input.dataset.table;
            const desktopId = table === 'events' ? 'eventSearchInput'
                            : table === 'tasks' ? 'taskSearchInput' : 'userSearchInput';
            const desktop = document.getElementById(desktopId);
            if (desktop) desktop.value = input.value;
            const loadFn = table === 'events' ? loadEvents : table === 'tasks' ? loadTasks : loadUsers;
            onFilterChange(table, loadFn);
        }, 300));
    });

    // Sortable column headers
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const table = th.dataset.table;
            const column = th.dataset.sort;
            const state = tableState[table];
            if (state.sortBy === column) {
                state.sortOrder = state.sortOrder === 'desc' ? 'asc' : 'desc';
            } else {
                state.sortBy = column;
                state.sortOrder = 'asc';
            }
            state.skip = 0;
            updateSortIndicators(table);
            if (table === 'events') loadEvents();
            else if (table === 'users') loadUsers();
        });
    });

    // Settings
    document.getElementById('emailEnabledToggle')?.addEventListener('change', (e) => {
        updateNotificationSettingsVisibility(e.target.checked);
    });
}

// Update sort arrow icons on column headers
function updateSortIndicators(table) {
    document.querySelectorAll(`.sortable[data-table="${table}"]`).forEach(th => {
        const icon = th.querySelector('.sort-icon');
        if (!icon) return;
        if (th.dataset.sort === tableState[table].sortBy) {
            th.classList.add('active-sort');
            icon.className = `fas fa-sort-${tableState[table].sortOrder === 'asc' ? 'up' : 'down'} sort-icon`;
        } else {
            th.classList.remove('active-sort');
            icon.className = 'fas fa-sort sort-icon';
        }
    });
}

// Render pagination controls (includes per-page selector)
function renderPagination(containerId, table, loadFn) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const state = tableState[table];
    const totalPages = Math.ceil(state.total / state.limit);
    const currentPage = Math.floor(state.skip / state.limit);

    if (state.total === 0) {
        container.innerHTML = '';
        return;
    }

    const from = state.skip + 1;
    const to = Math.min(state.skip + state.limit, state.total);

    const perPageHtml = `<div class="pagination-per-page"><label>Mostrar</label><select onchange="changePerPage('${table}', this.value)">${[10, 25, 50, 100].map(n => `<option value="${n}" ${state.limit === n ? 'selected' : ''}>${n}</option>`).join('')}</select></div>`;

    let html = `<span class="pagination-info">Mostrando ${from}-${to} de ${state.total}</span>`;
    html += perPageHtml;
    html += '<div class="pagination">';

    // Prev button
    html += `<button class="pagination-btn" ${currentPage === 0 ? 'disabled' : ''} onclick="goToPage('${table}', ${currentPage - 1})"><i class="fas fa-chevron-left"></i></button>`;

    // Page numbers (max 5 visible)
    const maxVisible = 5;
    let startPage = Math.max(0, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages - 1, startPage + maxVisible - 1);
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(0, endPage - maxVisible + 1);
    }

    if (startPage > 0) {
        html += `<button class="pagination-btn" onclick="goToPage('${table}', 0)">1</button>`;
        if (startPage > 1) html += '<span class="pagination-dots">...</span>';
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="pagination-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage('${table}', ${i})">${i + 1}</button>`;
    }

    if (endPage < totalPages - 1) {
        if (endPage < totalPages - 2) html += '<span class="pagination-dots">...</span>';
        html += `<button class="pagination-btn" onclick="goToPage('${table}', ${totalPages - 1})">${totalPages}</button>`;
    }

    // Next button
    html += `<button class="pagination-btn" ${currentPage >= totalPages - 1 ? 'disabled' : ''} onclick="goToPage('${table}', ${currentPage + 1})"><i class="fas fa-chevron-right"></i></button>`;
    html += '</div>';

    container.innerHTML = html;
}

// Navigate to a specific page
function goToPage(table, page) {
    const state = tableState[table];
    state.skip = page * state.limit;
    if (table === 'events') loadEvents();
    else if (table === 'users') loadUsers();
}

// Change items per page
function changePerPage(table, value) {
    tableState[table].limit = parseInt(value);
    tableState[table].skip = 0;
    if (table === 'events') loadEvents();
    else if (table === 'users') loadUsers();
}

const pageIcons = {
    dashboard: 'fa-gauge-high',
    agents: 'fa-desktop',
    metrics: 'fa-chart-line',
    events: 'fa-bell',
    globe: 'fa-globe',
    tasks: 'fa-list-check',
    users: 'fa-users',
    settings: 'fa-gear'
};

const pageTitles = {
    dashboard: 'Dashboard',
    agents: 'Agentes',
    metrics: 'Métricas',
    events: 'Eventos',
    globe: 'Globo de Ataques',
    tasks: 'Tareas Programadas',
    users: 'Usuarios',
    settings: 'Configuracion'
};

function switchPage(pageName) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelector(`[data-page="${pageName}"]`)?.classList.add('active');

    // Update pages with smooth fade (no bounce)
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const targetPage = document.getElementById(pageName + 'Page');
    if (targetPage) {
        targetPage.classList.add('active');
    }

    // Update header
    const titleEl = document.getElementById('pageTitle');
    titleEl.innerHTML = `<i class="fas ${pageIcons[pageName]}"></i><span>${pageTitles[pageName]}</span>`;

    // Stop globe when leaving globe page
    if (typeof window.stopGlobe === 'function') {
        window.stopGlobe();
    }

    // Stop auto refresh for non-dashboard pages
    if (pageName !== 'dashboard') {
        AutoRefresh.stop('dashboard');
    } else if (document.getElementById('autoRefreshToggle')?.checked) {
        startAutoRefresh();
    }

    // Load page data
    switch (pageName) {
        case 'dashboard': loadDashboard(); break;
        case 'agents': loadAgents(); break;
        case 'metrics': loadMetricsPage(); initCharts(); break;
        case 'events': loadEvents(); break;
        case 'globe': loadGlobePage(); break;
        case 'tasks': loadScheduledTasks(); break;
        case 'users': loadUsers(); break;
        case 'settings': loadSettingsPage(); break;
    }
}

// Load user info
async function loadUserInfo() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/users/me');
        if (response && response.ok) {
            currentUser = await response.json();
            document.getElementById('userName').textContent = currentUser.full_name || currentUser.username;
        }
    } catch (err) {
        console.error('Error loading user:', err);
    }
}

// Dashboard
async function loadDashboard() {
    // Show skeletons while loading
    _showDashboardSkeletons();

    try {
        const [devicesRes, collectorsRes, eventsRes, tasksRes] = await Promise.all([
            API.get(ROOT_PATH + '/api/v1/agents/?agent_type=device&limit=100'),
            API.get(ROOT_PATH + '/api/v1/agents/?agent_type=collector&limit=100'),
            API.get(ROOT_PATH + '/api/v1/events/?limit=10'),
            API.get(ROOT_PATH + '/api/v1/tasks/results?limit=10')
        ]);

        if (devicesRes && devicesRes.ok) {
            const devices = await devicesRes.json();
            const activeDevices = devices.filter(d => d.is_active);
            animateCounter('totalDevices', activeDevices.length);

            const devicesList = document.getElementById('recentDevicesList');
            devicesList.innerHTML = activeDevices.slice(0, 5).map(a => `
                <div class="list-item clickable" onclick="switchPage('metrics')">
                    <div>
                        <strong><i class="fas ${getOsIcon(a.os_type)} me-2"></i>${a.hostname}</strong>
                        <small style="display:block;color:var(--grey-dark);margin-top:0.25rem">
                            <i class="fas fa-cog"></i> ${a.os_type} -
                            <i class="fas fa-network-wired"></i> ${a.ip_address || 'N/A'}
                        </small>
                    </div>
                    <span class="badge badge-success">
                        <i class="fas fa-check-circle"></i> Activo
                    </span>
                </div>
            `).join('') || '<div class="empty-state"><i class="fas fa-inbox"></i><p>No hay dispositivos activos</p></div>';
        }

        if (collectorsRes && collectorsRes.ok) {
            const collectors = await collectorsRes.json();
            animateCounter('totalCollectors', collectors.filter(c => c.is_active).length);
        }

        if (eventsRes && eventsRes.ok) {
            const eventsData = await eventsRes.json();
            const events = eventsData.items || eventsData;
            animateCounter('recentEvents', eventsData.total ?? events.length);

            const eventsList = document.getElementById('recentEventsList');
            eventsList.innerHTML = events.slice(0, 5).map(e => `
                <div class="list-item clickable" onclick="showEventDetail(${e.id})">
                    <div>
                        <strong><i class="fas fa-exclamation-circle me-2"></i>${e.title}</strong>
                        <small style="display:block;color:var(--grey-dark);margin-top:0.25rem">
                            ${_renderServiceBadge(e)}
                            <i class="fas fa-clock" style="margin-left:0.3rem"></i> ${timeAgo(e.occurred_at)}
                        </small>
                    </div>
                    <span class="badge badge-${getSeverityClass(e.severity)}">
                        <i class="fas ${getSeverityIcon(e.severity)}"></i>
                        ${e.severity}
                    </span>
                </div>
            `).join('') || '<div class="empty-state"><i class="fas fa-inbox"></i><p>No hay eventos</p></div>';
        }

        if (tasksRes && tasksRes.ok) {
            const tasksData = await tasksRes.json();
            const tasks = tasksData.items || tasksData;
            animateCounter('recentTasks', tasksData.total ?? tasks.length);
        }
    } catch (err) {
        console.error('Error loading dashboard:', err);
    }
}

// ==================== AGENTS ====================
async function loadAgents() {
    try {
        const statusFilter = document.getElementById('agentStatusFilter')?.value;
        let url = ROOT_PATH + '/api/v1/agents/?limit=100&agent_type=collector';
        if (statusFilter === 'active') url += '&active_only=true';

        const response = await API.get(url);
        if (response && response.ok) {
            let agents = await response.json();

            if (statusFilter === 'inactive') {
                agents = agents.filter(a => !a.is_active);
            }

            const tbody = document.getElementById('agentsTableBody');
            tbody.innerHTML = agents.map(a => `
                <tr>
                    <td data-label="ID"><code>${a.agent_id}</code></td>
                    <td data-label="Hostname"><i class="fas fa-server me-2 text-muted"></i>${a.hostname}</td>
                    <td data-label="SO"><i class="fas ${getOsIcon(a.os_type)} me-2"></i>${a.os_type} ${a.os_version || ''}</td>
                    <td data-label="IP"><i class="fas fa-network-wired me-2 text-muted"></i>${a.ip_address || '-'}</td>
                    <td data-label="Estado">
                        <span class="badge ${a.is_active ? 'badge-success' : 'badge-danger'}">
                            <i class="fas ${a.is_active ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                            ${a.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </td>
                    <td data-label="Ultima conexion"><i class="fas fa-clock me-2 text-muted"></i>${timeAgo(a.last_seen)}</td>
                    <td class="actions-cell">
                        <button class="btn-icon" onclick="showAgentDetail(${a.id})" title="Ver detalles">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn-icon btn-icon-danger" onclick="deleteAgent(${a.id}, '${a.hostname}')" title="Eliminar">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('') || '<tr><td colspan="7" class="empty-state"><i class="fas fa-inbox"></i> No hay agentes</td></tr>';
        }
    } catch (err) {
        console.error('Error loading agents:', err);
    }
}

async function showAgentDetail(id) {
    DetailPanel.showAgent(id);
}

function deleteAgent(id, hostname) {
    Confirm.show(`¿Eliminar el agente "${hostname}"?`, async () => {
        const response = await API.delete(ROOT_PATH + `/api/v1/agents/${id}`);
        if (response && response.ok) {
            Toast.success('Agente eliminado');
            loadAgents();
            loadDashboard();
        } else {
            Toast.error('Error al eliminar agente');
        }
    });
}

// ==================== METRICS ====================
function initCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                max: 100,
                ticks: {
                    callback: value => value + '%'
                }
            }
        }
    };

    // CPU Chart
    if (!charts.cpu) {
        const cpuCtx = document.getElementById('cpuChart')?.getContext('2d');
        if (cpuCtx) {
            charts.cpu = new Chart(cpuCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU %',
                        data: [],
                        borderColor: '#4682B4',
                        backgroundColor: 'rgba(70, 130, 180, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: chartOptions
            });
        }
    }

    // Memory Chart
    if (!charts.memory) {
        const memCtx = document.getElementById('memoryChart')?.getContext('2d');
        if (memCtx) {
            charts.memory = new Chart(memCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Memoria %',
                        data: [],
                        borderColor: '#28A745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: chartOptions
            });
        }
    }

    // Disk Chart
    if (!charts.disk) {
        const diskCtx = document.getElementById('diskChart')?.getContext('2d');
        if (diskCtx) {
            charts.disk = new Chart(diskCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Usado', 'Libre'],
                    datasets: [{
                        data: [0, 100],
                        backgroundColor: ['#B22222', '#DEE2E6'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
    }
}

async function loadMetricsPage() {
    try {
        const statusFilter = document.getElementById('metricsDeviceStatusFilter')?.value;
        let url = ROOT_PATH + '/api/v1/agents/?limit=100&agent_type=device';
        if (statusFilter === 'active') url += '&active_only=true';

        const response = await API.get(url);
        if (response && response.ok) {
            let agents = await response.json();
            if (statusFilter === 'inactive') {
                agents = agents.filter(a => !a.is_active);
            }
            deviceAgents = agents;
            renderDeviceList(agents);

            const countEl = document.getElementById('deviceCount');
            if (countEl) countEl.textContent = agents.length;

            if (selectedDeviceId) {
                const stillExists = agents.find(a => a.id === selectedDeviceId);
                if (stillExists) {
                    expandDevice(selectedDeviceId);
                } else {
                    selectedDeviceId = null;
                    clearCharts();
                }
            }
        }
    } catch (err) {
        console.error('Error loading metrics page:', err);
    }
}

function renderDeviceList(agents) {
    const container = document.getElementById('deviceList');
    if (!container) return;

    if (agents.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>No hay dispositivos</p></div>';
        return;
    }

    container.innerHTML = agents.map(agent => `
        <div class="device-card ${selectedDeviceId === agent.id ? 'expanded' : ''}" id="device-${agent.id}">
            <div class="device-card-header" onclick="toggleDevice(${agent.id})">
                <div class="device-info">
                    <div class="device-os-icon">
                        <i class="fas ${getOsIcon(agent.os_type)}"></i>
                    </div>
                    <div class="device-details">
                        <span class="device-hostname">${agent.hostname}</span>
                        <span class="device-meta">
                            <i class="fas fa-network-wired"></i> ${agent.ip_address || 'N/A'}
                            &nbsp;|&nbsp;
                            ${agent.os_type} ${agent.os_version || ''}
                        </span>
                    </div>
                </div>
                <div class="device-status-area">
                    <span class="badge ${agent.is_active ? 'badge-success' : 'badge-danger'}">
                        <i class="fas ${agent.is_active ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                        ${agent.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                    <span class="device-last-seen">
                        <i class="fas fa-clock"></i> ${timeAgo(agent.last_seen)}
                    </span>
                    <button class="btn-icon device-detail-btn" onclick="event.stopPropagation(); showAgentDetail(${agent.id})" title="Ver detalles">
                        <i class="fas fa-eye"></i>
                    </button>
                    <i class="fas fa-chevron-down device-toggle-icon"></i>
                </div>
            </div>
            <div class="device-card-body" id="device-body-${agent.id}">
                <div class="device-loading">
                    <i class="fas fa-spinner fa-spin"></i> Cargando datos...
                </div>
            </div>
        </div>
    `).join('');
}

function toggleDevice(agentId) {
    if (selectedDeviceId === agentId) {
        collapseDevice(agentId);
        selectedDeviceId = null;
        clearCharts();
        updateChartAgentLabel(null);
    } else {
        if (selectedDeviceId) collapseDevice(selectedDeviceId);
        selectedDeviceId = agentId;
        expandDevice(agentId);
    }
}

function collapseDevice(agentId) {
    const card = document.getElementById(`device-${agentId}`);
    if (card) card.classList.remove('expanded');
}

async function expandDevice(agentId) {
    const card = document.getElementById(`device-${agentId}`);
    if (card) card.classList.add('expanded');

    const body = document.getElementById(`device-body-${agentId}`);
    if (!body) return;

    body.innerHTML = '<div class="device-loading"><i class="fas fa-spinner fa-spin"></i> Cargando datos...</div>';

    try {
        const [metricsRes, eventsRes, loginEventsRes] = await Promise.all([
            API.get(ROOT_PATH + `/api/v1/metrics/agent/${agentId}`),
            API.get(ROOT_PATH + `/api/v1/events/?agent_id=${agentId}&category=security&event_type=alert&limit=1`),
            API.get(ROOT_PATH + `/api/v1/events/?agent_id=${agentId}&event_type=login_audit&limit=1`)
        ]);

        let metrics = [];
        let latestEvent = null;
        let latestLoginEvent = null;

        if (metricsRes && metricsRes.ok) metrics = await metricsRes.json();
        if (eventsRes && eventsRes.ok) {
            const eventsData = await eventsRes.json();
            const events = eventsData.items || eventsData;
            latestEvent = events.length > 0 ? events[0] : null;
        }
        if (loginEventsRes && loginEventsRes.ok) {
            const loginData = await loginEventsRes.json();
            const loginEvents = loginData.items || loginData;
            latestLoginEvent = loginEvents.length > 0 ? loginEvents[0] : null;
        }

        renderDeviceExpanded(body, metrics, latestEvent, latestLoginEvent);
        updateCharts(metrics);

        const agent = deviceAgents.find(a => a.id === agentId);
        updateChartAgentLabel(agent ? agent.hostname : null);
    } catch (err) {
        console.error('Error expanding device:', err);
        body.innerHTML = '<div class="device-error"><i class="fas fa-exclamation-triangle"></i> Error al cargar datos</div>';
    }
}

function renderDeviceExpanded(bodyEl, metrics, event, loginEvent) {
    const cpuMetric = metrics.find(m => m.metric_type === 'cpu' && m.metric_name === 'usage_percent');
    const memMetric = metrics.find(m => m.metric_type === 'memory' && m.metric_name === 'usage_percent');
    const diskMetric = metrics.find(m => m.metric_type === 'disk' && m.metric_name.includes('usage_percent'));

    let html = '<div class="device-expanded-content">';

    // Key metrics row
    html += '<div class="device-metrics-row">';
    html += renderKeyMetric('fa-microchip', 'CPU', cpuMetric?.value, '#4682B4');
    html += renderKeyMetric('fa-memory', 'RAM', memMetric?.value, '#28A745');
    html += renderKeyMetric('fa-hard-drive', 'Disco', diskMetric?.value, '#B22222');
    html += '</div>';

    // Security event
    if (event && event.extra_data) {
        html += renderSecurityEvent(event);
    } else if (event) {
        html += `
            <div class="device-security-section">
                <div class="security-section-header">
                    <h4><i class="fas fa-shield-halved"></i> Ultimo Evento</h4>
                    <span class="badge badge-${getSeverityClass(event.severity)}">
                        <i class="fas ${getSeverityIcon(event.severity)}"></i> ${event.severity}
                    </span>
                </div>
                <p style="margin:0.5rem 0 0;color:var(--grey-dark)">${event.title}</p>
            </div>
        `;
    } else {
        html += `
            <div class="device-security-section">
                <div class="security-section-header">
                    <h4><i class="fas fa-shield-halved"></i> Seguridad</h4>
                </div>
                <div class="empty-state-small"><i class="fas fa-check-circle"></i> Sin eventos recientes</div>
            </div>
        `;
    }

    // Login audit event
    if (loginEvent && loginEvent.extra_data) {
        html += renderLoginAuditEvent(loginEvent);
    }

    html += '</div>';
    bodyEl.innerHTML = html;
}

function renderKeyMetric(icon, label, value, color) {
    const displayValue = value != null ? value.toFixed(1) : '--';
    const statusClass = value != null ? getMetricStatusClass(value, 'percent') : '';
    const barWidth = value != null ? Math.min(value, 100) : 0;

    return `
        <div class="device-key-metric">
            <div class="key-metric-top">
                <div class="key-metric-icon" style="background:${color}">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="key-metric-info">
                    <span class="key-metric-label">${label}</span>
                    <span class="key-metric-value ${statusClass}">${displayValue}%</span>
                </div>
            </div>
            <div class="key-metric-bar">
                <div class="key-metric-bar-fill ${statusClass}" style="width:${barWidth}%;background:${color}"></div>
            </div>
        </div>
    `;
}

function generateSecurityExplanation(data, detailed = false) {
    const items = [];
    const ssh = data.ssh_failures || [];
    if (ssh.length > 0) {
        const totalAttempts = ssh.reduce((sum, item) => sum + (item.attempts || 0), 0);
        items.push({
            icon: 'fa-terminal',
            text: `${ssh.length} IPs intentaron acceso SSH (${totalAttempts} intentos)`,
            context: 'Habitual en servidores expuestos; suelen ser bots probando credenciales por defecto'
        });
    }
    const nginx = data.nginx_suspicious || [];
    if (nginx.length > 0) {
        items.push({
            icon: 'fa-globe',
            text: `${nginx.length} IPs escaneando el servidor web (404, rutas sensibles)`,
            context: 'Escaneos automáticos buscando vulnerabilidades conocidas, típico de bots'
        });
    }
    const fw = data.firewall_blocked || [];
    if (fw.length > 0) {
        const totalBlocks = fw.reduce((sum, item) => sum + (item.blocks || 0), 0);
        items.push({
            icon: 'fa-shield-halved',
            text: `Firewall bloqueó ${totalBlocks} conexiones de ${fw.length} IPs`,
            context: 'El firewall las detuvo correctamente, no llegaron al sistema'
        });
    }
    const sudo = data.sudo_failures || [];
    if (sudo.length > 0) {
        items.push({
            icon: 'fa-user-lock',
            text: `${sudo.length} IPs con intentos fallidos de sudo`,
            context: 'Intentos de escalada de privilegios; si son IPs internas, revisar configuración de usuarios'
        });
    }
    const services = data.service_failures || [];
    if (services.length > 0) {
        const names = services.map(s => s.service).join(', ');
        items.push({
            icon: 'fa-server',
            text: `Errores en servicios: ${names}`,
            context: 'Puede indicar reinicio programado o fallo puntual; verificar si los servicios están activos'
        });
    }
    const defender = data.defender_alerts || [];
    if (defender.length > 0) {
        items.push({
            icon: 'fa-shield-virus',
            text: `${defender.length} alertas de Windows Defender`,
            context: 'Revisar si son falsos positivos o amenazas reales en el panel de Defender'
        });
    }
    const highRisk = data.high_risk_ips || [];
    if (highRisk.length > 0) {
        items.push({
            icon: 'fa-skull-crossbones',
            text: `${highRisk.length} superan el umbral de riesgo`,
            context: 'Estas IPs acumulan actividad sospechosa en múltiples vectores'
        });
    }
    if (items.length === 0) {
        if (detailed) return '<div class="security-insight-empty"><i class="fas fa-check-circle"></i> Sin incidencias de seguridad en el periodo analizado.</div>';
        return 'Sin incidencias de seguridad en el periodo analizado.';
    }
    if (!detailed) {
        return items.map(i => i.text).join('. ') + '.';
    }
    let html = '<div class="security-insights">';
    html += items.map(i => `
        <div class="security-insight-item">
            <div class="insight-main">
                <i class="fas ${i.icon}"></i>
                <span class="insight-fact">${i.text}</span>
            </div>
            <div class="insight-context">${i.context}</div>
        </div>
    `).join('');
    if (highRisk.length === 0) {
        html += `
        <div class="security-insight-footer">
            <i class="fas fa-check-circle"></i>
            Ninguna IP supera el umbral de riesgo; actividad dentro de lo esperado.
        </div>`;
    }
    html += '</div>';
    return html;
}

function renderSecurityEvent(event) {
    const data = event.extra_data;
    const highRiskCount = (data.high_risk_ips || []).length;
    const analysisPeriod = data.analysis_period_hours || 24;

    let html = `
        <div class="device-security-section">
            <div class="security-section-header">
                <h4><i class="fas fa-shield-halved"></i> Ultimo Evento de Seguridad</h4>
                <span class="badge badge-${getSeverityClass(event.severity)}">
                    <i class="fas ${getSeverityIcon(event.severity)}"></i> ${event.severity}
                </span>
                <span class="security-event-date"><i class="fas fa-clock"></i> ${timeAgo(event.occurred_at)}</span>
            </div>
            <div class="security-summary-bar">
                <span><i class="fas fa-clock"></i> Periodo: ${analysisPeriod}h</span>
                <span class="${highRiskCount > 0 ? 'text-danger-bold' : ''}">
                    <i class="fas fa-skull-crossbones"></i> IPs alto riesgo: ${highRiskCount}
                </span>
                <span><i class="fas fa-eye-slash"></i> Whitelist ignoradas: ${data.whitelisted_ignored || 0}</span>
            </div>
            <div class="security-explanation">
                <i class="fas fa-comment-dots"></i>
                <span>${generateSecurityExplanation(data)}</span>
            </div>
    `;

    // Security grid 2x2
    html += '<div class="security-grid">';
    html += renderSecurityCategory('fa-terminal', 'Fallos SSH', data.ssh_failures || [],
        item => `<span class="security-ip">${item.ip}</span> <span class="security-count">${item.attempts} intentos</span>`);
    html += renderSecurityCategory('fa-globe', 'Web Sospechoso', data.nginx_suspicious || [],
        item => `<span class="security-ip">${item.ip}</span> <span class="security-count">${item.count} accesos</span>`);
    html += renderSecurityCategory('fa-shield-halved', 'Firewall Bloqueado', data.firewall_blocked || [],
        item => `<span class="security-ip">${item.ip}</span> <span class="security-count">${item.blocks} bloqueos</span>`);
    html += renderSecurityCategory('fa-user-lock', 'Fallos Sudo', data.sudo_failures || [],
        item => `<span class="security-ip">${item.ip}</span> <span class="security-count">${item.attempts} intentos</span>`);
    html += '</div>';

    // Service failures
    if ((data.service_failures || []).length > 0) {
        html += `
            <div class="security-services">
                <h5><i class="fas fa-server"></i> Servicios con Errores</h5>
                <div class="security-services-list">
                    ${data.service_failures.map(s => `
                        <div class="service-failure-item">
                            <span class="service-name"><i class="fas fa-cog"></i> ${s.service}</span>
                            <span class="badge badge-danger" style="font-size:0.7rem">${s.error_count} errores</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // Threat scores top 5
    const scores = data.threat_scores || {};
    const scoreEntries = Object.entries(scores).sort((a, b) => b[1] - a[1]).slice(0, 5);
    if (scoreEntries.length > 0) {
        html += `
            <div class="security-scores">
                <h5><i class="fas fa-chart-bar"></i> Threat Scores (Top 5)</h5>
                <div class="threat-score-list">
                    ${scoreEntries.map(([ip, score]) => {
                        const barWidth = Math.min(score, 200) / 200 * 100;
                        const scoreClass = score > 100 ? 'score-critical' : score > 50 ? 'score-high' : 'score-medium';
                        return `
                            <div class="threat-score-item">
                                <span class="security-ip">${ip}</span>
                                <div class="threat-score-bar">
                                    <div class="threat-score-bar-fill ${scoreClass}" style="width:${barWidth}%"></div>
                                </div>
                                <span class="threat-score-value ${scoreClass}">${score}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    // High risk IPs
    if (highRiskCount > 0) {
        html += `
            <div class="security-high-risk">
                <h5><i class="fas fa-exclamation-triangle"></i> IPs de Alto Riesgo</h5>
                <div class="high-risk-ips">
                    ${data.high_risk_ips.map(ip => `
                        <span class="high-risk-ip-badge"><i class="fas fa-skull-crossbones"></i> ${ip}</span>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // Defender alerts (Windows)
    if ((data.defender_alerts || []).length > 0) {
        html += `
            <div class="security-services">
                <h5><i class="fas fa-shield-virus"></i> Windows Defender</h5>
                <div class="security-services-list">
                    ${data.defender_alerts.map(a => `
                        <div class="service-failure-item">
                            <span class="service-name"><i class="fas fa-bug"></i> ${a.type.replace(/_/g, ' ')}</span>
                            <span class="security-count">${a.time ? timeAgo(a.time) : ''}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function renderLoginAuditEvent(event) {
    const data = event.extra_data;
    const summary = data.summary || {};
    const anomalies = data.anomalies || [];
    const period = data.period_hours || 1;
    const autoExplanation = data.auto_explanation || null;

    let html = `
        <div class="device-security-section login-audit-section">
            <div class="security-section-header">
                <h4><i class="fas fa-right-to-bracket"></i> Auditoria de Logins</h4>
                <span class="badge badge-${getSeverityClass(event.severity)}">
                    <i class="fas ${getSeverityIcon(event.severity)}"></i> ${event.severity}
                </span>
                <span class="security-event-date"><i class="fas fa-clock"></i> ${timeAgo(event.occurred_at)}</span>
            </div>
            <div class="login-audit-summary-bar">
                <span class="login-stat-success"><i class="fas fa-check-circle"></i> ${summary.total_success || 0} exitosos</span>
                <span class="login-stat-failed"><i class="fas fa-times-circle"></i> ${summary.total_failed || 0} fallidos</span>
                <span><i class="fas fa-users"></i> ${summary.unique_users || 0} usuarios</span>
                <span><i class="fas fa-globe"></i> ${summary.unique_ips_failed || 0} IPs atacantes</span>
            </div>
    `;

    // Anomalies
    if (anomalies.length > 0) {
        html += '<div class="login-audit-anomalies">';
        anomalies.forEach(a => {
            const aClass = (a.type === 'success_after_fail' || a.type === 'root_external') ? 'anomaly-critical' : 'anomaly-warning';
            html += `<div class="login-anomaly-item ${aClass}"><i class="fas fa-exclamation-triangle"></i> ${a.detail}</div>`;
        });
        html += '</div>';
    }

    // Auto-explanation inline
    if (autoExplanation) {
        html += `
            <div class="security-explanation">
                <i class="fas fa-lightbulb"></i>
                <span>${autoExplanation}</span>
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function renderLoginAuditDetail(data) {
    const summary = data.summary || {};
    const anomalies = data.anomalies || [];
    const successLogins = data.successful_logins || [];
    const failedLogins = data.failed_logins || [];
    const sudoSessions = data.sudo_sessions || [];

    let html = '<div class="detail-item full-width">';

    // Anomalies section
    if (anomalies.length > 0) {
        html += `
            <div class="login-audit-anomalies" style="margin-bottom:1rem">
                <span class="detail-label"><i class="fas fa-exclamation-triangle"></i> Anomalias detectadas</span>
                ${anomalies.map(a => {
                    const aClass = (a.type === 'success_after_fail' || a.type === 'root_external') ? 'anomaly-critical' : 'anomaly-warning';
                    return `<div class="login-anomaly-item ${aClass}"><i class="fas fa-exclamation-triangle"></i> ${a.detail}</div>`;
                }).join('')}
            </div>
        `;
    }

    // Grid 2x2: success | failed | sudo | summary
    html += '<div class="security-grid">';

    // Successful logins
    html += `<div class="security-category ${successLogins.length === 0 ? 'security-category-empty' : ''}">
        <div class="security-category-header"><i class="fas fa-check-circle" style="color:var(--success)"></i><span>Logins Exitosos</span>
            <span class="security-category-count ${successLogins.length > 0 ? 'has-items' : ''}">${successLogins.length}</span>
        </div>
        ${successLogins.length > 0 ? `<div class="security-category-items">
            ${successLogins.slice(0, 5).map(l => `<div class="security-category-item">
                <span class="security-ip">${l.user}@${l.ip}</span> <span class="security-count">${l.method}</span>
            </div>`).join('')}
            ${successLogins.length > 5 ? `<div class="security-more">... y ${successLogins.length - 5} mas</div>` : ''}
        </div>` : '<div class="security-category-empty-msg"><i class="fas fa-check"></i> Ninguno</div>'}
    </div>`;

    // Failed logins
    html += `<div class="security-category ${failedLogins.length === 0 ? 'security-category-empty' : ''}">
        <div class="security-category-header"><i class="fas fa-times-circle" style="color:var(--danger)"></i><span>Logins Fallidos</span>
            <span class="security-category-count ${failedLogins.length > 0 ? 'has-items' : ''}">${failedLogins.length}</span>
        </div>
        ${failedLogins.length > 0 ? `<div class="security-category-items">
            ${failedLogins.slice(0, 5).map(l => `<div class="security-category-item">
                <span class="security-ip">${l.user}@${l.ip}</span> <span class="security-count">${l.method}</span>
            </div>`).join('')}
            ${failedLogins.length > 5 ? `<div class="security-more">... y ${failedLogins.length - 5} mas</div>` : ''}
        </div>` : '<div class="security-category-empty-msg"><i class="fas fa-check"></i> Ninguno</div>'}
    </div>`;

    // Sudo sessions
    html += `<div class="security-category ${sudoSessions.length === 0 ? 'security-category-empty' : ''}">
        <div class="security-category-header"><i class="fas fa-user-shield"></i><span>Sesiones Sudo</span>
            <span class="security-category-count ${sudoSessions.length > 0 ? 'has-items' : ''}">${sudoSessions.length}</span>
        </div>
        ${sudoSessions.length > 0 ? `<div class="security-category-items">
            ${sudoSessions.slice(0, 5).map(s => `<div class="security-category-item">
                <span class="security-ip">${s.user}</span> <span class="security-count" title="${s.command}">${s.command.substring(0, 40)}</span>
            </div>`).join('')}
            ${sudoSessions.length > 5 ? `<div class="security-more">... y ${sudoSessions.length - 5} mas</div>` : ''}
        </div>` : '<div class="security-category-empty-msg"><i class="fas fa-check"></i> Ninguna</div>'}
    </div>`;

    // Summary
    html += `<div class="security-category">
        <div class="security-category-header"><i class="fas fa-chart-pie"></i><span>Resumen</span></div>
        <div class="security-category-items">
            <div class="security-category-item"><span>Exitosos</span> <span class="security-count" style="color:var(--success)">${summary.total_success || 0}</span></div>
            <div class="security-category-item"><span>Fallidos</span> <span class="security-count" style="color:var(--danger)">${summary.total_failed || 0}</span></div>
            <div class="security-category-item"><span>Usuarios unicos</span> <span class="security-count">${summary.unique_users || 0}</span></div>
            <div class="security-category-item"><span>IPs exitosas</span> <span class="security-count">${summary.unique_ips_success || 0}</span></div>
            <div class="security-category-item"><span>IPs atacantes</span> <span class="security-count" style="color:var(--danger)">${summary.unique_ips_failed || 0}</span></div>
        </div>
    </div>`;

    html += '</div></div>';
    return html;
}

function renderSecurityCategory(icon, title, items, renderItem) {
    const count = items.length;
    return `
        <div class="security-category ${count === 0 ? 'security-category-empty' : ''}">
            <div class="security-category-header">
                <i class="fas ${icon}"></i>
                <span>${title}</span>
                <span class="security-category-count ${count > 0 ? 'has-items' : ''}">${count}</span>
            </div>
            ${count > 0 ? `
                <div class="security-category-items">
                    ${items.slice(0, 5).map(item => `
                        <div class="security-category-item">${renderItem(item)}</div>
                    `).join('')}
                    ${items.length > 5 ? `<div class="security-more">... y ${items.length - 5} mas</div>` : ''}
                </div>
            ` : `
                <div class="security-category-empty-msg">
                    <i class="fas fa-check"></i> Sin incidencias
                </div>
            `}
        </div>
    `;
}

function updateChartAgentLabel(hostname) {
    const label = document.getElementById('chartAgentLabel');
    if (label) {
        label.textContent = hostname ? hostname : '';
        label.style.display = hostname ? 'inline-block' : 'none';
    }
}

function clearCharts() {
    if (charts.cpu) {
        charts.cpu.data.labels = [];
        charts.cpu.data.datasets[0].data = [];
        charts.cpu.update();
    }
    if (charts.memory) {
        charts.memory.data.labels = [];
        charts.memory.data.datasets[0].data = [];
        charts.memory.update();
    }
    if (charts.disk) {
        charts.disk.data.datasets[0].data = [0, 100];
        charts.disk.update();
    }
    updateChartAgentLabel(null);
}

function getMetricStatusClass(value, format) {
    if (format !== 'percent') return '';
    if (value >= 90) return 'metric-critical';
    if (value >= 75) return 'metric-warning';
    return 'metric-ok';
}

function updateCharts(metrics) {
    // CPU metrics
    const cpuMetrics = metrics.filter(m => m.metric_type === 'cpu').slice(0, 20).reverse();
    if (charts.cpu && cpuMetrics.length > 0) {
        charts.cpu.data.labels = cpuMetrics.map(m => formatTime(m.collected_at));
        charts.cpu.data.datasets[0].data = cpuMetrics.map(m => m.value);
        charts.cpu.update();
    }

    // Memory metrics
    const memMetrics = metrics.filter(m => m.metric_type === 'memory' && m.metric_name.includes('percent')).slice(0, 20).reverse();
    if (charts.memory && memMetrics.length > 0) {
        charts.memory.data.labels = memMetrics.map(m => formatTime(m.collected_at));
        charts.memory.data.datasets[0].data = memMetrics.map(m => m.value);
        charts.memory.update();
    }

    // Disk metrics
    const diskMetric = metrics.find(m => m.metric_type === 'disk' && m.metric_name.includes('percent'));
    if (charts.disk && diskMetric) {
        const used = diskMetric.value;
        charts.disk.data.datasets[0].data = [used, 100 - used];
        charts.disk.update();
    }
}

function formatTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
}

// ==================== EVENTS ====================
async function loadEvents() {
    try {
        const state = tableState.events;
        const search = document.getElementById('eventSearchInput')?.value?.trim();

        let url = ROOT_PATH + `/api/v1/events/?limit=${state.limit}&skip=${state.skip}&sort_by=${state.sortBy}&sort_order=${state.sortOrder}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;

        const response = await API.get(url);
        if (response && response.ok) {
            const data = await response.json();
            const events = data.items || [];
            state.total = data.total || 0;

            const tbody = document.getElementById('eventsTableBody');
            tbody.innerHTML = events.map(e => `
                <tr>
                    <td class="event-check-cell"><input type="checkbox" class="event-check" value="${e.id}" onchange="updateEventSelectionUI()"></td>
                    <td data-label="Severidad">
                        <span class="badge badge-${getSeverityClass(e.severity)}">
                            <i class="fas ${getSeverityIcon(e.severity)}"></i>
                            ${e.severity}
                        </span>
                    </td>
                    <td data-label="Tipo">${_renderServiceBadge(e)}</td>
                    <td data-label="Categoria"><span class="event-cat-badge">${e.category}</span></td>
                    <td data-label="Titulo">${e.title}</td>
                    <td data-label="Agente">${e.agent_id}</td>
                    <td data-label="Fecha">${formatDate(e.occurred_at)}</td>
                    <td class="actions-cell">
                        <button class="btn-icon" onclick="showEventDetail(${e.id})" title="Ver detalles">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                </tr>
            `).join('') || '<tr><td colspan="8" class="empty-state"><i class="fas fa-inbox"></i> No hay eventos</td></tr>';

            const selectAll = document.getElementById('selectAllEvents');
            if (selectAll) selectAll.checked = false;
            updateEventSelectionUI();
            renderPagination('eventsPagination', 'events', loadEvents);
        } else {
            const tbody = document.getElementById('eventsTableBody');
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-inbox"></i> No hay eventos</td></tr>';
            document.getElementById('eventsPagination').innerHTML = '';
        }
    } catch (err) {
        console.error('Error loading events:', err);
    }
}

function deleteSelectedEvents() {
    const checked = document.querySelectorAll('.event-check:checked');
    const ids = Array.from(checked).map(cb => parseInt(cb.value));
    if (ids.length === 0) return;

    Confirm.show(`¿Eliminar ${ids.length} evento(s) seleccionado(s)?`, async () => {
        const response = await API.post(ROOT_PATH + '/api/v1/events/delete-batch', ids);
        if (response && response.ok) {
            const data = await response.json();
            Toast.success(`${data.deleted} evento(s) eliminado(s)`);
            loadEvents();
            loadDashboard();
        } else {
            Toast.error('Error al eliminar eventos');
        }
    });
}

function deleteOldEvents() {
    Confirm.show('¿Eliminar todos los eventos con mas de 7 dias?', async () => {
        const response = await API.delete(ROOT_PATH + '/api/v1/events/?days=7');
        if (response && response.ok) {
            const data = await response.json();
            Toast.success(`${data.deleted} evento(s) eliminado(s)`);
            loadEvents();
            loadDashboard();
        } else {
            Toast.error('Error al eliminar eventos');
        }
    });
}

function toggleEventSelection() {
    const selectAll = document.getElementById('selectAllEvents');
    const checkboxes = document.querySelectorAll('.event-check');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
    updateEventSelectionUI();
}

function updateEventSelectionUI() {
    const checked = document.querySelectorAll('.event-check:checked');
    const hasSelection = checked.length > 0;
    const defaultBar = document.getElementById('eventsActionDefault');
    const selectedBar = document.getElementById('eventsActionSelected');
    const count = document.getElementById('selectedCount');
    if (defaultBar) defaultBar.style.display = hasSelection ? 'none' : '';
    if (selectedBar) selectedBar.style.display = hasSelection ? 'inline-flex' : 'none';
    if (count) count.textContent = checked.length;
}

async function showEventDetail(id) {
    DetailPanel.showEvent(id);
}

// ==================== SCHEDULED TASKS ====================
let taskCatalog = [];
let selectedCatalogTask = null;
let currentScheduleType = 'interval';

async function loadScheduledTasks() {
    await Promise.all([loadSystemTasks(), loadUserTasks(), loadRecentExecutions()]);
}

async function loadSystemTasks() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/scheduled-tasks/system');
        if (response && response.ok) {
            const tasks = await response.json();
            const grid = document.getElementById('systemTasksGrid');
            const icons = {
                'cleanup-old-metrics': 'fa-broom',
                'check-agent-status': 'fa-heartbeat',
                'send-daily-report': 'fa-file-lines',
                'cleanup-old-events': 'fa-trash-can',
            };
            grid.innerHTML = tasks.map(t => `
                <div class="system-task-card">
                    <div class="system-task-icon">
                        <i class="fas ${icons[t.key] || 'fa-cog'}"></i>
                    </div>
                    <div class="system-task-info">
                        <h4>${t.name}</h4>
                        <p>${t.description}</p>
                        <div class="system-task-meta">
                            <span><i class="fas fa-clock"></i> ${t.schedule}</span>
                            <span class="badge badge-success"><i class="fas fa-check-circle"></i> ${t.status}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error('Error loading system tasks:', err);
    }
}

async function loadUserTasks() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/scheduled-tasks/?limit=100');
        if (response && response.ok) {
            const data = await response.json();
            const tasks = data.items || [];
            const grid = document.getElementById('userTasksGrid');

            if (tasks.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state" style="grid-column:1/-1;">
                        <i class="fas fa-calendar-plus"></i>
                        <p>No hay tareas programadas</p>
                        <button class="btn btn-primary btn-sm" onclick="openCreateTaskModal()">
                            <i class="fas fa-plus"></i> Crear primera tarea
                        </button>
                    </div>
                `;
                return;
            }

            grid.innerHTML = tasks.map(t => {
                const isAgent = t.target_type === 'agent';
                const scheduleLabel = getScheduleLabel(t);
                return `
                    <div class="task-card ${t.is_enabled ? '' : 'disabled'}">
                        <div class="task-card-header">
                            <div class="task-card-title">
                                <div class="task-icon">
                                    <i class="fas ${isAgent ? 'fa-desktop' : 'fa-server'}"></i>
                                </div>
                                <div>
                                    <h4>${t.display_name}</h4>
                                    <span class="task-target">${isAgent ? 'Agente #' + t.agent_id : 'Servidor'} &middot; ${scheduleLabel}</span>
                                </div>
                            </div>
                            <div class="task-card-actions">
                                <button class="btn-icon" onclick="runScheduledTask(${t.id})" title="Ejecutar ahora">
                                    <i class="fas fa-play"></i>
                                </button>
                                <button class="btn-icon btn-icon-toggle ${t.is_enabled ? '' : 'off'}" onclick="toggleScheduledTask(${t.id})" title="${t.is_enabled ? 'Desactivar' : 'Activar'}">
                                    <i class="fas ${t.is_enabled ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>
                                </button>
                                <button class="btn-icon" onclick="showScheduledTaskDetail(${t.id})" title="Ver detalle">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button class="btn-icon btn-icon-danger" onclick="deleteScheduledTask(${t.id}, '${t.display_name.replace(/'/g, "\\'")}')" title="Eliminar">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="task-card-stats">
                            <div class="task-stat">
                                <span class="task-stat-label">Ultima ejecucion</span>
                                <span class="task-stat-value">${t.last_run_at ? timeAgo(t.last_run_at) : 'Nunca'}</span>
                            </div>
                            <div class="task-stat">
                                <span class="task-stat-label">Proxima</span>
                                <span class="task-stat-value">${t.next_run_at ? timeAgo(t.next_run_at) : '-'}</span>
                            </div>
                            <div class="task-stat">
                                <span class="task-stat-label">Ejecuciones</span>
                                <span class="task-stat-value">${t.run_count}</span>
                            </div>
                            <div class="task-stat">
                                <span class="task-stat-label">Estado</span>
                                <span class="task-stat-value">
                                    ${t.last_status ? `<span class="badge badge-${getStatusClass(t.last_status)}">${t.last_status}</span>` : '-'}
                                </span>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (err) {
        console.error('Error loading user tasks:', err);
    }
}

async function loadRecentExecutions() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/scheduled-tasks/executions/recent?limit=20');
        if (response && response.ok) {
            const executions = await response.json();
            const tbody = document.getElementById('executionsTableBody');

            if (executions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state-small"><i class="fas fa-inbox"></i> Sin ejecuciones recientes</td></tr>';
                return;
            }

            tbody.innerHTML = executions.map(e => `
                <tr>
                    <td><code>${e.catalog_key}</code></td>
                    <td><span class="badge badge-${e.trigger_type === 'manual' ? 'info' : e.trigger_type === 'system' ? 'secondary' : 'primary'}">${e.trigger_type}</span></td>
                    <td>
                        <span class="badge badge-${getStatusClass(e.status)}">
                            <i class="fas ${getStatusIcon(e.status)}"></i> ${e.status}
                        </span>
                    </td>
                    <td>${e.duration_seconds ? e.duration_seconds.toFixed(2) + 's' : '-'}</td>
                    <td>${formatDate(e.created_at)}</td>
                    <td>
                        ${e.output || e.error ? `<button class="btn-icon" onclick="showExecutionOutput(${e.id})" title="Ver salida"><i class="fas fa-terminal"></i></button>` : ''}
                    </td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Error loading executions:', err);
    }
}

function getScheduleLabel(task) {
    if (task.schedule_type === 'interval' && task.interval_seconds) {
        const s = task.interval_seconds;
        if (s < 3600) return `Cada ${Math.round(s / 60)} min`;
        if (s < 86400) return `Cada ${Math.round(s / 3600)} h`;
        return `Cada ${Math.round(s / 86400)} dia(s)`;
    }
    if (task.schedule_type === 'cron') {
        return `Cron: ${task.cron_minute} ${task.cron_hour} ${task.cron_dom} ${task.cron_month} ${task.cron_dow}`;
    }
    if (task.schedule_type === 'once') {
        return task.run_at ? `Una vez: ${formatDate(task.run_at)}` : 'Una vez';
    }
    return task.schedule_type;
}

function toggleTasksSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) section.classList.toggle('collapsed');
}

// ---- Create Task Modal (Wizard) ----
async function openCreateTaskModal() {
    selectedCatalogTask = null;
    document.getElementById('wizardStep1').classList.add('active');
    document.getElementById('wizardStep2').classList.remove('active');
    document.getElementById('wizardBackBtn').style.display = 'none';
    document.getElementById('wizardNextBtn').style.display = 'none';
    document.getElementById('wizardSaveBtn').style.display = 'none';

    await loadTaskCatalog();
    Modal.show('createTaskModal');
}

async function loadTaskCatalog() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/scheduled-tasks/catalog');
        if (response && response.ok) {
            taskCatalog = await response.json();
            renderCatalogGrid('server');
        }
    } catch (err) {
        console.error('Error loading catalog:', err);
    }
}

function switchCatalogTab(category) {
    document.querySelectorAll('.catalog-tab').forEach(t => t.classList.remove('active'));
    event.target.closest('.catalog-tab').classList.add('active');
    renderCatalogGrid(category);
}

function renderCatalogGrid(category) {
    const grid = document.getElementById('catalogGrid');
    const filtered = taskCatalog.filter(t => t.category === category);

    grid.innerHTML = filtered.map(t => `
        <div class="catalog-item ${selectedCatalogTask?.key === t.key ? 'selected' : ''}" onclick="selectCatalogTask('${t.key}')">
            <div class="catalog-item-icon">
                <i class="fas ${t.icon}"></i>
            </div>
            <div class="catalog-item-info">
                <h5>${t.name}</h5>
                <p>${t.description}</p>
            </div>
        </div>
    `).join('') || '<div class="empty-state-small">No hay tareas en esta categoria</div>';
}

function selectCatalogTask(key) {
    selectedCatalogTask = taskCatalog.find(t => t.key === key);
    document.querySelectorAll('.catalog-item').forEach(el => el.classList.remove('selected'));
    event.target.closest('.catalog-item')?.classList.add('selected');
    document.getElementById('wizardNextBtn').style.display = '';
}

async function wizardNext() {
    if (!selectedCatalogTask) {
        Toast.warning('Selecciona una tarea del catalogo');
        return;
    }

    document.getElementById('wizardStep1').classList.remove('active');
    document.getElementById('wizardStep2').classList.add('active');
    document.getElementById('wizardBackBtn').style.display = '';
    document.getElementById('wizardNextBtn').style.display = 'none';
    document.getElementById('wizardSaveBtn').style.display = '';

    // Populate step 2
    const t = selectedCatalogTask;
    document.getElementById('stCatalogKey').value = t.key;
    document.getElementById('stTargetType').value = t.target_type;
    document.getElementById('stDisplayName').value = t.name;

    document.getElementById('selectedTaskInfo').innerHTML = `
        <div class="task-detail-icon"><i class="fas ${t.icon}"></i></div>
        <div class="task-detail-title">
            <h4>${t.name}</h4>
            <p>${t.description}</p>
        </div>
    `;

    // Agent selector
    const agentGroup = document.getElementById('agentSelectGroup');
    if (t.target_type === 'agent') {
        agentGroup.style.display = '';
        await loadAgentOptions();
    } else {
        agentGroup.style.display = 'none';
    }

    // Parameters
    const paramsGroup = document.getElementById('taskParamsGroup');
    const paramsFields = document.getElementById('taskParamsFields');
    if (t.parameters && t.parameters.length > 0) {
        paramsGroup.style.display = '';
        paramsFields.innerHTML = t.parameters.map(p => `
            <div class="form-group">
                <label for="param_${p.name}">${p.label}</label>
                <input type="${p.type === 'int' ? 'number' : 'text'}" id="param_${p.name}" class="form-control" value="${p.default ?? ''}" ${p.required ? 'required' : ''}>
            </div>
        `).join('');
    } else {
        paramsGroup.style.display = 'none';
        paramsFields.innerHTML = '';
    }

    // Default schedule
    if (t.default_schedule) {
        selectScheduleType(t.default_schedule.type || 'interval');
        if (t.default_schedule.interval_seconds) {
            document.getElementById('stIntervalSeconds').value = t.default_schedule.interval_seconds;
        }
    } else {
        selectScheduleType('interval');
    }
}

function wizardBack() {
    document.getElementById('wizardStep2').classList.remove('active');
    document.getElementById('wizardStep1').classList.add('active');
    document.getElementById('wizardBackBtn').style.display = 'none';
    document.getElementById('wizardNextBtn').style.display = selectedCatalogTask ? '' : 'none';
    document.getElementById('wizardSaveBtn').style.display = 'none';
}

async function loadAgentOptions() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/agents/?limit=100');
        if (response && response.ok) {
            const agents = await response.json();
            const select = document.getElementById('stAgentId');
            select.innerHTML = '<option value="">Seleccionar agente...</option>' +
                agents.map(a => `<option value="${a.id}">${a.hostname} (${a.agent_id})</option>`).join('');
        }
    } catch (err) {
        console.error('Error loading agents for selector:', err);
    }
}

function selectScheduleType(type) {
    currentScheduleType = type;
    document.querySelectorAll('.schedule-type-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.schedule-config').forEach(c => c.classList.remove('active'));

    document.querySelectorAll('.schedule-type-btn').forEach(b => {
        if (b.textContent.trim().toLowerCase().includes(type === 'interval' ? 'intervalo' : type === 'cron' ? 'cron' : 'una vez')) {
            b.classList.add('active');
        }
    });

    const configId = type === 'interval' ? 'scheduleInterval' : type === 'cron' ? 'scheduleCron' : 'scheduleOnce';
    document.getElementById(configId)?.classList.add('active');
}

async function saveScheduledTask() {
    const catalogKey = document.getElementById('stCatalogKey').value;
    const targetType = document.getElementById('stTargetType').value;
    const displayName = document.getElementById('stDisplayName').value;

    if (!displayName) {
        Toast.warning('El nombre es obligatorio');
        return;
    }

    const data = {
        catalog_key: catalogKey,
        display_name: displayName,
        schedule_type: currentScheduleType,
        target_type: targetType,
    };

    // Agent
    if (targetType === 'agent') {
        const agentId = document.getElementById('stAgentId').value;
        if (!agentId) {
            Toast.warning('Selecciona un agente');
            return;
        }
        data.agent_id = parseInt(agentId);
    }

    // Schedule
    if (currentScheduleType === 'interval') {
        data.interval_seconds = parseInt(document.getElementById('stIntervalSeconds').value) || 3600;
    } else if (currentScheduleType === 'cron') {
        data.cron_minute = document.getElementById('stCronMinute').value || '*';
        data.cron_hour = document.getElementById('stCronHour').value || '*';
        data.cron_dom = document.getElementById('stCronDom').value || '*';
        data.cron_month = document.getElementById('stCronMonth').value || '*';
        data.cron_dow = document.getElementById('stCronDow').value || '*';
    } else if (currentScheduleType === 'once') {
        const runAt = document.getElementById('stRunAt').value;
        if (!runAt) {
            Toast.warning('Selecciona fecha y hora');
            return;
        }
        data.run_at = new Date(runAt).toISOString();
    }

    // Parameters
    if (selectedCatalogTask?.parameters?.length > 0) {
        const params = {};
        selectedCatalogTask.parameters.forEach(p => {
            const val = document.getElementById(`param_${p.name}`)?.value;
            if (val !== '' && val !== undefined) {
                params[p.name] = p.type === 'int' ? parseInt(val) : val;
            }
        });
        if (Object.keys(params).length > 0) data.parameters = params;
    }

    try {
        const response = await API.post(ROOT_PATH + '/api/v1/scheduled-tasks/', data);
        if (response && response.ok) {
            Toast.success('Tarea creada correctamente');
            Modal.hide('createTaskModal');
            loadScheduledTasks();
        } else {
            const err = await response?.json();
            Toast.error(err?.detail || 'Error al crear tarea');
        }
    } catch (err) {
        console.error('Error creating task:', err);
        Toast.error('Error al crear tarea');
    }
}

async function toggleScheduledTask(taskId) {
    try {
        const response = await API.request(ROOT_PATH + `/api/v1/scheduled-tasks/${taskId}/toggle`, { method: 'PATCH' });
        if (response && response.ok) {
            const task = await response.json();
            Toast.success(task.is_enabled ? 'Tarea activada' : 'Tarea desactivada');
            loadUserTasks();
        } else {
            Toast.error('Error al cambiar estado');
        }
    } catch (err) {
        console.error('Error toggling task:', err);
        Toast.error('Error al cambiar estado');
    }
}

async function runScheduledTask(taskId) {
    Confirm.show('¿Ejecutar esta tarea ahora?', async () => {
        try {
            const response = await API.post(ROOT_PATH + `/api/v1/scheduled-tasks/${taskId}/run`, {});
            if (response && response.ok) {
                Toast.success('Tarea ejecutada');
                setTimeout(() => loadScheduledTasks(), 2000);
            } else {
                const err = await response?.json();
                Toast.error(err?.detail || 'Error al ejecutar');
            }
        } catch (err) {
            console.error('Error running task:', err);
            Toast.error('Error al ejecutar tarea');
        }
    });
}

function deleteScheduledTask(taskId, name) {
    Confirm.show(`¿Eliminar la tarea "${name}"?`, async () => {
        try {
            const response = await API.delete(ROOT_PATH + `/api/v1/scheduled-tasks/${taskId}`);
            if (response && response.ok) {
                Toast.success('Tarea eliminada');
                loadScheduledTasks();
            } else {
                Toast.error('Error al eliminar');
            }
        } catch (err) {
            console.error('Error deleting task:', err);
            Toast.error('Error al eliminar tarea');
        }
    });
}

async function showScheduledTaskDetail(taskId) {
    try {
        const [taskRes, execRes] = await Promise.all([
            API.get(ROOT_PATH + `/api/v1/scheduled-tasks/${taskId}`),
            API.get(ROOT_PATH + `/api/v1/scheduled-tasks/${taskId}/executions?limit=20`),
        ]);

        if (taskRes && taskRes.ok) {
            const task = await taskRes.json();
            const detail = document.getElementById('scheduledTaskDetail');
            const scheduleLabel = getScheduleLabel(task);

            detail.innerHTML = `
                <div class="task-detail-header">
                    <div class="task-detail-icon">
                        <i class="fas ${task.target_type === 'agent' ? 'fa-desktop' : 'fa-server'}"></i>
                    </div>
                    <div class="task-detail-title">
                        <h4>${task.display_name}</h4>
                        <p>${task.catalog_key} &middot; ${task.target_type === 'agent' ? 'Agente #' + task.agent_id : 'Servidor'}</p>
                    </div>
                </div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label"><i class="fas fa-clock"></i> Programacion</span>
                        <span class="detail-value">${scheduleLabel}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label"><i class="fas fa-toggle-on"></i> Estado</span>
                        <span class="detail-value">
                            <span class="badge badge-${task.is_enabled ? 'success' : 'secondary'}">
                                ${task.is_enabled ? 'Activa' : 'Desactivada'}
                            </span>
                        </span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label"><i class="fas fa-play"></i> Ultima ejecucion</span>
                        <span class="detail-value">${task.last_run_at ? formatDate(task.last_run_at) : 'Nunca'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label"><i class="fas fa-forward"></i> Proxima ejecucion</span>
                        <span class="detail-value">${task.next_run_at ? formatDate(task.next_run_at) : '-'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label"><i class="fas fa-flag"></i> Ultimo estado</span>
                        <span class="detail-value">
                            ${task.last_status ? `<span class="badge badge-${getStatusClass(task.last_status)}">${task.last_status}</span>` : '-'}
                        </span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label"><i class="fas fa-hashtag"></i> Ejecuciones</span>
                        <span class="detail-value">${task.run_count}</span>
                    </div>
                    ${task.last_error ? `
                    <div class="detail-item full-width">
                        <span class="detail-label"><i class="fas fa-exclamation-triangle"></i> Ultimo error</span>
                        <span class="detail-value" style="color:var(--danger)">${task.last_error}</span>
                    </div>
                    ` : ''}
                    ${task.parameters ? `
                    <div class="detail-item full-width">
                        <span class="detail-label"><i class="fas fa-sliders-h"></i> Parametros</span>
                        <pre class="detail-json">${JSON.stringify(task.parameters, null, 2)}</pre>
                    </div>
                    ` : ''}
                </div>
            `;
        }

        const execDiv = document.getElementById('scheduledTaskExecutions');
        if (execRes && execRes.ok) {
            const executions = await execRes.json();
            if (executions.length > 0) {
                execDiv.innerHTML = `
                    <h4 style="font-size:0.95rem;color:var(--steel-blue-dark);margin-bottom:0.75rem;">
                        <i class="fas fa-history"></i> Historial de Ejecuciones
                    </h4>
                    <div class="executions-table-container">
                        <table class="executions-table">
                            <thead><tr><th>Tipo</th><th>Estado</th><th>Duracion</th><th>Fecha</th></tr></thead>
                            <tbody>
                                ${executions.map(e => `
                                    <tr>
                                        <td><span class="badge badge-${e.trigger_type === 'manual' ? 'info' : 'primary'}">${e.trigger_type}</span></td>
                                        <td><span class="badge badge-${getStatusClass(e.status)}"><i class="fas ${getStatusIcon(e.status)}"></i> ${e.status}</span></td>
                                        <td>${e.duration_seconds ? e.duration_seconds.toFixed(2) + 's' : '-'}</td>
                                        <td>${formatDate(e.created_at)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            } else {
                execDiv.innerHTML = '<div class="empty-state-small"><i class="fas fa-inbox"></i> Sin ejecuciones</div>';
            }
        }

        Modal.show('scheduledTaskDetailModal');
    } catch (err) {
        console.error('Error loading task detail:', err);
        Toast.error('Error al cargar detalle');
    }
}

async function showExecutionOutput(executionId) {
    // Simple: show in taskModal
    try {
        // Reuse the old TaskResult detail modal for execution output
        Toast.info('Funcion en desarrollo');
    } catch (err) {
        console.error('Error:', err);
    }
}

// Keep old loadTasks for backward compat (dashboard stat cards still use it)
async function loadTasks() {
    loadScheduledTasks();
}

// ==================== USERS ====================
async function loadUsers() {
    try {
        const state = tableState.users;
        const search = document.getElementById('userSearchInput')?.value?.trim();

        let url = ROOT_PATH + `/api/v1/users/?limit=${state.limit}&skip=${state.skip}&sort_by=${state.sortBy}&sort_order=${state.sortOrder}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;

        const response = await API.get(url);
        if (response && response.ok) {
            const data = await response.json();
            const users = data.items || [];
            state.total = data.total || 0;

            const tbody = document.getElementById('usersTableBody');
            tbody.innerHTML = users.map(u => `
                <tr>
                    <td data-label="ID"><code>${u.id}</code></td>
                    <td data-label="Usuario"><i class="fas fa-user me-2 text-muted"></i>${u.username}</td>
                    <td data-label="Email"><i class="fas fa-envelope me-2 text-muted"></i>${u.email}</td>
                    <td data-label="Nombre">${u.full_name || '-'}</td>
                    <td data-label="Admin">
                        <span class="badge ${u.is_admin ? 'badge-info' : 'badge-secondary'}">
                            <i class="fas ${u.is_admin ? 'fa-user-shield' : 'fa-user'}"></i>
                            ${u.is_admin ? 'Sí' : 'No'}
                        </span>
                    </td>
                    <td data-label="Activo">
                        <span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">
                            <i class="fas ${u.is_active ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                            ${u.is_active ? 'Sí' : 'No'}
                        </span>
                    </td>
                    <td class="actions-cell">
                        <button class="btn-icon" onclick="editUser(${u.id})" title="Editar">
                            <i class="fas fa-edit"></i>
                        </button>
                        ${u.id !== currentUser?.id ? `
                        <button class="btn-icon btn-icon-danger" onclick="deleteUser(${u.id}, '${u.username}')" title="Eliminar">
                            <i class="fas fa-trash"></i>
                        </button>
                        ` : ''}
                    </td>
                </tr>
            `).join('') || '<tr><td colspan="7" class="empty-state"><i class="fas fa-inbox"></i> No hay usuarios</td></tr>';

            renderPagination('usersPagination', 'users', loadUsers);
        }
    } catch (err) {
        console.error('Error loading users:', err);
    }
}

function openUserModal(user = null) {
    const form = document.getElementById('userForm');
    const title = document.getElementById('userModalTitle');
    const passwordGroup = document.getElementById('passwordGroup');
    const passwordInput = document.getElementById('userPassword');

    form.reset();
    document.getElementById('userId').value = '';

    if (user) {
        title.innerHTML = '<i class="fas fa-user-edit"></i> Editar Usuario';
        document.getElementById('userId').value = user.id;
        document.getElementById('userUsername').value = user.username;
        document.getElementById('userEmail').value = user.email;
        document.getElementById('userFullName').value = user.full_name || '';
        document.getElementById('userIsAdmin').checked = user.is_admin;
        document.getElementById('userIsActive').checked = user.is_active;
        passwordInput.required = false;
        passwordInput.placeholder = 'Dejar vacío para mantener';
    } else {
        title.innerHTML = '<i class="fas fa-user-plus"></i> Nuevo Usuario';
        passwordInput.required = true;
        passwordInput.placeholder = '';
        document.getElementById('userIsActive').checked = true;
    }

    Modal.show('userModal');
}

async function editUser(id) {
    try {
        const response = await API.get(ROOT_PATH + `/api/v1/users/${id}`);
        if (response && response.ok) {
            const user = await response.json();
            openUserModal(user);
        }
    } catch (err) {
        console.error('Error loading user:', err);
        Toast.error('Error al cargar usuario');
    }
}

async function saveUser(event) {
    event.preventDefault();

    const id = document.getElementById('userId').value;
    const data = {
        username: document.getElementById('userUsername').value,
        email: document.getElementById('userEmail').value,
        full_name: document.getElementById('userFullName').value || null,
        is_admin: document.getElementById('userIsAdmin').checked,
        is_active: document.getElementById('userIsActive').checked
    };

    const password = document.getElementById('userPassword').value;
    if (password) {
        data.password = password;
    }

    try {
        let response;
        if (id) {
            response = await API.put(ROOT_PATH + `/api/v1/users/${id}`, data);
        } else {
            response = await API.post(ROOT_PATH + '/api/v1/users/', data);
        }

        if (response && response.ok) {
            Toast.success(id ? 'Usuario actualizado' : 'Usuario creado');
            Modal.hide('userModal');
            loadUsers();
        } else {
            const error = await response?.json();
            Toast.error(error?.detail || 'Error al guardar usuario');
        }
    } catch (err) {
        console.error('Error saving user:', err);
        Toast.error('Error al guardar usuario');
    }
}

function deleteUser(id, username) {
    Confirm.show(`¿Eliminar el usuario "${username}"?`, async () => {
        const response = await API.delete(ROOT_PATH + `/api/v1/users/${id}`);
        if (response && response.ok) {
            Toast.success('Usuario eliminado');
            loadUsers();
        } else {
            Toast.error('Error al eliminar usuario');
        }
    });
}

// ==================== HELPERS ====================
function getSeverityClass(severity) {
    const classes = {
        critical: 'danger',
        high: 'warning',
        medium: 'warning',
        low: 'info',
        info: 'secondary'
    };
    return classes[severity] || 'secondary';
}

function getSeverityIcon(severity) {
    const icons = {
        critical: 'fa-radiation',
        high: 'fa-exclamation-triangle',
        medium: 'fa-exclamation-circle',
        low: 'fa-info-circle',
        info: 'fa-info'
    };
    return icons[severity] || 'fa-info';
}

// Detect specific service type from event extra_data (mirrors globe IP_EXTRACTION_KEYS)
function _getEventServiceType(event) {
    const extra = event.extra_data || {};
    if (extra.system === 'pibicyber-progressive-ban') return 'SSH';
    if (extra.ssh_failures?.length)     return 'SSH';
    if (extra.firewall_blocked?.length) return 'Firewall';
    if (extra.nginx_suspicious?.length) return 'Nginx';
    if (extra.sudo_failures?.length)    return 'Sudo';
    if (extra.high_risk_ips?.length)    return 'High Risk';
    return null;
}

function _renderServiceBadge(event) {
    const svc = _getEventServiceType(event);
    const config = {
        'SSH':       { cls: 'svc-ssh',       icon: 'fa-terminal',         label: 'SSH' },
        'Firewall':  { cls: 'svc-firewall',  icon: 'fa-shield-alt',       label: 'Firewall' },
        'Nginx':     { cls: 'svc-nginx',     icon: 'fa-server',           label: 'Nginx' },
        'Sudo':      { cls: 'svc-sudo',      icon: 'fa-user-shield',      label: 'Sudo' },
        'High Risk': { cls: 'svc-high-risk', icon: 'fa-skull-crossbones', label: 'Alto Riesgo' },
    };
    if (svc && config[svc]) {
        const c = config[svc];
        return `<span class="event-svc-badge ${c.cls}"><i class="fas ${c.icon}"></i> ${c.label}</span>`;
    }
    return `<span class="event-svc-badge svc-default">${_dpEsc(event.event_type)}</span>`;
}

function getStatusClass(status) {
    const classes = {
        success: 'success',
        failed: 'danger',
        running: 'info',
        timeout: 'warning'
    };
    return classes[status] || 'secondary';
}

function getStatusIcon(status) {
    const icons = {
        success: 'fa-check-circle',
        failed: 'fa-times-circle',
        running: 'fa-spinner fa-spin',
        timeout: 'fa-clock'
    };
    return icons[status] || 'fa-question-circle';
}

function getOsIcon(osType) {
    const os = (osType || '').toLowerCase();
    if (os.includes('windows')) return 'fa-brands fa-windows';
    if (os.includes('mac') || os.includes('darwin')) return 'fa-brands fa-apple';
    if (os.includes('linux')) return 'fa-brands fa-linux';
    return 'fa-desktop';
}

// ==================== SETTINGS / NOTIFICATIONS ====================

async function loadNotificationPrefs() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/users/me/notifications');
        if (response && response.ok) {
            const prefs = await response.json();
            document.getElementById('emailEnabledToggle').checked = prefs.email_enabled;
            document.getElementById('notificationEmail').value = prefs.notification_email || '';
            document.getElementById('notifyNetworkThreats').checked = prefs.notify_network_threats;
            document.getElementById('notifySystemThreats').checked = prefs.notify_system_threats;
            document.getElementById('notifyGeneralSummary').checked = prefs.notify_general_summary;
            document.getElementById('effectiveEmail').textContent = prefs.effective_email;
            updateNotificationSettingsVisibility(prefs.email_enabled);
        }
    } catch (err) {
        console.error('Error loading notification prefs:', err);
        Toast.error('Error al cargar preferencias');
    }
}

function updateNotificationSettingsVisibility(enabled) {
    const body = document.getElementById('notificationSettings');
    if (body) {
        body.style.opacity = enabled ? '1' : '0.5';
    }
}

async function saveNotificationPrefs() {
    const data = {
        email_enabled: document.getElementById('emailEnabledToggle').checked,
        notification_email: document.getElementById('notificationEmail').value || null,
        notify_network_threats: document.getElementById('notifyNetworkThreats').checked,
        notify_system_threats: document.getElementById('notifySystemThreats').checked,
        notify_general_summary: document.getElementById('notifyGeneralSummary').checked,
    };

    if (data.email_enabled && !data.notify_network_threats && !data.notify_system_threats && !data.notify_general_summary) {
        Toast.warning('Debes seleccionar al menos una categoria o desactivar las notificaciones');
        return;
    }

    try {
        const response = await API.put(ROOT_PATH + '/api/v1/users/me/notifications', data);
        if (response && response.ok) {
            const prefs = await response.json();
            document.getElementById('effectiveEmail').textContent = prefs.effective_email;
            Toast.success('Preferencias guardadas correctamente');
        } else {
            const error = await response?.json();
            Toast.error(error?.detail || 'Error al guardar preferencias');
        }
    } catch (err) {
        console.error('Error saving notification prefs:', err);
        Toast.error('Error al guardar preferencias');
    }
}

// ==================== SKELETONS & TRANSITIONS ====================

function _showDashboardSkeletons() {
    // Skeleton for lists
    const skeletonList = Array.from({length: 3}, () =>
        '<div class="skeleton" style="height:52px;border-radius:8px;margin-bottom:0.5rem"></div>'
    ).join('');
    const devicesList = document.getElementById('recentDevicesList');
    const eventsList = document.getElementById('recentEventsList');
    if (devicesList && !devicesList.querySelector('.list-item')) devicesList.innerHTML = skeletonList;
    if (eventsList && !eventsList.querySelector('.list-item')) eventsList.innerHTML = skeletonList;
}

// Page transition: brief fade when switching pages
(function initPageTransitions() {
    const origSwitch = window.switchPage;
    if (!origSwitch) return;

    // Will be patched after switchPage is defined - see below
})();

// ==================== SETTINGS PAGE ====================

let _settingsLoaded = false;

function loadSettingsPage() {
    // Load current tab content
    const activeTab = document.querySelector('.settings-nav-item.active');
    const tab = activeTab?.dataset.settings || 'account';
    switchSettingsTab(tab);
}

function switchSettingsTab(tab) {
    // Update nav
    document.querySelectorAll('.settings-nav-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`.settings-nav-item[data-settings="${tab}"]`)?.classList.add('active');

    // Update content
    document.querySelectorAll('.settings-tab').forEach(el => el.classList.remove('active'));
    const tabEl = document.getElementById('settings' + tab.charAt(0).toUpperCase() + tab.slice(1));
    if (tabEl) tabEl.classList.add('active');

    // Load data for specific tabs
    if (tab === 'account') loadAccountSettings();
    if (tab === 'notifications') loadNotificationPrefs();
    if (tab === 'about') loadAboutInfo();
    if (tab === 'appearance') syncAppearanceToggle();
    if (tab === 'agents-install') loadAgentInstallInfo();
    if (tab === 'security') loadMfaStatus();
}

async function loadAccountSettings() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/users/me');
        if (response && response.ok) {
            const user = await response.json();
            document.getElementById('accountFullName').value = user.full_name || '';
            document.getElementById('accountEmail').value = user.email || '';
        }
    } catch (err) {
        console.error('Error loading account:', err);
    }
}

async function saveAccountSettings() {
    const data = {
        full_name: document.getElementById('accountFullName').value || null,
        email: document.getElementById('accountEmail').value,
    };
    try {
        const response = await API.put(ROOT_PATH + '/api/v1/users/me', data);
        if (response && response.ok) {
            Toast.success('Cuenta actualizada');
        } else {
            const error = await response?.json();
            Toast.error(error?.detail || 'Error al guardar');
        }
    } catch (err) {
        Toast.error('Error al guardar cuenta');
    }
}

async function savePasswordChange() {
    const pw = document.getElementById('accountNewPassword').value;
    const confirm = document.getElementById('accountConfirmPassword').value;
    if (!pw || pw.length < 8) { Toast.warning('La contrasena debe tener al menos 8 caracteres'); return; }
    if (pw !== confirm) { Toast.warning('Las contrasenas no coinciden'); return; }
    try {
        const response = await API.put(ROOT_PATH + '/api/v1/users/me', { password: pw });
        if (response && response.ok) {
            Toast.success('Contrasena cambiada');
            document.getElementById('accountNewPassword').value = '';
            document.getElementById('accountConfirmPassword').value = '';
        } else {
            const error = await response?.json();
            Toast.error(error?.detail || 'Error al cambiar contrasena');
        }
    } catch (err) {
        Toast.error('Error al cambiar contrasena');
    }
}

function syncAppearanceToggle() {
    const toggle = document.getElementById('darkModeToggle');
    if (toggle) {
        toggle.checked = document.documentElement.getAttribute('data-theme') === 'dark';
    }
}

async function loadAboutInfo() {
    const container = document.getElementById('aboutInfo');
    if (!container) return;
    try {
        const [healthRes, readyRes] = await Promise.all([
            API.get(ROOT_PATH + '/api/v1/health'),
            API.get(ROOT_PATH + '/api/v1/health/ready'),
        ]);
        const health = healthRes?.ok ? await healthRes.json() : {};
        const ready = readyRes?.ok ? await readyRes.json() : {};

        const statusBadge = health.status === 'healthy'
            ? '<span class="badge badge-success"><i class="fas fa-check-circle"></i> Operativo</span>'
            : '<span class="badge badge-danger"><i class="fas fa-times-circle"></i> Con problemas</span>';

        container.innerHTML = `
            <div class="dp-row"><span class="dp-label">Servicio</span><span class="dp-value">${health.service || 'api_cyber'}</span></div>
            <div class="dp-row"><span class="dp-label">Estado API</span><span class="dp-value">${statusBadge}</span></div>
            <div class="dp-row"><span class="dp-label">Readiness</span><span class="dp-value">${ready.status || 'unknown'}</span></div>
            <hr style="margin:1rem 0;border-color:var(--grey-light)">
            <div class="dp-row"><span class="dp-label">Aplicacion</span><span class="dp-value">PibiCyber</span></div>
            <div class="dp-row"><span class="dp-label">Frontend</span><span class="dp-value">Dashboard v29</span></div>
            <div class="dp-row"><span class="dp-label">Desarrollo</span><span class="dp-value">pibico.es</span></div>
        `;
    } catch (err) {
        container.innerHTML = '<div style="color:#CB4154"><i class="fas fa-exclamation-triangle"></i> Error de conexion</div>';
    }
}

// ==================== GLOBE ====================

let _globeDataFull = null; // Store full unfiltered data
const _globeDisabledTypes = new Set(); // Disabled attack types for legend filter
let _globeListenersAttached = false;

async function loadGlobePage() {
    const hours = document.getElementById('globeTimeRange')?.value || 24;

    // Start the Three.js globe
    if (typeof window.startGlobe === 'function') {
        window.startGlobe();
    }

    // Fetch attack data
    await fetchGlobeData(hours);

    // Wire up controls (only once)
    if (_globeListenersAttached) return;
    _globeListenersAttached = true;

    document.getElementById('globeRefreshBtn')?.addEventListener('click', () => {
        const h = document.getElementById('globeTimeRange')?.value || 24;
        fetchGlobeData(h);
    });
    document.getElementById('globeTimeRange')?.addEventListener('change', (e) => {
        fetchGlobeData(e.target.value);
    });
    document.getElementById('globeOsFilter')?.addEventListener('change', () => {
        if (_globeDataFull) applyGlobeFilters();
    });
    // Multi-select attack filter: toggle dropdown open/close
    document.getElementById('globeFilterBtn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        document.getElementById('globeAttackFilter')?.classList.toggle('open');
    });
    document.addEventListener('click', () => {
        document.getElementById('globeAttackFilter')?.classList.remove('open');
    });
    // "Todos los tipos" checkbox — select / deselect all
    document.getElementById('globeFilterAll')?.addEventListener('change', (e) => {
        const ALL_TYPES = ['SSH', 'Firewall', 'Nginx', 'Sudo', 'High Risk'];
        if (e.target.checked) {
            _globeDisabledTypes.clear();
        } else {
            ALL_TYPES.forEach(t => _globeDisabledTypes.add(t));
        }
        syncLegendVisuals();
        if (_globeDataFull) applyGlobeFilters();
    });
    // Individual checkboxes → update disabled set, sync legend, apply filters
    document.querySelectorAll('#globeFilterDropdown input[type="checkbox"]:not(#globeFilterAll)').forEach(cb => {
        cb.addEventListener('change', () => {
            if (cb.checked) {
                _globeDisabledTypes.delete(cb.value);
            } else {
                _globeDisabledTypes.add(cb.value);
            }
            syncLegendVisuals();
            if (_globeDataFull) applyGlobeFilters();
        });
    });
    // Legend click handlers (simplified — checkboxes synced inside syncLegendVisuals)
    document.querySelectorAll('#globeLegend .globe-legend-item[data-type]').forEach(item => {
        item.addEventListener('click', () => {
            const type = item.dataset.type;
            if (_globeDisabledTypes.has(type)) {
                _globeDisabledTypes.delete(type);
            } else {
                _globeDisabledTypes.add(type);
            }
            syncLegendVisuals();
            if (_globeDataFull) applyGlobeFilters();
        });
    });
    document.getElementById('globePanelClose')?.addEventListener('click', () => {
        document.getElementById('globeInfoPanel')?.classList.remove('visible');
    });
}

function syncLegendVisuals() {
    const ALL_TYPES = ['SSH', 'Firewall', 'Nginx', 'Sudo', 'High Risk'];
    // Sync legend items
    document.querySelectorAll('#globeLegend .globe-legend-item[data-type]').forEach(item => {
        item.classList.toggle('globe-legend-item--disabled', _globeDisabledTypes.has(item.dataset.type));
    });
    // Sync individual checkboxes
    document.querySelectorAll('#globeFilterDropdown input[type="checkbox"]:not(#globeFilterAll)').forEach(cb => {
        cb.checked = !_globeDisabledTypes.has(cb.value);
    });
    // Sync "Todos" checkbox (indeterminate when partial)
    const allCb = document.getElementById('globeFilterAll');
    if (allCb) {
        const activeCount = ALL_TYPES.filter(t => !_globeDisabledTypes.has(t)).length;
        if (activeCount === ALL_TYPES.length) {
            allCb.checked = true;
            allCb.indeterminate = false;
        } else if (activeCount === 0) {
            allCb.checked = false;
            allCb.indeterminate = false;
        } else {
            allCb.checked = false;
            allCb.indeterminate = true;
        }
    }
    // Update button label
    _updateFilterLabel();
}

function _updateFilterLabel() {
    const label = document.getElementById('globeFilterLabel');
    if (!label) return;
    const ALL_TYPES = ['SSH', 'Firewall', 'Nginx', 'Sudo', 'High Risk'];
    const SHORT = { SSH: 'SSH', Firewall: 'Firewall', Nginx: 'Nginx', Sudo: 'Sudo', 'High Risk': 'Alto Riesgo' };
    const active = ALL_TYPES.filter(t => !_globeDisabledTypes.has(t));
    if (active.length === 0) {
        label.textContent = 'Ningún tipo';
    } else if (active.length === ALL_TYPES.length) {
        label.textContent = 'Todos los ataques';
    } else {
        label.textContent = active.map(t => SHORT[t] || t).join(', ');
    }
}

function applyGlobeFilters() {
    const os = document.getElementById('globeOsFilter')?.value || 'all';
    const data = _globeDataFull;
    if (!data) return;

    // Step 1: Filter by OS
    let filteredTargets, filteredArcs, filteredSources;

    if (os === 'all') {
        filteredTargets = data.targets;
        filteredArcs = data.arcs;
        filteredSources = data.sources;
    } else {
        filteredTargets = data.targets.filter(t => t.os_type.toLowerCase() === os);
        const targetIds = new Set(filteredTargets.map(t => t.agent_id));
        filteredArcs = data.arcs.filter(a => targetIds.has(a.target_agent_id));
        const sourceIps = new Set(filteredArcs.map(a => a.source_ip));
        filteredSources = data.sources.filter(s => sourceIps.has(s.ip));
    }

    // Step 2: Filter by attack type
    if (_globeDisabledTypes.size > 0) {
        filteredArcs = filteredArcs.filter(a => !_globeDisabledTypes.has(a.attack_type));
        // Re-filter sources: keep only those that have at least one enabled attack type
        filteredSources = filteredSources.filter(s =>
            s.attack_types && s.attack_types.some(t => !_globeDisabledTypes.has(t))
        );
    }

    // Update stats with filtered counts
    animateCounter('globeTotalAttacks', filteredArcs.reduce((sum, a) => sum + a.hit_count, 0));
    animateCounter('globeUniqueIps', filteredSources.length);
    animateCounter('globeCountries', new Set(filteredSources.map(s => s.country_code)).size);
    animateCounter('globeHighRisk', filteredSources.filter(s => s.is_high_risk).length);

    // Render filtered data (always render, even empty — globe stays visible)
    if (typeof window.renderAttackData === 'function') {
        window.renderAttackData({ sources: filteredSources, targets: filteredTargets, arcs: filteredArcs });
    }
}

async function fetchGlobeData(hours) {
    const loading = document.getElementById('globeLoading');
    const noData = document.getElementById('globeNoData');

    if (loading) loading.style.display = 'flex';
    if (noData) noData.classList.remove('visible');

    try {
        const response = await API.get(ROOT_PATH + `/api/v1/globe/attacks?hours=${hours}`);
        if (response && response.ok) {
            const data = await response.json();

            // Store full data for client-side OS filtering
            _globeDataFull = data;

            // Hide loading
            if (loading) loading.style.display = 'none';

            // Apply OS filter (updates stats + renders)
            applyGlobeFilters();
        } else {
            if (loading) loading.style.display = 'none';
            Toast.error('Error al cargar datos del globo');
        }
    } catch (err) {
        console.error('Error loading globe data:', err);
        if (loading) loading.style.display = 'none';
        Toast.error('Error al cargar datos del globo');
    }
}

// ==================== DETAIL SIDE PANEL ====================

const DetailPanel = {
    _history: [],
    _panel: null,
    _overlay: null,
    _title: null,
    _body: null,
    _backBtn: null,

    _init() {
        if (this._panel) return;
        this._panel = document.getElementById('detailPanel');
        this._overlay = document.getElementById('detailPanelOverlay');
        this._title = document.getElementById('detailPanelTitle');
        this._body = document.getElementById('detailPanelBody');
        this._backBtn = document.getElementById('detailPanelBack');
    },

    open(title, contentHTML, replace = false) {
        this._init();
        if (!replace && this._panel.classList.contains('open')) {
            // Push current state to history
            this._history.push({
                title: this._title.textContent,
                html: this._body.innerHTML,
            });
        }
        this._title.textContent = title;
        this._body.innerHTML = contentHTML;
        this._panel.classList.add('open');
        this._overlay.classList.add('visible');
        this._backBtn.style.display = this._history.length > 0 ? '' : 'none';
    },

    close() {
        this._init();
        this._panel.classList.remove('open');
        this._overlay.classList.remove('visible');
        this._history = [];
        this._backBtn.style.display = 'none';
    },

    back() {
        if (this._history.length === 0) return;
        const prev = this._history.pop();
        this._title.textContent = prev.title;
        this._body.innerHTML = prev.html;
        this._backBtn.style.display = this._history.length > 0 ? '' : 'none';
    },

    // ---- Agent Panel ----
    async showAgent(agentId) {
        this._init();
        this.open('Cargando...', '<div style="text-align:center;padding:2rem"><i class="fas fa-spinner fa-spin fa-2x" style="color:#4682B4"></i></div>');
        try {
            const [agentRes, eventsRes] = await Promise.all([
                API.get(ROOT_PATH + `/api/v1/agents/${agentId}`),
                API.get(ROOT_PATH + `/api/v1/events?agent_id=${agentId}&limit=5&sort_by=occurred_at&sort_order=desc`),
            ]);
            if (!agentRes || !agentRes.ok) { Toast.error('Error al cargar agente'); this.close(); return; }
            const agent = await agentRes.json();
            const evData = eventsRes && eventsRes.ok ? await eventsRes.json() : { items: [] };
            const events = evData.items || evData || [];

            const statusBadge = agent.is_active
                ? '<span class="dp-badge-online"><i class="fas fa-check-circle"></i> Online</span>'
                : '<span class="dp-badge-offline"><i class="fas fa-times-circle"></i> Offline</span>';

            let eventsHTML = '';
            if (events.length > 0) {
                eventsHTML = events.map(e => `
                    <div class="dp-link-item" onclick="DetailPanel.showEvent(${e.id})">
                        <div class="dp-link-icon" style="background:${_dpSeverityBg(e.severity)};color:${_dpSeverityColor(e.severity)}">
                            <i class="fas ${getSeverityIcon(e.severity)}"></i>
                        </div>
                        <div class="dp-link-info">
                            <div class="dp-link-title">${_dpEsc(e.title)}</div>
                            <div class="dp-link-meta">${e.severity} &middot; ${timeAgo(e.occurred_at)}</div>
                        </div>
                    </div>
                `).join('');
            } else {
                eventsHTML = '<div style="color:#999;font-size:0.85rem;padding:0.5rem 0">Sin eventos recientes</div>';
            }

            const html = `
                <div class="dp-section">
                    <div class="dp-panel-hero">
                        <div class="dp-panel-hero-icon dp-hero-agent">
                            <i class="fas fa-desktop" style="font-size:1.2rem"></i>
                        </div>
                        <div>
                            <div class="dp-panel-hero-title">${_dpEsc(agent.hostname)}</div>
                            <div class="dp-panel-hero-sub">${_dpEsc(agent.agent_id)} ${statusBadge}</div>
                        </div>
                    </div>
                </div>
                <div class="dp-section">
                    <div class="dp-section-title">Informacion</div>
                    <div class="dp-row"><span class="dp-label">Sistema</span><span class="dp-value"><i class="fas ${getOsIcon(agent.os_type)}"></i> ${_dpEsc(agent.os_type)} ${_dpEsc(agent.os_version || '')}</span></div>
                    <div class="dp-row"><span class="dp-label">IP</span><span class="dp-value">${_dpEsc(agent.ip_address || '-')}</span></div>
                    <div class="dp-row"><span class="dp-label">Ultima conexion</span><span class="dp-value">${timeAgo(agent.last_seen)}</span></div>
                    <div class="dp-row"><span class="dp-label">Registrado</span><span class="dp-value">${formatDate(agent.created_at)}</span></div>
                </div>
                <div class="dp-section">
                    <div class="dp-section-title">Ultimos eventos</div>
                    ${eventsHTML}
                    <div class="dp-see-all" onclick="DetailPanel.close(); switchPage('events')">
                        Ver todos los eventos <i class="fas fa-arrow-right"></i>
                    </div>
                </div>
            `;

            this.open(_dpEsc(agent.hostname), html, true);
        } catch (err) {
            console.error('DetailPanel.showAgent error:', err);
            Toast.error('Error al cargar agente');
            this.close();
        }
    },

    // ---- Event Panel ----
    async showEvent(eventId) {
        this._init();
        this.open('Cargando...', '<div style="text-align:center;padding:2rem"><i class="fas fa-spinner fa-spin fa-2x" style="color:#4682B4"></i></div>');
        try {
            const res = await API.get(ROOT_PATH + `/api/v1/events/${eventId}`);
            if (!res || !res.ok) { Toast.error('Error al cargar evento'); this.close(); return; }
            const event = await res.json();

            // Rich panel for SSH progressive ban events
            if (event.extra_data?.system === 'pibicyber-progressive-ban') {
                const html = _renderBanEventHTML(event);
                const headerTitle = _dpEsc(event.extra_data.banned_ip || event.title);
                this.open(headerTitle, html, true);
                setTimeout(() => _loadBanTimeline(event.extra_data.banned_ip, event.id), 50);
                setTimeout(() => _loadBanGeoInfo(event.extra_data.banned_ip), 100);
                return;
            }

            const sevClass = getSeverityClass(event.severity);
            const sevIcon = getSeverityIcon(event.severity);

            // Extract IPs from extra_data
            const ips = _dpExtractIPs(event.extra_data);
            let ipsHTML = '';
            if (ips.length > 0) {
                ipsHTML = `
                    <div class="dp-section">
                        <div class="dp-section-title">IPs encontradas</div>
                        <div class="dp-ip-list">
                            ${ips.slice(0, 20).map(ip => `<span class="dp-ip-badge" onclick="DetailPanel.showIP('${ip}')">${ip}</span>`).join('')}
                            ${ips.length > 20 ? `<span style="font-size:0.8rem;color:#6c757d;padding:0.2rem">+${ips.length - 20} mas</span>` : ''}
                        </div>
                    </div>`;
            }

            // Auto explanation
            let explanationHTML = '';
            if (event.extra_data?.auto_explanation) {
                explanationHTML = `
                    <div class="dp-section">
                        <div class="dp-section-title"><i class="fas fa-lightbulb"></i> Analisis</div>
                        <div class="dp-explanation-text">${_dpEsc(event.extra_data.auto_explanation)}</div>
                    </div>`;
            }

            // JSON collapsible
            let jsonHTML = '';
            if (event.extra_data) {
                jsonHTML = `
                    <div class="dp-section">
                        <details class="dp-json-toggle">
                            <summary><i class="fas fa-code"></i> Ver datos completos (JSON)</summary>
                            <pre class="dp-json-pre">${_dpEsc(JSON.stringify(event.extra_data, null, 2))}</pre>
                        </details>
                    </div>`;
            }

            const html = `
                <div class="dp-section">
                    <div class="dp-panel-hero">
                        <div class="dp-panel-hero-icon" style="background:${_dpSeverityBg(event.severity)};color:${_dpSeverityColor(event.severity)}">
                            <i class="fas ${sevIcon}"></i>
                        </div>
                        <div>
                            <div class="dp-panel-hero-title">${_dpEsc(event.title)}</div>
                            <span class="badge badge-${sevClass}" style="font-size:0.75rem">${event.severity}</span>
                        </div>
                    </div>
                </div>
                <div class="dp-section">
                    <div class="dp-section-title">Detalles</div>
                    <div class="dp-row"><span class="dp-label">Tipo</span><span class="dp-value">${_dpEsc(event.event_type)}</span></div>
                    <div class="dp-row"><span class="dp-label">Categoria</span><span class="dp-value">${_dpEsc(event.category)}</span></div>
                    <div class="dp-row"><span class="dp-label">Fecha</span><span class="dp-value">${formatDate(event.occurred_at)}</span></div>
                    <div class="dp-row">
                        <span class="dp-label">Agente</span>
                        <span class="dp-value" style="color:#4682B4;cursor:pointer" onclick="DetailPanel.showAgent(${event.agent_id})">
                            <i class="fas fa-desktop"></i> #${event.agent_id}
                        </span>
                    </div>
                </div>
                ${event.message ? `
                <div class="dp-section">
                    <div class="dp-section-title">Mensaje</div>
                    <div class="dp-message-text">${_dpEsc(event.message)}</div>
                </div>` : ''}
                ${explanationHTML}
                ${ipsHTML}
                ${jsonHTML}
            `;

            this.open(_dpEsc(event.title), html, true);
        } catch (err) {
            console.error('DetailPanel.showEvent error:', err);
            Toast.error('Error al cargar evento');
            this.close();
        }
    },

    // ---- IP Panel ----
    async showIP(ip) {
        this._init();
        this.open('Cargando...', '<div style="text-align:center;padding:2rem"><i class="fas fa-spinner fa-spin fa-2x" style="color:#4682B4"></i></div>');
        try {
            const res = await API.get(ROOT_PATH + `/api/v1/globe/ip/${encodeURIComponent(ip)}`);
            if (!res || !res.ok) { Toast.error('Error al cargar IP'); this.close(); return; }
            const data = await res.json();

            // Attack type badges
            const attackBadges = Object.entries(data.attack_types || {}).map(([type, count]) => {
                const cls = type.toLowerCase().replace(/\s+/g, '-');
                return `<span class="dp-attack-badge ${cls}">${type}: ${count}</span>`;
            }).join('');

            // Daily activity bars
            const maxCount = Math.max(...(data.daily_activity || []).map(d => d.count), 1);
            const barsHTML = (data.daily_activity || []).map(d => {
                const h = Math.max((d.count / maxCount) * 100, 4);
                return `<div class="dp-activity-bar" style="height:${h}%" title="${d.date}: ${d.count}"></div>`;
            }).join('');
            const labelsHTML = (data.daily_activity || []).map(d => {
                const parts = d.date.split('-');
                return `<span>${parts[2]}/${parts[1]}</span>`;
            }).join('');

            const countryFlag = data.country_code ? `<img src="https://flagcdn.com/16x12/${data.country_code.toLowerCase()}.png" alt="${data.country_code}" style="vertical-align:middle;margin-right:4px">` : '';

            const html = `
                <div class="dp-section">
                    <div class="dp-panel-hero">
                        <div class="dp-panel-hero-icon dp-hero-ip">
                            <i class="fas fa-network-wired" style="font-size:1.2rem"></i>
                        </div>
                        <div>
                            <div class="dp-panel-hero-title dp-ip-title">${_dpEsc(data.ip)}</div>
                            <div class="dp-panel-hero-sub">${countryFlag}${_dpEsc(data.country_name || 'Desconocido')}${data.city ? ', ' + _dpEsc(data.city) : ''}</div>
                        </div>
                    </div>
                </div>
                <div class="dp-section">
                    <div class="dp-section-title">Geolocalizacion</div>
                    <div class="dp-row"><span class="dp-label">Pais</span><span class="dp-value">${countryFlag}${_dpEsc(data.country_name || 'N/A')} (${_dpEsc(data.country_code || '??')})</span></div>
                    ${data.city ? `<div class="dp-row"><span class="dp-label">Ciudad</span><span class="dp-value">${_dpEsc(data.city)}</span></div>` : ''}
                    ${data.latitude ? `<div class="dp-row"><span class="dp-label">Coordenadas</span><span class="dp-value">${data.latitude.toFixed(2)}, ${data.longitude.toFixed(2)}</span></div>` : ''}
                </div>
                <div class="dp-section">
                    <div class="dp-section-title">Historial (30 dias)</div>
                    <div class="dp-row"><span class="dp-label">Total eventos</span><span class="dp-value" style="font-weight:700;color:#CB4154">${data.total_events}</span></div>
                    ${data.first_seen ? `<div class="dp-row"><span class="dp-label">Primera vez</span><span class="dp-value">${formatDate(data.first_seen)}</span></div>` : ''}
                    ${data.last_seen ? `<div class="dp-row"><span class="dp-label">Ultima vez</span><span class="dp-value">${formatDate(data.last_seen)}</span></div>` : ''}
                    ${attackBadges ? `<div style="margin-top:0.5rem">${attackBadges}</div>` : ''}
                </div>
                <div class="dp-section">
                    <div class="dp-section-title">Actividad (7 dias)</div>
                    <div class="dp-activity-bars">${barsHTML}</div>
                    <div class="dp-activity-labels">${labelsHTML}</div>
                </div>
            `;

            this.open(ip, html, true);
        } catch (err) {
            console.error('DetailPanel.showIP error:', err);
            Toast.error('Error al cargar IP');
            this.close();
        }
    },
};

// ---- DetailPanel helpers ----

function _dpEsc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function _dpSeverityBg(sev) {
    const map = { critical: '#fde8eb', high: '#fde8eb', medium: '#fff8e1', low: '#e3f2fd', info: '#f5f5f5' };
    return map[sev] || '#f5f5f5';
}

function _dpSeverityColor(sev) {
    const map = { critical: '#c62828', high: '#c62828', medium: '#e65100', low: '#1565c0', info: '#616161' };
    return map[sev] || '#616161';
}

function _dpExtractIPs(extraData) {
    if (!extraData) return [];
    const ips = new Set();
    const keys = ['ssh_failures', 'firewall_blocked', 'nginx_suspicious', 'sudo_failures', 'high_risk_ips', 'anomalies', 'failed_logins'];
    for (const key of keys) {
        const data = extraData[key];
        if (!data || !Array.isArray(data)) continue;
        for (const item of data) {
            if (typeof item === 'string') { ips.add(item); continue; }
            const ip = item?.ip || item?.source_ip || item?.address;
            if (ip) ips.add(ip);
        }
    }
    return [...ips];
}

// ---- Ban Event Panel renderer ----

function _renderBanEventHTML(event) {
    const ed = event.extra_data;
    const ip        = ed.banned_ip || '?';
    const level     = ed.ban_level || 0;
    const levelName = ed.ban_level_name || `L${level}`;
    const score     = ed.total_score || 0;
    const sevClass  = getSeverityClass(event.severity);

    // Level display labels
    const levelLabels = { 1: '1 hora', 2: '24 horas', 3: '7 días', 4: 'Permanente' };
    const levelDisplay = `Nivel ${level} · ${levelLabels[level] || '?'}`;

    // Score colors by level
    const scoreColors = { 0: '#64748b', 1: '#f59e0b', 2: '#f97316', 3: '#CB4154', 4: '#991b1b' };
    const scoreColor  = scoreColors[level] || '#64748b';

    // Progress bar: max scale is 500 pts
    const maxScore = 500;
    const barPct   = Math.min((score / maxScore) * 100, 100).toFixed(1);

    // Next level message
    const thresholds = [50, 100, 200, 500];
    const nextThreshold = thresholds.find(t => t > score);
    let nextMsg = '';
    if (level >= 4 || !nextThreshold) {
        nextMsg = 'Baneado permanentemente';
    } else {
        const pts = nextThreshold - score;
        const nextLvlName = { 1: 'Nivel 2 · 24h', 2: 'Nivel 3 · 7d', 3: 'Nivel 4 · permanente' }[level] || 'Nivel 4 · permanente';
        nextMsg = `+${pts} pts → ${nextLvlName}`;
    }

    // Threshold markers at 10%, 20%, 40% of 500
    const markers = [50, 100, 200].map(t =>
        `<div class="dp-score-marker" style="left:${(t / maxScore * 100).toFixed(1)}%"></div>`
    ).join('');

    // Analysis block (collapsible, closed by default)
    const analysisHTML = ed.auto_explanation ? `
        <div class="dp-section">
            <details class="dp-json-toggle">
                <summary><i class="fas fa-robot"></i> Accion sugerida</summary>
                <div class="dp-explanation-text" style="margin-top:0.4rem">${_dpEsc(ed.auto_explanation)}</div>
            </details>
        </div>` : '';

    // JSON toggle
    const jsonHTML = `
        <div class="dp-section">
            <details class="dp-json-toggle">
                <summary><i class="fas fa-code"></i> Ver datos completos (JSON)</summary>
                <pre class="dp-json-pre">${_dpEsc(JSON.stringify(ed, null, 2))}</pre>
            </details>
        </div>`;

    return `<div class="dp-ban-body">
        <!-- Ban Hero -->
        <div class="dp-section">
            <div class="dp-ban-hero">
                <div class="dp-ban-hero-ip">
                    <span class="dp-ban-icon-pulse" style="color:${scoreColor};margin-right:0.4rem">
                        <i class="fas fa-ban"></i>
                    </span>${_dpEsc(ip)}
                </div>
                <div class="dp-ban-hero-badges">
                    <span class="dp-ban-level-badge l${level}">
                        <i class="fas fa-shield-alt"></i> ${_dpEsc(levelDisplay)}
                    </span>
                    <span class="badge badge-${sevClass}">${event.severity.toUpperCase()}</span>
                </div>
            </div>
        </div>

        <!-- Score card -->
        <div class="dp-section">
            <div class="dp-section-title"><i class="fas fa-tachometer-alt"></i> Score acumulado</div>
            <div class="dp-score-card">
                <div class="dp-score-header">
                    <span class="dp-score-number" style="color:${scoreColor}">${score}</span>
                    <span class="dp-score-unit">pts</span>
                    <span class="dp-score-next">${_dpEsc(nextMsg)}</span>
                </div>
                <div class="dp-score-bar-track">
                    <div class="dp-score-bar-fill l${level}" style="width:${barPct}%"></div>
                    ${markers}
                </div>
                <div class="dp-score-thresholds">
                    <span>0</span>
                    <span>N1·50</span>
                    <span>N2·100</span>
                    <span>N3·200</span>
                    <span>N4·500</span>
                </div>
            </div>
        </div>

        <!-- Details grid -->
        <div class="dp-section">
            <div class="dp-section-title">Detalles</div>
            <div class="dp-detail-grid">
                <div class="dp-detail-card">
                    <div class="dp-detail-card-label"><i class="fas fa-terminal"></i> Servicio</div>
                    <div class="dp-detail-card-value">${_renderServiceBadge(event)}</div>
                </div>
                <div class="dp-detail-card">
                    <div class="dp-detail-card-label"><i class="fas fa-map-marker-alt"></i> Origen</div>
                    <div class="dp-detail-card-value" id="dp-ban-geo">
                        <i class="fas fa-spinner fa-spin" style="color:#94a3b8;font-size:0.75rem"></i>
                    </div>
                </div>
                <div class="dp-detail-card">
                    <div class="dp-detail-card-label"><i class="fas fa-calendar-alt"></i> Fecha</div>
                    <div class="dp-detail-card-value">${formatDate(event.occurred_at)}</div>
                </div>
                <div class="dp-detail-card">
                    <div class="dp-detail-card-label"><i class="fas fa-desktop"></i> Agente</div>
                    <div class="dp-detail-card-value">
                        <span style="color:#4682B4;cursor:pointer" onclick="DetailPanel.showAgent(${event.agent_id})">
                            <i class="fas fa-server"></i> #${event.agent_id}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        ${analysisHTML}

        <!-- Timeline (loaded async) -->
        <div class="dp-section">
            <div class="dp-section-title"><i class="fas fa-history"></i> Historial de baneos</div>
            <div id="dp-ban-timeline" style="font-size:0.8rem;color:#94a3b8;padding:0.25rem 0">
                <i class="fas fa-spinner fa-spin"></i> Cargando historial...
            </div>
        </div>

        ${jsonHTML}
    </div>`;
}

async function _loadBanGeoInfo(ip) {
    const el = document.getElementById('dp-ban-geo');
    if (!el) return;
    try {
        const res = await API.get(ROOT_PATH + `/api/v1/globe/ip/${encodeURIComponent(ip)}`);
        if (!res || !res.ok) { el.innerHTML = '<span style="color:#94a3b8">Desconocido</span>'; return; }
        const data = await res.json();
        if (data.country_name) {
            const flag = data.country_code
                ? `<img src="https://flagcdn.com/16x12/${data.country_code.toLowerCase()}.png" alt="${data.country_code}" style="vertical-align:middle;margin-right:4px;border-radius:1px">`
                : '';
            const city = data.city ? `${_dpEsc(data.city)}, ` : '';
            el.innerHTML = `${flag}${city}${_dpEsc(data.country_name)}`;
        } else {
            el.innerHTML = '<span style="color:#94a3b8">Desconocido</span>';
        }
    } catch {
        el.innerHTML = '<span style="color:#94a3b8">Desconocido</span>';
    }
}

async function _loadBanTimeline(ip, currentEventId) {
    const container = document.getElementById('dp-ban-timeline');
    if (!container) return;
    try {
        const res = await API.get(ROOT_PATH + `/api/v1/events/?search=${encodeURIComponent(ip)}&category=security&limit=30`);
        if (!res || !res.ok) {
            container.innerHTML = '<span style="font-size:0.8rem;color:#94a3b8">Sin historial disponible</span>';
            return;
        }
        const data = await res.json();
        const allItems = data.items || data || [];

        // Filter to only ban events for this exact IP
        const items = allItems
            .filter(e => e.extra_data?.system === 'pibicyber-progressive-ban' && e.extra_data?.banned_ip === ip)
            .sort((a, b) => new Date(a.occurred_at) - new Date(b.occurred_at));

        if (items.length === 0) {
            container.innerHTML = '<span style="font-size:0.8rem;color:#94a3b8">Sin historial previo</span>';
            return;
        }

        const scoreColors = { 0: '#94a3b8', 1: '#f59e0b', 2: '#f97316', 3: '#CB4154', 4: '#991b1b' };
        const levelDurations = { 1: '1 hora', 2: '24 horas', 3: '7 días', 4: 'Permanente' };

        const timelineHTML = `<div class="dp-timeline">` +
            items.map(e => {
                const lvl = e.extra_data?.ban_level || 0;
                const isCurrent = e.id === currentEventId;
                const label = `Nivel ${lvl} · ${levelDurations[lvl] || '?'}`;
                const color = isCurrent ? (scoreColors[lvl] || '#CB4154') : '';
                return `
                    <div class="dp-timeline-item">
                        <div class="dp-timeline-dot l${lvl}${isCurrent ? ' current' : ''}"></div>
                        <div class="dp-timeline-content">
                            <span class="dp-timeline-label"${color ? ` style="color:${color}"` : ''}>
                                ${_dpEsc(label)}${isCurrent ? ' <span style="font-size:0.68rem;opacity:0.75">(actual)</span>' : ''}
                            </span>
                            <span class="dp-timeline-time">${timeAgo(e.occurred_at)}</span>
                        </div>
                    </div>`;
            }).join('') +
        `</div>`;

        container.innerHTML = timelineHTML;
    } catch (err) {
        console.error('_loadBanTimeline error:', err);
        container.innerHTML = '<span style="font-size:0.8rem;color:#94a3b8">Error al cargar historial</span>';
    }
}

// ==================== THEME TOGGLE ====================

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    if (next === 'dark') {
        html.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
    } else {
        html.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
    }
    _updateThemeIcon();
}

function _updateThemeIcon() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    btn.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
    btn.title = isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
}

// Init theme icon on load
document.addEventListener('DOMContentLoaded', _updateThemeIcon);

// ---- Agent Install Tab ----

async function loadAgentInstallInfo() {
    try {
        const resp = await API.get(ROOT_PATH + '/api/v1/downloads/scripts/info');
        if (!resp || !resp.ok) return;
        const info = await resp.json();
        _renderAgentInstallInfo(info);
    } catch (err) {
        console.error('Error loading agent info:', err);
    }
}

function _renderAgentInstallInfo(info) {
    const isWindows = info.detected_os === 'windows';

    const iconEl = document.getElementById('agentOsIcon');
    const titleEl = document.getElementById('agentOsTitle');
    const descEl = document.getElementById('agentOsDesc');
    const listEl = document.getElementById('agentScriptList');
    const btnTextEl = document.getElementById('btnDownloadText');

    if (!iconEl) return;

    if (isWindows) {
        iconEl.className = 'agent-os-icon windows';
        iconEl.innerHTML = '<i class="fab fa-windows"></i>';
        titleEl.textContent = 'Windows detectado';
        descEl.textContent = 'Paquete ZIP con scripts PowerShell para Windows 10/Server 2016+';
        btnTextEl.textContent = 'Descargar Scripts Windows (.zip)';
    } else {
        iconEl.className = 'agent-os-icon linux';
        iconEl.innerHTML = '<i class="fab fa-linux"></i>';
        titleEl.textContent = 'Linux detectado';
        descEl.textContent = 'Paquete tar.gz con scripts Bash + unidades systemd para Debian/Ubuntu/RHEL';
        btnTextEl.textContent = 'Descargar Scripts Linux (.tar.gz)';
    }

    listEl.innerHTML = info.scripts.map(f =>
        `<span class="agent-script-badge"><i class="fas fa-file-code"></i>${f}</span>`
    ).join('');
}

async function downloadScripts() {
    const btn = document.getElementById('btnDownloadScripts');
    const feedback = document.getElementById('downloadFeedback');
    if (btn) { btn.disabled = true; }

    try {
        const token = localStorage.getItem('access_token');
        const resp = await fetch(ROOT_PATH + '/api/v1/downloads/scripts', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!resp.ok) {
            showToast('Error al descargar los scripts', 'error');
            return;
        }

        const contentDisposition = resp.headers.get('Content-Disposition') || '';
        const match = contentDisposition.match(/filename="([^"]+)"/);
        const filename = match ? match[1] : 'pibicyber-scripts.zip';

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        if (feedback) {
            feedback.style.display = 'inline-flex';
            setTimeout(() => { feedback.style.display = 'none'; }, 6000);
        }
    } catch (err) {
        console.error('Download error:', err);
        showToast('Error al descargar los scripts', 'error');
    } finally {
        if (btn) { btn.disabled = false; }
    }
}

// ── Help button: context-aware link to documentation ──────────────────────────
const HELP_DOCS_MAP = {
    dashboard: '#s1-intro',
    agents:    '#s2-agents',
    metrics:   '#s8-metrics',
    events:    '#s7-events',
    globe:     '#s9-globe',
    tasks:     '#s10-tasks',
    users:     '#s19-usuarios',
    settings:  '#s12-config',
};

const HELP_SETTINGS_TAB_MAP = {
    account:        '#s14-mi-cuenta',
    appearance:     '#s15-apariencia',
    notifications:  '#s16-notificaciones',
    'agents-install': '#s17-instalacion',
    security:       '#s34-pca001',
    about:          '#s18-acerca',
};

function openHelpDocs() {
    const activePage = document.querySelector('.page.active')?.id?.replace('Page', '') || 'dashboard';
    let anchor = HELP_DOCS_MAP[activePage] || '';
    if (activePage === 'settings') {
        const activeTab = document.querySelector('.settings-nav-item.active')?.dataset?.settings;
        if (activeTab && HELP_SETTINGS_TAB_MAP[activeTab]) {
            anchor = HELP_SETTINGS_TAB_MAP[activeTab];
        }
    }
    window.open('/docs/' + anchor, '_blank');
}

// ── MFA / TOTP (v43) ──────────────────────────────────────────────────────────

let _mfaOtpauthUri = null;
let _mfaQrRendered = false;

async function loadMfaStatus() {
    try {
        const response = await API.get(ROOT_PATH + '/api/v1/users/me');
        if (!response || !response.ok) return;
        const data = await response.json();
        const enabled = data.totp_enabled;
        document.getElementById('mfaBadge').className = `mfa-status-badge ${enabled ? 'active' : 'inactive'}`;
        document.getElementById('mfaBadge').innerHTML = enabled
            ? '<i class="fas fa-circle-check"></i> Activado'
            : '<i class="fas fa-circle-xmark"></i> No activado';
        document.getElementById('mfaEnableBtn').style.display = enabled ? 'none' : 'inline-flex';
        document.getElementById('mfaDisableBtn').style.display = enabled ? 'inline-flex' : 'none';
        document.getElementById('mfaRegenBtn').style.display = enabled ? 'inline-flex' : 'none';
    } catch (e) { /* silent */ }
}

async function startMfaSetup() {
    document.getElementById('mfaSetupError').textContent = '';
    document.getElementById('mfaConfirmCode').value = '';
    _mfaQrRendered = false;
    _mfaOtpauthUri = null;

    try {
        const response = await API.get(ROOT_PATH + '/api/v1/auth/mfa/setup');
        if (!response || !response.ok) { Toast.error('Error al iniciar configuración 2FA'); return; }
        const data = await response.json();
        _mfaOtpauthUri = data.otpauth_uri;

        document.getElementById('mfaSetupFlow').classList.add('visible');
        document.getElementById('mfaStepQR').style.display = 'block';
        document.getElementById('mfaStepBackup').style.display = 'none';
        document.getElementById('mfaSecretBox').textContent = data.secret;

        // Render QR code
        const qrContainer = document.getElementById('mfaQrCode');
        qrContainer.innerHTML = '';
        if (window.QRCode) {
            new QRCode(qrContainer, { text: data.otpauth_uri, width: 180, height: 180 });
            _mfaQrRendered = true;
        } else {
            // Fallback: load qrcodejs then render
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
            script.onload = () => {
                new QRCode(qrContainer, { text: data.otpauth_uri, width: 180, height: 180 });
                _mfaQrRendered = true;
            };
            document.head.appendChild(script);
        }
        document.getElementById('mfaConfirmCode').focus();
    } catch (e) {
        Toast.error('Error al iniciar configuración 2FA');
    }
}

async function confirmMfaSetup() {
    const code = document.getElementById('mfaConfirmCode').value.trim();
    const errDiv = document.getElementById('mfaSetupError');
    errDiv.textContent = '';
    if (code.length !== 6) { errDiv.textContent = 'El código debe tener 6 dígitos'; return; }

    try {
        const response = await API.post(ROOT_PATH + '/api/v1/auth/mfa/setup/confirm', { totp_code: code });
        if (!response || !response.ok) {
            const err = response ? await response.json().catch(() => ({})) : {};
            errDiv.textContent = err.detail || 'Código inválido';
            return;
        }
        const data = await response.json();
        const grid = document.getElementById('mfaBackupCodesGrid');
        grid.innerHTML = data.backup_codes.map(c => `<div class="backup-code-item">${c}</div>`).join('');
        document.getElementById('mfaStepQR').style.display = 'none';
        document.getElementById('mfaStepBackup').style.display = 'block';
    } catch (e) {
        errDiv.textContent = 'Error de conexión';
    }
}

function finishMfaSetup() {
    document.getElementById('mfaSetupFlow').classList.remove('visible');
    document.getElementById('mfaStepQR').style.display = 'none';
    document.getElementById('mfaStepBackup').style.display = 'none';
    Toast.success('2FA activado correctamente');
    loadMfaStatus();
}

function cancelMfaSetup() {
    document.getElementById('mfaSetupFlow').classList.remove('visible');
    document.getElementById('mfaStepQR').style.display = 'none';
    document.getElementById('mfaStepBackup').style.display = 'none';
}

function showMfaDisable() {
    document.getElementById('mfaDisableFlow').style.display = 'block';
    document.getElementById('mfaDisableCode').value = '';
    document.getElementById('mfaDisableError').textContent = '';
    document.getElementById('mfaDisableCode').focus();
}

function hideMfaDisable() {
    document.getElementById('mfaDisableFlow').style.display = 'none';
}

async function confirmDisableMfa() {
    const code = document.getElementById('mfaDisableCode').value.trim();
    const errDiv = document.getElementById('mfaDisableError');
    errDiv.textContent = '';
    if (code.length !== 6) { errDiv.textContent = 'El código debe tener 6 dígitos'; return; }

    try {
        const response = await API.request(ROOT_PATH + '/api/v1/auth/mfa', {
            method: 'DELETE',
            body: JSON.stringify({ totp_code: code }),
        });
        if (!response || !response.ok) {
            const err = response ? await response.json().catch(() => ({})) : {};
            errDiv.textContent = err.detail || 'Código inválido';
            return;
        }
        hideMfaDisable();
        Toast.success('2FA desactivado');
        loadMfaStatus();
    } catch (e) {
        errDiv.textContent = 'Error de conexión';
    }
}

function showMfaRegen() {
    document.getElementById('mfaRegenFlow').style.display = 'block';
    document.getElementById('mfaRegenCode').value = '';
    document.getElementById('mfaRegenError').textContent = '';
    document.getElementById('mfaRegenResult').style.display = 'none';
    document.getElementById('mfaRegenCode').focus();
}

function hideMfaRegen() {
    document.getElementById('mfaRegenFlow').style.display = 'none';
    document.getElementById('mfaRegenResult').style.display = 'none';
}

async function confirmRegenCodes() {
    const code = document.getElementById('mfaRegenCode').value.trim();
    const errDiv = document.getElementById('mfaRegenError');
    errDiv.textContent = '';
    if (code.length !== 6) { errDiv.textContent = 'El código debe tener 6 dígitos'; return; }

    try {
        const response = await API.post(ROOT_PATH + '/api/v1/auth/mfa/backup-codes/regenerate', { totp_code: code });
        if (!response || !response.ok) {
            const err = response ? await response.json().catch(() => ({})) : {};
            errDiv.textContent = err.detail || 'Código inválido';
            return;
        }
        const data = await response.json();
        const grid = document.getElementById('mfaRegenCodesGrid');
        grid.innerHTML = data.backup_codes.map(c => `<div class="backup-code-item">${c}</div>`).join('');
        document.getElementById('mfaRegenResult').style.display = 'block';
        Toast.success('Códigos de recuperación regenerados');
    } catch (e) {
        errDiv.textContent = 'Error de conexión';
    }
}
