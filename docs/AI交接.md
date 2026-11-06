# AI交接文档

**作用：**当AI上下文过长、会话中断或另开窗口时，把本文件交给新AI，使其快速了解开发背景、现状和下一步。本文件由接手AI持续维护，不是逐条终端日志。

**维护要求：**重要操作、修改、验证、失败或决策后及时记录，结束本轮前必须更新。允许删改过时内容、合并已完成事项；保留关键约束、证据和未解决问题。只写短结论与文件链接，不粘贴长日志、密钥或密码。详细历史留在两份过程记录，不能为精简而抹去失败事实。

最近更新：**2026-11-06（北京时间）**。当前阶段：**1A、1B-1、1B-2通过**。本轮连续编号R08（用户消息称R05/1B-2），任务只做数据库与归属；下一批1B-3等待用户继续。

## 1. 背景与边界

- 目标：2026-12-03前完成硕士毕业系统：登录→PDF入库→真实页面检索→候选证据高亮；支持普通用户、管理员和文档隔离。
- 工作目录：`C:/Users/WenJing/Documents/WorkTransfer/layoutpatch-system`。Shell：PowerShell。实际文档目录为 `docs`，不要另建重复的 `doc`。
- 同级 `layoutpatch`、`layoutpatch-evidence`、`Snappy` 只读；只在本项目写入。复用Snappy时保留MIT和来源记录，不整体搬旧仓库。
- 不下载大模型、不训练、不换底座、不回放旧预测冒充真实检索；不擅自提交/推送。
- 用户会在新窗口使用6.1sol，要求边做边学。**每轮只完成一个指定批次，讲清后停止；用户说继续再做下一批。** 不自动完成整个1B，不重复询问已有业务背景。

## 2. 当前可信状态

| 状态 | 结论/证据 |
|---|---|
| 已验证（2026-11-05） | 新 `.venv` 离线加载原ColPali；2份完整PDF共13页、4个新问题实际编码；Top-3与官方参考一致，最大分数差约3.8×10⁻⁶；4项契约测试通过 |
| 证据 | [1A验收与命令](stage1a-verification.md)、[结构化报告](checks/stage1a-verification.json)；原始结果 `runtime/verification/20261105-gpu-first/`；语料 `runtime/corpus/manifest.json` |
| 环境 | Python3.11.16；torch2.13.0+cu130、transformers5.17.0、colpali-engine0.3.18；49包从已有安装包独立复制，锁文件在根目录。不要重建或升级已通过的模型环境 |
| 算法 | `backend/algorithms/colpali_adapter.py`、`contracts.py`；模型身份 `configs/colpali_local.json`；真实CLI `scripts/verify_colpali_local.py` |
| 限制 | 有目标页未进前三、参考文献排第一；只证明链路，不证明效果达标。GPU小负载峰值allocated约8.10GiB，不承诺并发 |
| R05已验证 | FastAPI仅health、Next.js壳页、生成SDK和同源代理；独立`.venv-web`；类型检查、生产构建、冻结安装、两轮12项HTTP检查通过；[命令](stage1b-1-runbook.md)、[证据](checks/stage1b-1-web.json) |
| R06已验证 | Docker29.8.0已响应；Qdrant1.16.2真实就绪200、正确key200、匿名/错误key401；loopback、独立卷、停止关闭端口、重启再次通过；镜像摘要已固定；[补验收](checks/r06-stage1b-1-completion.json) |
| 历史失败 | R05曾观察Docker启动错误；本轮未修复或重置Docker即已正常，恢复原因未核实；[原状态保留](checks/r05-stage1b-1-status.json) |
| R06浏览器 | 实际点击检查按钮显示“服务连接正常”，[截图](checks/r06-browser-health.png)；不代表登录或检索可用 |
| R08已验证 | 6张SQLAlchemy业务表、Alembic0001迁移、初始化/只读检查CLI；正式库admin/A/B，A-tuGEMM5页、B-Music8页均private；重复迁移/初始化新增0且逻辑内容/凭据不变，9项测试通过；[手册](stage1b-2-runbook.md)、[证据](checks/stage1b-2-verification.json) |
| R08环境与边界 | Web环境25包，原13包版本不变；原模型环境/算法锁及三旧库可检查快照一致。初次测试WinError32为sqlite3连接未关闭，显式closing后全过；细节在03。 |
| R08数据位置 | `runtime/metadata.sqlite3`；随机临时密码仅本地`runtime/secrets/development-initial-passwords.json`，Git忽略，不打印/提交。库仅存Argon2id哈希，三账号首次改密标志true。CLI默认交互密码，已有数据不重置。 |
| 尚未实现 | 登录/会话/HTTP授权、Qdrant业务接入、上传、区域推理与高亮；profile/index为pending、索引计数0。数据库CLI用--database，不读取.env的DATABASE_URL；会话及其余业务变量仍设计 |
| R05环境及边界 | Node24.14.0/Corepack0.34.6/Yarn1.22.22；仅本项目安装普通Web包；模型代码/锁及包版本、三旧库可检查状态快照一致（非ignored目录全量哈希）；无模型下载/训练/提交/推送 |
| 未解事项 | 旧环境写入失败的系统根因未知，新环境已绕开；解析/D推理、正式评价库、预算研究和再分发许可尚待核实 |

当前 `.gitignore` 已无 `/docs` 条目；旧记录中的“docs被忽略”是当时状态。保留用户现有Git状态，不自行恢复忽略规则。接手先检查差异，不清理现有文件。

## 3. 阶段1B：按批实施，不一轮做完

目标：**登录→授权范围内真实检索→受保护页面预览**。沿用原ColPali及开发PDF；上传、区域排序、高亮和完整管理页不在1B内。

| 批次 | 只完成什么 | 出口 |
|---|---|---|
| **1B-1（已通过）** | 独立运行骨架：依赖、最小FastAPI健康接口、Next.js壳页、同源代理、独立Qdrant | 本机前后端可启动，代理健康检查通过，Qdrant就绪，停止/重启命令可复现；不加登录/检索业务 |
| **1B-2（已通过）** | SQLite/SQLAlchemy/Alembic、账号及文档/页面/索引身份；初始化CLI | admin/A/B建号；tuGEMM归A、Music归B，各保留全页；重复初始化不覆盖已有数据 |
| 1B-3 | 登录、改密、退出、角色检查和会话撤销 | 直接HTTP验证401/403、CSRF、首次改密、退出/过期失效；不只隐藏菜单 |
| 1B-4 | 核验后导入1A页面特征；Qdrant授权检索、真实query编码 | 先过滤后Top-k、空范围短路、服务故障明确报错；参考评分一致 |
| 1B-5 | 登录/改密/检索页面、结果及授权图片预览 | A/B能操作真实网页，换号/退出清理结果；旧预览URL失效 |
| 1B-6 | 整体验收、重启/故障检查、截图和部署说明 | 记录T01—T03/T05/T06/T11适用子项；未覆盖部分明确保留 |

1B-1实施默认：先快照，按依赖选择性复用Snappy的框架/SDK机制并记录来源。允许安装必要普通依赖和Qdrant镜像，模型不得下载；保护模型版本锁。Windows原生前后端，Docker仅跑本项目Qdrant，独立卷、API key、固定镜像版本/摘要；端口默认3000/8000/6333，仅loopback，冲突时记录新端口，不杀用户进程。引擎无法启动则记录阻塞，不用替身冒充通过。

后续关键约定（均为设计，未实现）：

- Next.js/React/TypeScript、FastAPI、SQLite、Qdrant；单后端worker、单份ColPali、GPU串行。沿用Yarn Classic锁文件与生成SDK，关闭无关聊天/OCR/维护入口。
- `pwdlib[argon2]`密码哈希，`starsessions`＋SQLite会话；Cookie HttpOnly/SameSite=Lax，本机HTTP Secure=false；空闲30分钟/绝对8小时；可信Origin＋CSRF。改密/停用/重置撤销会话。密码不进代码或命令参数。
- 普通用户仅本人私有＋管理员共享；admin默认同样范围，跨用户管理入口留后续。共享隔离测试单设数据，不能用共享副本掩盖私有越权。
- 数据库生成文档版本白名单，Qdrant过滤先于Top-k；空范围不查全库，失败不降级。返回前复核会话/访问版本；授权图片经page_id回溯，禁止裸文件URL与公共缓存。
- Qdrant：`original`、128维完整多向量、Dot＋MAX_SIM、exact；无量化/pooling/prefetch。保持1A内积语义。对照CPU参考预设atol=1e-4、rtol=1e-5，非并列Top-k一致；超差定位原因，不事后放宽阈值。
- 页面 `[1031,128]` 全序列用于检索，前1024为视觉patch；query仅按attention_mask删补齐，保留有效增广token。复用页面特征前核验身份，每个新问题必须真实编码。
- 接口按 [interfaces](interfaces.md)：auth四接口、search、授权image/thumbnail、admin只读profiles、最小health；浏览器走同源 `/api` 和生成SDK。原图请求不走公共优化缓存；响应private/no-store；401未登录、403角色不足、404他人/不存在对象。

## 4. 接手与更新方式

1. 先读本文件及根 `AGENTS.md`，核对当前代码/Git状态、上一批证据与本批依赖。按需读 [架构](architecture.md)、[权限](requirements.md)、[接口](interfaces.md)、[验收](testing.md)，不要每次全扫旧研究库。
2. 开始用短句说明“本批目标、会改什么、如何验证”；执行中解释关键技术，批次内常规操作自主完成。
3. 完成后更新本文件“当前可信状态、批次进度、下一步”，必要时更正活文档；阶段1B同步追加 [03技术详解](过程记录/03_1b技术操作详解.md) 与 [04口述稿](过程记录/04_1b逐步口述稿.md)，01/02保留前期历史与迁移入口。每轮实际日期、连续R编号、相同步骤ID；口稿每步60—100字。
4. 交付：实际改动、命令/检查结果、失败限制、简短口述、下一批名称。到批次边界停止。实现与测试分开标记；未执行不记通过。

简短记录格式：`YYYY-MM-DD｜批次/轮次｜做了什么｜结果/证据路径｜阻塞｜下一步`。未完成交接另写已启动服务、端口及已知停止方式；不要写密码/令牌。

## 5. 最近交接

- 2026-11-05｜R03/1A｜离线真实检索通过；证据见上；Web未实现。
- 2026-11-06｜R04｜建立本交接与AGENTS入口，细分1B；只改文档，未安装/启动服务或执行1B。
- 2026-11-06｜R05 / 1B-1｜前后端通过、Docker/Qdrant阻塞；[复现与限制](stage1b-1-runbook.md)、[来源](checks/r05-provenance.json)。[收尾检查](checks/r05-document-checks.json)通过（5对步骤、口稿60—100字、语法/链接）；Web验收进程已停止，3000/8000/6333无监听；挂起的本轮Docker CLI调用已结束，Docker Desktop仍故障，未全局清理或重置。
- 2026-11-06｜R06 / 1B-1补验｜重新检查引擎正常，拉取并固定Qdrant镜像摘要；就绪/密钥/停止/重启及浏览器点击通过；未创建集合或向量，未验证非空数据持久性。模型/旧库快照前后一致。
- **R08复核监听（未重新业务验收）：**前端`127.0.0.1:3000`（PID50056）、后端`127.0.0.1:8000`（PID51084）、Qdrant`127.0.0.1:6333`。原生进程可在对应终端Ctrl+C；本轮PID停止命令见runbook，操作前复核身份，勿杀PID复用后的其他进程。Qdrant用`docker compose stop qdrant`，保留卷。
- R06收尾：[文档检查](checks/r06-document-checks.json)通过，3对步骤及97字口稿、JSON/链接/脚本语法通过；直接与代理health最终均为ok，Qdrant仍运行。
- **下一批：1B-3，登录、改密、退出、角色检查与会话撤销。等待用户明确继续，不提前开发。**

2026-11-06｜R07文档整理｜核实用户已新建空白03/04文件，迁入R05/R06并增加八步开发学习与对应复述；直接使用`docs/过程记录/03_1b技术操作详解.md`与`04_1b逐步口述稿.md`，不新建重复doc目录。01/02保留迁移锚点，后续1B只追加03/04；本轮未操作服务/安装依赖或推进1B-2，R06服务状态仅为上轮记录。

R07收尾：[检查](checks/r07-document-checks.json)通过，八步学习、R05/R06八对历史及R07两对步骤完整；口稿60—100字、链接/锚点有效，22个应用文件哈希未变。首次检查先于质量报告生成，出现报告自身链接暂缺，生成后复核通过；长写入命令被拒后改补丁完成，未改运行状态。

2026-11-06｜R08 / 1B-2完成｜6表及迁移、账号/文档/页面/索引身份、重复初始化保护已验收，profile/index仍pending；SQLite完整性ok、外键无违例。只操作本项目，未启停服务/操作Qdrant/重跑GPU；[03技术记录](过程记录/03_1b技术操作详解.md#r08)、[04口述](过程记录/04_1b逐步口述稿.md#r08)。

R08收尾：[质量检查](checks/r08-document-checks.json)通过，5对步骤/60—100字口稿、链接与脚本语法有效；22个UUID合法且唯一。9项最终测试再跑通过（为确认测试目录可从零建立、失败输出仅用脱敏逻辑指纹）；日志`runtime/verification/r08/unittest-final.log`。前端/后端/模型接口未改，未扩大测试到GPU或后续业务。
