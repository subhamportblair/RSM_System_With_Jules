const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

let ws;
let riskConfig = {};

async function fetchConfig() {
    const res = await fetch(`${API_BASE}/config`);
    riskConfig = await res.json();
    document.getElementById('max-loss-input').value = riskConfig.max_loss;
    document.getElementById('profit-target-input').value = riskConfig.profit_target;
    document.getElementById('auto-squareoff-input').checked = riskConfig.auto_squareoff;
    document.getElementById('trailing-sl-enabled').checked = riskConfig.trailing_sl_enabled;
    document.getElementById('trail-distance-input').value = riskConfig.trail_distance;
    document.getElementById('auto-exit-time-input').value = riskConfig.auto_exit_time;

    document.getElementById('max-loss-label').innerText = `Max Loss: ₹${riskConfig.max_loss.toLocaleString()}`;
    document.getElementById('profit-target-label').innerText = `Target: ₹${riskConfig.profit_target.toLocaleString()}`;
}

async function saveConfig() {
    const updated = {
        max_loss: parseFloat(document.getElementById('max-loss-input').value),
        profit_target: parseFloat(document.getElementById('profit-target-input').value),
        auto_squareoff: document.getElementById('auto-squareoff-input').checked,
        check_interval: riskConfig.check_interval || 3,
        trailing_sl_enabled: document.getElementById('trailing-sl-enabled').checked,
        trail_distance: parseFloat(document.getElementById('trail-distance-input').value),
        auto_exit_time: document.getElementById('auto-exit-time-input').value
    };

    await fetch(`${API_BASE}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
    });
    alert("Configuration Saved!");
    fetchConfig();
}

function connectWebSocket() {
    ws = new WebSocket(`${WS_BASE}/ws/pnl`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.config) {
            riskConfig = data.config;
            document.getElementById('max-loss-label').innerText = `Max Loss: ₹${riskConfig.max_loss.toLocaleString()}`;
            document.getElementById('profit-target-label').innerText = `Target: ₹${riskConfig.profit_target.toLocaleString()}`;
        }
        updateDashboard(data);
    };

    ws.onclose = () => {
        setTimeout(connectWebSocket, 2000);
    };
}

let currentSymbolRisks = {};

function updateDashboard(data) {
    const { pnl, status, positions, symbol_risks } = data;
    currentSymbolRisks = symbol_risks || {};

    // Status
    const statusEl = document.getElementById('app-status');
    statusEl.innerText = `Status: ${status}`;
    statusEl.className = `badge ${status.toLowerCase()}`;

    const pauseResumeBtn = document.getElementById('pause-resume');
    if (status === 'HALTED') {
        pauseResumeBtn.innerText = '▶ Resume Monitoring';
    } else {
        pauseResumeBtn.innerText = '⏸ Pause Monitoring';
    }

    // PnL Summary
    const totalPnlEl = document.getElementById('total-pnl');
    totalPnlEl.innerText = `₹ ${pnl.total_pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    totalPnlEl.className = `pnl-value ${pnl.total_pnl >= 0 ? 'profit' : 'loss'}`;

    document.getElementById('realized-pnl').innerText = `₹ ${pnl.realized.toLocaleString()}`;
    document.getElementById('unrealized-pnl').innerText = `₹ ${pnl.unrealized.toLocaleString()}`;

    // Progress Bar
    const range = riskConfig.profit_target - riskConfig.max_loss;
    const progress = ((pnl.total_pnl - riskConfig.max_loss) / range) * 100;
    const bar = document.getElementById('pnl-progress');
    bar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
    if (progress < 20) bar.style.backgroundColor = 'var(--danger-color)';
    else if (progress > 80) bar.style.backgroundColor = 'var(--success-color)';
    else bar.style.backgroundColor = 'var(--primary-color)';

    // Breakdown pills
    document.getElementById('type-breakdown').innerHTML = `
        <div class="pill ce-pill">CE: ₹${pnl.by_type.CE.toLocaleString()}</div>
        <div class="pill pe-pill">PE: ₹${pnl.by_type.PE.toLocaleString()}</div>
        <div class="pill fut-pill">FUT: ₹${pnl.by_type.FUT.toLocaleString()}</div>
    `;

    document.getElementById('exchange-breakdown').innerHTML = `
        <div class="pill nfo-pill">NFO: ₹${pnl.by_exchange.NFO.toLocaleString()}</div>
        <div class="pill bfo-pill">BFO: ₹${pnl.by_exchange.BFO.toLocaleString()}</div>
    `;

    // Tables
    updateTables(positions);
}

function updateTables(positions) {
    const groups = {
        'options-mis': [],
        'options-nrml': [],
        'futures-mis': [],
        'futures-nrml': []
    };

    positions.forEach(p => {
        const isOpt = p.tradingsymbol.endswith ? p.tradingsymbol.endsWith("CE") || p.tradingsymbol.endsWith("PE") : (p.tradingsymbol.slice(-2) === "CE" || p.tradingsymbol.slice(-2) === "PE");
        const type = isOpt ? 'options' : 'futures';
        const product = p.product.toLowerCase();
        const key = `${type}-${product}`;
        if (groups[key]) groups[key].push(p);
    });

    Object.keys(groups).forEach(key => {
        const tbody = document.querySelector(`#table-${key} tbody`);
        if (!tbody) return;

        tbody.innerHTML = groups[key].map(p => {
            const pnl = (p.last_price - p.average_price) * p.quantity + p.realised;
            const type = (p.tradingsymbol.slice(-2) === "CE") ? "CE" : ((p.tradingsymbol.slice(-2) === "PE") ? "PE" : "FUT");
            const risk = currentSymbolRisks[p.tradingsymbol] || { sl: '', target: '' };

            return `
                <tr>
                    <td>${p.tradingsymbol}</td>
                    <td><span class="exchange-badge exchange-${p.exchange.toLowerCase()}">${p.exchange}</span></td>
                    <td>${type}</td>
                    <td>${p.quantity}</td>
                    <td>${p.average_price.toFixed(2)}</td>
                    <td>${p.last_price.toFixed(2)}</td>
                    <td class="${pnl >= 0 ? 'profit' : 'loss'}">${pnl.toFixed(2)}</td>
                    <td>
                        <input type="number" placeholder="SL" value="${risk.sl || ''}"
                            onchange="updateSymbolRisk('${p.tradingsymbol}', this.value, null)" style="width: 60px">
                        <input type="number" placeholder="Tgt" value="${risk.target || ''}"
                            onchange="updateSymbolRisk('${p.tradingsymbol}', null, this.value)" style="width: 60px">
                    </td>
                </tr>
            `;
        }).join('');
    });
}

async function updateSymbolRisk(symbol, sl, target) {
    const existing = currentSymbolRisks[symbol] || { sl: null, target: null };
    const payload = {
        tradingsymbol: symbol,
        stop_loss: sl !== null ? (sl === '' ? null : parseFloat(sl)) : existing.sl,
        target: target !== null ? (target === '' ? null : parseFloat(target)) : existing.target
    };

    await fetch(`${API_BASE}/config/symbols`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
}

function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    document.getElementById(tabId).classList.add('active');
    event.currentTarget.classList.add('active');
}

document.getElementById('save-config').onclick = saveConfig;

document.getElementById('square-off-all').onclick = async () => {
    if (confirm("Are you sure you want to square off ALL F&O positions?")) {
        await fetch(`${API_BASE}/squareoff/all`, { method: 'POST' });
        alert("Square-off orders placed!");
    }
};

document.getElementById('pause-resume').onclick = async () => {
    const statusEl = document.getElementById('app-status');
    const isHalted = statusEl.innerText.includes('HALTED');
    const endpoint = isHalted ? 'resume' : 'pause';
    await fetch(`${API_BASE}/status/${endpoint}`, { method: 'POST' });
};

document.getElementById('test-telegram').onclick = async () => {
    await fetch(`${API_BASE}/telegram/test`, { method: 'POST' });
    alert("Test message sent!");
};

document.getElementById('login-kite').onclick = async () => {
    const res = await fetch(`${API_BASE}/auth/login`);
    const data = await res.json();
    window.open(data.login_url, '_blank');
};

document.getElementById('system-date').innerText = new Date().toLocaleDateString();

fetchConfig();
connectWebSocket();
