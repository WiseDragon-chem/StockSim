let token = "";
let currentPrice = 0;
let ws = null;
let wsConnected = false;
let chartInstance = null;
let candlestickSeries = null;
let heartbeatInterval = null;
let currentPeriod = 'daily'; // 默认日K

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
});

async function autoLogin() {
    const savedToken = localStorage.getItem('stockSimToken');
    const savedUsername = localStorage.getItem('stockSimUsername');
    
    if (savedToken && savedUsername) {
        token = savedToken;
        try {
            const res = await fetch('/api/users/me', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                updateLoginUI(true, savedUsername);
                refreshAccount();
                console.log('自动登录成功');
            } else {
                // Token 无效，执行登出清理
                logout(); 
            }
        } catch (e) {
            console.error('自动登录网络错误:', e);
            // 网络错误不一定代表token失效，但为了安全可以转为未登录态
            updateLoginUI(false);
        }
    } else {
        updateLoginUI(false);
    }
}

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

async function login() {
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    
    const username = usernameInput.value;
    const password = passwordInput.value;
    
    if (!username || !password) { alert("请输入用户名和密码"); return; }
    
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    try {
        const res = await fetch('/api/users/login', { method: 'POST', body: formData });
        if (res.ok) {
            const data = await res.json();
            token = data.access_token;
            
            // 保存到本地
            localStorage.setItem('stockSimToken', token);
            localStorage.setItem('stockSimUsername', username);
            
            updateLoginUI(true, username);
            refreshAccount();
            
            // 清空密码框
            passwordInput.value = '';
        } else {
            alert("登录失败：用户名或密码错误");
        }
    } catch (e) {
        console.error(e);
        alert("连接服务器失败");
    }
}

function logout() {
    localStorage.removeItem('stockSimToken');
    localStorage.removeItem('stockSimUsername');
    token = "";
    
    updateLoginUI(false);
    
    // 隐藏资产看板
    const dashboard = document.getElementById('dashboard');
    if (dashboard) dashboard.style.display = 'none';
    
    if (wsConnected) disconnectWebSocket();
}

/**
 * 修复后的 UI 更新函数
 * 适配新的 HTML 结构 (login-area 和 logout-section)
 */
function updateLoginUI(isLoggedIn, username = '') {
    const loginArea = document.getElementById('login-area');
    const logoutSection = document.getElementById('logout-section');
    const loggedInUser = document.getElementById('logged-in-user');
    
    // 安全检查：防止页面元素找不到导致报错
    if (!loginArea || !logoutSection) return;

    if (isLoggedIn) {
        // 登录状态：隐藏输入框，显示用户信息
        loginArea.style.display = 'none';
        logoutSection.style.display = 'flex'; // Flex布局保持对齐
        if (loggedInUser) loggedInUser.innerText = username;
    } else {
        // 未登录状态：显示输入框，隐藏用户信息
        loginArea.style.display = 'flex';
        logoutSection.style.display = 'none';
        if (loggedInUser) loggedInUser.innerText = '';
    }
}

function showRegister() {
    const modal = document.getElementById('register-modal');
    if(modal) {
        modal.style.display = 'block';
        document.getElementById('register-status').innerText = '';
    }
}

function hideRegister() {
    const modal = document.getElementById('register-modal');
    if(modal) modal.style.display = 'none';
}

async function register() {
    const username = document.getElementById('register-username').value;
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const statusBox = document.getElementById('register-status');

    if (!username || !password) { statusBox.innerText = '用户名和密码不能为空'; statusBox.style.color = 'red'; return; }
    if (password !== confirmPassword) { statusBox.innerText = '密码不一致'; statusBox.style.color = 'red'; return; }
    if (password.length < 3) { statusBox.innerText = '密码至少3位'; statusBox.style.color = 'red'; return; }

    try {
        const res = await fetch('/api/users/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (res.ok) {
            statusBox.innerText = '注册成功！请登录';
            statusBox.style.color = 'green';
            
            // 自动填充登录框
            const loginUser = document.getElementById('username');
            if(loginUser) loginUser.value = username;
            
            setTimeout(hideRegister, 2000);
        } else {
            const err = await res.json();
            statusBox.innerText = '注册失败: ' + (err.detail || '未知错误');
            statusBox.style.color = 'red';
        }
    } catch (e) {
        console.error(e);
        statusBox.innerText = '网络错误';
    }
}

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
            candlestickSeries.setData(data);
            chartInstance.timeScale().fitContent();
            
            // 更新价格显示
            currentPrice = data[data.length - 1].close;
            updatePriceUI(currentPrice, 0); 
            
            // 更新更新时间
            const lastTime = data[data.length - 1].time;
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

async function buy() { trade('buy'); }
async function sell() { trade('sell'); }

async function trade(type) {
    if (!token) { alert("请先登录！"); return; }

    
    const symbol = document.getElementById('symbol').value;
    const qtyInput = document.getElementById('qty');
    const qty = parseInt(qtyInput.value);
    const msgBox = document.getElementById('trade-msg');

        // === 新增校验 1: 检查价格 ===
    if (!currentPrice || currentPrice <= 0) {
        alert("当前没有行情价格，请先点击【查询】或【加载K线】获取最新价格！");
        return; 
    }
    
    // === 新增校验 2: 检查代码 ===
    if (!symbol) {
        alert("请输入股票代码");
        return;
    }
    
    // === 新增校验 3: 检查数量 ===
    if(!qty || qty <= 0) { 
        alert("请输入有效的交易数量"); 
        return; 
    }
    
    if(!qty || qty <= 0) { alert("请输入有效的数量"); return; }

    try {
        const res = await fetch(`/api/trade/${type}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ symbol: symbol, price: currentPrice, quantity: qty })
        });
        const data = await res.json();
        
        if (res.ok) {
            msgBox.innerText = `${type === 'buy' ? '买入' : '卖出'}成功！余额: ${data.new_balance.toFixed(2)}`;
            msgBox.style.color = 'green';
            refreshAccount();
        } else {
            msgBox.innerText = "交易失败: " + (data.detail || "未知错误");
            msgBox.style.color = 'red';
        }
        
        // 3秒后清除消息
        setTimeout(() => { if(msgBox) msgBox.innerText = ''; }, 4000);
        
    } catch (e) { 
        console.error(e); 
        alert("交易请求失败"); 
    }
}

function quickSell(symbol) {
    document.getElementById('symbol').value = symbol;
    document.getElementById('qty').value = 100;
    loadChart();
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

// 存储当前WebSocket连接的股票代码
let currentWsSymbol = '';

function connectWebSocket() {
    const symbol = document.getElementById('symbol').value;
    if (!symbol) { alert('请输入股票代码'); return; }
    
    // 如果已经连接，断开并返回（toggle off）
    if (wsConnected) {
        disconnectWebSocket();
        return;
    }
    
    // 更新当前WebSocket连接的股票代码
    currentWsSymbol = symbol;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/${symbol}`;
    
    try {
        ws = new WebSocket(wsUrl);
        const sock = ws;  // 捕获当前连接引用，防止 onclose 关闭后覆盖新连接状态

        sock.onopen = () => {
            wsConnected = true;
            updateWsStatus('connected');
            startHeartbeat();
        };

        sock.onmessage = (event) => {
            if (event.data === 'ping') { sock.send('pong'); return; }
            
            try {
                const payload = JSON.parse(event.data);
                
                // 确保收到的是 update 类型的数据
                if (payload.type === 'update' && payload.data) {
                    // 检查当前显示的股票代码是否与WebSocket连接的股票代码一致
                    const currentDisplaySymbol = document.getElementById('symbol').value;
                    if (currentDisplaySymbol !== currentWsSymbol) {
                        return; // 如果不一致，忽略此消息
                    }

                    // ── 绘图暂时注释（LightweightCharts update 待修复时间格式兼容）──
                    // if (currentPeriod === 'daily') {
                    //     const klineData = payload.data;
                    //     if (candlestickSeries) {
                    //         candlestickSeries.update({
                    //             time: klineData.time,
                    //             open: klineData.open,
                    //             high: klineData.high,
                    //             low: klineData.low,
                    //             close: klineData.close
                    //         });
                    //     }
                    // }

                    const kd = payload.data;

                    // 更新右侧文本面板
                    const currentPrice = kd.close;
                    // 后端没传 change，前端根据 (close-open)/open×100 计算涨跌幅
                    const change = kd.open ? ((kd.close - kd.open) / kd.open * 100) : 0;
                    updatePriceUI(currentPrice, change);

                    const volEl = document.getElementById('volume');
                    if (volEl) volEl.innerText = kd.volume || 0;

                    const timeEl = document.getElementById('update-time');
                    if (timeEl) {
                        const now = new Date();
                        timeEl.innerText = now.toLocaleTimeString();
                    }
                }
            } catch (e) {
                console.log('WS 数据解析忽略');
            }
        };
        
        sock.onclose = (event) => {
            // 身份校验：只处理当前活跃连接的事件
            if (sock !== ws) return;
            wsConnected = false;
            updateWsStatus('disconnected');
            stopHeartbeat();
        };
    } catch (e) { console.error('WebSocket Error', e); }
}

// 页面卸载前关闭WebSocket连接
window.addEventListener('beforeunload', () => {
    if (ws) {
        // 主动关闭，避免服务器端抛出异常
        ws.close();
    }
});

function disconnectWebSocket() {
    if (ws) {
        ws.onclose = null;   // 阻止旧回调异步触发（避免干扰新连接 / 自动重连）
        ws.close(1000);
        ws = null;
    }
    // 同步更新状态和 UI，不依赖异步 onclose
    wsConnected = false;
    stopHeartbeat();
    updateWsStatus('disconnected');
}

function updateWsStatus(status) {
    const el = document.getElementById('ws-status');
    const btn = document.getElementById('ws-btn');
    if(!el || !btn) return;

    if (status === 'connected') {
        el.className = 'ws-status ws-connected';
        el.innerText = '● 实时连接';
        btn.innerText = '关闭推送';
        btn.classList.add('btn-danger'); // 变为红色按钮提示关闭
        btn.classList.remove('btn-secondary');
    } else {
        el.className = 'ws-status ws-disconnected';
        el.innerText = '● 实时断开';
        btn.innerText = '开启实时推送';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-secondary');
    }
}

function startHeartbeat() {
    heartbeatInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 25000);
}

function stopHeartbeat() {
    if (heartbeatInterval) clearInterval(heartbeatInterval);
}
