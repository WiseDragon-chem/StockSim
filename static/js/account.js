// ============================================================
// account.js — 账户：资产看板 / 持仓刷新 / 顶栏资产更新 / 实时盈亏更新
// ============================================================

// 缓存持仓明细，供 WebSocket 实时更新盈亏时使用
let positionCache = {};   // { symbol: { quantity, averageCost, name } }
let cachedCashBalance = 0;

function clearAccountCache() {
    positionCache = {};
    cachedCashBalance = 0;
}

async function refreshAccount() {
    if (!token) return;
    try {
        const res = await fetch('/api/users/me', { headers: { 'Authorization': `Bearer ${token}` } });
        const user = await res.json();
        cachedCashBalance = user.cash_balance;

        // 并行获取所有持仓的股票名称和最新价格
        const positionDetails = await Promise.all(
            (user.positions || []).map(async (pos) => {
                try {
                    const [dataRes, nameRes] = await Promise.all([
                        fetch(`/api/market/${pos.symbol}?period=daily`),
                        fetch(`/api/market/${pos.symbol}/name`)
                    ]);
                    const data = await dataRes.json();
                    const nameData = await nameRes.json();
                    const cp = (Array.isArray(data) && data.length > 0) ? data[0].close : 0;
                    return {
                        ...pos,
                        name: nameData.name || '',
                        currentPrice: cp,
                        marketValue: pos.quantity * cp
                    };
                } catch (e) {
                    return { ...pos, name: '', currentPrice: 0, marketValue: 0 };
                }
            })
        );

        // 缓存持仓数据供 WebSocket 实时更新使用
        positionCache = {};
        positionDetails.forEach(p => {
            p.pnl = p.currentPrice ? (p.currentPrice - p.average_cost) * p.quantity : null;
            positionCache[p.symbol] = {
                quantity: p.quantity,
                averageCost: p.average_cost,
                name: p.name,
            };
        });

        // 计算总资产 = 现金 + 所有持仓市值
        const totalMarketValue = positionDetails.reduce((sum, p) => sum + p.marketValue, 0);
        const totalAssets = user.cash_balance + totalMarketValue;
        const totalPnl = positionDetails.reduce((sum, p) => sum + (p.pnl || 0), 0);

        // ---- 更新顶栏 ----
        updateTopBarAssets(totalAssets, user.cash_balance);

        // ---- 更新资产看板 ----
        updateDashboardSummary(totalAssets, user.cash_balance, totalPnl, positionDetails);

        // ---- 更新持仓列表 ----
        renderPositionTable(positionDetails);

        if (typeof updateAssetsLoginHint === 'function') {
            updateAssetsLoginHint();
        }

    } catch (e) {
        console.error("刷新账户失败", e);
    }
}

// ============================================================
// 顶栏资产更新
// ============================================================

function updateTopBarAssets(totalAssets, cashBalance) {
    const topAssets = document.getElementById('top-bar-assets');
    if (topAssets) topAssets.innerText = '¥' + totalAssets.toFixed(2);
    const topCash = document.getElementById('top-bar-cash');
    if (topCash) topCash.innerText = '现金 ¥' + cashBalance.toFixed(2);
}

// ============================================================
// 看板汇总更新（总资产、现金、总盈亏）
// ============================================================

function updateDashboardSummary(totalAssets, cashBalance, totalPnl, positionDetails) {
    const totalDisplay = document.getElementById('total-assets-display');
    if (totalDisplay) totalDisplay.innerText = totalAssets.toFixed(2);

    const cashDisplay = document.getElementById('cash-display');
    if (cashDisplay) cashDisplay.innerText = cashBalance.toFixed(2);

    const totalPnlEl = document.getElementById('total-pnl-display');
    if (totalPnlEl) {
        const hasPnlData = positionDetails.some(p => p.pnl !== null);
        if (hasPnlData) {
            const absPnl = Math.abs(totalPnl);
            totalPnlEl.innerText = (totalPnl >= 0 ? '+' : '-') + '¥' + absPnl.toFixed(2);
            totalPnlEl.style.color = totalPnl >= 0 ? 'var(--danger)' : 'var(--success)';
        } else {
            totalPnlEl.innerText = '--';
            totalPnlEl.style.color = '';
        }
    }
}

// ============================================================
// 持仓表格渲染
// ============================================================

function renderPositionTable(positionDetails) {
    const tbody = document.getElementById('position-list');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (positionDetails.length > 0) {
        positionDetails.forEach(pos => {
            const tr = document.createElement('tr');
            tr.setAttribute('data-symbol', pos.symbol);

            const cpStr = pos.currentPrice ? pos.currentPrice.toFixed(2) : '--';
            const mvStr = pos.marketValue ? pos.marketValue.toFixed(2) : '--';

            let pnlHtml = '--';
            if (pos.pnl !== null) {
                const absPnl = Math.abs(pos.pnl);
                const color = pos.pnl >= 0 ? 'var(--danger)' : 'var(--success)';
                const sign = pos.pnl >= 0 ? '+' : '-';
                pnlHtml = `<strong class="pnl-cell" style="color:${color};">${sign}¥${absPnl.toFixed(2)}</strong>`;
            }

            tr.innerHTML = `
                <td>
                    <strong>${pos.symbol}</strong>
                    ${pos.name ? '<br><span style="font-size:11px;color:var(--text-secondary);">' + pos.name + '</span>' : ''}
                </td>
                <td class="qty-cell">${pos.quantity}</td>
                <td class="cost-cell">${pos.average_cost.toFixed(2)}</td>
                <td class="price-cell">${cpStr}</td>
                <td class="mv-cell">${mvStr}</td>
                <td class="pnl-container">${pnlHtml}</td>
                <td><button class="btn-sell" style="padding: 4px 8px; font-size: 12px;" onclick="quickSell('${pos.symbol}')">卖出</button></td>
            `;
            tbody.appendChild(tr);
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:20px;">暂无持仓</td></tr>';
    }
}

// ============================================================
// WebSocket 实时更新持仓现价和盈亏
// ============================================================

function updatePositionPrice(symbol, newPrice) {
    const cached = positionCache[symbol];
    if (!cached) return;  // 未持有该股票

    // 找到对应行
    const row = document.querySelector(`#position-list tr[data-symbol="${symbol}"]`);
    if (!row) return;

    const quantity = cached.quantity;
    const avgCost = cached.averageCost;
    const marketValue = quantity * newPrice;
    const pnl = (newPrice - avgCost) * quantity;

    // 更新现价
    const priceCell = row.querySelector('.price-cell');
    if (priceCell) priceCell.innerText = newPrice.toFixed(2);

    // 更新市值
    const mvCell = row.querySelector('.mv-cell');
    if (mvCell) mvCell.innerText = marketValue.toFixed(2);

    // 更新盈亏
    const pnlContainer = row.querySelector('.pnl-container');
    if (pnlContainer) {
        const absPnl = Math.abs(pnl);
        const color = pnl >= 0 ? 'var(--danger)' : 'var(--success)';
        const sign = pnl >= 0 ? '+' : '-';
        pnlContainer.innerHTML = `<strong class="pnl-cell" style="color:${color};">${sign}¥${absPnl.toFixed(2)}</strong>`;
    }

    // 重新计算总资产和总盈亏
    recalcTotalFromDom();
}

function recalcTotalFromDom() {
    const tbody = document.getElementById('position-list');
    if (!tbody || !tbody.children.length) {
        // 没有持仓时仅用现金显示总资产
        const topAssets = document.getElementById('top-bar-assets');
        if (topAssets) topAssets.innerText = '¥' + cachedCashBalance.toFixed(2);
        return;
    }

    let totalMv = 0;
    let totalPnl = 0;
    let hasPnl = false;

    const rows = tbody.querySelectorAll('tr[data-symbol]');
    rows.forEach(row => {
        const mvCell = row.querySelector('.mv-cell');
        if (mvCell) {
            const mv = parseFloat(mvCell.innerText);
            if (!isNaN(mv)) totalMv += mv;
        }
        const pnlEl = row.querySelector('.pnl-cell');
        if (pnlEl) {
            const pnlText = pnlEl.innerText.replace(/[+¥,-]/g, '');  // 提取数字部分
            const pnlVal = parseFloat(pnlText);
            if (!isNaN(pnlVal)) {
                // 判断正负号
                const sign = pnlEl.innerText.startsWith('+') ? 1 : -1;
                totalPnl += sign * pnlVal;
                hasPnl = true;
            }
        }
    });

    const totalAssets = cachedCashBalance + totalMv;

    // 更新顶栏总资产
    const topAssets = document.getElementById('top-bar-assets');
    if (topAssets) topAssets.innerText = '¥' + totalAssets.toFixed(2);

    // 更新看板总资产
    const totalDisplay = document.getElementById('total-assets-display');
    if (totalDisplay) totalDisplay.innerText = totalAssets.toFixed(2);

    // 更新总盈亏
    const totalPnlEl = document.getElementById('total-pnl-display');
    if (totalPnlEl && hasPnl) {
        const absPnl = Math.abs(totalPnl);
        totalPnlEl.innerText = (totalPnl >= 0 ? '+' : '-') + '¥' + absPnl.toFixed(2);
        totalPnlEl.style.color = totalPnl >= 0 ? 'var(--danger)' : 'var(--success)';
    }
}
