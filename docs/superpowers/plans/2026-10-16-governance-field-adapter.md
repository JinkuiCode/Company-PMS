# 字段元数据与结构化错误适配实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans 内联实施。

**Goal:** 落实已确认治理第四节的字段状态/后端错误共享适配，以档案新增和现有详情表单为试点，不改字段规则或授权。

**Architecture:** 纯TypeScript解析器将生效元数据和页面代码上限合并为显示/编辑/必填/列表/只读原因；另将后端结构化字段错误投影到当前可见字段，按页面字段顺序定位。业务历史必填、锁及权限判断保留原适配，后端仍承担最终校验。

**Tech Stack:** TypeScript、Vue3、既有PmsFormField/ArchiveRecordForm。

## Global Constraints

已有规范与已确认字段逻辑是唯一基线；不新建接口、不改字段策略或枚举，不增加授权，不改数据库/业务数据；无新布局，不部署、发信、合并推送。

## Task 1：适配函数与测试

新增 `frontend/src/form-system/fieldMetadata.ts`、`frontend/tests/field-metadata.test.mjs`，在index导出。
接口：`resolveFieldMetadata(policy, {hidden?,readonly?,required?,readonlyReason?})`；`mapFormFieldErrors(error, fieldsInOrder, visible)`返回errors与firstField。解析已知字段规则错误、唯一性错误及FastAPI字段校验数组，未知/不可见字段不进入控件。

- [x] RED：配置不能放宽代码只读/隐藏上限；隐藏字段不必输；历史必填由原适配传入；列表状态与可见一致；服务器字段错误按表单顺序，忽略隐藏/未知/非字段错误。
- [x] 实现并GREEN；结构化错误仅接收字符串消息，不将对象或内部路径当业务文字。

## Task 2：档案适配及浏览器验证

- [x] 档案visible/editable/listAvailable复用解析器，历史必填继续通过governanceFieldRequired计算；不改权限节点/写路径/后端。
- [x] 字段规则错误先重新读取元数据，再映射到当前可见控件并滚动到第一个错误，输入修正清除对应消息；现有唯一性错误处理保留。
- [x] 在全模拟API的新增表单浏览器测试中加入422字段错误与改值后清除/重试；不创建真实档案。
- [x] 新增及相关字段/治理契约、必需3项规范/build、已完成共享模块回归；更新说明、覆盖矩阵、change.md并审查。
