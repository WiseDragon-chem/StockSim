"""
管理后台路由 — 密码保护的管理面板 + 认证 API。
访问 /admin 需要密码登录；默认密码: admin。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from passlib.context import CryptContext
from pydantic import BaseModel

router = APIRouter()

# ── 密码管理 ────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "admin_config.json")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Admin JWT 密钥（与用户 JWT 分离）
ADMIN_SECRET_KEY = "admin-secret-key-stocksim-2024"
ADMIN_ALGORITHM = "HS256"
ADMIN_TOKEN_EXPIRE_HOURS = 24


def _load_password_hash() -> str:
    """从配置文件加载密码 hash。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["admin_password_hash"]


def _save_password_hash(hash_value: str) -> None:
    """保存新的密码 hash 到配置文件。"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"admin_password_hash": hash_value}, f, indent=2)


def verify_admin_token(token: str) -> bool:
    """验证 admin JWT token 是否有效。"""
    try:
        payload = jwt.decode(token, ADMIN_SECRET_KEY, algorithms=[ADMIN_ALGORITHM])
        return payload.get("sub") == "admin"
    except jwt.PyJWTError:
        return False


def require_admin(request: Request) -> bool:
    """FastAPI 依赖：验证请求中的 admin token。"""
    token = request.headers.get("X-Admin-Token") or request.cookies.get("admin_token")
    if not token or not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="需要管理员权限")
    return True


# ── Pydantic schemas ──────────────────────────────────────────────────


class AdminAuthRequest(BaseModel):
    password: str


class AdminPasswordChange(BaseModel):
    old_password: str
    new_password: str


# ── API 端点 ─────────────────────────────────────────────────────────


@router.post("/api/admin/auth")
def admin_auth(data: AdminAuthRequest):
    """验证管理员密码，返回 JWT token。"""
    stored_hash = _load_password_hash()
    if not pwd_context.verify(data.password, stored_hash):
        raise HTTPException(status_code=401, detail="密码错误")

    expire = datetime.now(timezone.utc) + timedelta(hours=ADMIN_TOKEN_EXPIRE_HOURS)
    payload = {"sub": "admin", "exp": expire, "iat": datetime.now(timezone.utc)}
    token = jwt.encode(payload, ADMIN_SECRET_KEY, algorithm=ADMIN_ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


@router.put("/api/admin/password")
def change_admin_password(data: AdminPasswordChange, _admin: bool = Depends(require_admin)):
    """修改管理员密码（需验证旧密码）。"""
    stored_hash = _load_password_hash()
    if not pwd_context.verify(data.old_password, stored_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    if len(data.new_password) < 4:
        raise HTTPException(status_code=400, detail="新密码至少4位")
    new_hash = pwd_context.hash(data.new_password[:72])
    _save_password_hash(new_hash)
    return {"detail": "密码修改成功"}


# ══════════════════════════════════════════════════════════════════════
# Admin HTML 页面（内嵌）
# ══════════════════════════════════════════════════════════════════════

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StockSim 管理后台</title>
<link rel="stylesheet" href="/style.css">
<style>
    :root { --bg: #f5f7fb; --primary: #2563eb; --primary-light: #e0e7ff; --text: #1e293b; --text-secondary: #64748b; --border: #d1d5db; --border-light: #e5e7eb; --danger: #dc2626; --success: #059669; --radius: 8px; --font: 'Segoe UI', system-ui, sans-serif; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font); background: var(--bg); color: var(--text); min-height: 100vh; }
    .admin-topbar { background: #fff; border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }
    .admin-topbar h1 { font-size: 18px; color: var(--primary); }
    .admin-container { max-width: 1400px; margin: 24px auto; padding: 0 24px; }
    .admin-card { background: #fff; border-radius: var(--radius); box-shadow: 0 1px 3px rgba(0,0,0,.08); padding: 20px; margin-bottom: 20px; }
    .admin-card h2 { font-size: 16px; margin-bottom: 12px; color: var(--text); }

    /* 登录页面 */
    .login-box { max-width: 400px; margin: 100px auto; }
    .login-box input { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 15px; margin-bottom: 12px; }
    .login-box button { width: 100%; }

    /* 按钮 */
    .btn { padding: 8px 16px; border: none; border-radius: var(--radius); cursor: pointer; font-size: 13px; font-family: var(--font); transition: background .15s; }
    .btn-primary { background: var(--primary); color: #fff; }
    .btn-primary:hover { background: #1d4ed8; }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-danger:hover { background: #b91c1c; }
    .btn-success { background: var(--success); color: #fff; }
    .btn-success:hover { background: #047857; }
    .btn-outline { background: #fff; color: var(--primary); border: 1px solid var(--primary); }
    .btn-outline:hover { background: var(--primary-light); }
    .btn-sm { padding: 4px 10px; font-size: 12px; }
    .btn-group { display: flex; gap: 6px; }

    /* 表格 */
    .admin-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .admin-table th, .admin-table td { padding: 6px 8px; border-bottom: 1px solid var(--border-light); text-align: left; white-space: nowrap; }
    .admin-table th { color: var(--text-secondary); font-weight: 600; background: #f8fafc; position: sticky; top: 0; }
    .admin-table tr:hover { background: #f8fafc; }
    .admin-table td.price { font-family: monospace; font-weight: 600; }
    .admin-table .active-badge { color: var(--success); font-weight: 600; }
    .admin-table .inactive-badge { color: var(--text-secondary); }
    .table-wrap { overflow-x: auto; max-height: 500px; overflow-y: auto; }

    /* 弹窗 */
    .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,.4); z-index: 999; justify-content: center; align-items: center; }
    .modal-overlay.show { display: flex; }
    .modal-content { background: #fff; border-radius: var(--radius); padding: 24px; max-width: 500px; width: 90%; max-height: 80vh; overflow-y: auto; }
    .modal-content h3 { margin-bottom: 16px; }
    .modal-content label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; margin-top: 10px; }
    .modal-content input, .modal-content select { width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }
    .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

    /* 表单 */
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .form-row label { margin-top: 6px; }
    .form-row input { width: 100%; }

    /* Toast */
    .toast { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: var(--radius); color: #fff; font-size: 14px; z-index: 2000; opacity: 0; transition: opacity .3s; }
    .toast.show { opacity: 1; }
    .toast-info { background: var(--primary); }
    .toast-error { background: var(--danger); }
    .toast-ok { background: var(--success); }

    .hidden { display: none !important; }
</style>
</head>
<body>

<!-- Toast -->
<div id="toast" class="toast"></div>

<!-- 登录界面 -->
<div id="login-page">
    <div class="login-box admin-card">
        <h2 style="text-align:center;">📈 StockSim 管理后台</h2>
        <p style="text-align:center;color:var(--text-secondary);margin-bottom:16px;">请输入管理员密码</p>
        <input type="password" id="login-password" placeholder="管理员密码" onkeypress="if(event.key==='Enter')doLogin()">
        <button class="btn btn-primary" onclick="doLogin()">登 录</button>
        <p id="login-error" style="color:var(--danger);text-align:center;margin-top:8px;font-size:13px;"></p>
    </div>
</div>

<!-- 管理面板 -->
<div id="admin-page" class="hidden">
    <div class="admin-topbar">
        <h1>📈 模拟股市管理后台</h1>
        <div class="btn-group">
            <button class="btn btn-outline btn-sm" onclick="showChangePwdModal()">修改密码</button>
            <button class="btn btn-danger btn-sm" onclick="doLogout()">退出</button>
        </div>
    </div>
    <div class="admin-container">
        <!-- 公司列表 -->
        <div class="admin-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <h2>🏭 模拟公司列表</h2>
                <button class="btn btn-primary" onclick="showAddModal()">+ 新增公司</button>
            </div>
            <div class="table-wrap">
                <table class="admin-table" id="company-table">
                    <thead>
                        <tr>
                            <th>代码</th><th>名称</th><th>初始价</th><th>drift</th><th>sigma</th>
                            <th>均值回归</th><th>tick_sigma</th><th>tick间隔</th><th>ticks/天</th>
                            <th>价格下限</th><th>价格上限</th><th>状态</th><th>操作</th>
                        </tr>
                    </thead>
                    <tbody id="company-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- 编辑/新增弹窗 -->
<div id="edit-modal" class="modal-overlay">
    <div class="modal-content">
        <h3 id="edit-modal-title">编辑公司</h3>
        <div class="form-row">
            <div><label>代码</label><input id="edit-code" placeholder="m00001"></div>
            <div><label>名称</label><input id="edit-name" placeholder="公司名称"></div>
            <div><label>初始价格</label><input id="edit-initial_price" type="number" step="0.01"></div>
            <div><label>daily_drift_mu</label><input id="edit-daily_drift_mu" type="number" step="0.0001"></div>
            <div><label>daily_sigma</label><input id="edit-daily_sigma" type="number" step="0.001"></div>
            <div><label>mean_reversion</label><input id="edit-mean_reversion" type="number" step="0.01"></div>
            <div><label>tick_sigma</label><input id="edit-tick_sigma" type="number" step="0.001"></div>
            <div><label>tick间隔(秒)</label><input id="edit-tick_interval_seconds" type="number" step="1"></div>
            <div><label>ticks/天</label><input id="edit-ticks_per_day" type="number" step="1"></div>
            <div><label>价格下限</label><input id="edit-price_min" type="number" step="0.01"></div>
            <div><label>价格上限</label><input id="edit-price_max" type="number" step="0.01"></div>
            <div><label>状态</label><select id="edit-is_active"><option value="true">启用</option><option value="false">停用</option></select></div>
        </div>
        <input type="hidden" id="edit-is-new">
        <div class="modal-actions">
            <button class="btn btn-outline" onclick="closeEditModal()">取消</button>
            <button class="btn btn-primary" onclick="saveCompany()">保存</button>
        </div>
    </div>
</div>

<!-- 修改密码弹窗 -->
<div id="pwd-modal" class="modal-overlay">
    <div class="modal-content" style="max-width:360px;">
        <h3>修改管理员密码</h3>
        <label>旧密码</label><input type="password" id="pwd-old">
        <label>新密码</label><input type="password" id="pwd-new">
        <div class="modal-actions">
            <button class="btn btn-outline" onclick="closePwdModal()">取消</button>
            <button class="btn btn-primary" onclick="changePassword()">确认修改</button>
        </div>
    </div>
</div>

<script>
// ── 全局状态 ────────────────────────────────────────────────────────
let adminToken = sessionStorage.getItem('admin_token');
const API = (url, opts = {}) => fetch(url, { ...opts, headers: { ...opts.headers, 'X-Admin-Token': adminToken || '', 'Content-Type': 'application/json' } });

// ── 初始化 ──────────────────────────────────────────────────────────
if (adminToken) { showPanel(); loadCompanies(); } else { showLogin(); }

function showLogin() { document.getElementById('login-page').classList.remove('hidden'); document.getElementById('admin-page').classList.add('hidden'); }
function showPanel() { document.getElementById('login-page').classList.add('hidden'); document.getElementById('admin-page').classList.remove('hidden'); }

async function doLogin() {
    const pw = document.getElementById('login-password').value;
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';
    try {
        const res = await fetch('/api/admin/auth', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw }) });
        if (!res.ok) { const d = await res.json(); errEl.textContent = d.detail || '登录失败'; return; }
        const d = await res.json();
        adminToken = d.access_token;
        sessionStorage.setItem('admin_token', adminToken);
        showPanel();
        loadCompanies();
    } catch (e) { errEl.textContent = '网络错误'; }
}

function doLogout() { sessionStorage.removeItem('admin_token'); adminToken = null; showLogin(); }

function toast(msg, type) { const t = document.getElementById('toast'); t.textContent = msg; t.className = 'toast toast-' + (type || 'info') + ' show'; setTimeout(() => t.classList.remove('show'), 2500); }

// ── 公司列表 ────────────────────────────────────────────────────────

async function loadCompanies() {
    const res = await API('/api/admin/companies');
    const data = await res.json();
    const tbody = document.getElementById('company-tbody');
    tbody.innerHTML = (data.companies || []).map(c => `
        <tr>
            <td><strong>${c.code}</strong></td>
            <td>${c.name}</td>
            <td>${c.initial_price}</td>
            <td>${c.daily_drift_mu.toFixed(4)}</td>
            <td>${c.daily_sigma.toFixed(3)}</td>
            <td>${c.mean_reversion.toFixed(2)}</td>
            <td>${c.tick_sigma.toFixed(3)}</td>
            <td>${c.tick_interval_seconds}</td>
            <td>${c.ticks_per_day}</td>
            <td>${c.price_min}</td>
            <td>${c.price_max}</td>
            <td>${c.is_active ? '<span class="active-badge">启用</span>' : '<span class="inactive-badge">停用</span>'}</td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-outline btn-sm" onclick="showEditModal('${c.code}')">编辑</button>
                    <button class="btn btn-outline btn-sm" onclick="resetCompany('${c.code}')">重置</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteCompany('${c.code}','${c.name}')">删除</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// ── 编辑弹窗 ────────────────────────────────────────────────────────

const FIELD_LIST = ['code','name','initial_price','daily_drift_mu','daily_sigma','mean_reversion','tick_sigma','tick_interval_seconds','ticks_per_day','price_min','price_max','is_active'];

function showAddModal() {
    document.getElementById('edit-modal-title').textContent = '新增公司';
    document.getElementById('edit-is-new').value = '1';
    FIELD_LIST.forEach(f => {
        const el = document.getElementById('edit-' + f);
        if (el) el.value = '';
    });
    document.getElementById('edit-is_active').value = 'true';
    document.getElementById('edit-code').disabled = false;
    document.getElementById('edit-modal').classList.add('show');
}

async function showEditModal(code) {
    const res = await API('/api/admin/companies/' + code);
    const c = await res.json();
    document.getElementById('edit-modal-title').textContent = '编辑 ' + code;
    document.getElementById('edit-is-new').value = '0';
    FIELD_LIST.forEach(f => {
        const el = document.getElementById('edit-' + f);
        if (el) el.value = c[f] != null ? c[f] : '';
    });
    document.getElementById('edit-code').disabled = true;
    document.getElementById('edit-modal').classList.add('show');
}

function closeEditModal() { document.getElementById('edit-modal').classList.remove('show'); }

async function saveCompany() {
    const isNew = document.getElementById('edit-is-new').value === '1';
    const body = {};
    FIELD_LIST.forEach(f => {
        const el = document.getElementById('edit-' + f);
        if (!el) return;
        let val = el.value;
        if (val === '' || val == null) return;
        if (['initial_price','daily_drift_mu','daily_sigma','mean_reversion','tick_sigma','price_min','price_max'].includes(f)) val = parseFloat(val);
        if (['tick_interval_seconds','ticks_per_day'].includes(f)) val = parseInt(val);
        if (f === 'is_active') val = val === 'true';
        body[f] = val;
    });

    const code = body.code || document.getElementById('edit-code').value;
    let res;
    if (isNew) {
        res = await API('/api/admin/companies', { method: 'POST', body: JSON.stringify(body) });
    } else {
        delete body.code;
        res = await API('/api/admin/companies/' + code, { method: 'PUT', body: JSON.stringify(body) });
    }
    if (res.ok) { toast(isNew ? '公司已创建' : '参数已更新', 'ok'); closeEditModal(); loadCompanies(); }
    else { const e = await res.json(); toast(e.detail || '操作失败', 'error'); }
}

// ── 删除 / 重置 ─────────────────────────────────────────────────────

async function deleteCompany(code, name) {
    if (!confirm(`确定要彻底删除 ${code} ${name} 吗？\n\n这将删除该公司所有的历史 K 线数据，此操作不可撤销！`)) return;
    const res = await API('/api/admin/companies/' + code + '/hard', { method: 'DELETE' });
    if (res.ok) { toast('已删除 ' + code, 'ok'); loadCompanies(); }
    else { const e = await res.json(); toast(e.detail || '删除失败', 'error'); }
}

async function resetCompany(code) {
    if (!confirm(`确定要重置 ${code} 吗？将清除所有历史 K 线，价格回到初始值。`)) return;
    const res = await API('/api/admin/companies/' + code + '/reset', { method: 'POST' });
    if (res.ok) { toast(code + ' 已重置', 'ok'); }
    else { const e = await res.json(); toast(e.detail || '重置失败', 'error'); }
}

// ── 修改密码 ────────────────────────────────────────────────────────

function showChangePwdModal() { document.getElementById('pwd-modal').classList.add('show'); }
function closePwdModal() { document.getElementById('pwd-modal').classList.remove('show'); }

async function changePassword() {
    const oldPwd = document.getElementById('pwd-old').value;
    const newPwd = document.getElementById('pwd-new').value;
    if (!oldPwd || !newPwd) { toast('请填写旧密码和新密码', 'error'); return; }
    const res = await API('/api/admin/password', { method: 'PUT', body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }) });
    if (res.ok) { toast('密码修改成功', 'ok'); closePwdModal(); }
    else { const e = await res.json(); toast(e.detail || '修改失败', 'error'); }
}

// 点击弹窗外部关闭
document.getElementById('edit-modal').addEventListener('click', function(e) { if (e.target === this) closeEditModal(); });
document.getElementById('pwd-modal').addEventListener('click', function(e) { if (e.target === this) closePwdModal(); });
</script>
</body>
</html>"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """返回管理后台页面。"""
    return HTMLResponse(ADMIN_HTML)
