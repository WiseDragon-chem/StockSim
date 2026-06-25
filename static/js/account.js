// ============================================================
// account.js — 账户：资产看板 / 持仓刷新 / 顶栏资产更新
// ============================================================

async function refreshAccount() {
    if (!token) return;
    try {
        const res = await fetch('/api/users/me', { headers: { 'Authorization': `Bearer ${token}` } });
        const user = await res.json();

        // 更新顶栏资产显示
        const topAssets = document.getElementById('top-bar-assets');
        if (topAssets) {
            topAssets.innerText = '¥' + user.cash_balance.toFixed(2);
        }

        // 更新资产看板中的现金
        const cashDisplay = document.getElementById('cash-display');
        if (cashDisplay) cashDisplay.innerText = user.cash_balance.toFixed(2);

        // 更新持仓列表
        const tbody = document.getElementById('position-list');
        if (tbody) {
            tbody.innerHTML = '';
            if (user.positions && user.positions.length > 0) {
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
            } else {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-secondary);padding:20px;">暂无持仓</td></tr>';
            }
        }

        // 更新资产选项卡的登录提示
        if (typeof updateAssetsLoginHint === 'function') {
            updateAssetsLoginHint();
        }

    } catch (e) {
        console.error("刷新账户失败", e);
    }
}
