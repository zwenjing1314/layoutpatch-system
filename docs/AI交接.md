# AI交接文档

最近更新：**2026-11-07（北京时间），R11 / 1B-5实现、本批覆盖验收和文档收尾已通过。** 已在本批停止，等待用户明确继续1B-6。先读根AGENTS，再核对真实代码/端口/数据库；记录不能替代新证据。

## 1. 用户约束与记录入口

- 仅写`C:/Users/WenJing/Documents/WorkTransfer/layoutpatch-system`；旧layoutpatch、layoutpatch-evidence、Snappy只读，不下载模型、不训练、不换底座、不覆盖旧结果、不暂存/提交/推送。
- 用户逐批学习：每轮只完成指定小批，开头解释目标/改动/验收，过程讲技术，结束讲结果/口述后停止。重要操作、修改、失败和验证及时同步本交接。
- **用户最新要求：R11起写[05技术详解](过程记录/05_1b技术操作详解.md)和[06口述](过程记录/06_1b追逐口述稿.md)，不再修改03/04内容。** 日期/轮次/R11-S01—S06对应，每步口稿60—100字。AGENTS已同步。01/02与03/04保留历史，现有用户.gitignore忽略过程记录目录，05/06已写本地，未擅自放行或暂存。
- 密码/Cookie/CSRF/key及私密运行数据只留忽略runtime，不进文档/报告/聊天。区分已验证、设计与待核实；目标2026-12-03首版。

## 2. 已验证结果与证据

| 批次 | 实际结果 |
|---|---|
| 1A/R03 | 原ColPali离线完整13页/4题，与官方参考Top-3一致，最大差约3.8e-6；有未命中，只证明计算链。[证据](checks/stage1a-verification.json) |
| 1B-1/R05—06 | FastAPI/Next/SDK/代理、独立Docker Qdrant1.16.2摘要/密钥/停止重启；R05失败与R06补验保留。[补验](checks/r06-stage1b-1-completion.json) |
| 1B-2/R08 | 元数据库及admin/A/B，A-tuGEMM5页/B-Music8页private，重复初始化不覆盖身份/密码，9项数据测试。[手册](stage1b-2-runbook.md) |
| 1B-3/R09 | auth四接口、首次改密/CSRF/角色/持久会话/CLI撤销，23项测试/17项真实代理。[证据](checks/stage1b-3-verification.json) |
| 1B-4/R10 | 核验完整特征并导入13页/13403向量；逐query真实编码、先授权过滤后exact Top-k、返回前复核；36项测试、59项真实HTTP/GPU/Qdrant、8组官方评分最大差2.3300781251123226e-6（固定atol1e-4/rtol1e-5），非并列Top-k一致。[证据](checks/stage1b-4-verification.json) |
| **1B-5/R11** | **登录/首次改密表单/真实检索/原图网页与会话绑定图片授权。45项后端（9新增）、3项前端、41项真实HTTP、16项浏览器观察、16项正式恢复检查通过。** [汇总](checks/stage1b-5-verification.json)、[手册](stage1b-5-runbook.md)、[HTTP](checks/stage1b-5-http.json)、[浏览器及5截图](checks/stage1b-5-browser.json)、[正式恢复](checks/stage1b-5-formal.json) |

**R11人工边界：**浏览器工具要求“Changing a password ... user must ... entry ... submission”；本轮只观察改密表单/门禁/minLength12和退出，没有自动输入/提交新凭据。隔离A/B/admin经非UI HTTP完成改密、撤销/重新登录，正式密码未改；正式首次改密由用户本人输入提交。不得声称浏览器改密按钮已自动化点通。

**正式数据：**仍0003_search_pages、9张业务表＋alembic_version；3账号、2private文档、2版本、13页、1validated profile、1ready index、IndexPage13行、13403 token向量。collection=`layoutpatch_system_original_abf31f5bd1ac8442_g1`，Qdrant13点。R11备份`runtime/verification/r11/metadata-before.sqlite3`；七张原业务表与备份逐行一致、integrity ok/FK0、未撤销冒烟会话0，三账号must_change_password仍true。初始随机密码在`runtime/secrets/development-initial-passwords.json`，不打印。R10迁移前备份仍保留。

## 3. 当前实现入口

- auth使用starsessions2.2.1＋SQLite，Cookie随机128位、库内SHA256；HttpOnly/Lax/Path=/，本机HTTP非Secure，HTTPS必须Secure。每次检查active/version/撤销/空闲30分钟/绝对8小时；改密/停用/重置撤销全部旧会话，迟到写入不复活。写请求唯一可信Origin/JSON，password/logout检查本会话CSRF。首改门禁适用于profiles/search/image。
- `backend/documents/access.py`统一检索和图片的ready/未删除/本人＋启用管理员shared规则；admin普通search/image无全库旁路。`search/scope.py`还核验当前版本/完整IndexPage与配置身份，空范围不调模型/向量查询。
- GET /search（浏览器/api/search），q去空白1—2000/k1—50；额外/重复参数422。原ColPali逐问题（含重复）forward，Qdrant original128维Dot/MAX_SIM/float32、exact、m=0、无量化/prefetch；过滤含版本/profile/index/page白名单。结果身份/哈希/有限分数核验，返回前新SQLite Session复核完整范围和账号；撤销401、范围变409、依赖503，不回放结果。
- search现在有preview_url，仍有scope_version；没有search_record_id或持久access_epoch。`documents/previews.py`对page_id/render哈希用会话CSRF派生HMAC，地址必须与当前有效Cookie同时使用，不是独立授权令牌。GET /pages/{page_id}/image?preview=...回溯page→version→当前document→owner，未知/越权/错签名404，未登录401/未改密403。
- `documents/routes.py`只读解析到runtime/corpus下的≤20MiB PNG，核验RGB/尺寸/哈希，读完新Session复查再返回同一份字节；文件故障503 PREVIEW_UNAVAILABLE。private,no-store/Vary Cookie、nosniff/no-referrer，无ETag/Last-Modified、304/Range旁路或裸静态目录。旧Cookie失效401，同账号新会话旧URL404；shared也需本会话签名。无PDF/thumbnail路由，已交付字节无法收回，未做撤权推送。
- 前端`app/page.tsx`五态checking/login/password/workspace/unavailable；auth/search生成SDK、CSRF仅内存。图片用白名单路径＋原生fetch/Blob/AbortController，固定SDK生成器非JSON按文本读，不能直接调用其Blob声明的方法；未手改生成代码。请求代号拒绝迟到返回，图片独立序号；退出/换号/401/隐藏/pagehide清身份/CSRF/问题/结果/Blob URL，409/404清结果，503明确故障；退出失败不伪报成功。BroadcastChannel只广播变化，恢复可见/BFCache查me，可见会话30秒核验。没有localStorage/sessionStorage结果/秘密缓存。
- 模型仍独立`.venv`，Web`.venv-web`30包，未安装/升级依赖。单后端worker单持久子进程、stdin/stdout内部管道、串行锁，队列5秒/编码180秒，Next代理240秒；离线核验锁/权重/实现。原torch2.13.0+cu130/transformers5.17.0/colpali-engine0.3.18不变，不改算法底座。正式模型按需加载，门禁冒烟未启动GPU。
- search只读进程QDRANT_URL（loopback HTTP），key优先进程QDRANT_API_KEY，缺省只读项目.env同名单项，不通用dotenv。auth只读进程LAYOUTPATCH_DATABASE_PATH/APP_ORIGIN/SESSION_COOKIE_SECURE；CLI用--database。验收LAYOUTPATCH_QUERY_AUDIT_DIR仅设runtime，向量/计数不保存问题/凭据；正式默认不设。

## 4. 证据、失败和限制

- R11全部命令/失败详见05、手册。后端最终45项14.622秒；补OpenAPI preview参数后9项复查2.995秒；3项前端生命周期测试、SDK/typecheck/最终build9.11秒通过。[测试](checks/stage1b-5-tests.json)。不把首轮重复发现的55次当独立覆盖。
- R11真实隔离库/唯一集合与随机凭据在`runtime/verification/r11/workspace-state.json`及其folder；41项真实HTTP含B8张PNG哈希、旧URL/新会话/共享撤回。浏览器A/B新query、切页、退出/撤销清理、空admin、实际停止本测试模型503、390窄屏、跨标签退出均观察。测试模型/前后端/唯一_r11test_集合已清理；正式集合未改。本批没有重做R10官方评分，不把旧评分当新证据。
- R11保护前后[快照](checks/source-state-r11-before.json)/[快照](checks/source-state-r11-after.json)一致；原03/04/.gitignore当前字节与开工时相同、算法/模型锁/包及三旧库可检查状态相同，不是ignored文件全量审计。[最终文档检查](checks/r11-document-checks.json)通过：六对步骤/口稿88—99字、121处链接、54个Python/53个JSON、21个SDK文件、174个文本的已知本机秘密扫描、5张PNG及diff。已知秘密扫描不是通用安全审计。
- R11实际失败：PowerShell中文stdin编码改apply_patch；同路径delete/add整体拒绝后拆开；测试Cookie jar域重复改清理、TestCase导入改模块避免重复发现；辅助make_engine str改Path；Stop-Process空引用而未停，核对PID后taskkill；浏览器先于服务打开连接拒绝/旧错误data页绑定失败，服务就绪新标签成功；alert匹配Next播报器改精确文案。均非模型/评分阈值变更。
- 文档首查S04/S05口稿各102字，压缩后通过；截图API返回JPEG但保存名为.png，检查魔数发现后仅转码PNG，不改画面；检查stdout设UTF-8避免路径乱码。最终文档检查全部通过。
- 历史关键：R05 Docker启动失败/R06恢复原因未知；R08 SQLite未close导致WinError32已修；R09 starsessions2.2.1先loaded再store.read导致故障路径异常，LoadGuard复位后503，升级需重验；SDK类型忽略例外保留。R10沙箱Argon2/Docker/uv缓存限制获批运行，不重装；float64 JSON误判改float32字节哈希；默认30秒代理冷启动超时改240秒，原失败证据保留，未放宽评分容差。
- 特征复用：R03报告哈希有历史锚点；page_embeddings.pt哈希**R10首次固定**，不是R03历史校验。复核完整PDF/页图/1031×128 BF16和身份后导入，无13页重编码。新问题不读旧query或预测表。导入重复仅核验，不覆盖未知/部分集合，ready集合失踪不自动重建；远端部分失败需核查，不能自动清库。
- 仍未覆盖：浏览器改密提交、实际BFCache导航、共享撤回实时推送；PDF/缩略图/上传解析/区域高亮、完整管理/共享发布/审计/历史；非空Qdrant容器重启、GPU并发容量、正式效果评价。未宣布T01—T15整表通过。GET问题可能出现在代理错误日志，生产日志策略待审，Uvicorn已关闭access log；旧环境根因/新PDF/D推理/预算/再分发许可仍待核实。

## 5. 保留运行态与下一批

R11恢复实际检查：**前端127.0.0.1:3000 PID36376（会话84476），后端8000 PID32432（会话4521），Qdrant6333原PID49880。** 正式16项恢复检查通过；初始admin登录仍有效、首改search/image403、退出204、旧Cookie image401，测试会话已撤销。PID只是本轮快照，操作前重查CIM命令行与netstat。

正式启动用未设置隔离变量的新终端；如复用测试终端，先清LAYOUTPATCH_DATABASE_PATH/LAYOUTPATCH_QUERY_AUDIT_DIR，再根目录`.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log`；frontend目录`node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000`。停止优先所属终端Ctrl+C；不照抄历史PID杀进程，Qdrant stop保留卷。真实测试需3000/8000空闲，不为收尾重复GPU或完整重启。

**下一批1B-6（设计，未执行）：**整体启停/故障、非空Qdrant持久性、逐项适用T01—T03/T05/T06/T11验收与部署说明；只在用户继续后开始。当前网页与图片本批结束后停止。05/06六对R11步骤已写，03/04保持原内容。
