<%@ page language="java" contentType="text/html; charset=UTF-8" %>
<%@ page import="weaver.hrm.User" %>
<%@ page import="weaver.hrm.HrmUserVarify" %>
<%@ page import="javax.crypto.Mac" %>
<%@ page import="javax.crypto.spec.SecretKeySpec" %>
<%@ page import="java.util.Base64" %>
<%
    // 1. 获取OA当前用户
    User hrmUser = HrmUserVarify.getUser(request, response);
    if (hrmUser == null) {
        response.sendRedirect("/login/Login.jsp"); // 未登录踢回OA登录页
        return;
    }

    // 2. 获取登录账号
    String loginId = hrmUser.getLoginid();
    long timestamp = System.currentTimeMillis() / 1000; // 秒级时间戳

    // 3. 生成 HMAC-SHA256 签名（双方约定密钥，与 PMS 后端 SSO_SECRET_KEY 一致）
    String secretKey = "weaver-sso-secret-32byte-key!!";
    // 签名格式与 PMS 后端 _make_sign 一致: loginid|username|dept|ts（无 username/dept 时填空字符串）
    String signData = loginId + "|||" + timestamp;
    Mac mac = Mac.getInstance("HmacSHA256");
    SecretKeySpec keySpec = new SecretKeySpec(secretKey.getBytes("UTF-8"), "HmacSHA256");
    mac.init(keySpec);
    byte[] signBytes = mac.doFinal(signData.getBytes("UTF-8"));
    // 转为十六进制字符串（与 Python hexdigest 一致）
    StringBuilder sb = new StringBuilder();
    for (byte b : signBytes) {
        sb.append(String.format("%02x", b));
    }
    String sign = sb.toString();

    // 4. 302 重定向到 PMS 前端 SSO 免密登录页
    String pmsUrl = "http://10.10.91.60:5174/sso/start?sso_login_id="
        + java.net.URLEncoder.encode(loginId, "UTF-8")
        + "&ts=" + timestamp
        + "&sign=" + sign;
    response.sendRedirect(pmsUrl);
%>