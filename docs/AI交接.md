# AI交接文档

最近更新：**2026-11-07（北京时间），R09 / 1B-3已通过并收尾。** 1A、1B-1至1B-3通过；下一批只做1B-4，**等待用户说继续**。本文件是接手摘要，不是新运行证据；先读根AGENTS，再核对代码、Git与当前端口。详细历史见[03技术操作](过程记录/03_1b技术操作详解.md)和[04口述](过程记录/04_1b逐步口述稿.md)。

## 1. 固定边界

- 项目：`C:/Users/WenJing/Documents/WorkTransfer/layoutpatch-system`，PowerShell；实际文档目录为docs，不另建doc。目标2026-12-03首版：登录→PDF入库→授权真实检索→候选证据定位。
- 只修改本项目；同级layoutpatch、layoutpatch-evidence、Snappy只读。不下载模型、不训练、不换底座、不覆盖旧研究结果、不擅自暂存/提交/推送，保留已有Git差异。
- 每轮只完成用户指定小批，开始讲目标/改动/验收，执行解释关键技术，完成讲结果与口述后停止；批内常规操作自主完成。
- 重要操作/修改/验证/失败后及时更新本文件。阶段1B详细记录只追加03/04，日期/连续R编号/步骤ID对应，口稿每步60—100字；01/02保留前期历史和迁移入口。
- 区分已验证、设计与待核实。Cookie、密码、哈希、CSRF和服务key不进聊天/日志/文档；私密材料留Git忽略的runtime。

## 2. 当前已验证

| 批次 | 事实与证据 |
|---|---|
| 1A / R03 | 独立模型环境离线加载原ColPali，两完整PDF13页、4题真实编码，Top-3与参考一致，最大差约3.8×10⁻⁶；4项契约测试。仍有未命中，非效果达标。[手册](stage1a-verification.md)、[证据](checks/stage1a-verification.json) |
| 1B-1 / R05—R06 | 独立FastAPI/Next壳页、生成SDK、同源代理及Qdrant；Web类型/生产构建/HTTP通过；Qdrant1.16.2镜像摘要固定，就绪/正确key200、匿名与错误key401、停止/重启通过，浏览器健康按钮截图已保存。[手册](stage1b-1-runbook.md)、[补验](checks/r06-stage1b-1-completion.json) |
| 1B-2 / R08 | 六业务表及0001迁移，admin/A/B；A-tuGEMM5页、B-Music8页均private；全文件核验、重复初始化不覆盖密码/身份；9项测试。[手册](stage1b-2-runbook.md)、[证据](checks/stage1b-2-verification.json) |
| **1B-3 / R09** | **0002_auth新增auth_sessions/login_attempts；auth四接口、首次改密门禁、最小admin/profiles角色检查、持久会话与本地撤销CLI。14项auth＋9项数据回归共23项、真实Uvicorn/Next代理17项全部通过。** [手册](stage1b-3-runbook.md)、[汇总](checks/stage1b-3-verification.json) |
| R09正式库 | SQLite backup API先备份至runtime/verification/r09/metadata-before-0002.sqlite3，再重复迁移0002。与备份比六原表逐行内容（含密码/归属）不变，integrity=ok、FK0违例。真实代理6项冒烟通过，测试会话全撤销；正式账号未改密/停用/重置。[证据](checks/stage1b-3-formal.json) |
| R09环境边界 | Web30包，原25包版本不变，pip check通过；前后模型/算法锁/包版本、三旧库HEAD/状态及列出的变更文件哈希一致。不是ignored目录全量哈希。[前](checks/source-state-r09-before.json)、[后](checks/source-state-r09-after.json) |
| R09文档 | [质量检查](checks/r09-document-checks.json)：五对R09步骤、口稿60—100字、链接/锚点、JSON/Python语法、已知本机秘密扫描、SDK导入及忽略状态、diff检查通过。最终状态以报告为准 |

**数据和环境位置：**正式库`runtime/metadata.sqlite3`，现为8张业务表＋alembic_version；原数据3账号、2文档、2版本、13页、1profile、1index。profile/index仍pending，向量计数0。初始随机密码只在本地`runtime/secrets/development-initial-passwords.json`，本轮未改变；三个账号仍must_change_password=true。Web用`.venv-web`，模型用`.venv`（Python3.11.16、torch2.13.0+cu130、transformers5.17.0、colpali-engine0.3.18），不重建/升级已通过的模型环境。

## 3. 认证实现与限制

- 后端`backend/auth/`，starsessions2.2.1生成128位随机会话ID；Cookie原ID、库内SHA256。每次复核active/auth_version/撤销/空闲1800秒/绝对28800秒；仅成功登录可创建行，迟到更新不复活失效会话。Cookie HttpOnly/Lax/Path=/，本机HTTP Secure=false，HTTPS要求true。
- POST login、GET me、POST password/logout；所有写请求唯一可信Origin＋JSON，已登录写请求增加本会话CSRF。改密撤销所有会话并清Cookie，重新登录；退出只撤销当前。首次未改密受保护业务403，普通用户管理403；profiles只返回name/config_sha256/status。认证/admin含private,no-store和Vary Cookie。
- 失败限速持久化（账号5/客户端20次，300秒窗口）；应用按ASGI request.client计数、不直接读取转发IP头，但地址仍受Uvicorn代理配置影响。本轮只验本机开发，生产IP防伪造/可信代理部署边界待验。DB故障503，health仅存活。
- `scripts/manage_account.py`支持disable/enable/revoke/reset，增加auth_version并撤销全部会话，reset隐藏输入且强制改密。仅本地CLI；正式账号没有执行这些动作。完整管理/最后管理员保护留后续。
- SDK已通过OpenAPI重新生成，中央client注入JSON/内存CSRF，logout空body也有JSON头；generated/models/*.ts已从通用models/忽略规则中特定放行，模型权重仍忽略。**UI获取/清理token与结果留1B-5，不能称已完成。**
- auth只读进程环境LAYOUTPATCH_DATABASE_PATH/APP_ORIGIN/SESSION_COOKIE_SECURE，不自动加载.env；CLI用--database，不读取DATABASE_URL。SameSite/超时目前固定默认值，模板同名变量未解析。
- **尚未实现：**登录/改密网页、检索HTTP/对象授权、授权图片预览、Qdrant业务导入、上传、区域推理/高亮。过期测试注入应用时钟，并非实际等待8小时；starsessions元数据仍用库墙上时钟。未做登录UI截图；不能宣布T01/T02/T05整项通过。

**仍影响接手的失败：**R05 Docker曾启动失败，R06未重置即恢复，根因未知，[原记录](checks/r05-stage1b-1-status.json)。R08测试曾WinError32，sqlite3上下文不自动close，显式closing后通过。R09 SDK头回调TS推断失败，明确Record返回类型后typecheck/build通过；扩展DB故障测试发现starsessions2.2.1读取完成前置is_loaded，LoadGuard错误已通过公开handler复位处理，最终503/23项通过，升级该依赖必须重验。失败日志`runtime/verification/r09/unittest.log`，最终`unittest-final.log`。文档检查初次Git输出按GBK解码报错，显式UTF-8后复验；补丁同路径重复操作被拒且未写入，改直接写文件，详见03。

## 4. 本轮结束运行态

2026-11-07收尾实查：仅loopback前端3000（PID48232）、后端8000（PID4968），直接及代理health200、代理me401。Qdrant6333为原Docker监听（PID49880），本轮未启停或重新业务验收。

- 前端已在最终生产build后恢复：frontend目录`node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000`，终端会话35800。
- 后端本轮重启运行新auth代码：根目录`.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1`，终端会话11321。
- 停止优先所属终端Ctrl+C；需要Stop-Process时先用Get-CimInstance核对实际PID/命令行，PID会复用，不杀用户其他进程。Qdrant用`docker compose stop qdrant`保留卷。
- `scripts/check_auth_http.py`需要3000/8000空闲，现有17项已验，不要为了收尾再次占端口。普通单元测试用隔离SQLite，不碰正式密码。启动不自动迁移/初始化。

## 5. 下一批边界（均待用户继续）

| 批次 | 只做什么 |
|---|---|
| **1B-4** | 核验1A页面特征身份再导入；Qdrant授权检索、每个新query真实编码；白名单先于Top-k、空范围短路、故障明确失败、参考评分一致 |
| 1B-5 | 登录/改密/检索网页、结果与授权图片；换号/退出/401清状态，旧预览URL失效 |
| 1B-6 | 整体重启/故障检查、截图/部署说明；逐项列T01—T03/T05/T06/T11适用子项 |

后续设计保留：单后端worker、单份ColPali、GPU串行；普通用户本人私有＋管理员共享，admin默认同样可见范围，跨用户管理另授权审计。数据库版本白名单在Qdrant Top-k前过滤，返回前复核会话/访问版本；图片按page_id授权回溯，禁止裸文件URL与公共缓存。Qdrant基线original、128维完整多向量、Dot＋MAX_SIM、exact，无量化/pooling/prefetch；页面[1031,128]完整检索，前1024为视觉patch；query只删attention_mask补齐，保留增广token。CPU参考预设atol=1e-4、rtol=1e-5，超差定位不放宽阈值。详细以[架构](architecture.md)、[接口](interfaces.md)、[验收](testing.md)为准。

待核实：旧环境写入失败根因、新PDF解析/D推理、正式评价库/标签、预算方法、再分发许可与持久GPU容量。它们不改变本轮1B-3已验事实，也不允许提前声明后续能力。

本轮已同步03/04的2026-11-07 / R09-S01—S05。**在1B-3边界停止，等待用户继续1B-4。**
