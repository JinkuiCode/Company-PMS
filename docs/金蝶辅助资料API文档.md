一、请求参数说明：
1.formid：业务对象表单Id，字符串类型（必录）
2.data：JSON格式数据（详情参考JSON格式数据）（必录）
     2.1.NeedUpDateFields：需要更新的字段，数组类型，格式：[key1,key2,...] （非必录）注（更新字段时Model数据包中必须设置内码，若更新单据体字段还需设置分录内码）
     2.2.NeedReturnFields：需返回结果的字段集合，数组类型，格式：[key,entitykey.key,...]（非必录） 注（返回单据体字段格式：entitykey.key）
     2.3.IsDeleteEntry：是否删除已存在的分录，布尔类型，默认true（非必录）
     2.4.SubSystemId：表单所在的子系统内码，字符串类型（非必录）
     2.5.IsVerifyBaseDataField：是否验证所有的基础资料有效性，布尔类，默认false（非必录）
     2.6.IsEntryBatchFill：是否批量填充分录，默认true（非必录）
     2.7.ValidateFlag：是否验证数据合法性标志，布尔类型，默认true（非必录）注（设为false时不对数据合法性进行校验）
     2.8.NumberSearch：是否用编码搜索基础资料，布尔类型，默认true（非必录）
     2.9.IsAutoAdjustField：是否自动调整JSON字段顺序，布尔类型，默认false（非必录）
     2.10.InterationFlags：交互标志集合，字符串类型，分号分隔，格式："flag1;flag2;..."（非必录） 例如（允许负库存标识：STK_InvCheckResult）
     2.11.IgnoreInterationFlag：是否允许忽略交互，布尔类型，默认true（非必录）
     2.12.IsControlPrecision：是否控制精度，为true时对金额、单价和数量字段进行精度验证，默认false（非必录）
     2.13.ValidateRepeatJson：校验Json数据包是否重复传入，一旦重复传入，接口调用失败，默认false（非必录）
     2.14.Model：表单数据包，JSON类型（必录）
备注:
1.示例Model数据包中字段顺序不建议改变，否则可能会有相互影响，如果出现字段值被覆盖或丢失，则可以尝试把字段顺序向后调整一下。
2.示例Model数据包默认包含允许引入的字段，实际按需构建既可。
3.如需创建关联关系，可参考http://club.kingdee.com/forum.php?mod=viewthread&tid=1394265 。

二、返回结果：
{"Result":{"ResponseStatus":{"ErrorCode":"","IsSuccess":"false","Errors":[{"FieldName":"","Message":"","DIndex":0}],"SuccessEntitys":[{"Id":"","Number":"","DIndex":0}],"SuccessMessages":[{"FieldName":"","Message":"","DIndex":0}],"MsgCode":""},"Id":"","Number":"","NeedReturnData":[{}]}}

三、代码示例：
// 引用SDK组件Kingdee.BOS.WebApi.Client.dll；SDK下载地址：https://openapi.open.kingdee.com/ApiSdkCenter
var client = new K3CloudApi();
// 初始化登录认证，appID、appSec可在"第三方系统登录授权"中获取
client.InitClient("6a1fd19d9e068f", "appID", "appSec", "userName", 2052, "100", "https://10.10.1.248/k3cloud/");
client.Save("BOS_ASSISTANTDATA_DETAIL","{"NeedUpDateFields":[],"NeedReturnFields":[],"IsDeleteEntry":"true","SubSystemId":"","IsVerifyBaseDataField":"false","IsEntryBatchFill":"true","ValidateFlag":"true","NumberSearch":"true","IsAutoAdjustField":"false","InterationFlags":"","IgnoreInterationFlag":"","IsControlPrecision":"false","ValidateRepeatJson":"false","Model":{"FEntryID":"","FNumber":"","FDataValue":"","FId":{"FNumber":""},"FParentId":"","FSeq":0,"FDescription":"","FCreateOrgId":{"FNumber":""},"FUseOrgId":{"FNumber":""},"F_TWBJ_Text_qtr":"","F_TWBJ_Combo_re5":"","F_TWBJ_Integer_apv":0,"F_TWBJ_Integer_tzk":0,"F_TWBJ_Decimal_ca9":0}}");

四、JSON格式数据：
{
    "NeedUpDateFields": [],
    "NeedReturnFields": [],
    "IsDeleteEntry": "true",
    "SubSystemId": "",
    "IsVerifyBaseDataField": "false",
    "IsEntryBatchFill": "true",
    "ValidateFlag": "true",
    "NumberSearch": "true",
    "IsAutoAdjustField": "false",
    "InterationFlags": "",
    "IgnoreInterationFlag": "",
    "IsControlPrecision": "false",
    "ValidateRepeatJson": "false",
    "Model": {
        "FEntryID": "",
        "FNumber": "",
        "FDataValue": "",
        "FId": {
            "FNumber": ""
        },
        "FParentId": "",
        "FSeq": 0,
        "FDescription": "",
        "FCreateOrgId": {
            "FNumber": ""
        },
        "FUseOrgId": {
            "FNumber": ""
        },
        "F_TWBJ_Text_qtr": "",
        "F_TWBJ_Combo_re5": "",
        "F_TWBJ_Integer_apv": 0,
        "F_TWBJ_Integer_tzk": 0,
        "F_TWBJ_Decimal_ca9": 0
    }
}

五、字段说明：
辅助资料：FBillHead 
	 实体主键：FEntryID 
	 编码：FNumber  (必填项)
	 名称：FDataValue  (必填项)
	 备注：FDescription 
	 类别：FId  (必填项)
	 系统预置：FIsSysPreset 
	 显示顺序：FSeq 
	 创建组织：FCreateOrgId 
	 使用组织：FUseOrgId 
	 创建人：FCreatorId 
	 创建日期：FCreateDate 
	 修改人：FModifierId 
	 修改日期：FModifyDate 
	 禁用日期：FForbidDate 
	 禁用人：FForbiderId 
	 禁用状态：FForbidStatus 
	 数据状态：FDocumentStatus 
	 审核人：FApproverID 
	 审核日期：FApproveDate 
	 上级资料：FParentId 
	 地址：F_TWBJ_Text_qtr 
	 费用类型：F_TWBJ_Combo_re5 
	 年份：F_TWBJ_Integer_apv 
	 季度：F_TWBJ_Integer_tzk 
	 金额：F_TWBJ_Decimal_ca9 

备注：错误代码MsgCode说明
           0：默认
           1：上下文丢失
           2：没有权限
           3：操作标识为空
           4：异常
           5：单据标识为空
           6：数据库操作失败
           7：许可错误
           8：参数错误
           9：指定字段/值不存在
           10：未找到对应数据
           11：验证失败
           12：不可操作
           13：网控冲突
           14：调用限制
           15：禁止管理员登录