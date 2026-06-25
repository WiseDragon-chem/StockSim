// ============================================================
// auth.js — 认证：登录 / 注册 / 登出 / 自动登录
// ============================================================

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
