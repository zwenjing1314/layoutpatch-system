# 视觉文档检索与证据定位系统

**2026-11-07 / R11：1B-5网页与授权预览已实现并完成本批覆盖验收。** 可登录、进入首次改密表单、检索并回看原图；退出/换号/401清理状态，旧图片地址与会话绑定。45项后端、3项前端、41项真实HTTP、16项浏览器观察和16项正式恢复检查通过。[学习手册](docs/stage1b-5-runbook.md)、[验收汇总](docs/checks/stage1b-5-verification.json)。浏览器改密提交由本人操作，自动化未输入新凭据；隔离HTTP改密流程已验证。

正式库仍0003，13页、13403个token向量、profile validated/index ready；七张业务表与本轮备份逐行一致，原密码和文档归属不变。浏览器打开 <http://127.0.0.1:3000>，本人完成正式首次改密后可检索；admin无私有/共享文档时显示空态。下一批只做1B-6，等待用户继续；上传与区域高亮留后续。

新AI先读[交接文档](docs/AI交接.md)与根[AGENTS.md](AGENTS.md)，核对实际代码、数据与端口后再操作。按用户要求，R11起学习记录写[05技术详解](docs/过程记录/05_1b技术操作详解.md)和[06口述稿](docs/过程记录/06_1b追逐口述稿.md)，[03](docs/过程记录/03_1b技术操作详解.md)/[04](docs/过程记录/04_1b逐步口述稿.md)保持原内容；早期历史留[01](docs/过程记录/01_技术操作详解.md)/[02](docs/过程记录/02_逐步口述稿.md)。

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

浏览器访问`http://127.0.0.1:3000`；同源`/api`转发至8000。Qdrant独立容器只监听loopback6333，命令见[1B-1手册](docs/stage1b-1-runbook.md)。数据库初始化/密码位置见[1B-2](docs/stage1b-2-runbook.md)，认证原理见[1B-3](docs/stage1b-3-runbook.md)，特征与真实检索见[1B-4](docs/stage1b-4-runbook.md)，网页操作、授权预览与当前启停见[1B-5](docs/stage1b-5-runbook.md)。从测试终端启动正式后端前清除隔离数据库/audit环境变量；不要将密码、Cookie或CSRF贴入日志或聊天。

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
| 新PDF入库、区域排序/高亮、完整管理 | 后续阶段设计；不提前宣称可用 |

[需求与权限](docs/requirements.md)、[架构](docs/architecture.md)、[接口](docs/interfaces.md)、[分阶段验收](docs/testing.md)、[进度](docs/progress.md)区分已验证、设计与待核实。系统整体目标为登录→PDF入库→授权真实检索→候选证据定位，目标交付日期2026-12-03。

仅修改本项目；旧layoutpatch、layoutpatch-evidence、Snappy只读。选择性复用Snappy工程机制并保留来源与MIT，不整体搬上游栈；不下载模型、不训练、不换底座、不覆盖旧研究结果、不擅自提交或推送。运行数据和秘密位于Git忽略的runtime目录。
