# 视觉文档检索与证据定位系统

**2026-11-07 / R13：仅完成阶段规划，阶段1B已收尾、阶段2未开始。** [项目开发阶段规划与任务](docs/项目开发阶段规划与任务.md)补齐后续15个小批次、验收条件与日期预算。下一唯一开发批为2-1“新PDF上传、归属与持久任务基础”，等待用户指定。本轮未运行应用测试；下面R12状态是历史验收快照，使用前仍需核对实际服务。[R13文档检查](docs/checks/r13-document-checks.json)。

**2026-11-07 / R12：1B-6整体验收完成，阶段1B在现有13页链路范围收尾。** 本轮45项后端、3项前端、78项真实生命周期、13项浏览器观察、10项正式恢复和5组官方评分对照通过。非空Qdrant重启后13点/13403向量、payload/config完全一致；模型/向量库故障明确503，恢复后真实检索成功。[本机部署与学习手册](docs/stage1b-6-runbook.md)、[验收汇总与适用范围](docs/checks/stage1b-6-verification.json)。浏览器观察含10项DOM检查及3项AX/截图观察，错误角色计数原报告保留。浏览器改密提交仍由本人操作。

正式库仍0003，13页、13403个token向量、profile validated/index ready；七张业务表与两张认证表均与R12备份逐行一致，本轮未使用或更改正式凭据。正式服务已恢复，打开 <http://127.0.0.1:3000>，本人完成首次改密后可检索；admin无私有/共享文档时显示空态。本批结束停止，阶段2等待用户继续；上传、新PDF解析与区域高亮仍未实现。

新AI先读[交接文档](docs/AI交接.md)与根[AGENTS.md](AGENTS.md)，核对实际代码、数据与端口后再操作。按用户要求，R11起学习记录写[05技术详解](docs/过程记录/05_1b技术操作详解.md)和[06口述稿](docs/过程记录/06_1b逐步口述稿.md)，[03](docs/过程记录/03_1b技术操作详解.md)/[04](docs/过程记录/04_1b逐步口述稿.md)保持原内容；早期历史留[01](docs/过程记录/01_技术操作详解.md)/[02](docs/过程记录/02_逐步口述稿.md)。

## 运行和学习

PowerShell在项目根目录使用独立Web环境；端口已占用时先核对进程，不重复启动：

```powershell
.venv-web/Scripts/python.exe -m scripts.inspect_database
.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

前端另开终端进入frontend目录，已有生产build时执行：

```powershell
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
```

浏览器访问`http://127.0.0.1:3000`；同源`/api`转发至8000。先启动Qdrant，再后端、前端；整体启停/故障判断与非空持久化见[1B-6手册](docs/stage1b-6-runbook.md)。数据库初始化/密码位置见[1B-2](docs/stage1b-2-runbook.md)，认证原理见[1B-3](docs/stage1b-3-runbook.md)，特征与真实检索见[1B-4](docs/stage1b-4-runbook.md)，网页与授权预览见[1B-5](docs/stage1b-5-runbook.md)。从测试终端启动正式后端前清除隔离数据库/audit环境变量；不要将密码、Cookie或CSRF贴入日志或聊天。

`.env.example`区分当前实际读取的进程变量和后续设计；后端不整体加载该文件；Qdrant key缺省时仅读取项目.env的同名单项。模型使用独立`.venv`，不能用Web安装操作更新模型锁。

## 已验证与后续设计

| 内容 | 状态与证据 |
|---|---|
| 原ColPali离线算法 | 1A通过，两份完整PDF共13页、4题真实编码；与参考Top-3一致，最大分数差约3.8×10⁻⁶；仍有未命中，不能称准确率达标。[详情](docs/stage1a-verification.md) |
| 独立运行骨架 | 1B-1通过，Docker/Qdrant密钥与停止重启已验；R05引擎失败、R06恢复事实均保留。[补验收](docs/checks/r06-stage1b-1-completion.json) |
| 数据库与归属 | 1B-2通过，A-tuGEMM5页、B-Music8页均private，初始化不覆盖已有密码/身份。[证据](docs/checks/stage1b-2-verification.json) |
| 认证与会话 | 1B-3通过HTTP认证/CSRF/角色/撤销，1B-5接入网页。[证据](docs/checks/stage1b-3-verification.json) |
| 授权真实检索HTTP | 1B-4通过，真实新query、范围内Top-k、共享撤回与故障503；[证据](docs/checks/stage1b-4-verification.json) |
| 登录/检索网页、授权图片预览 | 1B-5已实现，真实浏览器结果/切页/401/503/空态/跨标签验证；正式新密码由本人输入提交。[截图](docs/checks/stage1b-5-results.png) |
| 整体启停与非空持久化 | 1B-6通过适用子集，重启前后全量向量/payload/config一致，故障后真实恢复，正式数据及服务已恢复。[证据](docs/checks/stage1b-6-verification.json) |
| 新PDF入库、区域排序/高亮、完整管理 | 后续阶段设计；不提前宣称可用 |

[需求与权限](docs/requirements.md)、[架构](docs/architecture.md)、[接口](docs/interfaces.md)、[分阶段验收](docs/testing.md)、[进度](docs/progress.md)区分已验证、设计与待核实。系统整体目标为登录→PDF入库→授权真实检索→候选证据定位，目标交付日期2026-12-03。

仅修改本项目；旧layoutpatch、layoutpatch-evidence、Snappy只读。选择性复用Snappy工程机制并保留来源与MIT，不整体搬上游栈；不下载模型、不训练、不换底座、不覆盖旧研究结果、不擅自提交或推送。运行数据和秘密位于Git忽略的runtime目录。
