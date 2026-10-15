# 金蝶同步队列执行前授权实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 队列在外部写入前，以原操作者当前有效动作授权及档案范围重新校验，排队后撤权不能继续同步。

**Architecture:** 在现有任务history首事件中保存服务端动作来源；新增独立队列授权服务，实际领取及金蝶声明档案时重复校验。保留外部结果未知不自动重试、最新版本与组织快照、归档手动同步和原工作锁。

**Tech Stack:** Python、SQLAlchemy、现有授权服务及内存／临时SQLite契约。

## Global Constraints

- 属于用户2026-10-15批准开发的统一权限范围；不访问金蝶、不启动真实工作线程、不修改角色配置或实际数据库；不新增结构／初始化逻辑。
- 自动新增使用add授权，自动编辑／审批使用edit，手动同步使用sync，交互重试使用system:sync:retry；维护引发自动同步要求maintain＋view＋edit。这些动作不互相隐含授权。
- 不按admin名称旁路、不将None身份视为系统用户；旧任务无法证明来源时失败关闭，提示重新授权提交／重试，不自动发外部请求。
- 不改变已送达金蝶的历史结果，撤权只拦截尚未发送的请求。第一版在实际声明前重新校验，不宣称已经撤回外部事务。
- 仅在失败事务回滚后写入失败事件；授权失败明确无外部发送，保留原档案正式数据、不自动重试。

## Task 1：实际数据库授权测试先行

**Files:** Create `backend/tests/erp_execution_authorization_contract.py`；复用`erp_queue_contract.QueueContract`的独立SQLite夹具，通过模块引用避免重复发现测试。

**Interfaces:** 外部调用仍为`erp_queue.run_once(db)`；测试仅拦截外部金蝶发送，真实角色／范围解析不替换。

- [x] 编写测试：授权有效时发送且传scope；排队后删除角色产品线、动作权限、用户禁用／删除、缺操作者、缺任务来源均不发送且标记failed；有全部数据而无动作仍拒绝；动作权限按新增／编辑／手动／重试区分，撤权后下一次执行拒绝。
- [x] 使用`PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B tests/erp_execution_authorization_contract.py`观察拒绝测试在原实现上失败，再实现。

## Task 2：独立执行身份与任务来源

**Files:** Create `backend/app/services/erp_execution_authorization.py`；Modify `erp_queue.py`、`project.py`、`kingdee.py`。

**Interfaces:** `authorize_task_execution(db, task, archive) -> dict`输出实时授权上下文；`enqueue(..., required_permission: str | None = None)`只接受服务端白名单动作来源，写入首条history的`authorization_permissions`。

入口核心契约：

```python
ACTION_PERMISSIONS = frozenset({
    'project:archive:add', 'project:archive:edit', 'project:archive:sync',
    'project:archive:maintain', 'system:sync:retry',
})

def task_permissions(action):
    if action not in ACTION_PERMISSIONS:
        raise ValueError('不支持的同步授权来源')
    return ([action, 'project:archive:view', 'project:archive:edit']
            if action == 'project:archive:maintain' else [action])
```

执行函数读取首事件来源且与白名单生成的权限列表精确一致；拒绝非列表、空列表、额外权限或缺少required_action的数据。读取有效用户／角色／权限，再对当前档案执行`ensure_archive_access`；缺身份／来源返回结构化403，失效用户／撤权和跨范围保持拒绝。调用前`db.expire_all()`使长生命周期工作会话不保留旧用户状态。

- [x] `event`增加仅enqueue使用的可选authorization参数，首事件保存`{'action': action, 'permissions': task_permissions(action)}`。自动enqueue默认edit，explicit默认sync，创建调用明确add，重试明确retry。
- [x] worker在attempts递增和外部调用之前执行授权；失败记录固定中文消息“原操作人或授权已变化，未发送金蝶请求；请重新授权后提交或重试”，task和当前档案标failed并提交，不自动重试。同步调用显式传scope_context。
- [x] kingdee队列validate_claim再次调用授权服务，复用原组织／最新任务检查；因此授权不是仅在任务领取时读一次。
- [x] 原队列测试给执行样本补有效身份和对应权限；保留专门缺身份拒绝测试。并发执行夹具也配置合成角色和产品线，禁止测试用生产身份或增加运行时旁路。

## Task 3：回归及交付

- [x] 新契约GREEN后执行`erp_queue_contract.py`、`product_line_sync_contract.py`、`offline_archive_contract.py`、`archive_change_contract.py`、`dashboard_scope_contract.py`及`rbac_permission_contract.py`。
- [x] 独立代码审查，核对动作来源不可由API任意传入、撤权失败不调用金蝶、无结果未知重发；修复范围内缺陷。
- [x] 记录本计划、总跟踪及change.md。回退仅本批独立源码差异，旧任务history新增键可被旧代码忽略；不执行实际回退或部署。

## 2026-10-15开发验证结论

以上勾选表示代码、隔离契约、模拟接口浏览器及独立审查完成，不代表真实账号授权、数据库升级或正式发布完成。详见[本批验证与覆盖记录](../../releases/2026-10-15-governance-development-validation.md)。实际数据库升级、现场用户闭环和真实邮件投递仍待独立批准。
