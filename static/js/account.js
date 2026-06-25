// ============================================================
// account.js — 账户：资产看板 / 持仓刷新 / 顶栏资产更新
// ============================================================

async function refreshAccount() {
    if (!token) return;
    try {
        const res = await fetch('/api/users/me', { headers: { 'Authorization': `Bearer ${token}` } });
        const user = await res.json();

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
                    // 获取行情失败，名称和价格留空
                    return { ...pos, name: '', currentPrice: 0, marketValue: 0 };
                }
            })
        );

        // 计算每只持仓的盈亏 = (现价 - 成本) × 数量
        positionDetails.forEach(p => {
            p.pnl = p.currentPrice ? (p.currentPrice - p.average_cost) * p.quantity : null;
        });

        // 计算总资产 = 现金 + 所有持仓市值
        const totalMarketValue = positionDetails.reduce((sum, p) => sum + p.marketValue, 0);
        const totalAssets = user.cash_balance + totalMarketValue;
        // 总盈亏（排除无法获取价格的数据）
        const totalPnl = positionDetails.reduce((sum, p) => sum + (p.pnl || 0), 0);

        // ---- 更新顶栏 ----
        const topAssets = document.getElementById('top-bar-assets');
        if (topAssets) {
            topAssets.innerText = '¥' + totalAssets.toFixed(2);
        }
        const topCash = document.getElementById('top-bar-cash');
        if (topCash) {
            topCash.innerText = '现金 ¥' + user.cash_balance.toFixed(2);
        }

        // ---- 更新资产看板 ----
        const totalDisplay = document.getElementById('total-assets-display');
        if (totalDisplay) totalDisplay.innerText = totalAssets.toFixed(2);

        const cashDisplay = document.getElementById('cash-display');
        if (cashDisplay) cashDisplay.innerText = user.cash_balance.toFixed(2);

        // 总盈亏显示
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

        // ---- 更新持仓列表 ----
        const tbody = document.getElementById('position-list');
        if (tbody) {
            tbody.innerHTML = '';
            if (positionDetails.length > 0) {
                positionDetails.forEach(pos => {
                    const tr = document.createElement('tr');
                    const cpStr = pos.currentPrice ? pos.currentPrice.toFixed(2) : '--';
                    const mvStr = pos.marketValue ? pos.marketValue.toFixed(2) : '--';

                    // 盈亏列
                    let pnlHtml = '--';
                    if (pos.pnl !== null) {
                        const absPnl = Math.abs(pos.pnl);
                        const color = pos.pnl >= 0 ? 'var(--danger)' : 'var(--success)';
                        const sign = pos.pnl >= 0 ? '+' : '-';
                        pnlHtml = `<strong style="color:${color};">${sign}¥${absPnl.toFixed(2)}</strong>`;
                    }

                    tr.innerHTML = `
                        <td>
                            <strong>${pos.symbol}</strong>
                            ${pos.name ? '<br><span style="font-size:11px;color:var(--text-secondary);">' + pos.name + '</span>' : ''}
                        </td>
                        <td>${pos.quantity}</td>
                        <td>${pos.average_cost.toFixed(2)}</td>
                        <td>${cpStr}</td>
                        <td>${mvStr}</td>
                        <td>${pnlHtml}</td>
                        <td><button class="btn-sell" style="padding: 4px 8px; font-size: 12px;" onclick="quickSell('${pos.symbol}')">卖出</button></td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:20px;">暂无持仓</td></tr>';
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
