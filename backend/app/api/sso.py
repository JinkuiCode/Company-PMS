"""泛微 OA SSO 单点登录接口"""
import logging

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.services import sso as sso_service

router = APIRouter(prefix="/api/sso", tags=["SSO 单点登录"])
logger = logging.getLogger(__name__)


class SsoVerifyRequest(BaseModel):
    token: str


class SsoUrlRequest(BaseModel):
    loginid: str
    username: str
    dept: str = ""


class SsoOaLoginRequest(BaseModel):
    loginid: str
    username: str = ""
    dept: str = ""


class SsoOaPasswordLoginRequest(BaseModel):
    loginid: str  # OA 工号
    password: str  # OA 密码
    remember_me: bool = False  # 是否开启长期免密登录


@router.post("/oa-password-login", summary="PMS 账号密码登录（OA 菜单跳转入口）")
def sso_oa_password_login(req: SsoOaPasswordLoginRequest, db: Session = Depends(get_db)):
    """PMS 账号密码验证，成功后签发 JWT。勾选记住我时额外生成长期免密令牌并种 Cookie。"""
    result = sso_service.sso_login_by_password(
        db, req.loginid, req.password, req.remember_me,
    )
    resp = JSONResponse(content=result)
    resp.set_cookie(
        key="pms_token",
        value=result["access_token"],
        max_age=8 * 3600,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )
    # 勾选记住我：种长期 Cookie（HttpOnly=False 允许 JS 在 iframe 中通过 document.cookie 读取）
    if req.remember_me and "remember_token" in result:
        resp.set_cookie(
            key="pms_remember",
            value=result["remember_token"],
            max_age=settings.REMEMBER_TOKEN_EXPIRE_DAYS * 24 * 3600,
            httponly=False,  # JS 需可读，iframe 中通过 document.cookie 拿到免密令牌
            samesite="lax",
            secure=False,
            path="/",
        )
    return resp


@router.post("/verify", summary="验证 SSO Token（AES 加密）并返回 JWT")
def sso_verify(req: SsoVerifyRequest, db: Session = Depends(get_db)):
    """泛微 OA 传来的加密 token，验证后签发 PMS 的 JWT"""
    return sso_service.sso_login(db, req.token)


@router.get("/url/verify", summary="验证 SSO URL 参数（HMAC 签名）并返回 JWT")
def sso_url_verify(
    loginid: str = Query(...),
    username: str = Query(...),
    dept: str = Query(""),
    ts: int = Query(...),
    sign: str = Query(...),
    db: Session = Depends(get_db),
):
    """URL 参数方式 SSO 登录，适合 OA 菜单直接配置"""
    return sso_service.sso_login_by_params(db, loginid, username, dept, ts, sign)


@router.post("/oa-login", summary="OA 统一认证登录")
async def sso_oa_login(req: SsoOaLoginRequest, db: Session = Depends(get_db)):
    """通过 OA getToken API 验证用户身份，成功后签发 PMS JWT 并设置 Cookie"""
    result = await sso_service.sso_login_by_loginid(
        db, req.loginid, req.username or req.loginid, req.dept,
    )
    # 设置 Cookie，以便下次自动登录（SameSite=Lax 允许 iframe 内的请求携带）
    resp = JSONResponse(content=result)
    resp.set_cookie(
        key="pms_token",
        value=result["access_token"],
        max_age=8 * 3600,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )
    return resp


@router.post("/generate-url", summary="生成 SSO 链接（管理工具）")
def sso_generate_url(req: SsoUrlRequest):
    """输入用户信息，返回带签名的 SSO URL"""
    url = sso_service.generate_sso_url(req.loginid, req.username, req.dept)
    return {"url": url}


# ==================== OA 统一认证中心（CAS 流程） ====================


@router.get("/oa-redirect", summary="重定向到 OA 统一认证登录页")
def sso_oa_redirect():
    """将浏览器重定向到 OA 统一认证登录页，登录后 OA 会回调到 /sso/callback"""
    oa_login_url = sso_service.build_oa_login_url()
    logger.info(f"SSO 重定向到 OA: {oa_login_url}")
    return RedirectResponse(url=oa_login_url, status_code=302)


@router.get("/callback", summary="OA 统一认证回调")
async def sso_oa_callback(
    ticket: str = Query(""),
    loginid: str = Query(""),
    token: str = Query(""),
    username: str = Query(""),
    db: Session = Depends(get_db),
):
    """
    OA 统一认证回调端点。OA 登录成功后重定向到此地址。
    当前支持：
    - ticket: CAS ticket（通过 checkToken 验证，必要时用 serviceValidate 获取用户）
    - token: ssoToken（与 ticket 同等对待）
    - loginid: 用户登录名（若 OA 直接传递，可跳过 CAS 解析步骤）
    """
    tkt = ticket or token
    service_url = settings.PMS_CALLBACK_URL

    logger.info(
        f"SSO 回调: ticket={tkt}, loginid={loginid}, username={username}"
    )

    result = await sso_service.handle_oa_callback(
        db, ticket=tkt, loginid=loginid, service_url=service_url
    )
    return result


@router.get("/oa-login-page", summary="OA 菜单跳转 PMS 入口")
def sso_oa_login_page(request: Request, db: Session = Depends(get_db)):
    """OA 菜单跳转入口。
    通道1: Cookie 免密（弹出窗口/直接访问，SameSite=Lax 在顶级导航时发送）。
    通道2: 无 Cookie 时返回 HTML 页，在浏览器中通过 localStorage 免密令牌自动登录。
    """
    ft = settings.PMS_FRONTEND_URL
    be = str(request.base_url).rstrip("/")  # 后端地址，供 HTML 中的 fetch 使用

    # 通道1：服务端 Cookie 免密
    remember = request.cookies.get("pms_remember")
    if remember:
        from app.services import auth as auth_service
        try:
            result = auth_service.auto_login(db, remember)
            new_token = result.access_token
            resp = RedirectResponse(url=f"{ft}/?token={new_token}", status_code=302)
            resp.set_cookie(
                key="pms_token", value=new_token, max_age=8 * 3600,
                httponly=False, samesite="lax", secure=False, path="/",
            )
            return resp
        except Exception:
            pass  # Cookie 失效，继续走通道2

    # 通道2：返回自包含 HTML 页，通过 localStorage 免密令牌自动登录
    html = _build_oa_login_html(ft, be)
    resp = HTMLResponse(content=html, status_code=200)
    resp.set_cookie(
        key="pms_remember", value="", max_age=0,
        path="/", samesite="lax", secure=False,
    )
    return resp


def _build_oa_login_html(frontend_url: str, backend_url: str) -> str:
    """构建 OA 跳转 PMS 的自包含登录 HTML 页"""
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>PMS 项目管理系统</title>
<style>
:root {{ --pms-bg:#f6f8fb; --pms-surface:#fff; --pms-border:#edf1f6; --pms-text:#162033; --pms-text-secondary:#667085; --pms-primary:#4f46e5; --pms-primary-hover:#4338ca; --pms-warning:#d97706; --pms-danger:#dc2626; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--pms-bg); color:var(--pms-text); display:flex; justify-content:center; align-items:center; min-height:100vh; padding:24px; }}
.card {{ background:var(--pms-surface); border:1px solid var(--pms-border); border-radius:8px; padding:38px 34px 30px; text-align:center; box-shadow:0 1px 2px rgba(16,24,40,.05); width:380px; max-width:100%; }}
h2 {{ font-size:20px; line-height:1.25; color:var(--pms-text); margin-bottom:12px; font-weight:700; }}
.hint {{ color:var(--pms-text-secondary); font-size:14px; line-height:1.6; margin-bottom:20px; }}
.loading {{ color:var(--pms-warning); font-size:14px; }}
.spinner {{ width:32px; height:32px; border:3px solid #e8edf5; border-top-color:var(--pms-primary); border-radius:50%; animation:spin .8s linear infinite; margin:0 auto 16px; }}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}
.input-group {{ margin-bottom:16px; text-align:left; }}
.input-group label {{ display:block; font-size:13px; color:var(--pms-text-secondary); margin-bottom:6px; }}
.input-group input {{ width:100%; height:40px; border:1px solid #dfe5ee; border-radius:6px; padding:0 12px; font-size:14px; outline:none; color:var(--pms-text); }}
.input-group input:focus {{ border-color:var(--pms-primary); box-shadow:0 0 0 3px rgba(79,70,229,.12); }}
.check-row {{ text-align:left; margin-bottom:20px; font-size:13px; color:var(--pms-text-secondary); display:flex; align-items:center; gap:6px; }}
.check-row input[type=checkbox] {{ accent-color:var(--pms-primary); }}
.btn {{ width:100%; height:40px; background:var(--pms-primary); color:#fff; border:none; border-radius:6px; font-size:15px; font-weight:600; cursor:pointer; }}
.btn:hover {{ background:var(--pms-primary-hover); }}
.btn:disabled {{ background:#a5b4fc; cursor:not-allowed; }}
.error {{ color:var(--pms-danger); font-size:13px; margin-top:12px; display:none; }}
.hidden {{ display:none; }}
</style>
</head>
<body>
<div class="card">
  <div id="autoBlock">
    <div class="spinner"></div>
    <p class="loading">正在验证登录状态...</p>
  </div>
  <div id="formBlock" class="hidden">
    <h2>PMS 项目管理系统</h2>
    <p class="hint">请输入您的 <strong>PMS 账号和密码</strong></p>
    <div class="input-group"><label>账号</label><input type="text" id="username" placeholder="PMS 账号" autocomplete="username"></div>
    <div class="input-group"><label>密码</label><input type="password" id="password" placeholder="PMS 密码" autocomplete="current-password"></div>
    <div class="check-row"><input type="checkbox" id="rememberMe" checked><label for="rememberMe">记住我（半年内免密登录）</label></div>
    <button class="btn" id="loginBtn" onclick="doLogin()">登录 PMS</button>
    <p class="error" id="errorMsg"></p>
  </div>
</div>
<script>
var FRONTEND = '{frontend_url}';
var BACKEND = '{backend_url}';

function $(id) {{ return document.getElementById(id); }}

function showForm() {{
  $('autoBlock').classList.add('hidden');
  $('formBlock').classList.remove('hidden');
}}

function showError(msg) {{
  var el = $('errorMsg');
  el.textContent = msg;
  el.style.display = 'block';
}}

// 从 document.cookie 中读取指定 key 的值
function getCookie(name) {{
  var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : null;
}}

// 检测 localStorage 是否可用
function hasStorage() {{
  try {{ localStorage.setItem("_t","1"); localStorage.removeItem("_t"); return true; }}
  catch(e) {{ return false; }}
}}

// 用免密令牌自动登录（多通道：Cookie > localStorage）
async function tryAutoLogin() {{
  var rt = null;

  // 通道A：从 Cookie 读取 pms_remember（跨会话持久化，iframe 中也可读）
  rt = getCookie("pms_remember");
  if (rt) {{
    var ok = await doAutoLogin(rt);
    if (ok) return;
  }}

  // 通道B：从 localStorage 读取 pms_remember_token（同会话 iframe 分区持久化）
  if (hasStorage()) {{
    rt = localStorage.getItem("pms_remember_token");
    if (rt) {{
      var ok = await doAutoLogin(rt);
      if (ok) return;
      localStorage.removeItem("pms_remember_token");
    }}
  }}

  showForm();
}}

// 用免密令牌调用后端换取 JWT
async function doAutoLogin(rt) {{
  try {{
    var resp = await fetch(BACKEND + "/api/auth/auto-login", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ remember_token: rt }})
    }});
    if (resp.ok) {{
      var data = await resp.json();
      if (data.access_token) {{
        if (hasStorage()) {{
          localStorage.setItem("access_token", data.access_token);
          if (data.remember_token) {{
            localStorage.setItem("pms_remember_token", data.remember_token);
          }}
        }}
        window.location.href = FRONTEND + "/?token=" + data.access_token;
        return true;
      }}
    }}
  }} catch(e) {{}}
  return false;
}}

// 登录
async function doLogin() {{
  var btn = $("loginBtn");
  var username = $("username").value.trim();
  var password = $("password").value;
  var rememberMe = $("rememberMe").checked;

  if (!username || !password) {{ showError("请输入账号和密码"); return; }}

  btn.disabled = true;
  btn.textContent = "正在验证...";
  $("errorMsg").style.display = "none";

  try {{
    var resp = await fetch(BACKEND + "/api/sso/oa-password-login", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ loginid: username, password: password, remember_me: rememberMe }})
    }});
    var data = await resp.json();
    if (resp.ok && data.access_token) {{
      localStorage.setItem("access_token", data.access_token);
      if (data.remember_token) {{
        localStorage.setItem("pms_remember_token", data.remember_token);
      }}
      window.location.href = FRONTEND + "/?token=" + data.access_token;
    }} else {{
      showError(data.detail || "账号或密码错误");
    }}
  }} catch(e) {{
    showError("网络错误，请检查连接后重试");
  }}

  btn.disabled = false;
  btn.textContent = "登录 PMS";
}}

// 回车键登录
$("password").addEventListener("keydown", function(e) {{
  if (e.key === "Enter") doLogin();
}});

// 启动
tryAutoLogin();
</script>
</body>
</html>'''
