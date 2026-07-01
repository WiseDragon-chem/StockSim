// ============================================================
// bank.js — 银行模块：储蓄（含利息）、融资、交易记录
// ============================================================

// 这两个变量供 account.js 读取，用于计算总资产（扣除贷款）
var cachedLoanPrincipal = 0;
var cachedAccruedInterest = 0;

// 内联输入状态
let currentBankAction = null;
let currentBankActionData = {};

function clearBankCache() {
    cachedLoanPrincipal = 0;
    cachedAccruedInterest = 0;
}

// ============================================================
// 银行主刷新
// ============================================================

async function refreshBankTab() {
    if (!token) return;
    try {
        const [userRes, bankRes] = await Promise.all([
            fetch('/api/users/me', { headers: { 'Authorization': `Bearer ${token}` } }),
            fetch('/api/bank/status', { headers: { 'Authorization': `Bearer ${token}` } })
        ]);
        if (!userRes.ok || !bankRes.ok) return;

        const user = await userRes.json();
        const bank = await bankRes.json();

        // 储蓄卡片
        document.getElementById('bank-savings').innerText = '¥' + (bank.savings_balance || 0).toFixed(2);
        document.getElementById('bank-savings-rate').innerText = (bank.savings_annual_rate_pct || 1.50).toFixed(2) + '%';
        document.getElementById('bank-cash').innerText = '¥' + (user.cash_balance || 0).toFixed(2);

        // 融资卡片
        document.getElementById('bank-loan-principal').innerText = '¥' + (bank.loan_principal || 0).toFixed(2);
        document.getElementById('bank-accrued-interest').innerText = '¥' + (bank.accrued_interest || 0).toFixed(2);
        document.getElementById('bank-loan-rate').innerText = (bank.loan_annual_rate_pct || 7.30).toFixed(2) + '%';
        document.getElementById('bank-available-credit').innerText = '¥' + (bank.available_credit || 0).toFixed(2);

        // 贷款本金高亮（红色 = 有负债）
        const lpEl = document.getElementById('bank-loan-principal');
        if (lpEl) {
            lpEl.classList.toggle('warning', (bank.loan_principal || 0) > 0);
        }

        // 存储默认值供内联输入使用
        currentBankActionData = {
            cashBalance: user.cash_balance || 0,
            savingsBalance: bank.savings_balance || 0,
            availableCredit: bank.available_credit || 0,
            totalOwed: bank.total_loan_and_interest || 0,
        };

        // 更新全局缓存（account.js 用）
        cachedLoanPrincipal = bank.loan_principal || 0;
        cachedAccruedInterest = bank.accrued_interest || 0;

        // 刷新交易记录
        await refreshBankTransactions();

    } catch (e) {
        console.error('刷新银行信息失败', e);
    }
}

// ============================================================
// 内联输入 — 替换 prompt()
// ============================================================

function toggleBankInput(action) {
    // 相同操作 → 切换关闭
    if (currentBankAction === action) { cancelBankInput(); return; }
    // 换一个操作 → 先关再开
    cancelBankInput();
    currentBankAction = action;

    if (action === 'deposit' || action === 'withdraw') {
        showSavingsInput(action);
    } else {
        showLoanInput(action);
    }
}

function showSavingsInput(action) {
    const row = document.getElementById('bank-savings-input-row');
    const input = document.getElementById('bank-savings-input');
    const btn = document.getElementById('bank-savings-confirm-btn');
    const msg = document.getElementById('bank-savings-input-msg');
    if (!row || !input) return;

    row.style.display = 'flex';
    if (action === 'deposit') {
        // 默认填充当前全部现金
        input.value = (currentBankActionData.cashBalance || 0).toFixed(2);
        input.placeholder = '';
    } else {
        input.value = '';
        input.placeholder = '最多可取 ¥' + (currentBankActionData.savingsBalance || 0).toFixed(2);
    }
    input.focus();
    if (msg) msg.innerText = '';
    if (btn) {
        btn.textContent = action === 'deposit' ? '确认存入' : '确认取出';
        btn.onclick = () => confirmBankAction(action);
    }
    input.onkeydown = (e) => { handleBankKeydown(e, action, input); };
}

function showLoanInput(action) {
    const row = document.getElementById('bank-loan-input-row');
    const input = document.getElementById('bank-loan-input');
    const btn = document.getElementById('bank-loan-confirm-btn');
    const msg = document.getElementById('bank-loan-input-msg');
    if (!row || !input) return;

    row.style.display = 'flex';
    if (action === 'borrow') {
        input.value = currentBankActionData.availableCredit || 0;
    } else {
        input.value = currentBankActionData.totalOwed || 0;
    }
    input.focus();
    input.select();
    if (msg) msg.innerText = '';
    if (btn) {
        btn.textContent = action === 'borrow' ? '确认借款' : '确认还款';
        btn.className = action === 'borrow' ? 'btn-success btn-sm' : 'btn-sell btn-sm';
        btn.onclick = () => confirmBankAction(action);
    }
    input.onkeydown = (e) => { handleBankKeydown(e, action, input); };
}

// 上下箭头每次增减 5 %
function handleBankKeydown(e, action, input) {
    if (e.key === 'Enter') { confirmBankAction(action); return; }
    if (e.key === 'ArrowUp')   { e.preventDefault(); adjustBankInput(input, 1.05); }
    if (e.key === 'ArrowDown') { e.preventDefault(); adjustBankInput(input, 0.95); }
}

function adjustBankInput(input, factor) {
    const current = parseFloat(input.value);
    if (!current || current <= 0) return;
    const newVal = Math.max(0.01, Math.round(current * factor * 100) / 100);
    input.value = newVal.toFixed(2);
}

function cancelBankInput() {
    currentBankAction = null;
    const savingsRow = document.getElementById('bank-savings-input-row');
    const loanRow = document.getElementById('bank-loan-input-row');
    if (savingsRow) savingsRow.style.display = 'none';
    if (loanRow) loanRow.style.display = 'none';
}

async function confirmBankAction(action) {
    const isSavings = (action === 'deposit' || action === 'withdraw');
    const inputEl = document.getElementById(isSavings ? 'bank-savings-input' : 'bank-loan-input');
    const msgEl = document.getElementById(isSavings ? 'bank-savings-input-msg' : 'bank-loan-input-msg');
    const amount = parseFloat(inputEl?.value);
    if (!amount || amount <= 0) {
        if (msgEl) { msgEl.style.color = 'var(--danger)'; msgEl.innerText = '请输入有效金额'; }
        return;
    }

    const endpointMap = { deposit: 'deposit', withdraw: 'withdraw', borrow: 'borrow', repay: 'repay' };
    const endpoint = endpointMap[action];
    if (!endpoint) return;

    try {
        const res = await fetch('/api/bank/' + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ amount })
        });
        const data = await res.json();
        if (!res.ok) {
            if (msgEl) { msgEl.style.color = 'var(--danger)'; msgEl.innerText = data.detail || '操作失败'; }
            return;
        }
        if (msgEl) { msgEl.style.color = 'var(--success)'; msgEl.innerText = data.msg || '操作成功'; }
        // 1 秒后自动隐藏输入行并刷新
        setTimeout(() => {
            cancelBankInput();
            refreshBankTab();
            if (typeof refreshAccount === 'function') refreshAccount();
        }, 800);
    } catch (e) {
        if (msgEl) { msgEl.style.color = 'var(--danger)'; msgEl.innerText = '操作失败: ' + e.message; }
    }
}

// ============================================================
// 交易记录
// ============================================================

async function refreshBankTransactions() {
    const tbody = document.getElementById('bank-transaction-list');
    if (!tbody || !token) return;
    try {
        const res = await fetch('/api/bank/transactions', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const txns = await res.json();
        if (txns.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-secondary);">暂无记录</td></tr>';
            return;
        }
        const typeMap = {
            deposit: '存入', withdraw: '取出', borrow: '借款',
            repay: '还款', interest: '贷款利息', savings_interest: '储蓄利息'
        };
        const typeColors = {
            deposit: 'var(--danger)', withdraw: 'var(--text-secondary)',
            borrow: 'var(--primary)', repay: 'var(--success)',
            interest: '#f59e0b', savings_interest: 'var(--success)'
        };
        tbody.innerHTML = txns.map(t => {
            const typeLabel = typeMap[t.type] || t.type;
            const typeColor = typeColors[t.type] || 'var(--text)';
            const time = new Date(t.timestamp + 'Z').toLocaleString('zh-CN');
            return `
                <tr>
                    <td style="font-size:12px;">${time}</td>
                    <td style="color:${typeColor};font-weight:600;">${typeLabel}</td>
                    <td>¥${t.amount.toFixed(2)}</td>
                    <td style="font-size:12px;color:var(--text-secondary);">${t.detail || ''}</td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error('获取银行交易记录失败', e);
    }
}

// ============================================================
// 登录提示切换
// ============================================================

function updateBankLoginHint() {
    const hint = document.getElementById('bank-login-hint');
    const dashboard = document.getElementById('bank-dashboard');
    if (!hint || !dashboard) return;
    if (token) {
        hint.style.display = 'none';
        dashboard.style.display = 'block';
    } else {
        hint.style.display = 'block';
        dashboard.style.display = 'none';
    }
}
