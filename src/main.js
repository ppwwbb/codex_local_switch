// ===== 配置 =====
const API_BASE = 'http://127.0.0.1:8318';  // Python 后端 API 端口

// ===== 状态 =====
let providers = [];
let currentProviderId = null;
let proxyRunning = false;
let logEntries = [];
let stats = { total: 0, success: 0, failed: 0, today: 0 };

// ===== DOM 元素缓存 =====
const els = {};

function $(id) {
    return document.getElementById(id);
}

// ===== Tab 切换 =====
function initTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            $(target + '-tab').classList.add('active');
        });
    });
}

// ===== API 调用 =====
async function api(path, opts = {}) {
    const url = API_BASE + path;
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
    }
    return res.json().catch(() => ({}));
}

// ===== 预设 Provider =====
const PRESET_PROVIDERS = [
    { name: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat', icon: 'D', color: '#4A90D9' },
    { name: 'Kimi (月之暗面)', base_url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k', icon: 'K', color: '#1A1A1A' },
    { name: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o', icon: 'O', color: '#10A37F' },
    { name: '智谱 GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4', icon: 'G', color: '#0066FF' },
];

let editingProviderId = null;

// ===== Provider 管理 =====
async function loadProviders() {
    try {
        const data = await api('/api/providers');
        providers = data.providers || [];
        currentProviderId = data.current_id || null;
        renderProviders();
        renderPresetProviders();
    } catch (e) {
        showError('加载 Provider 失败: ' + e.message);
    }
}

function renderProviders() {
    const list = $('providersList');
    list.innerHTML = '';

    if (providers.length === 0) {
        list.innerHTML = '<div class="log-empty" style="padding:30px">暂无 Provider，点击下方预设添加</div>';
        return;
    }

    providers.forEach(p => {
        const isDefault = p.id === currentProviderId;
        const card = document.createElement('div');
        card.className = 'provider-card' + (isDefault ? ' active' : '');
        card.innerHTML = `
            <div class="provider-drag">≡</div>
            <div class="provider-icon" style="background:${p.color || 'var(--primary)'}">${(p.name || '?')[0].toUpperCase()}</div>
            <div class="provider-info">
                <div class="provider-name">${escapeHtml(p.name || '未命名')}</div>
                <div class="provider-url">${escapeHtml(p.base_url || '')}</div>
            </div>
            <div class="provider-actions">
                <button class="btn-enable" data-action="enable" data-id="${p.id}">
                    ${isDefault ? '▶ 默认' : '启用'}
                </button>
                <button class="action-icon" data-action="speed" data-id="${p.id}" title="测速">⚡</button>
                <button class="action-icon" data-action="edit" data-id="${p.id}" title="修改">✎</button>
                <button class="action-icon" data-action="copy" data-id="${p.id}" title="复制">⎘</button>
                <button class="action-icon" data-action="delete" data-id="${p.id}" title="删除">🗑</button>
            </div>
        `;
        list.appendChild(card);
    });

    // 绑定操作按钮事件
    list.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const action = btn.dataset.action;
            const id = btn.dataset.id;
            handleProviderAction(action, id);
        });
    });
}

function renderPresetProviders() {
    const list = $('presetProvidersList');
    list.innerHTML = '';

    PRESET_PROVIDERS.forEach(preset => {
        const card = document.createElement('div');
        card.className = 'preset-card';
        card.innerHTML = `
            <div class="preset-icon" style="color:${preset.color}; background:${preset.color}15">${preset.icon}</div>
            <div class="provider-info">
                <div class="provider-name">${escapeHtml(preset.name)}</div>
                <div class="provider-url">${escapeHtml(preset.base_url)}</div>
            </div>
            <button class="btn-add-preset" data-name="${escapeHtml(preset.name)}" data-url="${escapeHtml(preset.base_url)}" data-model="${escapeHtml(preset.model)}">
                + 添加提供商
            </button>
        `;
        list.appendChild(card);
    });

    list.querySelectorAll('.btn-add-preset').forEach(btn => {
        btn.addEventListener('click', async () => {
            try {
                const data = await api('/api/providers', { method: 'POST' });
                const id = data.id;
                await api('/api/providers/' + id, {
                    method: 'PUT',
                    body: JSON.stringify({
                        name: btn.dataset.name,
                        base_url: btn.dataset.url,
                        api_key: '',
                        model: btn.dataset.model,
                    }),
                });
                await loadProviders();
                openModal(id);
            } catch (e) {
                alert('添加失败: ' + e.message);
            }
        });
    });
}

async function handleProviderAction(action, id) {
    const p = providers.find(x => x.id === id);
    if (!p) return;

    switch (action) {
        case 'enable':
            try {
                await api('/api/config', {
                    method: 'POST',
                    body: JSON.stringify({ current_provider_id: id }),
                });
                currentProviderId = id;
                renderProviders();
                showFooter(`已切换默认 Provider: ${p.name}`);
            } catch (e) {
                // API 可能不存在，直接前端切换
                currentProviderId = id;
                renderProviders();
            }
            break;
        case 'speed':
            alert('测速功能开发中...');
            break;
        case 'edit':
            openModal(id);
            break;
        case 'copy':
            try {
                const data = await api('/api/providers', { method: 'POST' });
                const newId = data.id;
                await api('/api/providers/' + newId, {
                    method: 'PUT',
                    body: JSON.stringify({
                        name: p.name + ' (复制)',
                        base_url: p.base_url,
                        api_key: p.api_key,
                        model: p.model,
                    }),
                });
                await loadProviders();
                showFooter('Provider 已复制');
            } catch (e) {
                alert('复制失败: ' + e.message);
            }
            break;
        case 'delete':
            if (!confirm(`确定要删除 Provider "${p.name}" 吗？`)) return;
            try {
                await api('/api/providers/' + id, { method: 'DELETE' });
                await loadProviders();
                showFooter('Provider 已删除');
            } catch (e) {
                alert('删除失败: ' + e.message);
            }
            break;
    }
}

// ===== 模态框 =====
function openModal(id) {
    editingProviderId = id;
    const p = providers.find(x => x.id === id);
    if (!p) return;
    $('mName').value = p.name || '';
    $('mUrl').value = p.base_url || '';
    $('mKey').value = p.api_key || '';
    $('mModel').value = p.model || '';
    $('modalTitle').textContent = '编辑 Provider';
    $('providerModal').style.display = 'flex';
}

function closeModal() {
    editingProviderId = null;
    $('providerModal').style.display = 'none';
}

async function saveModal(e) {
    e.preventDefault();
    if (!editingProviderId) return;
    const body = {
        name: $('mName').value.trim(),
        base_url: $('mUrl').value.trim(),
        api_key: $('mKey').value.trim(),
        model: $('mModel').value.trim(),
    };
    try {
        await api('/api/providers/' + editingProviderId, {
            method: 'PUT',
            body: JSON.stringify(body),
        });
        closeModal();
        await loadProviders();
        showFooter('配置已保存');
    } catch (err) {
        alert('保存失败: ' + err.message);
    }
}

// ===== 代理控制 =====
async function loadProxyStatus() {
    try {
        const data = await api('/api/proxy/status');
        setProxyRunning(data.running);
        if (data.host) $('listenHost').value = data.host;
        if (data.port) $('proxyPort').value = data.port;
    } catch (e) {
        // 后端可能还没启动
    }
}

async function startProxy() {
    try {
        const port = parseInt($('proxyPort').value) || 8317;
        await api('/api/proxy/start', {
            method: 'POST',
            body: JSON.stringify({ port }),
        });
        setProxyRunning(true);
        log('INFO', `代理启动成功，监听 http://127.0.0.1:${port}`);
        showFooter('代理已启动');
    } catch (e) {
        alert('启动失败: ' + e.message);
    }
}

async function stopProxy() {
    try {
        await api('/api/proxy/stop', { method: 'POST' });
        setProxyRunning(false);
        log('INFO', '代理已停止');
        showFooter('代理已停止');
    } catch (e) {
        alert('停止失败: ' + e.message);
    }
}

function setProxyRunning(running) {
    proxyRunning = running;
    const dot = $('statusDot');
    const text = $('statusText');
    const startBtn = $('startProxyBtn');
    const stopBtn = $('stopProxyBtn');
    const portInput = $('proxyPort');

    if (running) {
        dot.classList.add('running');
        text.classList.add('running');
        text.textContent = '运行中';
        startBtn.style.display = 'none';
        stopBtn.style.display = 'inline-flex';
        portInput.disabled = true;
    } else {
        dot.classList.remove('running');
        text.classList.remove('running');
        text.textContent = '已停止';
        startBtn.style.display = 'inline-flex';
        stopBtn.style.display = 'none';
        portInput.disabled = false;
    }
}

// ===== 日志 =====
function log(level, message) {
    const container = $('logContainer');
    const empty = container.querySelector('.log-empty');
    if (empty) empty.remove();

    const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-timestamp">${timestamp}</span>
        <span class="log-level log-level-${level.toLowerCase()}">[${level}]</span>
        <span class="log-message">${escapeHtml(message)}</span>
    `;
    container.appendChild(entry);

    if ($('autoScroll').checked) {
        container.scrollTop = container.scrollHeight;
    }

    // 过滤
    const minLevel = $('logLevel').value;
    const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
    if (levels.indexOf(level) < levels.indexOf(minLevel)) {
        entry.style.display = 'none';
    }
}

function clearLogs() {
    $('logContainer').innerHTML = '<div class="log-empty">暂无日志</div>';
}

function filterLogs() {
    const minLevel = $('logLevel').value;
    const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
    const entries = $('logContainer').querySelectorAll('.log-entry');
    entries.forEach(e => {
        const levelMatch = e.querySelector('.log-level');
        if (!levelMatch) return;
        const level = levelMatch.textContent.replace(/[\[\]]/g, '');
        e.style.display = levels.indexOf(level) < levels.indexOf(minLevel) ? 'none' : '';
    });
}

// ===== 轮询日志 =====
async function pollLogs() {
    try {
        const data = await api('/api/logs');
        if (data.entries) {
            data.entries.forEach(e => log(e.level, e.message));
        }
        // 更新统计
        if (data.stats) {
            $('statTotal').textContent = data.stats.total || 0;
            $('statSuccess').textContent = data.stats.success || 0;
            $('statFailed').textContent = data.stats.failed || 0;
            $('statToday').textContent = data.stats.today || 0;
        }
    } catch (e) {
        // 后端可能还没启动，静默忽略
    }
}

// ===== 工具函数 =====
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showFooter(msg) {
    $('footerStatus').textContent = msg;
    setTimeout(() => {
        $('footerStatus').textContent = '就绪';
    }, 3000);
}

function showError(msg) {
    console.error(msg);
    log('ERROR', msg);
}

// ===== 初始化 =====
function init() {
    initTabs();

    // 模态框事件
    $('modalForm').addEventListener('submit', saveModal);
    $('modalClose').addEventListener('click', closeModal);
    $('modalCancel').addEventListener('click', closeModal);
    $('mToggleKey').addEventListener('click', () => {
        const input = $('mKey');
        const btn = $('mToggleKey');
        if (input.type === 'password') {
            input.type = 'text';
            btn.textContent = '隐藏';
        } else {
            input.type = 'password';
            btn.textContent = '显示';
        }
    });
    $('providerModal').addEventListener('click', (e) => {
        if (e.target === $('providerModal')) closeModal();
    });

    // 代理事件
    $('startProxyBtn').addEventListener('click', startProxy);
    $('stopProxyBtn').addEventListener('click', stopProxy);

    // 日志事件
    $('clearLogBtn').addEventListener('click', clearLogs);
    $('logLevel').addEventListener('change', filterLogs);

    // 加载数据
    loadProviders();
    loadProxyStatus();

    // 轮询日志和状态
    setInterval(pollLogs, 1000);
    setInterval(loadProxyStatus, 2000);
}

document.addEventListener('DOMContentLoaded', init);
