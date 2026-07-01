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

    // === 校验: 检查代码 ===
    if (!symbol) {
        alert("请输入股票代码");
        return;
    }

    // === 校验: 检查数量 ===
    if (!qty || qty <= 0) {
        alert("请输入有效的交易数量");
        return;
    }

    try {
        // 价格由服务器端获取，客户端不再传入
        const res = await fetch(`/api/trade/${type}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ symbol: symbol, quantity: qty })
        });
        const data = await res.json();

        if (res.ok) {
            const priceInfo = data.price ? `（成交价: ${data.price.toFixed(2)}）` : '';
            msgBox.innerText = `${type === 'buy' ? '买入' : '卖出'}成功！${priceInfo} 余额: ${data.new_balance.toFixed(2)}`;
            msgBox.style.color = 'green';

            // 立即更新顶栏现金（总资产由 refreshAccount 精确计算后更新）
            const topCash = document.getElementById('top-bar-cash');
            if (topCash) topCash.innerText = '现金 ¥' + data.new_balance.toFixed(2);

            refreshAccount();
        } else {
            msgBox.innerText = "交易失败: " + (data.detail || "未知错误");
            msgBox.style.color = 'red';
        }

        // 3秒后清除消息
        setTimeout(() => { if (msgBox) msgBox.innerText = ''; }, 4000);

    } catch (e) {
        console.error(e);
        alert("交易请求失败");
    }
}
