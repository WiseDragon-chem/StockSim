// ============================================================
// websocket.js — WebSocket：实时推送 / 心跳 / 连接管理
// ============================================================

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

                    const kd = payload.data;

                    if (currentPeriod === 'daily') {
                        if (candlestickSeries) {
                            candlestickSeries.update({
                                time: kd.time,
                                open: kd.open,
                                high: kd.high,
                                low: kd.low,
                                close: kd.close
                            });
                        }
                    }

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
