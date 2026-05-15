"""泛微 OA SSO 单点登录接口"""
import logging

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
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
        max_age=8 * 3600,  # 8 小时
        httponly=False,  # 允许 JS 读取，方便登录页检测
        samesite="none",  # 允许 OA iframe 跨站携带
        secure=False,  # 内网 HTTP，不要求 HTTPS
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
    记录所有参数以便调试，当前支持：
    - ticket: CAS ticket（通过 checkToken 验证）
    - token: ssoToken（与 ticket 同等对待）
    - loginid: 用户登录名（若 OA 直接传递）
    """
    # 合并 ticket 和 token 参数
    tkt = ticket or token

    logger.info(
        f"SSO 回调: ticket={tkt}, loginid={loginid}, username={username}"
    )

    # 用 checkToken 验证 ticket，并通过 loginid 确定用户身份
    result = await sso_service.handle_oa_callback(db, ticket=tkt, loginid=loginid)
    return result


@router.get("/oa-login-page", summary="OA 统一认证登录页面（后端直出 HTML）")
def sso_oa_login_page():
    """返回完整的 OA 统一认证登录 HTML 页面，绕过 SPA 适合 OA iframe 嵌入"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OA 统一认证 - PMS</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: flex; align-items: center; justify-content: center;
  min-height: 100vh; background: #f0f2f5;
}}
.card {{
  background: #fff; border-radius: 8px; padding: 40px 36px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08); width: 380px; text-align: center;
}}
.icon {{ margin-bottom: 16px; font-size: 48px; }}
.title {{ font-size: 20px; color: #303133; margin-bottom: 8px; }}
.hint {{ color: #909399; margin-bottom: 24px; font-size: 14px; }}
.input {{
  width: 100%; padding: 10px 14px; font-size: 15px;
  border: 1px solid #dcdfe6; border-radius: 6px; outline: none;
  box-sizing: border-box;
}}
.input:focus {{ border-color: #409EFF; }}
.btn {{
  width: 100%; padding: 10px; font-size: 16px; margin-top: 16px;
  background: #409EFF; color: #fff; border: none; border-radius: 6px;
  cursor: pointer;
}}
.btn:hover {{ background: #337ECC; }}
.btn:disabled {{ background: #a0cfff; cursor: not-allowed; }}
.error {{ color: #F56C6C; margin-top: 12px; font-size: 13px; }}
.footer {{ margin-top: 20px; color: #b0b0b0; font-size: 13px; }}
.footer a {{ color: #409EFF; text-decoration: none; }}
</style>
</head>
<body>
<div class="card">
  <div class="icon">&#128274;</div>
  <div class="title">OA 统一认证登录</div>
  <!-- 自动登录状态 -->
  <div class="hint" id="autoStatus" style="color:#E6A23C;">正在自动登录...</div>
  <!-- 登录表单（自动登录成功则隐藏） -->
  <div class="hint" id="formHint">请输入您的 OA 工号，系统将自动验证身份</div>
  <form id="loginForm" style="display:none">
    <input class="input" id="loginid" name="loginid" placeholder="请输入 OA 工号" required autofocus />
    <button class="btn" type="submit" id="submitBtn">统一认证登录</button>
  </form>
  <div class="error" id="error"></div>
  <div class="footer">
    也可使用 <a href="/login">账号密码登录</a>
  </div>
</div>
<script>
// 跳转到 PMS 前台（iframe 内导航，始终可用）
function goToPms(token) {{
  // 保存 token 到 localStorage，下次自动登录
  try {{ localStorage.setItem('pms_token', token); }} catch(e) {{}}
  var pmsUrl = 'http://10.10.91.60:5174/?token=' + encodeURIComponent(token);
  // 优先在 iframe 内跳转到 PMS（作为 OA 子页面展示）
  window.location.href = pmsUrl;
}}

// 页面加载时检查 localStorage 中是否有 pms_token，有则自动登录
async function autoLogin() {{
  var token = null;
  try {{ token = localStorage.getItem('pms_token'); }} catch(e) {{}}
  if (!token) return false;

  try {{
    var resp = await fetch('/api/auth/me', {{
      headers: {{ 'Authorization': 'Bearer ' + token }}
    }});
    if (resp.ok) {{
      goToPms(token);
      return true;
    }} else {{
      // token 过期，清除
      try {{ localStorage.removeItem('pms_token'); }} catch(e) {{}}
    }}
  }} catch(e) {{}}
  return false;
}}

// 显示登录表单
function showLoginForm() {{
  document.getElementById('loginForm').style.display = '';
  document.getElementById('formHint').style.display = '';
  document.getElementById('autoStatus').style.display = 'none';
}}

// 提交登录
document.getElementById('loginForm').addEventListener('submit', async function(e) {{
  e.preventDefault();
  var loginid = document.getElementById('loginid').value.trim();
  var btn = document.getElementById('submitBtn');
  var errorEl = document.getElementById('error');

  if (!loginid) {{
    errorEl.textContent = '请输入 OA 工号';
    return;
  }}

  btn.disabled = true;
  btn.textContent = '正在验证...';
  errorEl.textContent = '';

  try {{
    var resp = await fetch('/api/sso/oa-login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ loginid: loginid }}),
    }});

    if (resp.ok) {{
      var data = await resp.json();
      goToPms(data.access_token);
    }} else {{
      var data = await resp.json();
      errorEl.textContent = data.detail || 'OA 认证失败，请检查工号是否正确';
    }}
  }} catch (err) {{
    errorEl.textContent = '网络错误，请重试';
  }} finally {{
    btn.disabled = false;
    btn.textContent = '统一认证登录';
  }}
}});

// 启动：尝试自动登录，失败则显示表单
autoLogin().then(function(ok) {{
  if (!ok) showLoginForm();
}});
</script>
</body>
</html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
