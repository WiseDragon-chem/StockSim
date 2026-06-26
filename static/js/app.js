// ============================================================
// app.js — 全局状态 + 启动引导 + 选项卡切换 + 模拟公司侧边栏 + 用户指南
// 此文件必须第一个加载（提供全局变量和 DOMContentLoaded 入口）
// ============================================================

let token = "";
let currentPrice = 0;
let ws = null;
let wsConnected = false;
let chartInstance = null;
let candlestickSeries = null;
let heartbeatInterval = null;
let currentPeriod = 'daily'; // 默认日K
let currentWsSymbol = '';
let currentTab = 'mock';
let mockCompanies = [];

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

    // 加载模拟公司列表 → 完成后渲染列表并加载第一家公司
    fetchMockCompanies().then(() => {
        renderMockCompanyList();
        if (mockCompanies.length > 0) {
            document.getElementById('symbol').value = mockCompanies[0].code;
            loadChart();  // chart.js 内部有 if (!candlestickSeries) return; 保护
        }
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

    if (tabName === 'assets') {
        // 显示资产区，隐藏交易区
        if (contentTrading) contentTrading.style.display = 'none';
        if (tradeBar) tradeBar.style.display = 'none';
        if (contentAssets) contentAssets.style.display = 'block';

        // 如果已登录则刷新账户
        if (token) {
            refreshAccount();
        }

        // 更新登录提示
        updateAssetsLoginHint();

    } else {
        // 显示交易区，隐藏资产区
        if (contentTrading) contentTrading.style.display = 'flex';
        if (tradeBar) tradeBar.style.display = 'block';
        if (contentAssets) contentAssets.style.display = 'none';

        // 切换侧边栏内容
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
    const sidebar = document.getElementById('tab-sidebar');
    // 如果侧边栏存在但还没有 mock-company-sidebar，直接渲染到 sidebar
    // 如果 sidebar 不存在（初始加载时），创建临时容器

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

        item.innerHTML = `
            <span class="company-code">${c.code}</span>
            <span class="company-name">${c.name}</span>
            <span class="company-sigma">σ${c.daily_sigma.toFixed(2)}</span>
        `;

        item.addEventListener('click', () => {
            document.getElementById('symbol').value = c.code;
            // 更新激活状态
            container.querySelectorAll('.company-list-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            loadChart();
        });

        container.appendChild(item);
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
