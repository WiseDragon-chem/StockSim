// ============================================================
// app.js — 全局状态 + 启动引导 + 模拟公司 + 用户指南
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

document.addEventListener('DOMContentLoaded', () => {
    // 初始化图表
    const chartDom = document.getElementById('chart-container');
    if (chartDom) {
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
    }

    // 为股票代码输入框添加事件监听
    const symbolInput = document.getElementById('symbol');
    if (symbolInput) {
        // 回车键触发加载
        symbolInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                loadChart();
            }
        });

        // 输入框失去焦点时触发加载（可选）
        symbolInput.addEventListener('blur', () => {
            loadChart();
        });
    }

    // 自动登录检测
    autoLogin();
    checkAndShowGuide();
    // 加载模拟公司列表
    fetchMockCompanies();
});

// ============================================================
// 用户指南弹窗
// ============================================================

function checkAndShowGuide() {
    // 检查本地存储中是否有标记
    const hasSeenGuide = localStorage.getItem('stockSimHasSeenGuide');

    // 如果没看过，显示弹窗
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

        // localStorage.setItem('stockSimHasSeenGuide', 'true');
    }
}

// ============================================================
// 快速卖出 & 模拟公司
// ============================================================

function quickSell(symbol) {
    document.getElementById('symbol').value = symbol;
    document.getElementById('qty').value = 100;
    loadChart();
}

// 获取并渲染模拟公司快捷选择按钮
async function fetchMockCompanies() {
    const listEl = document.getElementById('mock-company-list');
    if (!listEl) return;

    try {
        const res = await fetch('/api/admin/companies');
        if (!res.ok) {
            listEl.innerHTML = '<span style="font-size:12px;color:#999;">不可用</span>';
            return;
        }
        const data = await res.json();
        const companies = data.companies || [];

        if (companies.length === 0) {
            listEl.innerHTML = '<span style="font-size:12px;color:#999;">暂无公司</span>';
            return;
        }

        listEl.innerHTML = '';
        companies.forEach(c => {
            const btn = document.createElement('button');
            btn.textContent = c.code;
            btn.title = `${c.name} (σ=${c.daily_sigma.toFixed(3)})`;
            btn.style.cssText = 'padding:3px 6px;font-size:11px;cursor:pointer;border:1px solid #ddd;border-radius:3px;background:#f7f9fc;';
            btn.onmouseenter = () => { btn.style.background = '#e3edf7'; };
            btn.onmouseleave = () => { btn.style.background = '#f7f9fc'; };
            btn.onclick = () => {
                document.getElementById('symbol').value = c.code;
                loadChart();
            };
            listEl.appendChild(btn);
        });
    } catch (e) {
        console.error('加载模拟公司列表失败', e);
        listEl.innerHTML = '<span style="font-size:12px;color:#999;">加载失败</span>';
    }
}
