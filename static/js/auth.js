// ============================================================
// auth.js — 认证：登录模态框 / 注册 / 登出 / 自动登录
// ============================================================

// ==================== 模态框控制 ====================

function showLoginModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) {
        modal.style.display = 'flex';
        // 默认显示登录选项卡
        switchAuthTab('login');
        // 清空表单和状态
        document.getElementById('modal-username').value = '';
        document.getElementById('modal-password').value = '';
        const loginStatus = document.getElementById('login-status');
        if (loginStatus) loginStatus.innerText = '';
        const registerStatus = document.getElementById('register-status');
        if (registerStatus) registerStatus.innerText = '';
    }
}

function hideAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function switchAuthTab(tabName) {
    document.querySelectorAll('#auth-modal .modal-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.modal === tabName);
    });
    const loginForm = document.getElementById('modal-login');
    const registerForm = document.getElementById('modal-register');
    if (tabName === 'login') {
        if (loginForm) loginForm.style.display = 'block';
        if (registerForm) registerForm.style.display = 'none';
    } else {
        if (loginForm) loginForm.style.display = 'none';
        if (registerForm) registerForm.style.display = 'block';
    }
}

// 为模态框选项卡按钮绑定事件
document.addEventListener('DOMContentLoaded', () => {
    // 使用事件委托处理模态框选项卡点击
    const authModal = document.getElementById('auth-modal');
    if (authModal) {
        authModal.addEventListener('click', (e) => {
            const tabBtn = e.target.closest('.modal-tab');
            if (tabBtn) {
                switchAuthTab(tabBtn.dataset.modal);
            }
        });

        // 点击遮罩层关闭
        authModal.addEventListener('click', (e) => {
            if (e.target === authModal) {
                hideAuthModal();
            }
        });
    }
});

// ==================== 自动登录 ====================

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
                const user = await res.json();
                updateLoginUI(true, savedUsername, user.cash_balance);
                refreshAccount();
                updateAssetsLoginHint();
                console.log('自动登录成功');
            } else {
                logout();
            }
        } catch (e) {
            console.error('自动登录网络错误:', e);
            updateLoginUI(false);
        }
    } else {
        updateLoginUI(false);
    }
}

// ==================== 登录 ====================

async function login() {
    const usernameInput = document.getElementById('modal-username');
    const passwordInput = document.getElementById('modal-password');
    const statusEl = document.getElementById('login-status');

    const username = usernameInput ? usernameInput.value : '';
    const password = passwordInput ? passwordInput.value : '';

    if (!username || !password) {
        if (statusEl) { statusEl.innerText = '请输入用户名和密码'; statusEl.style.color = 'red'; }
        return;
    }

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

            // 获取用户资产信息
            const userRes = await fetch('/api/users/me', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const user = await userRes.json();

            updateLoginUI(true, username, user.cash_balance);
            refreshAccount();  // 刷新持仓列表
            updateAssetsLoginHint();
            hideAuthModal();

            // 清空密码框
            passwordInput.value = '';
            if (statusEl) statusEl.innerText = '';
        } else {
            if (statusEl) { statusEl.innerText = '登录失败：用户名或密码错误'; statusEl.style.color = 'red'; }
        }
    } catch (e) {
        console.error(e);
        if (statusEl) { statusEl.innerText = '连接服务器失败'; statusEl.style.color = 'red'; }
    }
}

// ==================== 登出 ====================

function logout() {
    localStorage.removeItem('stockSimToken');
    localStorage.removeItem('stockSimUsername');
    token = "";

    updateLoginUI(false);

    // 如果 WebSocket 已连接则断开
    if (wsConnected) disconnectWebSocket();

    // 更新资产选项卡提示
    updateAssetsLoginHint();

    // 清空持仓列表
    const tbody = document.getElementById('position-list');
    if (tbody) tbody.innerHTML = '';
    const cashDisplay = document.getElementById('cash-display');
    if (cashDisplay) cashDisplay.innerText = '0.00';
}

// ==================== UI 更新 ====================

/**
 * 更新顶栏登录状态
 * @param {boolean} isLoggedIn - 是否已登录
 * @param {string} username - 用户名
 * @param {number} cashBalance - 现金余额（可选）
 */
function updateLoginUI(isLoggedIn, username = '', cashBalance = null) {
    const btnLogin = document.getElementById('btn-login-modal');
    const userArea = document.getElementById('top-bar-user-area');
    const usernameEl = document.getElementById('top-bar-username');
    const assetsEl = document.getElementById('top-bar-assets');

    if (!btnLogin || !userArea) return;

    if (isLoggedIn) {
        btnLogin.style.display = 'none';
        userArea.style.display = 'flex';
        if (usernameEl) usernameEl.innerText = username;
        if (assetsEl && cashBalance !== null) {
            assetsEl.innerText = '¥' + Number(cashBalance).toFixed(2);
        }
    } else {
        btnLogin.style.display = 'inline-block';
        userArea.style.display = 'none';
        if (usernameEl) usernameEl.innerText = '';
        if (assetsEl) assetsEl.innerText = '--';
    }
}

// ==================== 注册 ====================

function showRegister() {
    const modal = document.getElementById('auth-modal');
    if (modal) {
        modal.style.display = 'flex';
        switchAuthTab('register');
        document.getElementById('register-status').innerText = '';
    }
}

function hideRegister() {
    switchAuthTab('login');
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

            // 自动填充登录表单
            const modalUser = document.getElementById('modal-username');
            if (modalUser) modalUser.value = username;

            // 2秒后切换到登录选项卡
            setTimeout(() => switchAuthTab('login'), 1800);
        } else {
            const err = await res.json();
            statusBox.innerText = '注册失败: ' + (err.detail || '未知错误');
            statusBox.style.color = 'red';
        }
    } catch (e) {
        console.error(e);
        statusBox.innerText = '网络错误';
        statusBox.style.color = 'red';
    }
}
