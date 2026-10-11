# 引用查询共享模块与档案试点

## Goal
按已确认引用样稿实现正式独立组件，先在开发机项目档案试点。采用现有 Vue/TypeScript/form-system、FastAPI/SQLAlchemy；复用 archives/list 的 RBAC、人员/部门及产品线范围，不新增权限或数据库结构，不部署、不合并、不推送。

## Architecture
字段元数据声明引用来源和稳定键；共享引用弹窗调用来源 provider，不依赖业务页面或样稿。项目编码/名称均存档案ID；枚举保留稳定值并提供字符匹配。后端在分页前应用引用和字符谓词。引用选择只在确认时回填，取消不改条件；候选查询不自动选择，跨搜索和分页保留已选区域。大量粘贴分批查询，参数预算明确拒绝而非静默截断。

## Tasks
- [x] 1. TDD：协议/单列粘贴/身份、后端分页/权限/参数绑定测试先RED；实现引用协议和条件谓词，兼容旧方案。
- [x] 2. 实现可复用 provider 与引用弹窗、已选明细、批量匹配提示、错误和异步防覆盖；接入统一条件编辑器及档案试点，产品线限制候选，枚举停用值可查询。
- [x] 3. 浏览器验证搜索/累计选择/取消/保存恢复/批量/加载失败/窄屏/鼠标与键盘焦点；运行四项前端契约、构建和后端相关契约。
- [x] 4. 对照已确认样稿自审，更新本计划、UI标准及 change.md，提供开发机试点入口及隔离数据截图，不发布服务器。

## Boundaries
本批不迁移其他页面，不实施前面尚未落地的个人默认方案全新工具栏或列漏斗；这些沿用已确认样稿进入后续批次。本批不改 OA、ERP 同步、认证或权限分配。候选和结果请求仍由既有接口在每次请求校验当前权限。未知引用、非法值、字段变化和请求失败不能取消条件扩大范围。

## 实施与验证结果
2026-10-11完成共享组件与档案试点代码，分支 `codex/pms-unified-query` 保持未提交，不合并、不推送、不部署。

- 新增 `reference.ts`、`archive-reference.ts`、`PmsQueryReference.vue`；统一条件面板与列表适配使用稳定引用身份，项目编码/名称共用档案ID，枚举按稳定值引用及显示名字符查询。
- 保留已选记录，并在应用前重新校验产品线及当前权限；无法访问的引用明确报错，不静默去除查询限制。真实数据库结构与权限分配未改动。
- Excel单列解析保留前导零并去空行/重复，1000项上限及256字符上限明确提示。候选分批读取，匹配统计与后端大小写/首尾空白语义对齐，同名多候选不会自动勾选。
- MSSQL参数预算用 pyodbc `qmark` 的展开绑定位置数计算，包含人员/部门及产品线范围，预留分页余量；600部门人员＋1600引用，以及900部门人员＋1000引用＋49重复状态条件均先RED后GREEN。
- 同步状态字符查询复用既有状态名称，未调整ERP同步流程。独立审查四项发现已修复并限定复核关闭。

验证命令（相关最终版本均退出0）：

```bash
cd frontend
node tests/query-reference-core.test.mjs
node tests/unified-query-core.test.mjs
node tests/archive-reference-browser.mjs
node tests/unified-archive-query-browser.mjs
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/data-dictionary-contract.test.mjs
node tests/enum-management-contract.test.mjs
npm run build
```

后端使用Python3.12及项目现有 `.venv-deps312`，每条命令前设置 `PYTHONPATH=.:.venv-deps312`，运行 `tests/archive_reference_query_contract.py`、`archive_reference_authorization_contract.py`、`unified_archive_query_contract.py`、`field_catalog_contract.py`、`enum_management_contract.py`、`product_line_authorization_contract.py`（10项）、`product_line_project_scope_contract.py`（14项）。同一隔离API会话撤销产品线后候选与引用结果立即为0，撤销页面权限立即403。

浏览器回归使用正式档案页及隔离125条模拟记录，覆盖显式搜索/回车、跨搜索/分页累计、单列批量/重名/多列错误后恢复、取消、旧方案/新方案保存恢复、失败重试、产品线应用前复核、鼠标无外圈/键盘焦点及1182/390视口边界，无页面错误。截图 `.runtime/archive-reference-pilot.png` 是正式组件的隔离数据验收，不是生产数据。构建仅有既有大分块警告。

实际开发机入口为 `http://127.0.0.1:5174/project/archive`。用户自行登录后，以本机现有两条档案验证不同搜索累计勾选、独立已选区回显、批量输入3个去重值匹配2条及1项未匹配、取消保留原来的2条引用，以及改为1条引用后列表仅返回该档案。真实查询截图为 `.runtime/archive-reference-live-20261011.png`。临时引用条件已清除，未保存或覆盖个人方案；当前固定类别为全部档案类别，便于查看两条档案。未修改档案内容或触发金蝶同步。

本机未配置产品线，真实多产品线场景尚未验收，相关隔离回归已通过；Windows/OA及真实SQL Server效果未验证。其他列表迁移、个人默认工具栏与列漏斗仍待后续批准批次。
