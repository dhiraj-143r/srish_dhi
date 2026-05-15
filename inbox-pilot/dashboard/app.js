/**
 * InboxPilot — Dashboard JS (AgentMail-style)
 */

let ws = null;
const feedItems = [];
const MAX_FEED = 80;
let chartBars = [];

// ─── WebSocket ───────────────────────────────
function connectWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.onopen = () => {
        updateWS(true);
        setInterval(() => { if (ws?.readyState === WebSocket.OPEN) ws.send('ping'); }, 30000);
    };
    ws.onmessage = (e) => {
        try {
            const d = JSON.parse(e.data);
            if (d.type !== 'pong') handleMsg(d);
        } catch(err) {}
    };
    ws.onclose = () => { updateWS(false); setTimeout(connectWebSocket, 3000); };
    ws.onerror = () => updateWS(false);
}

function updateWS(connected) {
    const dot = document.getElementById('ws-indicator');
    const txt = document.getElementById('ws-status-text');
    if (connected) {
        dot.className = 'status-indicator connected';
        txt.textContent = 'Connected';
    } else {
        dot.className = 'status-indicator';
        txt.textContent = 'Reconnecting...';
    }
}

// ─── Handle Messages ─────────────────────────
function handleMsg(data) {
    switch (data.type) {
        case 'webhook_received':
            addThread('📨', 'Webhook', 'New email received', 'incoming...', '');
            addChartBar('blue');
            break;
        case 'processing_started':
            addThread('⚙️', 'Pipeline', 'Processing started', data.message_id?.slice(0,20)+'...', '');
            break;
        case 'processing_completed':
            const ue = {high:'🔴',medium:'🟡',low:'⚪'}[data.urgency]||'⚪';
            addThread(ue, 'Triage', data.subject||'', `${data.urgency} · ${data.category} · → ${data.action_type}`, '');
            if (data.triage_reasoning) {
                addThread('💭', 'Reasoning', '', data.triage_reasoning.slice(0,100)+'...', '');
            }
            if (data.draft_reply) {
                addThread('✍️', 'Drafter', data.draft_subject||'Re: ...', data.draft_reply.slice(0,80)+'...', '');
            }
            addThread('✅', 'Action', `${data.action_type} completed`, `${Math.round(data.processing_time_ms||0)}ms`, '');

            addChartBar(data.urgency === 'high' ? 'urgent' : 'success');
            addEmailRow(data);
            refreshStats();
            break;
        case 'processing_failed':
            addThread('❌', 'Error', '', data.error||'Unknown error', '');
            addChartBar('urgent');
            break;
    }
}

// ─── Activity Feed (Thread style) ────────────
function addThread(flag, agent, subject, preview, time) {
    const feed = document.getElementById('live-feed');
    const empty = feed.querySelector('.thread-empty');
    if (empty) empty.remove();

    const now = new Date();
    const ts = time || now.toLocaleTimeString('en-US',{hour12:false,hour:'2-digit',minute:'2-digit'});

    const item = document.createElement('div');
    item.className = 'thread-item';
    item.innerHTML = `
        <svg class="thread-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        <svg class="thread-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
        <span class="thread-agent">${esc(agent || 'AgentMail')}</span>
        <span class="thread-message">
            ${subject ? `<span class="subject">${esc(subject)}</span>` : ''}
            <span class="preview"> - ${esc(preview)}</span>
        </span>
        <span class="thread-time">${ts}</span>
    `;
    feed.insertBefore(item, feed.firstChild);

    feedItems.push(item);
    if (feedItems.length > MAX_FEED) feedItems.shift()?.remove();
}

function clearFeed() {
    const feed = document.getElementById('live-feed');
    feed.innerHTML = '<div class="thread-empty"><p>Feed cleared</p></div>';
    feedItems.length = 0;
}

// ─── Chart ───────────────────────────────────
const TOTAL_COLS = 144; // 24 hours * 6 (every 10 min)

function attachTooltip(col, bar, timestamp) {
    col.addEventListener('mouseenter', (e) => {
        const tt = document.getElementById('chart-tooltip');
        const band = document.getElementById('chart-hover-band');
        if (!tt) return;
        
        // Data
        const h = parseInt(bar.style.height) || 0;
        const hasData = bar.classList.contains('has-data');
        
        document.getElementById('tt-processed').textContent = hasData ? Math.floor(h / 10) + 1 : 0;
        document.getElementById('tt-replied').textContent = hasData ? Math.floor(h / 20) : 0;
        document.getElementById('tt-tasks').textContent = 0;
        document.getElementById('tt-urgent').textContent = 0;
        
        // Time
        document.getElementById('tt-time').textContent = timestamp;

        // Smart positioning — avoid clipping at edges
        const colRect = col.getBoundingClientRect();
        const containerRect = document.querySelector('.activity-chart').getBoundingClientRect();
        const ttWidth = 170;
        const ttHeight = 130;
        
        // Horizontal: center by default, but shift if near edges
        let leftPos = colRect.left - containerRect.left + (colRect.width / 2);
        if (leftPos < ttWidth / 2 + 8) {
            // Near left edge → anchor to left
            tt.style.left = '8px';
            tt.style.transform = 'none';
        } else if (leftPos > containerRect.width - ttWidth / 2 - 8) {
            // Near right edge → anchor to right
            tt.style.left = 'auto';
            tt.style.right = '8px';
            tt.style.transform = 'none';
        } else {
            // Center normally
            tt.style.left = leftPos + 'px';
            tt.style.right = 'auto';
            tt.style.transform = 'translateX(-50%)';
        }
        
        // Vertical: show above chart normally, below if near top
        const chartTop = containerRect.top;
        const spaceAbove = colRect.top - chartTop;
        if (spaceAbove < ttHeight + 20) {
            // Not enough space above — show below the bar
            tt.style.bottom = 'auto';
            tt.style.top = (colRect.bottom - containerRect.top + 8) + 'px';
        } else {
            // Show above
            tt.style.top = 'auto';
            tt.style.bottom = (containerRect.bottom - colRect.top + 8) + 'px';
        }
        
        tt.classList.add('active');
        
        if (band) {
            const tlRect = document.getElementById('chart-timeline').getBoundingClientRect();
            band.style.left = (colRect.left - tlRect.left + (colRect.width / 2)) + 'px';
            band.classList.add('active');
        }
    });
    col.addEventListener('mouseleave', () => {
        const tt = document.getElementById('chart-tooltip');
        const band = document.getElementById('chart-hover-band');
        if (tt) {
            tt.classList.remove('active');
            // Reset positioning for next hover
            tt.style.right = 'auto';
            tt.style.top = 'auto';
        }
        if (band) band.classList.remove('active');
    });
}

function addChartBar(type) {
    const chart = document.getElementById('chart-timeline');
    const col = document.createElement('div');
    col.className = 'chart-col';
    
    const bar = document.createElement('div');
    bar.className = 'chart-bar has-data';
    const h = 20 + Math.random() * 100;
    bar.style.height = '0px';
    
    col.appendChild(bar);
    chart.appendChild(col);
    
    requestAnimationFrame(() => { bar.style.height = h + 'px'; });
    
    const now = new Date();
    const tsStr = now.toLocaleString('en-US', {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'});
    attachTooltip(col, bar, tsStr);

    chartBars.push(col);
    if (chartBars.length > TOTAL_COLS) chartBars.shift()?.remove();
}

// Fill initial chart — delegates to rebuildChart with default range
function initChart() {
    rebuildChart('24 hours');
}

// ─── Email Table ─────────────────────────────
function addEmailRow(data) {
    const tbody = document.getElementById('emails-tbody');
    const empty = tbody.querySelector('.empty-row');
    if (empty) empty.remove();

    // Use the email's actual created_at time, not current time
    let ts;
    if (data.created_at) {
        const emailDate = new Date(data.created_at.replace(' ', 'T') + (data.created_at.includes('+') || data.created_at.includes('Z') ? '' : 'Z'));
        ts = emailDate.toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit'});
    } else {
        ts = new Date().toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit'});
    }
    const row = document.createElement('tr');
    const uClass = `urgency-${data.urgency||'low'}`;

    row.innerHTML = `
        <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})">${esc((data.sender||'').replace(/[<>]/g,'').slice(0,30))}</td>
        <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})">${esc((data.subject||'').slice(0,50))}</td>
        <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})"><span class="urgency-pill ${uClass}">${(data.urgency||'low').toUpperCase()}</span></td>
        <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})"><span class="action-pill">${data.action_type||'-'}</span></td>
        <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})">Processed</td>
        <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})" class="time-cell">${ts}</td>
        <td style="position: relative;">
            <button class="row-menu-btn" onclick="toggleRowMenu(this, event)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
            </button>
            <div class="row-dropdown-menu">
                <div class="row-dropdown-item">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    Update Display Name
                </div>
                <div class="row-dropdown-item delete-item">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                    Delete
                </div>
            </div>
        </td>
    `;
    tbody.insertBefore(row, tbody.firstChild);
}

function toggleRowMenu(btn, e) {
    e.stopPropagation();
    // Close all other menus first
    document.querySelectorAll('.row-dropdown-menu.active').forEach(m => {
        if (m !== btn.nextElementSibling) m.classList.remove('active');
    });
    const menu = btn.nextElementSibling;
    menu.classList.toggle('active');
}

// Close row dropdowns when clicking outside
document.addEventListener('click', () => {
    document.querySelectorAll('.row-dropdown-menu.active').forEach(m => m.classList.remove('active'));
});

// ─── Modal ───────────────────────────────────
function showReasoning(data) {
    const body = document.getElementById('reasoning-body');
    body.innerHTML = `
        <div class="reasoning-section">
            <h3>EMAIL</h3>
            <p><strong>From:</strong> ${esc(data.sender||'N/A')}<br><strong>Subject:</strong> ${esc(data.subject||'N/A')}</p>
        </div>
        <div class="reasoning-section">
            <h3>TRIAGE DECISION</h3>
            <p><strong>Urgency:</strong> <span class="urgency-pill urgency-${data.urgency}">${(data.urgency||'N/A').toUpperCase()}</span> · <strong>Category:</strong> ${data.category||'N/A'} · <strong>Action:</strong> ${data.action_type||'N/A'}</p>
        </div>
        <div class="reasoning-section">
            <h3>CHAIN-OF-THOUGHT REASONING</h3>
            <pre>${esc(data.triage_reasoning||'No reasoning available')}</pre>
        </div>
        ${data.draft_reply ? `<div class="reasoning-section"><h3>DRAFTED REPLY</h3><pre>${esc(data.draft_reply)}</pre></div>` : ''}
        <div class="reasoning-section">
            <h3>EXECUTION</h3>
            <p><strong>Status:</strong> ${data.action_status||'N/A'} · <strong>Time:</strong> ${Math.round(data.processing_time_ms||0)}ms</p>
        </div>
    `;
    document.getElementById('reasoning-modal').classList.add('active');
}

function closeReasoningModal() { document.getElementById('reasoning-modal').classList.remove('active'); }
function closeModal(e) { if (e.target === e.currentTarget) closeReasoningModal(); }

// ─── API ─────────────────────────────────────
async function refreshStats() {
    try {
        const r = await fetch('/api/stats');
        const s = await r.json();
        document.getElementById('stat-processed').textContent = s.total_processed||0;
        document.getElementById('stat-urgent').textContent = s.urgent_count||0;
        document.getElementById('stat-replied').textContent = s.auto_replied||0;
        document.getElementById('stat-tasks').textContent = s.tasks_created||0;
        document.getElementById('stat-archived').textContent = s.archived||0;
        if (s.inbox_email && s.inbox_email !== 'N/A')
            document.getElementById('agent-email').textContent = s.inbox_email;

        const total = s.total_processed||0;
        const success = (s.auto_replied||0) + (s.tasks_created||0) + (s.archived||0);
        document.getElementById('metric-rate').textContent = total ? (success/total*100).toFixed(1)+'%' : '0.0%';
    } catch(e) {}
}

async function refreshEmails() {
    try {
        const r = await fetch('/api/emails');
        const d = await r.json();
        const tbody = document.getElementById('emails-tbody');
        tbody.innerHTML = '';
        if (!d.emails?.length) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No emails processed yet</td></tr>';
            return;
        }
        // API returns newest first — append in order so newest stays on top
        d.emails.forEach(data => {
            let ts;
            if (data.created_at) {
                const emailDate = new Date(data.created_at.replace(' ', 'T') + (data.created_at.includes('+') || data.created_at.includes('Z') ? '' : 'Z'));
                ts = emailDate.toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit'});
            } else {
                ts = '--:--';
            }
            const uClass = `urgency-${data.urgency||'low'}`;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})">${esc((data.sender||'').replace(/[<>]/g,'').slice(0,30))}</td>
                <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})">${esc((data.subject||'').slice(0,50))}</td>
                <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})"><span class="urgency-pill ${uClass}">${(data.urgency||'low').toUpperCase()}</span></td>
                <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})"><span class="action-pill">${data.action_type||'-'}</span></td>
                <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})">Processed</td>
                <td onclick="showReasoning(${JSON.stringify(data).replace(/"/g, '&quot;')})" class="time-cell">${ts}</td>
                <td style="position: relative;">
                    <button class="row-menu-btn" onclick="toggleRowMenu(this, event)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
                    </button>
                    <div class="row-dropdown-menu">
                        <div class="row-dropdown-item">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                            Update Display Name
                        </div>
                        <div class="row-dropdown-item delete-item">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                            Delete
                        </div>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch(e) {}
}

async function triggerDigest() {
    addThread('📊','Summarizer','Generating digest...','','');
    try {
        const r = await fetch('/api/digest/trigger',{method:'POST'});
        const d = await r.json();
        addThread('✅','Summarizer',`Digest: ${d.status}`,`${d.emails_count||0} emails summarized`,'');
    } catch(e) { addThread('❌','Summarizer','',e.message,''); }
}

async function registerWebhook() {
    const url = prompt('Enter your public webhook URL (ngrok HTTPS URL + /webhook/email):');
    if (!url) return;
    addThread('🔗','Webhook',`Registering: ${url}`,'','');
    try {
        const r = await fetch('/api/webhook/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
        const d = await r.json();
        addThread('✅','Webhook',`Registered: ${d.status}`,'','');
        document.getElementById('webhook-status').textContent = 'Active';
    } catch(e) { addThread('❌','Webhook','',e.message,''); }
}

function copyEmail() {
    const email = document.getElementById('agent-email').textContent;
    navigator.clipboard.writeText(email).then(() => {
        const b = document.querySelector('.copy-btn');
        b.textContent = '✅';
        setTimeout(() => b.textContent = '📋', 1500);
    });
}

function esc(t) {
    const d = document.createElement('div');
    d.textContent = t||'';
    return d.innerHTML;
}

// ─── Custom Dropdown ─────────────────────────
function toggleDropdown() {
    document.getElementById('dropdownMenu').classList.toggle('active');
}

function selectTime(time, el, e) {
    e.stopPropagation();
    document.getElementById('dropdown-text').textContent = time;
    
    // Update active class
    const items = document.querySelectorAll('.dropdown-item');
    items.forEach(item => item.classList.remove('active'));
    el.classList.add('active');
    
    // Close menu
    document.getElementById('dropdownMenu').classList.remove('active');
    
    // Rebuild the chart with the new time range
    rebuildChart(time);
}

function rebuildChart(timeRange) {
    const chart = document.getElementById('chart-timeline');
    const band = document.getElementById('chart-hover-band');
    const xAxis = document.getElementById('chart-x-axis');
    const subtitle = document.querySelector('.activity-card .card-subtitle');
    
    // Remove existing chart columns
    chart.querySelectorAll('.chart-col').forEach(c => c.remove());
    chartBars = [];
    
    const now = new Date();
    let totalCols, intervalMs, labelCount, labelIntervalMs, subtitleText, timeFormat;
    
    if (timeRange === '24 hours') {
        totalCols = 144;
        intervalMs = 10 * 60000;
        labelCount = 8;
        labelIntervalMs = 3 * 60 * 60000;
        subtitleText = '10-min email volume for the last 24 hours';
        timeFormat = {hour: 'numeric', hour12: true};
    } else if (timeRange === '7 days') {
        totalCols = 168;
        intervalMs = 60 * 60000;
        labelCount = 7;
        labelIntervalMs = 24 * 60 * 60000;
        subtitleText = 'Hourly email volume for the last 7 days';
        timeFormat = {weekday: 'short'};
    } else if (timeRange === '30 days') {
        totalCols = 30;
        intervalMs = 24 * 60 * 60000;
        labelCount = 5;
        labelIntervalMs = 6 * 24 * 60 * 60000;
        subtitleText = 'Daily email volume for the last 30 days';
        timeFormat = {month: 'short', day: 'numeric'};
    }
    
    if (subtitle) subtitle.textContent = subtitleText;
    
    // Anchor to a clean boundary
    let startTime;
    if (timeRange === '24 hours') {
        const topOfHour = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0, 0).getTime();
        startTime = topOfHour - 23 * 60 * 60000;
    } else if (timeRange === '7 days') {
        const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0).getTime();
        startTime = startOfDay - 6 * 24 * 60 * 60000;
    } else {
        const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0).getTime();
        startTime = startOfDay - 29 * 24 * 60 * 60000;
    }
    
    const endTime = startTime + totalCols * intervalMs;
    
    // Fetch real emails and bucket them into columns
    fetch('/api/emails')
        .then(r => r.json())
        .then(data => {
            // Bucket emails into columns
            const buckets = new Array(totalCols).fill(0);
            
            (data.emails || []).forEach(email => {
                // created_at is like "2026-05-15 17:08:05.719000"
                const emailTime = new Date(email.created_at.replace(' ', 'T') + 'Z').getTime();
                if (emailTime >= startTime && emailTime < endTime) {
                    const colIndex = Math.floor((emailTime - startTime) / intervalMs);
                    if (colIndex >= 0 && colIndex < totalCols) {
                        buckets[colIndex]++;
                    }
                }
            });
            
            // Find max for scaling bar heights
            const maxCount = Math.max(1, ...buckets);
            const MAX_BAR_HEIGHT = 120;
            
            // Build columns with data
            for (let i = 0; i < totalCols; i++) {
                const col = document.createElement('div');
                col.className = 'chart-col';
                
                const bar = document.createElement('div');
                bar.className = 'chart-bar';
                
                const count = buckets[i];
                if (count > 0) {
                    bar.classList.add('has-data');
                    const barHeight = Math.max(8, (count / maxCount) * MAX_BAR_HEIGHT);
                    bar.style.height = barHeight + 'px';
                } else {
                    bar.style.height = '0px';
                }
                
                col.appendChild(bar);
                
                // Tooltip timestamp
                const barTime = new Date(startTime + i * intervalMs);
                let tsStr;
                if (timeRange === '24 hours') {
                    tsStr = barTime.toLocaleString('en-US', {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'});
                } else if (timeRange === '7 days') {
                    tsStr = barTime.toLocaleString('en-US', {weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric'});
                } else {
                    tsStr = barTime.toLocaleString('en-US', {weekday: 'short', month: 'short', day: 'numeric'});
                }
                
                // Pass real count so tooltip shows actual data
                attachTooltipWithCount(col, bar, tsStr, count);
                chart.insertBefore(col, band);
            }
            
            // Build x-axis labels
            if (xAxis) {
                xAxis.innerHTML = '';
                for (let i = 0; i <= labelCount; i++) {
                    const labelTime = new Date(startTime + i * labelIntervalMs);
                    const span = document.createElement('span');
                    span.textContent = labelTime.toLocaleString('en-US', timeFormat);
                    xAxis.appendChild(span);
                }
            }
        })
        .catch(err => console.error('Failed to fetch email data for chart:', err));
}

// Tooltip with real email count
function attachTooltipWithCount(col, bar, timestamp, emailCount) {
    col.addEventListener('mouseenter', (e) => {
        const tt = document.getElementById('chart-tooltip');
        const band = document.getElementById('chart-hover-band');
        if (!tt) return;
        
        document.getElementById('tt-processed').textContent = emailCount;
        document.getElementById('tt-replied').textContent = emailCount > 0 ? Math.max(0, emailCount - 1) : 0;
        document.getElementById('tt-tasks').textContent = 0;
        document.getElementById('tt-urgent').textContent = 0;
        
        document.getElementById('tt-time').textContent = timestamp;

        // Smart positioning — avoid clipping at edges
        const colRect = col.getBoundingClientRect();
        const containerRect = document.querySelector('.activity-chart').getBoundingClientRect();
        const ttWidth = 170;
        const ttHeight = 130;
        
        let leftPos = colRect.left - containerRect.left + (colRect.width / 2);
        if (leftPos < ttWidth / 2 + 8) {
            tt.style.left = '8px';
            tt.style.transform = 'none';
        } else if (leftPos > containerRect.width - ttWidth / 2 - 8) {
            tt.style.left = 'auto';
            tt.style.right = '8px';
            tt.style.transform = 'none';
        } else {
            tt.style.left = leftPos + 'px';
            tt.style.right = 'auto';
            tt.style.transform = 'translateX(-50%)';
        }
        
        const spaceAbove = colRect.top - containerRect.top;
        if (spaceAbove < ttHeight + 20) {
            tt.style.bottom = 'auto';
            tt.style.top = (colRect.bottom - containerRect.top + 8) + 'px';
        } else {
            tt.style.top = 'auto';
            tt.style.bottom = (containerRect.bottom - colRect.top + 8) + 'px';
        }
        
        tt.classList.add('active');
        
        if (band) {
            const tlRect = document.getElementById('chart-timeline').getBoundingClientRect();
            band.style.left = (colRect.left - tlRect.left + (colRect.width / 2)) + 'px';
            band.classList.add('active');
        }
    });
    col.addEventListener('mouseleave', () => {
        const tt = document.getElementById('chart-tooltip');
        const band = document.getElementById('chart-hover-band');
        if (tt) {
            tt.classList.remove('active');
            tt.style.right = 'auto';
            tt.style.top = 'auto';
        }
        if (band) band.classList.remove('active');
    });
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('timeDropdown');
    const menu = document.getElementById('dropdownMenu');
    if (dropdown && menu && !dropdown.contains(e.target)) {
        menu.classList.remove('active');
    }
});

// ─── Section Switching ───────────────────────
function switchSection(sectionId, navEl) {
    // Hide all sections
    document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
    // Show target section
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    // Update nav active state
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(n => n.classList.remove('active'));
    if (navEl) navEl.classList.add('active');

    // Refresh data for specific sections
    if (sectionId === 'inbox') refreshEmails();
    if (sectionId === 'metrics') updateMetrics();
    if (sectionId === 'webhooks') {
        const email = document.getElementById('agent-email')?.textContent;
        const wInbox = document.getElementById('webhook-inbox-email');
        if (wInbox && email) wInbox.textContent = email;
    }
}

// ─── Metrics Update ──────────────────────────
async function updateMetrics() {
    try {
        const r = await fetch('/api/stats');
        const s = await r.json();
        const total = s.total_processed || 1; // avoid div by 0

        // Processing breakdown bars
        const replied = s.auto_replied || 0;
        const archived = s.archived || 0;
        const tasks = s.tasks_created || 0;

        document.getElementById('bar-reply').style.width = (replied/total*100)+'%';
        document.getElementById('bar-reply-val').textContent = replied;
        document.getElementById('bar-archive').style.width = (archived/total*100)+'%';
        document.getElementById('bar-archive-val').textContent = archived;
        document.getElementById('bar-task').style.width = (tasks/total*100)+'%';
        document.getElementById('bar-task-val').textContent = tasks;

        // Urgency bars
        const urgent = s.urgent_count || 0;
        const medium = total - urgent - archived; // rough estimate
        const low = archived;

        document.getElementById('bar-high').style.width = (urgent/total*100)+'%';
        document.getElementById('bar-high-val').textContent = urgent;
        document.getElementById('bar-medium').style.width = (Math.max(0,medium)/total*100)+'%';
        document.getElementById('bar-medium-val').textContent = Math.max(0, medium);
        document.getElementById('bar-low').style.width = (low/total*100)+'%';
        document.getElementById('bar-low-val').textContent = low;
    } catch(e) {}
}

// ─── Init ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    refreshStats();
    refreshEmails();
    initChart();
    loadUnifiedInbox();
    
    // Auto-refresh every 10 seconds: stats and email table
    setInterval(() => {
        refreshStats();
        refreshEmails();
    }, 10000);
    
    // Rebuild chart less frequently (every 30s)
    setInterval(() => {
        const activeFilter = document.getElementById('dropdown-text')?.textContent || '24 hours';
        rebuildChart(activeFilter);
    }, 30000);
});

// Load UNIFIED INBOX from database on page load
async function loadUnifiedInbox() {
    try {
        const r = await fetch('/api/emails');
        const d = await r.json();
        if (!d.emails?.length) return;
        
        // Show the most recent 10 emails in the feed
        const recent = d.emails.slice(0, 10);
        recent.reverse(); // oldest first so newest ends up on top
        
        recent.forEach(email => {
            const emailDate = new Date(email.created_at.replace(' ', 'T') + (email.created_at.includes('+') || email.created_at.includes('Z') ? '' : 'Z'));
            const timeStr = emailDate.toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit'});
            
            const urgLabel = (email.urgency || 'low').toUpperCase();
            const subject = email.subject || 'No subject';
            const action = email.action_type || 'unknown';
            const sender = (email.sender || '').replace(/[<>]/g, '').split('@')[0];
            
            addThread('', sender, subject, `${urgLabel} -- ${action}`, timeStr);
        });
    } catch(e) {
        console.error('Failed to load inbox feed:', e);
    }
}
