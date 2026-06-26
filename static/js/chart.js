// ============================================================
// chart.js — 图表：K线加载 / 周期切换 / 价格显示
// ============================================================

async function loadChart() {
    if (!candlestickSeries) return;
    const symbolInput = document.getElementById('symbol');
    const symbol = symbolInput ? symbolInput.value : '600519';

    try {
        // 同时获取股票数据和股票名称
        const [dataRes, nameRes] = await Promise.all([
            fetch(`/api/market/${symbol}?period=${currentPeriod}`),
            fetch(`/api/market/${symbol}/name`)
        ]);

        const data = await dataRes.json();
        const nameData = await nameRes.json();

        if (Array.isArray(data) && data.length > 0) {
            // 清除现有数据并设置新数据
            // API 返回最新在前，LightweightCharts 需要按时间升序（最旧在前）
            const sortedData = [...data].reverse();
            candlestickSeries.setData(sortedData);
            chartInstance.timeScale().fitContent();

            // 更新价格显示（反转后最后一条是最新数据）
            currentPrice = sortedData[sortedData.length - 1].close;
            updatePriceUI(currentPrice, 0);

            // 更新更新时间
            const lastTime = sortedData[sortedData.length - 1].time;
            document.getElementById('update-time').innerText = lastTime;

            // 更新股票名称显示
            document.getElementById('current-symbol').innerText = symbol;
            document.getElementById('stock-name').innerText = ' - ' + nameData.name;

            // 检查WebSocket连接状态
            if (wsConnected && currentWsSymbol !== symbol) {
                // 如果WebSocket连接的股票代码与当前股票代码不一致，提示用户重新连接
                alert('已切换股票，请重新开启实时推送以获取新股票的实时数据');
                // 可以选择自动断开连接
                disconnectWebSocket();
            }

        } else {
            alert("未获取到数据，请检查股票代码");
        }
    } catch (e) {
        console.error(e);
        alert("请求数据出错");
    }
}

function switchPeriod(period) {
    if (currentPeriod === period) return; // 点击当前已选中的，不做反应

    currentPeriod = period;

    // 1. 更新按钮样式 UI
    document.querySelectorAll('.btn-period').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`btn-${period}`).classList.add('active');

    // 2. 重新加载数据
    loadChart();
}

// ============================================================
// 十字光标悬浮提示（K线详细数据）
// ============================================================

let chartTooltip = null;

function setupChartTooltip() {
    if (!chartInstance || !candlestickSeries) return;
    if (chartTooltip) return; // 防止重复初始化

    // 创建悬浮提示 div
    chartTooltip = document.createElement('div');
    chartTooltip.id = 'chart-tooltip';
    chartTooltip.style.cssText = `
        display: none;
        position: absolute;
        z-index: 100;
        background: rgba(224, 242, 254, 0.95);
        color: #1e293b;
        padding: 10px 14px;
        border-radius: 6px;
        font-size: 12px;
        line-height: 1.7;
        pointer-events: none;
        white-space: nowrap;
        font-family: 'Consolas', 'Courier New', monospace;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border: 1px solid rgba(14, 165, 233, 0.25);
    `;
    document.getElementById('chart-container').appendChild(chartTooltip);

    chartInstance.subscribeCrosshairMove((param) => {
        if (!param.point || !param.time || !param.seriesData || !param.seriesData.size) {
            chartTooltip.style.display = 'none';
            return;
        }

        const data = param.seriesData.get(candlestickSeries);
        if (!data) {
            chartTooltip.style.display = 'none';
            return;
        }

        const change = data.open ? ((data.close - data.open) / data.open * 100) : 0;
        const changeSign = change >= 0 ? '+' : '';
        const changeColor = change >= 0 ? '#dc2626' : '#059669';  // 红涨绿跌

        chartTooltip.innerHTML = `
            <div style="color:#64748b;margin-bottom:3px;">📅 ${data.time}</div>
            <div>开: <span style="color:#1e293b;font-weight:600;">${data.open.toFixed(2)}</span></div>
            <div>高: <span style="color:#dc2626;">${data.high.toFixed(2)}</span></div>
            <div>低: <span style="color:#059669;">${data.low.toFixed(2)}</span></div>
            <div>收: <span style="color:#1e293b;font-weight:600;">${data.close.toFixed(2)}</span></div>
            <div style="color:${changeColor};font-weight:600;">涨跌: ${changeSign}${change.toFixed(2)}%</div>
            ${data.volume !== undefined ? '<div style="color:#64748b;">量: ' + data.volume.toLocaleString() + '</div>' : ''}
        `;

        // 定位 tooltip（避免超出图表边界）
        const container = document.getElementById('chart-container');
        const rect = container.getBoundingClientRect();
        let left = param.point.x + 16;
        let top = param.point.y - 160;

        // 防止超出右边界
        if (left + 150 > rect.width) left = param.point.x - 160;
        // 防止超出上边界
        if (top < 0) top = param.point.y + 10;
        // 防止超出下边界
        if (top + 150 > rect.height) top = param.point.y - 150;

        chartTooltip.style.left = left + 'px';
        chartTooltip.style.top = top + 'px';
        chartTooltip.style.display = 'block';
    });
}

// 辅助函数：更新价格颜色
function updatePriceUI(price, change) {
    const priceEl = document.getElementById('current-price');
    const changeEl = document.getElementById('price-change');

    if(priceEl) priceEl.innerText = price.toFixed(2);

    if(changeEl) {
        changeEl.innerText = change.toFixed(2) + '%';
        // 移除旧类
        priceEl.classList.remove('price-up', 'price-down');
        changeEl.classList.remove('price-up', 'price-down');

        if (change > 0) {
            priceEl.classList.add('price-up');
            changeEl.classList.add('price-up');
        } else if (change < 0) {
            priceEl.classList.add('price-down');
            changeEl.classList.add('price-down');
        }
    }
}
