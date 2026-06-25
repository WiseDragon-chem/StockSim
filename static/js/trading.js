// ============================================================
// trading.js — 交易：买入 / 卖出
// ============================================================

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
