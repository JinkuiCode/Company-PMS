package weaver.interfaces.workflow.action.javacode;

import weaver.interfaces.workflow.action.Action;
import weaver.general.BaseBean;
import weaver.soa.workflow.request.RequestInfo;
import weaver.soa.workflow.request.Property;

// 引入泛微自带的JSON包和HTTP包
import com.alibaba.fastjson.JSONObject;
import com.alibaba.fastjson.JSONArray;
import org.apache.http.HttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * 在线自定义action接口 - 流程归档推送到金蝶云星空（物料保存）
 */
public class Action20260128015019 extends BaseBean implements Action {

    // ================= 1. 金蝶配置信息 =================
    // 注意：建议优先使用 http 避免内网IP证书报错，如果必须https请确保服务器信任该证书
    private static final String K3_URL = "http://10.10.1.248/k3cloud";
    private static final String DB_ID = "69420d0e5ae609"; // 账套ID
    private static final String USER_NAME = "I0003";      // 账号
    private static final String PASSWORD = "Qw123456.";   // 密码
    private static final String FORM_ID = "BD_MATERIAL";  // 目标单据：物料
    // =================================================

    public String execute(RequestInfo request) {
        String requestId = request.getRequestid();
        writeLog("【开始】物料推送金蝶 Action. RequestID: " + requestId);

        CloseableHttpClient httpClient = HttpClients.createDefault();
        try {
            // --- 第一步：获取OA流程表单数据 ---
            // 将主表数据放入Map中，方便按字段名取值
            Map<String, String> oaData = new HashMap<>();
            Property[] properties = request.getMainTableInfo().getProperty();
            for (Property prop : properties) {
                // key转小写，方便后续取值
                oaData.put(prop.getName().toLowerCase(), prop.getValue());
            }

            // 调试：打印一下获取到的OA数据，方便你看日志核对字段名
            writeLog("获取到的OA表单数据: " + JSONObject.toJSONString(oaData));

            // --- 第二步：登录金蝶 ---
            String cookies = loginK3(httpClient);
            if (cookies == null) {
                request.getRequestManager().setMessageid("90001");
                request.getRequestManager().setMessagecontent("金蝶登录失败，请检查账号密码或网络连通性。");
                return Action.FAILURE_AND_CONTINUE;
            }

            // --- 第三步：组装并发送物料数据 ---
            boolean success = saveMaterialToK3(httpClient, oaData);

            if (success) {
                return Action.SUCCESS;
            } else {
                request.getRequestManager().setMessageid("90002");
                request.getRequestManager().setMessagecontent("推送到金蝶失败，请检查OA日志详情。");
                return Action.FAILURE_AND_CONTINUE;
            }

        } catch (Exception e) {
            writeLog("接口异常: " + e);
            request.getRequestManager().setMessagecontent("系统异常：" + e.getMessage());
            return Action.FAILURE_AND_CONTINUE;
        } finally {
            try { httpClient.close(); } catch (IOException e) {}
        }
    }

    /**
     * 登录金蝶获取Session
     */
    private String loginK3(CloseableHttpClient client) throws Exception {
        String loginUrl = K3_URL + "/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc";

        JSONObject json = new JSONObject();
        json.put("acctID", DB_ID);
        json.put("username", USER_NAME);
        json.put("password", PASSWORD);
        json.put("lcid", 2052);

        HttpPost post = new HttpPost(loginUrl);
        post.setHeader("Content-Type", "application/json");
        post.setEntity(new StringEntity(json.toJSONString(), StandardCharsets.UTF_8));

        HttpResponse res = client.execute(post);
        String result = EntityUtils.toString(res.getEntity(), StandardCharsets.UTF_8);

        JSONObject resObj = JSONObject.parseObject(result);
        if (resObj != null && resObj.getInteger("LoginResultType") == 1) {
            writeLog("金蝶登录成功");
            return "SessionActive";
        } else {
            writeLog("金蝶登录失败: " + result);
            return null;
        }
    }

    /**
     * 组装物料JSON并保存
     */
    private boolean saveMaterialToK3(CloseableHttpClient client, Map<String, String> oaData) throws Exception {
        String saveUrl = K3_URL + "/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.Save.common.kdsvc";

        // =================================================================
        // 核心区域：字段映射 (请根据你OA表单的实际数据库字段名修改)
        // =================================================================

        // 假设OA表单里的字段名如下（你需要改成你真实的字段名）：
        String code = oaData.get("wlbm"); // 物料编码
        String name = oaData.get("wlmc"); // 物料名称
        String orgNo = "001";//oaData.get("zzbm"); // 组织编码 (金蝶里的编码，如 100)
       // String groupNo = oaData.get("wlfz"); // 物料分组编码
        //String unitNo = oaData.get("jldw"); // 计量单位编码

        // 必填项校验 (防止传空值给金蝶导致报错)
        if(code == null || name == null || orgNo == null) {
            writeLog("错误：OA表单中关键字段为空，无法推送。请检查映射代码。");
            return false;
        }

        // --- 构建 Model (参考你提供的JSON结构，但剔除了无用的空字段) ---
        JSONObject model = new JSONObject();
        model.put("FMATERIALID", 0); // 0代表新增
        model.put("FNumber", code);  // 物料编码
        model.put("FName", name);    // 物料名称
        model.put("FDescription", name); // 描述

        // 创建组织 (关键)
        JSONObject createOrg = new JSONObject(); createOrg.put("FNumber", orgNo);
        model.put("FCreateOrgId", createOrg);

        // 使用组织 (关键)
        JSONObject useOrg = new JSONObject(); useOrg.put("FNumber", orgNo);
        model.put("FUseOrgId", useOrg);

        // 物料分组
//        if(groupNo != null && !groupNo.isEmpty()){
//            JSONObject group = new JSONObject(); group.put("FNumber", groupNo);
//            model.put("FMaterialGroup", group);
//        }


        // 基本单位 (SubHeadEntity)
//        if(unitNo != null && !unitNo.isEmpty()){
//            JSONObject subHead = new JSONObject();
//            JSONObject unit = new JSONObject(); unit.put("FNumber", unitNo); // 如 "Pcs"
//            subHead.put("FBaseUnitId", unit);
//            model.put("SubHeadEntity", subHead);
//        }

        // *如果你需要传更多字段，请仿照上面继续 model.put(...) *
        // 例如：model.put("FSpecification", oaData.get("ggxh"));

        // --- 构建 Data ---
        JSONObject dataParams = new JSONObject();
        dataParams.put("NeedUpDateFields", new JSONArray());
        dataParams.put("NeedReturnFields", new String[]{"FMATERIALID", "FNumber"});
        dataParams.put("IsDeleteEntry", "true");
        dataParams.put("IsVerifyBaseDataField", "false");
        dataParams.put("IsEntryBatchFill", "true");
        dataParams.put("Model", model);

        // --- 构建最终 Payload ---
        JSONObject finalPayload = new JSONObject();
        finalPayload.put("formid", FORM_ID); // BD_MATERIAL
        finalPayload.put("data", dataParams.toJSONString()); // 金蝶要求data
        // 是字符串

        writeLog("推送给金蝶的数据: " + finalPayload.toJSONString());

        // 发送请求
        HttpPost post = new HttpPost(saveUrl);
        post.setHeader("Content-Type", "application/json");
        post.setEntity(new StringEntity(finalPayload.toJSONString(), StandardCharsets.UTF_8));

        HttpResponse res = client.execute(post);
        String result = EntityUtils.toString(res.getEntity(), StandardCharsets.UTF_8);
        writeLog("金蝶保存返回: " + result);





        // 解析结果
        JSONObject resObj = JSONObject.parseObject(result);
        JSONObject resultBody = resObj.getJSONObject("Result");
        JSONObject responseStatus = resultBody.getJSONObject("ResponseStatus");

        if (responseStatus.getBoolean("IsSuccess")) {
            writeLog("金蝶物料创建成功！");
            return true;
        } else {
            writeLog("金蝶报错: " + responseStatus.getJSONArray("Errors").toJSONString());
            return false;
        }
    }
}