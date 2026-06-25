// ============================================================
// account.js — 账户：资产看板 / 持仓刷新
// ============================================================

async function refreshAccount() {
    if (!token) return;
    try {
        const res = await fetch('/api/users/me', { headers: { 'Authorization': `Bearer ${token}` } });
        const user = await res.json();

        const dashboard = document.getElementById('dashboard');
        if (dashboard) dashboard.style.display = 'block';

        const cashDisplay = document.getElementById('cash-display');
        if (cashDisplay) cashDisplay.innerText = user.cash_balance.toFixed(2);

        const tbody = document.getElementById('position-list');
        if (tbody) {
            tbody.innerHTML = '';
            user.positions.forEach(pos => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${pos.symbol}</strong></td>
                    <td>${pos.quantity}</td>
                    <td>${pos.average_cost.toFixed(2)}</td>
                    <td><button class="btn-sell" style="padding: 4px 8px; font-size: 12px;" onclick="quickSell('${pos.symbol}')">卖出</button></td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) { console.error("刷新账户失败", e); }
}
