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
                <td class="cost-cell cost-clickable" onclick="toggleBuyHistory(this, '${pos.symbol}')" title="点击查看买入明细">
                    ${pos.average_cost.toFixed(2)} <span class="expand-icon">▼</span>
                </td>
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

// ============================================================
// 交易历史（个人账户选项卡）
// ============================================================

async function refreshOrderHistory() {
    const tbody = document.getElementById('order-history-list');
    if (!tbody || !token) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:20px;">请先登录后查看</td></tr>';
        return;
    }

    try {
        const res = await fetch('/api/users/orders', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Failed');
        const orders = await res.json();

        if (orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:20px;">暂无交易记录</td></tr>';
            return;
        }

        // 并行获取所有涉及股票的名称
        const symbolSet = [...new Set(orders.map(o => o.symbol))];
        const nameMap = {};
        await Promise.all(symbolSet.map(async s => {
            try {
                const r = await fetch(`/api/market/${s}/name`);
                if (r.ok) { const d = await r.json(); nameMap[s] = d.name; }
            } catch (e) { /* ignore */ }
        }));

        tbody.innerHTML = orders.map(o => {
            const typeLabel = o.order_type === 'buy' ? '买入' : '卖出';
            const typeColor = o.order_type === 'buy' ? 'var(--danger)' : 'var(--success)';
            const amount = (o.price * o.quantity).toFixed(2);
            const name = nameMap[o.symbol] || '';
            const time = new Date(o.timestamp + 'Z').toLocaleString('zh-CN');
            return `
                <tr>
                    <td style="font-size:12px;">${time}</td>
                    <td><strong>${o.symbol}</strong></td>
                    <td style="font-size:12px;color:var(--text-secondary);">${name}</td>
                    <td style="color:${typeColor};font-weight:600;">${typeLabel}</td>
                    <td>${o.price.toFixed(2)}</td>
                    <td>${o.quantity}</td>
                    <td>¥${amount}</td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error('获取订单历史失败', e);
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:20px;">加载失败，请稍后重试</td></tr>';
    }
}

// ============================================================
// 平均成本价展开 — 买入明细
// ============================================================

async function toggleBuyHistory(cellEl, symbol) {
    // 如果已展开则收起
    const parentRow = cellEl.parentElement;
    const nextRow = parentRow.nextElementSibling;
    if (nextRow && nextRow.classList.contains('order-detail-row')) {
        nextRow.remove();
        const icon = cellEl.querySelector('.expand-icon');
        if (icon) icon.textContent = '▼';
        return;
    }

    try {
        const res = await fetch(`/api/users/orders?symbol=${symbol}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const orders = await res.json();
        const buys = orders.filter(o => o.order_type === 'buy');
        if (buys.length === 0) return;

        const totalQty = buys.reduce((s, o) => s + o.quantity, 0);
        const totalCost = buys.reduce((s, o) => s + o.price * o.quantity, 0);
        const avgCost = totalQty > 0 ? (totalCost / totalQty).toFixed(2) : '--';

        const detailRow = document.createElement('tr');
        detailRow.className = 'order-detail-row';
        detailRow.innerHTML = `
            <td colspan="7">
                <div class="order-detail-panel">
                    <table class="order-detail-table">
                        <thead><tr>
                            <th>买入时间</th><th>数量（股）</th><th>买入价格</th><th>金额</th>
                        </tr></thead>
                        <tbody>${buys.map(o => `
                            <tr>
                                <td>${new Date(o.timestamp + 'Z').toLocaleString('zh-CN')}</td>
                                <td>${o.quantity}</td>
                                <td>${o.price.toFixed(2)}</td>
                                <td>¥${(o.price * o.quantity).toFixed(2)}</td>
                            </tr>
                        `).join('')}</tbody>
                    </table>
                    <div class="order-detail-footer">
                        加权平均：总成本 ¥${totalCost.toFixed(2)} / 总股数 ${totalQty} = <strong>¥${avgCost}</strong>
                    </div>
                </div>
            </td>
        `;
        parentRow.after(detailRow);
        const icon = cellEl.querySelector('.expand-icon');
        if (icon) icon.textContent = '▲';
    } catch (e) {
        console.error('获取买入明细失败', e);
    }
}

// ============================================================
// 自动刷新持仓价格（每 5s，供资产选项卡使用）
// ============================================================

async function refreshPositionPrices() {
    if (!token) return;
    const symbols = Object.keys(positionCache);
    if (symbols.length === 0) return;

    // 并行获取所有持仓的最新价格
    const priceMap = {};
    await Promise.all(symbols.map(async (sym) => {
        try {
            const res = await fetch(`/api/market/${sym}?period=daily`);
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
                priceMap[sym] = data[0].close;
            }
        } catch (e) { /* ignore */ }
    }));

    // 更新 DOM
    let totalMv = 0;
    let totalPnl = 0;
    let hasPnl = false;

    for (const sym of symbols) {
        const newPrice = priceMap[sym];
        if (newPrice == null) continue;

        const cached = positionCache[sym];
        const row = document.querySelector(`#position-list tr[data-symbol="${sym}"]`);
        if (!row) continue;

        const mv = cached.quantity * newPrice;
        const pnl = (newPrice - cached.averageCost) * cached.quantity;
        totalMv += mv;
        totalPnl += pnl;
        hasPnl = true;

        const priceCell = row.querySelector('.price-cell');
        if (priceCell) priceCell.innerText = newPrice.toFixed(2);

        const mvCell = row.querySelector('.mv-cell');
        if (mvCell) mvCell.innerText = mv.toFixed(2);

        const pnlContainer = row.querySelector('.pnl-container');
        if (pnlContainer) {
            const absPnl = Math.abs(pnl);
            const color = pnl >= 0 ? 'var(--danger)' : 'var(--success)';
            const sign = pnl >= 0 ? '+' : '-';
            pnlContainer.innerHTML = `<strong class="pnl-cell" style="color:${color};">${sign}¥${absPnl.toFixed(2)}</strong>`;
        }
    }

    // 更新总资产和总盈亏
    const totalAssets = cachedCashBalance + totalMv;
    const topAssets = document.getElementById('top-bar-assets');
    if (topAssets) topAssets.innerText = '¥' + totalAssets.toFixed(2);
    const totalDisplay = document.getElementById('total-assets-display');
    if (totalDisplay) totalDisplay.innerText = totalAssets.toFixed(2);

    if (hasPnl) {
        const totalPnlEl = document.getElementById('total-pnl-display');
        if (totalPnlEl) {
            const absPnl = Math.abs(totalPnl);
            totalPnlEl.innerText = (totalPnl >= 0 ? '+' : '-') + '¥' + absPnl.toFixed(2);
            totalPnlEl.style.color = totalPnl >= 0 ? 'var(--danger)' : 'var(--success)';
        }
    }
}
