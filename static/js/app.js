// ============================================================
// app.js — 全局状态 + 启动引导 + 选项卡切换 + 模拟公司侧边栏 + 用户指南
// 此文件必须第一个加载（提供全局变量和 DOMContentLoaded 入口）
// ============================================================

let token = "";
let currentPrice = 0;
let ws = null;
let wsConnected = false;
let mockAllWs = null;
let mockAllWsConnected = false;
let chartInstance = null;
let candlestickSeries = null;
let ma5Series = null;
let ma10Series = null;
let ma20Series = null;
let volumeSeries = null;
let heartbeatInterval = null;
let currentPeriod = 'daily'; // 默认日K
let currentWsSymbol = '';
let currentTab = 'mock';
let mockCompanies = [];
let sidebarPrices = {};  // {code: {price, open}} — 侧边栏实时价格
let loadChartRequestId = 0;  // 防止并发 loadChart() 竞态
let assetsRefreshInterval = null;  // 资产自动刷新定时器

document.addEventListener('DOMContentLoaded', () => {
    // ================================================================
    // 图表初始化（可能因 CDN 加载失败而无法执行，不影响其余功能）
    // ================================================================
    const chartDom = document.getElementById('chart-container');
    if (chartDom) {
        if (typeof LightweightCharts !== 'undefined') {
            try {
                chartInstance = LightweightCharts.createChart(chartDom, {
                    width: chartDom.clientWidth,
                    height: 450,
                    layout: { background: { color: '#ffffff' }, textColor: '#333' },
                    grid: { vertLines: { color: '#f0f3fa' }, horzLines: { color: '#f0f3fa' } },
                    timeScale: { borderColor: '#e1e3e6' },
                });
                candlestickSeries = chartInstance.addCandlestickSeries({
                    upColor: '#d50000',
                    downColor: '#00c853',
                    borderUpColor: '#d50000',
                    borderDownColor: '#00c853',
                    wickUpColor: '#d50000',
                    wickDownColor: '#00c853',
                });

                // 移动均线 MA5 / MA10 / MA20
                ma5Series = chartInstance.addLineSeries({
                    color: '#f59e0b', lineWidth: 1, priceLineVisible: false,
                });
                ma10Series = chartInstance.addLineSeries({
                    color: '#8b5cf6', lineWidth: 1, priceLineVisible: false,
                });
                ma20Series = chartInstance.addLineSeries({
                    color: '#3b82f6', lineWidth: 1, priceLineVisible: false,
                });

                // 成交量柱（独立窗格）
                volumeSeries = chartInstance.addHistogramSeries({
                    priceScaleId: 'volume',
                    priceFormat: { type: 'volume' },
                });
                chartInstance.priceScale('volume').applyOptions({
                    scaleMargins: { top: 0.85, bottom: 0 },
                });

                // 窗口大小自适应
                window.addEventListener('resize', () => {
                    if (chartInstance) {
                        chartInstance.resize(chartDom.clientWidth, 450);
                    }
                });

                // 启用 K 线悬浮提示
                setupChartTooltip();
            } catch (e) {
                console.error('图表初始化失败', e);
                chartDom.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:14px;">⚠️ 图表初始化失败，请刷新页面重试</div>';
            }
        } else {
            // LightweightCharts CDN 未加载
            console.warn('LightweightCharts 库未加载，图表功能不可用');
            chartDom.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:14px;">⚠️ 图表库加载失败，请检查网络后刷新页面</div>';
        }
    }

    // ================================================================
    // 以下代码无论图表是否成功加载都执行
    // ================================================================

    // 初始化侧边栏（模拟公司列表）
    renderSidebar('mock');

    // 加载模拟公司列表 → 渲染列表 → 自动连接全量 WebSocket
    fetchMockCompanies().then(() => {
        renderMockCompanyList();
        if (mockCompanies.length > 0) {
            document.getElementById('symbol').value = mockCompanies[0].code;
            loadChart();
        }
        connectMockAllWebSocket();  // 自动连接模拟股市全量推送
    });

    // 自动登录检测
    autoLogin();
    checkAndShowGuide();
});

// ============================================================
// 选项卡切换
// ============================================================

function switchTab(tabName) {
    currentTab = tabName;

    // 更新选项卡按钮激活状态
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    const contentTrading = document.getElementById('content-trading');
    const tradeBar = document.getElementById('trade-bar');
    const contentAssets = document.getElementById('content-assets');
    const contentAccount = document.getElementById('content-account');
    const contentBank = document.getElementById('content-bank');

    // 先全部隐藏
    if (contentTrading) contentTrading.style.display = 'none';
    if (tradeBar) tradeBar.style.display = 'none';
    if (contentAssets) contentAssets.style.display = 'none';
    if (contentAccount) contentAccount.style.display = 'none';
    if (contentBank) contentBank.style.display = 'none';

    // 清除旧定时器
    if (assetsRefreshInterval) { clearInterval(assetsRefreshInterval); assetsRefreshInterval = null; }

    if (tabName === 'assets') {
        // 显示资产区
        if (contentAssets) contentAssets.style.display = 'block';
        if (token) {
            refreshAccount();
            // 每 5 秒刷新价格和盈亏
            assetsRefreshInterval = setInterval(refreshPositionPrices, 5000);
        }
        updateAssetsLoginHint();

    } else if (tabName === 'account') {
        // 显示个人账户（交易历史）
        if (contentAccount) contentAccount.style.display = 'block';
        if (token) refreshOrderHistory();

    } else if (tabName === 'bank') {
        // 显示银行
        if (contentBank) contentBank.style.display = 'block';
        if (token) refreshBankTab();
        if (typeof updateBankLoginHint === 'function') updateBankLoginHint();

    } else {
        // 显示交易区（mock / real）
        if (contentTrading) contentTrading.style.display = 'flex';
        if (tradeBar) tradeBar.style.display = 'block';
        renderSidebar(tabName);
    }
}

// ============================================================
// 侧边栏渲染
// ============================================================

function renderSidebar(tabName) {
    const sidebar = document.getElementById('tab-sidebar');
    if (!sidebar) return;

    if (tabName === 'mock') {
        // 模拟公司列表
        sidebar.innerHTML = `
            <div class="card">
                <h3>🏭 模拟公司列表</h3>
                <div id="mock-company-sidebar"></div>
            </div>
        `;
        renderMockCompanyList();
    } else if (tabName === 'real') {
        // 实时A股查询
        sidebar.innerHTML = `
            <div class="card">
                <h3>🔍 行情查询</h3>
                <input type="text" id="symbol-real" class="stock-lookup-input"
                       placeholder="输入代码 e.g. 600519"
                       onkeypress="if(event.key==='Enter')loadRealStock()">
                <button onclick="loadRealStock()" style="width:100%;">查询</button>
                <p style="font-size:11px;color:var(--text-secondary);margin-top:8px;">
                    输入6位A股代码后点击查询
                </p>
            </div>
        `;
    }
}

function loadRealStock() {
    const realInput = document.getElementById('symbol-real');
    if (!realInput || !realInput.value.trim()) {
        alert('请输入股票代码');
        return;
    }
    const symbol = realInput.value.trim();
    document.getElementById('symbol').value = symbol;
    loadChart();
}

// ============================================================
// 模拟公司列表
// ============================================================

async function fetchMockCompanies() {
    try {
        const res = await fetch('/api/admin/companies');
        if (!res.ok) {
            mockCompanies = [];
            return;
        }
        const data = await res.json();
        mockCompanies = data.companies || [];
    } catch (e) {
        console.error('加载模拟公司列表失败', e);
        mockCompanies = [];
    }
}

function renderMockCompanyList() {
    const container = document.getElementById('mock-company-sidebar');
    if (!container) return;

    if (mockCompanies.length === 0) {
        container.innerHTML = '<p style="font-size:12px;color:var(--text-secondary);">暂无可用的模拟公司</p>';
        return;
    }

    const currentSymbol = document.getElementById('symbol')?.value || '';

    container.innerHTML = '';
    mockCompanies.forEach(c => {
        const item = document.createElement('div');
        item.className = 'company-list-item';
        if (c.code === currentSymbol) {
            item.classList.add('active');
        }

        // 获取该公司的当前价格（红涨绿跌）
        const priceData = sidebarPrices[c.code];
        let priceHTML = '';
        if (priceData && priceData.price != null) {
            const change = priceData.open ? (priceData.price - priceData.open) / priceData.open : 0;
            const colorClass = change >= 0 ? 'price-up' : 'price-down';
            priceHTML = `<span class="company-price ${colorClass}">${priceData.price.toFixed(2)}</span>`;
        } else {
            priceHTML = `<span class="company-price">-</span>`;
        }

        item.innerHTML = `
            <span class="company-code">${c.code}</span>
            <span class="company-name">${c.name}</span>
            ${priceHTML}
        `;

        item.addEventListener('click', () => {
            document.getElementById('symbol').value = c.code;
            // 更新激活状态
            container.querySelectorAll('.company-list-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            loadChart();
            // 模拟股市使用全量 WebSocket，无需切换连接
        });

        container.appendChild(item);
    });
}

// ============================================================
// 模拟股市全量 WebSocket（单连接，推送所有公司价格）
// ============================================================

function connectMockAllWebSocket() {
    if (mockAllWsConnected) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/mock/all`;

    try {
        mockAllWs = new WebSocket(wsUrl);
        const sock = mockAllWs;  // 捕获引用，防止 onclose 覆盖

        sock.onopen = () => {
            mockAllWsConnected = true;
            updateWsStatus('connected');
            startHeartbeat();
        };

        sock.onmessage = (event) => {
            // 身份校验：防止旧连接消息污染
            if (sock !== mockAllWs) return;

            if (event.data === 'ping') { sock.send('pong'); return; }

            try {
                const payload = JSON.parse(event.data);
                if (payload.type === 'update_all' && payload.data) {
                    const allData = payload.data;

                    // 1. 更新所有侧边栏价格
                    updateAllSidebarPrices(allData);

                    // 2. 更新当前选中股票的图表、价格UI、持仓
                    const currentSymbol = document.getElementById('symbol')?.value || '';
                    const curData = allData[currentSymbol];
                    if (curData && currentPeriod === 'daily') {
                        if (candlestickSeries) {
                            candlestickSeries.update({
                                time: curData.time,
                                open: curData.open,
                                high: curData.high,
                                low: curData.low,
                                close: curData.close,
                            });
                        }

                        currentPrice = curData.close;
                        const change = curData.open ? ((curData.close - curData.open) / curData.open * 100) : 0;
                        updatePriceUI(currentPrice, change);

                        // 更新持仓表
                        if (typeof updatePositionPrice === 'function') {
                            updatePositionPrice(currentSymbol, currentPrice);
                        }

                        const volEl = document.getElementById('volume');
                        if (volEl) volEl.innerText = curData.volume || 0;

                        const timeEl = document.getElementById('update-time');
                        if (timeEl) {
                            timeEl.innerText = new Date().toLocaleTimeString();
                        }
                    }
                }
            } catch (e) {
                console.log('Mock WS 数据解析忽略');
            }
        };

        sock.onclose = () => {
            // 身份校验：只处理当前活跃连接的事件
            if (sock !== mockAllWs) return;
            mockAllWsConnected = false;
            updateWsStatus('disconnected');
            stopHeartbeat();
        };
    } catch (e) {
        console.error('Mock WebSocket Error', e);
    }
}

function disconnectMockAllWebSocket() {
    if (mockAllWs) {
        mockAllWs.onclose = null;  // 阻止旧回调触发
        mockAllWs.close(1000);
        mockAllWs = null;
    }
    mockAllWsConnected = false;
    stopHeartbeat();
    updateWsStatus('disconnected');
}

// ============================================================
// 侧边栏价格批量更新
// ============================================================

function updateAllSidebarPrices(allData) {
    // 更新全局缓存
    for (const [code, data] of Object.entries(allData)) {
        sidebarPrices[code] = { price: data.close, open: data.open };
    }

    // 刷新侧边栏 DOM
    const container = document.getElementById('mock-company-sidebar');
    if (!container) return;

    const items = container.querySelectorAll('.company-list-item');
    items.forEach(item => {
        const codeEl = item.querySelector('.company-code');
        if (!codeEl) return;
        const code = codeEl.textContent;
        const priceData = sidebarPrices[code];
        const priceEl = item.querySelector('.company-price');
        if (!priceEl) return;

        if (priceData && priceData.price != null) {
            const change = priceData.open ? (priceData.price - priceData.open) / priceData.open : 0;
            priceEl.textContent = priceData.price.toFixed(2);
            priceEl.className = 'company-price ' + (change >= 0 ? 'price-up' : 'price-down');
        }
    });
}

// ============================================================
// 用户指南弹窗
// ============================================================

function checkAndShowGuide() {
    const hasSeenGuide = localStorage.getItem('stockSimHasSeenGuide');
    if (!hasSeenGuide) {
        const modal = document.getElementById('guide-modal');
        if (modal) {
            modal.style.display = 'block';
        }
    }
}

function closeGuide() {
    const modal = document.getElementById('guide-modal');
    if (modal) {
        modal.style.display = 'none';
        localStorage.setItem('stockSimHasSeenGuide', 'true');
    }
}

// ============================================================
// 快速卖出 — 从持仓表点击卖出按钮调用
// ============================================================

function quickSell(symbol) {
    document.getElementById('symbol').value = symbol;
    document.getElementById('qty').value = 100;
    // 切换到模拟公司或实时A股 tab 以便看到图表
    if (currentTab === 'assets') {
        // 判断 symbol 是模拟公司还是真实股票
        if (symbol.startsWith('m')) {
            switchTab('mock');
        } else {
            switchTab('real');
        }
    }
    loadChart();
}

// ============================================================
// 更新"我的资产"选项卡的登录提示
// ============================================================

function updateAssetsLoginHint() {
    const hint = document.getElementById('assets-login-hint');
    const dashboard = document.getElementById('dashboard');
    if (!hint || !dashboard) return;

    if (token) {
        hint.style.display = 'none';
        dashboard.style.display = 'block';
    } else {
        hint.style.display = 'block';
        dashboard.style.display = 'none';
    }
}
