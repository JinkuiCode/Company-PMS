# 首页统计统一权限实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 首页所有统计与项目列表使用同一项目范围，产品线与人员／部门范围相交，空授权或缺少部门不放宽数据。

**Architecture:** 在现有项目服务提供公开的范围查询入口，沿用现有 `_apply_project_scope`；首页不再自行拼一套权限。接口地址、响应结构和 `dashboard:view` 动作权限保留。

**Tech Stack:** FastAPI、SQLAlchemy；SQLite独立契约测试；现有Python授权服务。

**状态：2026-10-15用户明确“另一段对话已经暂停，现在可以启动方案开发”，本批本地代码实施已批准并开始。** 继续复用已批准分支与目录；数据库升级、正式部署及Git操作不包含在本次开发启动中。

## Global Constraints

- 当前核对基线为 `codex/pms-unified-query`、`973c9af`；实施前复核文件，保留另一对话全部改动。复用已批准工作区，不新建或移动worktree。
- 项目数据同时满足产品线及人员／部门范围；产品类别不参与。组织级ERP报表不在本小批次修改。
- `business:data:all`只扩展数据范围，不增加动作权限；不得按角色名称旁路，不写入真实角色配置。
- JWT不固化权限；仍由每次请求的当前有效用户／角色／权限生成上下文。
- 不修改模型、迁移、初始化逻辑，不提升或伪造数据库版本，不接触生产库。
- 仅增加共享查询入口并修复首页，禁止顺带全面重构项目服务或改变其他调用者的默认参数语义。其他缺口单独登记、分批治理。
- 不修改前端页面或已批准样稿；不触发ERP写入、邮件、部署、重启、提交、合并或推送。

## 当前证据与改动影响

2026-10-15复核发现 `backend/app/services/dashboard.py`仍自行过滤人员／部门，缺少产品线过滤；部门级／含下级部门级范围在 `dept_id`为空时不收窄。`backend/main.py`的 `/api/dashboard/stats` 已使用 `require_permission("dashboard:view")`。

`backend/app/services/project.py::_apply_project_scope`已按档案的 `business_product_line_id`过滤，且缺少部门时返回空结果。它对 `None`仍有内部历史语义，因此新增公开入口显式拒绝缺少上下文，不改变现有内部函数的全部调用者。

影响为：首页总数、任务数、平均进度、状态分布、部门分布、临期项目和最近项目只显示当前可见数据。原来越范围的首页数字可能减少，这是修复目标；HTTP协议和响应字段保持不变。

## Task 1：用同一项目范围驱动首页全部结果

**Files:**
- Modify: `backend/app/services/project.py`，在 `get_scoped_archive_query`附近增加项目查询入口。
- Modify: `backend/app/services/dashboard.py`，替换函数开头的自定义权限分支。
- Test: `backend/tests/dashboard_scope_contract.py`（新增）。
- Documentation: 本计划、`change.md`。

**Interfaces:**
- Consumes: `_apply_project_scope(query, db, scope_context)`，现有项目范围适配。
- Produces: `get_scoped_project_query(db: Session, scope_context: dict | None)`，返回SQLAlchemy查询；上下文为空时为空查询。
- Preserves: `get_dashboard_stats(db: Session, scope_context: dict) -> dict`及现有响应结构。

- [x] **Step 1：先增加行为测试。** 复用同版本现有契约的内存数据库夹具，只复用 `setUp/tearDown`，不继承并重复执行其全部测试。新增文件内容：

```python
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from app.services.authorization import enforce_permission
from app.services.dashboard import get_dashboard_stats
import product_line_project_scope_contract as scope_fixture


class DashboardScope(unittest.TestCase):
    setUp = scope_fixture.ProjectScope.setUp
    tearDown = scope_fixture.ProjectScope.tearDown

    def prepare(self):
        for index, item in enumerate(self.projects):
            item.end_date = date.today() + timedelta(days=3)
            item.status = 1
            self.tasks[index].progress = (index + 1) * 10
        self.db.commit()

    def test_all_sections_share_line_scope(self):
        self.prepare()
        result = get_dashboard_stats(self.db, self.ctx)
        self.assertEqual(result['total_projects'], 1)
        self.assertEqual(result['total_tasks'], 1)
        self.assertEqual(result['avg_progress'], 10.0)
        self.assertEqual(result['status_distribution'],
                         {'ongoing': 1, 'finished': 0, 'paused': 0})
        self.assertEqual(result['dept_distribution'],
                         [{'dept_name': '部门1', 'count': 1}])
        expected = {self.projects[0].id}
        for field in ('nearing_deadline', 'recent_projects'):
            self.assertEqual({row['id'] for row in result[field]}, expected)

    def test_empty_scope_never_reveals_projects(self):
        self.prepare()
        contexts = [None, {},
                    {**self.ctx, 'product_line_ids': []},
                    {**self.ctx, 'product_line_ids': [], 'role_codes': ['admin']},
                    {**self.ctx, 'data_scope': 2, 'dept_id': None},
                    {**self.ctx, 'data_scope': 3, 'dept_id': None},
                    {**self.ctx, 'data_scope': 2, 'dept_id': 2}]
        for context in contexts:
            with self.subTest(context=context):
                result = get_dashboard_stats(self.db, context)
                self.assertEqual(result['total_projects'], 0)
                self.assertEqual(result['total_tasks'], 0)
                self.assertEqual(result['avg_progress'], 0.0)
                self.assertEqual(result['dept_distribution'], [])
                self.assertEqual(result['nearing_deadline'], [])
                self.assertEqual(result['recent_projects'], [])

    def test_person_and_department_intersect_with_lines(self):
        self.prepare()
        self.projects[0].pm_id = self.users[1].id
        self.projects[0].dept_id = 2
        self.db.commit()
        for changes in ({'data_scope': 1}, {'data_scope': 2, 'dept_id': 1},
                        {'data_scope': 3, 'dept_id': 1}):
            result = get_dashboard_stats(self.db, {**self.ctx, **changes})
            self.assertEqual(result['total_projects'], 0)
        self.assertEqual(get_dashboard_stats(self.db, self.ctx)['total_projects'], 1)

    def test_revocable_all_data_grant_does_not_grant_action(self):
        self.prepare()
        context = {**self.ctx, 'dept_id': None, 'data_scope': 2,
                   'product_line_ids': [], 'permissions': ['business:data:all']}
        self.assertEqual(get_dashboard_stats(self.db, context)['total_projects'], 4)
        with self.assertRaises(HTTPException) as error:
            enforce_permission(context, 'dashboard:view')
        self.assertEqual(error.exception.status_code, 403)
        context['permissions'] = []
        self.assertEqual(get_dashboard_stats(self.db, context)['total_projects'], 0)


if __name__ == '__main__':
    unittest.main()
```

- [x] **Step 2：观察真实RED。** 在项目现有后端环境运行 `cd backend && python tests/dashboard_scope_contract.py`，应因首页跨产品线统计及缺少部门放宽而失败；记录结果，不能因预期RED中止批准范围内任务。若现有夹具已被另一任务修改，先按实际版本调整测试夹具，不能删掉目标断言。

- [x] **Step 3：实现公开查询入口。** 在 `project.py`增加：

```python
def get_scoped_project_query(db: Session, scope_context: dict | None):
    """项目公共查询入口；缺少授权上下文时默认拒绝。"""
    query = db.query(PmsProject)
    if not scope_context:
        return query.filter(PmsProject.id == -1)
    return _apply_project_scope(query, db, scope_context)
```

`dashboard.py`将 `from app.services.project import get_child_dept_ids`替换为 `get_scoped_project_query`；将函数内从 `user_id = ...`到 `# scope == 4: 不过滤`整段替换为：

```python
    base_query = get_scoped_project_query(db, scope_context)
```

其余统计继续从该查询得出的 `visible_project_ids`计算，不增加角色旁路或第二套范围规则。

- [x] **Step 4：执行针对性GREEN与相关回归。** 在backend依次执行，全部应退出0：

```bash
python tests/dashboard_scope_contract.py
python tests/product_line_project_scope_contract.py
python tests/rbac_permission_contract.py
python tests/purchase_organization_scope_contract.py
```

- [x] **Step 5：复核接口与交付。** 核对 `backend/main.py`仍以 `dashboard:view`依赖保护路由、首页全部七类结果使用范围内项目；按当前版本补齐本计划结果与本项目 `change.md`。先做本地真实账号流程检查：首页授权产品线内结果可见，撤去产品线后再次请求不返回原数据，无首页查看权限时返回403。使用隔离测试身份或现成授权测试夹具，不保存实际角色变更。

## 验收与回退

- 仅本地修复及验证；不连接生产、不变更真实角色、不写金蝶。若实际登录会话不可用，保留自动化接口/服务证据并明确剩余现场验收，不能用样稿代替实际首页。
- 回退只需回退本批两个服务文件的独立差异和相应部署包；无数据库结构或数据回滚。禁止用整目录覆盖或重置丢弃另一对话改动。
- 本批修复完成后，权限覆盖矩阵继续登记其他页面与后台流程；全系统合格需逐项证据，不能据本批推断。
- 日志与版本通知各自再出实施方案。数据库升级、真实发送、正式部署、GitHub合并/推送仍保留各自批准要求。


## 2026-10-15 本地实施与验证

- 已增加公共项目查询入口，首页全部七类结果复用该范围；接口和响应结构保持。
- 新增4项服务行为测试先失败：跨产品线总数4而非1、空产品线和缺部门泄露、None/空字典异常；修改后通过。测试夹具以模块导入，避免unittest重复发现外部测试。
- 独立审查未发现生产代码阻断项，指出缺少真实路由撤权证据，已补第5项测试：复制实际`/api/dashboard/stats`路由到无启动任务的FastAPI，只覆盖隔离数据库；同一合成OA JWT依次验证产品线撤销、全部业务数据授权撤销、仍持全部数据但撤销首页查看、用户禁用。实际认证与RBAC依赖均保留。
- 命令统一使用`PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B`：dashboard_scope_contract.py 5项、product_line_project_scope_contract.py 14项、purchase_organization_scope_contract.py 8项及rbac_permission_contract.py均退出0。rbac初次因缺少PYTHONPATH根目录未进入测试，补上`.`后通过；未安装依赖。
- JWT既有utcnow弃用警告保留，未扩展修改认证代码。真实首页接口已在隔离数据库验收，未运行带业务工作线程的main lifespan、未变更真实账号或访问生产。前端无改动，不将接口测试声称为现场浏览器验收。
- 继续同一功能分支，未提交、合并、推送或部署。后续其他治理批次继续。
