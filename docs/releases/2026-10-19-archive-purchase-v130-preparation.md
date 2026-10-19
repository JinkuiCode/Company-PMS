# v1.3.0 档案与采购合并发布准备

状态：本机已验收，尚未固定Git候选或发布。日期：2026-10-19。

## 本次内容及证据

1. 采购申请明细仅纳入已审核且业务终止正常，基础选择和详情共用判断，取消数据状态查询条件；旧方案明确拦截重配。证据：outputs/purchase-population-20261019/verification.json（采购83项、报表73项、模拟页面）。
2. 正式档案及所有有效未提交草稿全局编码唯一；跨用户/产品线通用提示，保留输入；同事务锁和转正式幂等，改号或删除释放编码。证据：outputs/draft-code-unique-20261019/verification.json，后续相关路径已随本轮重跑。
3. 草稿和正式档案均要求档案类别；新建默认本人、恢复保留负责人；台排首但不改稳定枚举编号。产品线分别限制机型和设备系列，三组已确认映射，通用项及其他线保留，历史不自动改写。
4. 对应项目档案、草稿管理及采购进度说明同步修订。版本内容草案：outputs/archive-field-linkage-20261019/release-notes.draft.json，尚未向用户发布。

本轮证据：outputs/archive-field-linkage-20261019/verification.json。后端16组共131项相关测试通过，字段目录/枚举契约通过；前端必需规范、筛选及枚举契约、构建、联动/草稿测试和7项说明测试通过；两套隔离浏览器通过，真实业务写入0。独立审查两项P2已修正并回归，当前无未解决发现。已核对视觉截图。既有3项老测试夹具问题见outputs/draft-code-unique-20261019/baseline-failures.json，不宣称全库测试通过。

## 程序、数据库与权限边界

- Mac源码基线：542409037240428e34661173a07fd1ffda7d04a2，当前分支codex/pms-unified-query。
- 最近正式运行记录：v1.2.1 / f15d4f4527b5f837b622cf0370f6dadf87e562b2；维护前须重新核对，不将旧记录当当前证明。
- 不改结构或初始化数据，版本保持2026-10-16-form-draft-02；无需数据库结构升级。
- 不新增接口、权限、角色或保护配置修改。现有档案字段接口增加范围内联动元数据，后端维持实时权限。单位仅在选项读取时排序。
- 业务导入继续保留未归属历史，不重写数据；期初档案日常修改相关字段同样联动校验。

## 固定清单

精确路径和当前摘要：outputs/archive-field-linkage-20261019/combined-lock-manifest.json。仅以下文件；不纳入根Excel、outputs、.runtime、保护配置、旧原型、其他任务未提交材料或root/release.json。固定候选使用真实新提交标识，从提交重建前端并逐文件校验，保留旧包。

- backend/app/api/projects.py
- backend/app/models/project.py
- backend/app/services/archive_code_unique.py
- backend/app/services/archive_field_linkage.py
- backend/app/services/dict.py
- backend/app/services/field_policy.py
- backend/app/services/form_drafts.py
- backend/app/services/project.py
- backend/app/services/purchase_fields.py
- backend/app/services/purchase_reader.py
- backend/app/services/report_filters.py
- backend/tests/archive_code_lock_contract.py
- backend/tests/archive_form_linkage_contract.py
- backend/tests/form_draft_contract.py
- backend/tests/form_draft_unique_contract.py
- backend/tests/purchase_population_contract.py
- backend/tests/purchase_reader_contract.py
- backend/tests/report_query_v2_contract.py
- backend/tests/report_typed_filters_contract.py
- change.md
- docs/releases/2026-10-19-archive-purchase-v130-preparation.md
- docs/superpowers/plans/2026-10-19-archive-category-linkage.md
- docs/superpowers/plans/2026-10-19-draft-code-uniqueness.md
- docs/superpowers/plans/2026-10-19-purchase-normal-request-population.md
- docs/superpowers/specs/2026-10-16-archive-persistent-drafts-design.md
- docs/采购进度查询报表说明.md
- frontend/src/form-system/usePersistentDraft.ts
- frontend/src/page-guide/registry.ts
- frontend/src/views/project/ProjectArchive.vue
- frontend/src/views/project/archiveDraftValidation.ts
- frontend/src/views/project/archiveFieldLinkage.ts
- frontend/tests/archive-draft-validation.test.mjs
- frontend/tests/archive-field-linkage-browser.mjs
- frontend/tests/archive-field-linkage.test.mjs
- frontend/tests/archive-persistent-drafts-browser.mjs
- frontend/tests/fixtures/archive-field-linkage.json
- frontend/tests/persistent-draft.test.mjs
- frontend/tests/purchase-population-browser.mjs

## 下一阶段建议批准范围（尚未执行）

A. 仅上述清单提交当前功能分支，形成v1.3.0固定候选、清单与配套部署/回退材料；不合并master或推送。

B. 正式服务器10.10.1.228先重新只读预检（源码/运行版本/schema/队列/保护配置摘要），上传固定代码与受限助手；对SQL230/PMS做COPY_ONLY/CHECKSUM备份、VERIFYONLY及另名随机隔离库恢复。只在隔离库验证当前schema、普通运行身份的事务锁权限、SQL排序规则下编码重号/并发/回滚、档案与草稿规则、组织内码与枚举编号。背景任务和外部连接全部禁用，不实际调用金蝶或邮件。还应只读检查原有编号冲突数量，若有不自动改值。失败保留材料及隔离库，不自动重试或删除。

这两步均不停止正式PMS、不升级或写正式库、不更换正式程序或授权、不发通知。SQL身份需要时由用户在维护窗口隐藏输入，不保存或输出。备份恢复会增加SQL主机负载，须单独批准。若现状偏离基线则停止受影响操作并说明差异。

## 正式维护方案草案（候选固定及隔离验证后另批）

仅停启10.10.1.228的PMS，不重启服务器、OA或SQL服务。切换前重新备份并校验旧程序和保护配置；程序切换不附带结构升级。验收阶段保持写入、OA入口及金蝶/导出/邮件后台暂停，核对固定提交、schema、三组组织与枚举、实际表单的四项草稿必输/默认/排序/联动/历史显示、正式规则、采购查询元数据与页面说明；不创建真实项目或同步金蝶。

验收及队列核对后按明确批准范围恢复常规运行；失败保留现场，不自动反复启动。代码回退使用已校验的v1.2.1备份；不自动恢复生产数据库，不重写业务数据。新增历史草稿若缺档案类别，会在下次保存时提示补齐；原有冲突只提示不替人修改。

升级通知及有界邮件、master合并/推送、三端同步在提交/包/维护证据具体后按各自批准边界执行。此文件与内容草案不是发布或真实通知证据。
