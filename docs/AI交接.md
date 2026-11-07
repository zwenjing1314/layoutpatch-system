# AI交接文档

本文件用于AI换窗口或上下文恢复：先了解当前背景、约束与证据，再核实现状。重要操作、修改、测试、故障或决策后须更新；可精简过时内容，保留仍影响接手的失败和限制。

最近更新：**2026-11-07（北京时间），R13仅完成后续阶段文档规划。** 最后代码验收为R12 / 1B-6；阶段1B在现有13页登录→授权检索→PNG→启停恢复范围收尾，阶段2尚未开始。[路线图](项目开发阶段规划与任务.md)把阶段2/3/4拆为6/5/4批；下一唯一开发任务为2-1，等待用户明确指定。本轮未启停服务、运行模型、迁移数据库或重跑应用测试。先读根AGENTS，再核对实际代码/端口/库；历史记录不能替代新运行证据。

## 1. 用户约束与学习入口

- 只修改独立layoutpatch-system；旧layoutpatch、layoutpatch-evidence、Snappy只读。不下载模型、不训练、不换底座、不覆盖旧研究结果、不暂存/提交/推送。
- 每轮只做指定批次，先讲目标/改动/验收，边做讲关键技术，完成讲结果/口述后停止。重要操作/失败/验证及时更新本交接。
- R11起写[05技术详解](过程记录/05_1b技术操作详解.md)及[06口述稿](过程记录/06_1b逐步口述稿.md)，**03/04不得再修改**。R12-S01—S06历史保留；本轮R13-S01/S02日期编号配对，每步口稿60—100字。原.gitignore忽略过程记录，保留设置，05/06实际在本地，检查时显式包含。阶段2起建议新建07/08，尚未创建。
- 凭据/Cookie/CSRF/key/私密向量日志只留忽略runtime，不打印或纳入报告。区分已验证、建议设计、待核实；目标2026-12-03。

## 2. 已有验收状态（R12历史证据）

**R12证据：**[汇总与适用矩阵](checks/stage1b-6-verification.json)、[本机部署手册](stage1b-6-runbook.md)。本节“本轮/本次”均指R12，R13只核对材料，不重跑以下验收。

| 检查 | 本轮结果 |
|---|---|
| 自动回归 | 45后端13.869秒＋3前端227.2619毫秒通过；[摘要](checks/stage1b-6-tests.json)。无API/前端变化，未重复SDK/build，不把R11构建冒充本轮 |
| 真实生命周期 | 78项通过；隔离SQLite、真实生产Next/Uvicorn/Qdrant/原GPU。前后端重启会话/PNG保留、撤销后重启不复活、依赖故障503和真实恢复。[证据](checks/stage1b-6-lifecycle.json) |
| 非空Qdrant | 实际stop/start；13点/13403向量、点ID/payload/float32字节指纹及完整config一致，同容器/镜像/卷、StartedAt变化；无导入/upsert/删除。网页追加一次故障恢复，正式收尾再次全量核对 |
| 官方评分 | 本次5组HTTP/同次query对照官方processor＋CPU float32，非并列Top-k一致，最大差2.284912110184223e-6；atol1e-4/rtol1e-5不变。[证据](checks/stage1b-6-reference.json) |
| 浏览器 | 13项观察：10DOM自动＋3AX/截图；实际向量库故障清旧结果/图片、恢复3条tuGEMM和原图、刷新会话保留、退出清理、正式登录页。[报告/3截图](checks/stage1b-6-browser.json)。未自动提交浏览器新密码 |
| 正式恢复 | 10项通过；7业务表＋2认证表逐行等于R12备份、integrity ok/FK0、Qdrant全指纹一致、测试进程/模型清理、正式匿名HTTP正常。未读取/使用/改变正式凭据。[证据](checks/stage1b-6-formal.json) |
| 保护 | [前](checks/source-state-r12-before.json)/[后](checks/source-state-r12-after.json)相同：原03/04/.gitignore、算法/配置/锁/模型包、三旧库可检查Git状态不变。不是ignored文件全盘审计；[收尾检查](checks/r12-document-checks.json)通过：6对口稿93—98字、55Python/64JSON、160处链接、21SDK、187文本已知秘密扫描、3PNG及diff |

最终轮9次实际forward（5成功脚本查询＋1脚本Qdrant停机查询＋3浏览器查询，其中1次故障），9份audit网络尝试均0；失败首轮另存，不混入该分母。授权/故障回归替身不代替真实GPU。仅证明本机开发样例链路，不代表正式准确率或容量。

**正式数据当前：**revision0003_search_pages，9业务表＋alembic_version；3账号、2private文档/2版本、13页、1validated profile、1ready index、IndexPage13。A-tuGEMM5页/B-Music8页；admin普通检索无私有全库旁路、当前空范围。collection=`layoutpatch_system_original_abf31f5bd1ac8442_g1`。三账号首改标志仍true、密码与本轮开工相同。初始凭据由本人在runtime/secrets/development-initial-passwords.json查看，禁止打印。

R12一致备份`runtime/verification/r12/metadata-before.sqlite3`；R11备份和R10迁移前备份保留。私密state在`runtime/verification/r12/state.json`，隔离库仍保留供复查，owned为空；失败attempt1在其子目录。复制正式页面/索引ID只读复用集合，未新增测试集合。**不要直接重新prepare/run覆盖本轮记录**；新练习用新轮次/目录/报告，先核实基线。

## 3. 当前实现和容易踩的契约

- Auth：starsessions2.2.1＋SQLite；随机128bit Cookie、库内SHA256；HttpOnly/Lax/Path=/，本机HTTP非Secure，HTTPS必须Secure。idle30分钟/absolute8小时，每次重查active/auth_version/撤销；改密/重置/停用撤销旧会话，迟到写入不复活。唯一可信Origin/JSON，改密/退出加本会话CSRF。首次改密门禁；浏览器新凭据由用户输入提交，隔离HTTP业务流程已验。
- GET /search q去空白1—2000/k1—50，额外或重复参数422。SQLite先决定本人＋启用管理员shared且ready当前版本范围，再实际原ColPali新query编码；每次包括重复问题都forward，空范围不调模型/Qdrant。Qdrant128/Dot/MAX_SIM/float32/exact、m=0、无量化/prefetch。返回前新Session重查完整范围/身份，撤销401、范围变409、依赖503，无结果回放。权限过滤实现在documents/access.py、search/scope.py。
- 搜索preview_url用会话CSRF派生HMAC(page_id/render_sha256)，仍需同一有效Cookie和当前归属，不是独立bearer。GET /pages/{id}/image逐次回溯page/version/current-document/owner，错签/越权/未知404；未认证401、首改403。PNG≤20MiB、runtime/corpus约束、RGB/几何/哈希及读取后新事务复核；异常503。private,no-store/Vary Cookie/nosniff/no-referrer，无裸files/PDF/thumbnail/304/Range旁路。新会话旧URL404，已交付字节不能收回，无撤权推送。
- UI五态checking/login/password/workspace/unavailable。SDK调用auth/search，CSRF内存；PNG单独fetch/Blob/AbortController（固定生成器非JSON按文本读，不能直接用其Blob声明）。代号＋取消拒绝迟到返回；退出/换号/401/隐藏/pagehide清身份/问题/结果/Blob；跨标签BroadcastChannel、可见会话30秒复核。无local/sessionStorage秘密或结果。
- 模型`.venv`独立于Web`.venv-web`30包；原torch2.13.0+cu130/transformers5.17.0/colpali-engine0.3.18未变。单后端worker/持久模型子进程，内部stdin/stdout、串行锁，队列5秒/编码180秒/Next代理240秒，无模型TCP入口。本地权重/实现锁定离线校验，不下载。Windows venv可能一棵模型树含启动器＋实际解释器，不按命令行重复数模型份数。
- search读进程QDRANT_URL；key优先进程QDRANT_API_KEY，否则仅读项目.env同名项，不通用dotenv。Auth读进程LAYOUTPATCH_DATABASE_PATH/APP_ORIGIN/SESSION_COOKIE_SECURE，CLI用--database。audit目录仅runtime、本机显式验收使用；正式默认无。health仅Web存活，不能当搜索依赖ready。GET问题可能进代理错误日志，关闭Uvicorn access log不等于完整日志治理。

算法/接口细节见[接口](interfaces.md)、[1B-3认证](stage1b-3-runbook.md)、[1B-4检索](stage1b-4-runbook.md)、[1B-5网页](stage1b-5-runbook.md)。

## 4. 失败、历史证据与限制

- R12：预检psutil不存在，改Windows CIM、不安装包；首轮把venv启动器/解释器误算两模型，[失败报告](checks/r12-lifecycle-first-failure.json)保留，改一棵树后完整重跑78项。报告汇总首查拒绝浏览器failed断言，核对源码/既有AX/真实截图后发现AX checkbox对应DOM button；保留[原报告](checks/r12-browser-first-check.json)，最终3卡观察按AX/截图注明，未称自动计数通过。错误文案定位漏“时”已纠正、未重发原请求。截图魔数统一PNG，只格式转码不改内容。
- 历史：R05 Docker失败/R06恢复根因未知；R08 SQLite未close锁文件已修；R09 starsessions部分加载异常由LoadGuard复位，升级需重验；R10 float64 JSON比较误判改float32字节，代理30秒超时改240秒，未放宽评分容差；R11 Stop-Process失败先确认PID再taskkill、CookieConflict/重复发现/编码问题均记录在05及原手册。
- 特征复用：page_embeddings.pt哈希R10首次固定，不能称R03历史锚点；完整PDF/页图/1031×128 BF16身份核验后导入，无13页重新编码。新query不读旧缓存/预测表；ready集合丢失不自动建空、部分失败不自动清库。
- 早期证据：1A13页4题/参考一致但有未命中；[R06骨架](checks/r06-stage1b-1-completion.json)、[1B-2数据](checks/stage1b-2-verification.json)、[1B-3认证](checks/stage1b-3-verification.json)、[1B-4检索](checks/stage1b-4-verification.json)、[1B-5网页](checks/stage1b-5-verification.json)保留；不当成本轮新运行。
- 尚未验证/实现：浏览器改密提交/BFCache实际导航、共享撤回实时推送、新PDF上传/解析/D真实区域/高亮、完整管理/审计/历史、长时并发容量、正式效果评价、外部新机器部署和再分发许可。T01—T03/T05/T06/T11只通过汇总中的适用子集，不宣布T01—T15整表通过。旧环境根因/新PDF/D/预算仍待核实。

## 5. 保留运行态与下一步

R12正式恢复观测：**前端127.0.0.1:3000 PID38744（exec会话63245），后端8000 PID6240（会话91968），Qdrant6333 Docker后端PID49880。** 浏览器现为正式登录页；正式模型按需加载，测试模型已清。PID只是快照，停止前重查创建时间/CIM命令行，不直接复用旧PID。

启停详见[1B-6手册](stage1b-6-runbook.md)：Qdrant start→干净终端正式后端单worker/no-access-log→Next生产start。测试终端须清隔离数据库/audit变量；APP_ORIGIN为3000，本机HTTP secure=false。停止所属终端Ctrl+C，必要时核对本项目进程树后taskkill；Qdrant只stop保留卷，不杀Desktop后端、不删卷、不重新导入。容器restart:no，Windows重启后需按顺序手动启动。

**R13出口：路线图与入口、学习记录同步后停止。** [文档检查](checks/r13-document-checks.json)只验证本轮文档与文件保护，不代替应用测试。修正原“06_1b追逐口述稿.md”失效入口为实际“06_1b逐步口述稿.md”，未重命名文件，未改03/04、旧报告或.gitignore。

**下一唯一开发批：建议R14 / 2-1，新PDF上传、服务端归属、文档版本、持久任务与授权状态查询。** 先核对实际基线和迁移/接口设计，再在用户明确指定后实施；本批不做页面编码、MinerU、D或高亮。详细依赖、出口和交接提示见[路线图下一步](项目开发阶段规划与任务.md#next)。MinerU/D新输入、动态索引一致性、评价材料与预算方法仍待核实；外部HTTPS/Secure Cookie、日志脱敏、监管/协同备份尚非已执行部署。
