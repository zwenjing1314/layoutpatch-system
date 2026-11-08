# 模块与接口契约

## 2026-11-08｜R26 / 3-2共享管理契约

新增GET /admin/documents（name/limit/offset，默认10，items/next_offset/scope_version）以及POST /admin/documents/{id}/publish、/unpublish。列表与写入只对已完成首改的当前admin本人非删除文档开放，其他owner统一404；不提供跨private管理或普通搜索旁路。发布须ready/有效当前版本/活动索引全页，撤回不以索引ready阻断。

写入必带document_version_id（UUID或null）、严格整数access_version>=1及confirmed=true，拒绝多余字段/参数；cookie/Origin/CSRF/首改/角色仍逐次检查。BEGIN IMMEDIATE锁后重查权限和版本：旧输入409 SHARING_INPUT_CHANGED，未就绪发布409 DOCUMENT_NOT_READY，当前同状态noop不增加版本，真实visibility变化递增版本；状态/版本/事件原子，事件失败回滚503。返回SharingMutation(document,changed)。安全/schema/未知对象拒绝不造业务事件；已授权业务拒绝记录固定最小事件。

0010增加documents.access_version默认1和sharing_events。授权版本进入普通列表指纹、AllowedScope及PageFile、v2 PNG/crop签名；推理/读取后新事务复查，包括撤回再发布ABA。旧链接404，新检索/定位取新链接。D输入及P′缓存键不增加授权字段；算法不变。SharingService及四模型已生成，48份SDK重新隔离生成一致；详见[手册](stage3-2-runbook.md)。

网页管理员专属入口、每页10份、两个明确确认弹窗；独立列表/写入代号、同步重复锁和15秒等待上限。离页/身份变动清管理，写入成功或结果未知清检索/目标/Blob/区域并刷新；不自动重试写。正式仍0008，未部署本批；未来需另行备份/0010迁移和重启。

## 2026-11-08｜R25 / 3-1B管理网页接入

无新API/表/SDK契约；实际OpenAPI和隔离重新生成43个SDK文件与R24冻结文件相同。用户管理入口只对当前admin显示，列表limit10与next_offset；五类操作均弹出对象、影响及明确确认。本人输入初始/临时新密码两次，非受控表单提交即清空，不获取或显示已有密码/哈希，不落应用持久存储。

管理列表/写入独立代号和即时重复锁，15秒等待上限不表示服务端取消；未知写结果不自动重试。409最后管理员/重名、404、422使用固定提示；401清工作台、403清管理并查身份。退出/换号/离页/首改/角色变化拒绝迟到响应，本人reset/revoke成功退出；无共享/删除/历史/主题扩展。适用证据与浏览器新凭据限制见[手册](stage3-1b-runbook.md)。正式仍未部署，启用需新备份/0009迁移/重启。

## 2026-11-08｜R24 / 3-1A用户管理契约

新增GET/POST `/admin/users`、PATCH `/admin/users/{user_id}`、POST `/{user_id}/password`及`/{user_id}/sessions/revoke`（均在/admin/users下）；当前已首改启用管理员，写入Origin/JSON/CSRF。分页limit1—100/offset0—1000000，用户名NOCASE/ID顺序，返回安全账号字段和next_offset；不冻结跨请求分页快照。建号201且必须首改，大小写重名409；启停严格bool、同状态noop，最后启用管理员409；重置密码/撤销提升auth_version并撤销所有旧会话，新启用不复活旧会话。UUID目标、额外字段/参数及重复参数拒绝。无角色修改、用户删除或private文档旁路。

五类操作和错误/幂等细节见[冻结API手册](stage3-1a-runbook.md#api冻结)，以新生成OpenAPI/Account类型/AdminService为准。CLI和HTTP公共BEGIN IMMEDIATE事务先锁再查身份和管理员计数，账号/会话/最小事件原子提交；已授权业务拒绝记rejected，DB错误全回滚。合法匿名401、普通用户/首改/CSRF403、对象404、冲突409、非法输入422、数据库503，private,no-store/Vary Cookie。正式本轮未迁移或部署管理API。

## 2026-11-08｜R22 / 2-6授权区域契约

- GET `/pages/{page_id}/regions/status`：已首改cookie会话，检查当前可读ready页面/活动版本及索引；返回页面/PNG尺寸与SHA、解析状态、task/候选/parser/D身份和本人can_parse，不返回路径、正文或框。缺完整PageFeature为unavailable；共享只读，普通admin无private旁路。
- POST `/pages/{page_id}/regions`：同源Origin、JSON、X-CSRF-Token及已首改会话；body仅q（1—2000）、document_version_id、render_sha256、index_generation。非ready返回空items，不隐式执行D；ready返回当次query hash、所有候选candidate_id/layout_id/rank/有限score/type、原PNG像素xyxy及crop_url，网页只展示Top5且不改排。推理后新事务重查会话及全部输入。
- GET `/pages/{page_id}/regions/{layout_id}/crop?task=&candidate_hash=&model=&token=`：严格参数集、拒绝重复，HMAC绑定当前会话和page/task/candidate/model/layout/render。检查当前ready尝试、完整输入及PNG，floor左上/ceil右下裁剪，读PNG后再次授权；新会话不能重放旧签名。
- 合法匿名/撤销请求401，首改/Origin/CSRF403，越权/撤回404，输入变化409，非法body/参数422，依赖/校验503。畸形body可能在路由principal前收到422，不声明全部匿名畸形请求401。模型失败状态failed并附REGION_INFERENCE_FAILED或MODEL_BUSY，网页仅重试定位；解析失败才走文档解析重试。
- 业务响应private,no-store/Vary Cookie，上传Origin/CSRF不变。RegionState/Input/Item/Response及PagesService由实际OpenAPI生成，items为required。SearchHit.region_status=not_requested只描述search未运行区域定位；网页独立请求regions/status。完整特征与原search/PNG契约不变。

实际109项HTTP、26项网页及会话重启/原链检查见[本批手册](stage2-6-runbook.md)、[汇总](checks/stage2-6-verification.json)。状态字段、可选项及错误结构以[导出OpenAPI](../frontend/docs/openapi.json)为准，下文旧轮次保留为历史。

## 2026-11-08｜R19 / 2-3C已实现任务契约

- GET /jobs?limit=10&cursor=：本人非删除文档的任务；limit1—50，cursor≤2048，未知/重复参数422。按created_at/id倒序；签名游标绑定当前会话和limit，非法/跨会话422 INVALID_JOB_CURSOR，进度更新不使分页失效。不是全库管理员接口。
- GET /jobs/{id}及上传响应扩展display_name/page_count、cancel_available/retry_available、cancel_requested_at和有序attempts（状态/阶段/进度/错误、created/updated/started/ended）。保留原字段及相同job/document/version；未知/越权404。
- POST /jobs/{id}/retry、/cancel：JSON仅`{"attempt": 当前尝试编号}`；需同源Origin、X-CSRF-Token、已首改会话及本人归属。期望attempt变化409 JOB_ATTEMPT_CHANGED，拒绝迟到操作。任务状态不可操作409；多余字段422。最多10次尝试，失败/中断/取消且源文件存在、文档尚未激活才可retry；损坏409 REUPLOAD_REQUIRED，源文件缺失时retry_available=false。
- cancel对receiving/queued立即cancelled；running返回已保存请求，cancel_available=false，安全检查点/最终激活事务再终止；completed不可取消/重试。重启中断同步attempt，旧attempt不覆写。默认总时限900秒，LAYOUTPATCH_INGEST_MAX_SECONDS范围1—7200秒，非抢占式检查。
- 任务及其它业务响应保持private,no-store/Vary Cookie。POST /index仍multipart单PDF、X-Upload-ID及CSRF，同标识同内容返回原任务；不能为了上传关闭保护。OpenAPI已重新导出、SDK用frontend的gen:sdk生成；旧两参search调用兼容。网页45秒上传/15秒列表控制/2.5秒轮询/10分钟暂停，仅停止客户端等待，不承诺终止GPU。

原检索与原图契约保留，完整页面特征不能由预算序列替代。见[手册](stage2-3c-runbook.md)、[HTTP](checks/stage2-3c-http.json)。

**2026-11-08｜R18 / 2-3B-2前端接入：**公开接口与生成SDK未改；网页用listDocuments(name,10,cursor)和searchPages(q,k,documentId)，library省略ID，document必有searchable目标。scope_version是当前名称筛选快照，不能跨筛选直接比较；切换筛选重置游标/快照但保留已选对象。返回额外校验mode/document/每页version，整包不符拒绝展示，不事后过滤Top-k。404/409清选择并重载，列表游标409/422要求刷新，401锁定，首改403不挂工作台。见[实际手册](stage2-3b2-runbook.md)。

## R17 / 2-3B-1前端对接状态（2026-11-07）

本批公开HTTP/OpenAPI/生成SDK无变化；新工作台继续SearchService.searchPages(q,k)两参文档库查询，未调用授权列表或传document_id。结果组件收到完整SearchResponse/SearchHit，选页回调原preview，授权签名PNG、no-store、同源路径限制和Blob释放不变。组件无独立网络/持久缓存；B-2才接双模式及文档选择。实际UI/HTTP对应及边界见[手册](stage2-3b1-runbook.md)。

## R16 / 2-3A已实现公开契约（2026-11-07）

GET /documents?name=&limit=20&cursor=：name原长度≤255、NFKC＋casefold普通子串，空白等于不筛选；limit1—100；cursor非空≤2048。未知/重复参数422。返回items、next_cursor、scope_version；每项含document_id/display_name、当前或待处理版本ID/号/页数、visibility/access、status、本人job_status/error_code、created_at、searchable/unsearchable_reason，无总数/内部路径。本人未ready可见但不能搜索，共享只列启用管理员ready且不返回任务细节。searchable为DB资格，不保证依赖在线。

游标HMAC绑定当前会话、名称、limit及可见快照；非法/跨会话/参数不符422 INVALID_CURSOR，列表或权限变化409 DOCUMENT_LIST_CHANGED，须从第一页刷新。列表返回前新事务复核会话/权限。所有保护响应private,no-store/Vary Cookie；未认证401、首改403。当前服务器快照线性计算，仅返回单页，不称大库游标优化。

GET /search保留q/k，新增可选UUID document_id；响应新增search_mode=library/document、document_id（库模式null），其余profile/index/scope/timings/items保持。目标无权/未知404 DOCUMENT_NOT_FOUND、本人未ready409 DOCUMENT_NOT_READY、非法/空/重复422；实际查询前后都用相同目标，Top-k前过滤所选当前版本页，整代计数保持全局；返回时目标已撤回或版本/权限改变409 SEARCH_SCOPE_CHANGED。绝不回退全库，原401/503与PNG独立授权仍有效。

已导出OpenAPI并生成DocumentsService.listDocuments(name,limit,cursor)、SearchService.searchPages(q,k,documentId?)，原两参调用兼容，无手工改生成代码。前端选择UI尚未实现。详情及实测见[2-3A手册](stage2-3a-runbook.md)。下方R14“尚未实现”为历史设计状态，当前以上述契约为准。

## R15 / 2-2实际任务语义（2026-11-07）

本批无新增公开路由/字段，实际OpenAPI与已生成SDK完全相同。POST /index仍以同源/CSRF/已改密会话上传且202，服务端owner/private；响应后后台自动处理，GET /jobs/{id}可见status=running及stage=rendering/encoding/indexing/activating，成功status/stage=completed、progress=100，GET /documents/{id}变ready。失败以固定error_code和最后stage表达，页面不激活；attempt仍1，无retry/cancel接口。重复upload key语义沿用2-1，不能将已完成任务重跑。

0005增加内部system_state活动索引指针、page_features全特征来源，不向客户端暴露路径/张量。启动时receiving→UPLOAD_INTERRUPTED、running→INGEST_INTERRUPTED、building索引→failed；queued仍可领取，completed保留。LAYOUTPATCH_INGEST_ENABLED=false为服务端暂停领任务开关，不是客户端参数。新PNG继续GET /pages/{id}/image会话签名、当前归属和哈希校验；不挂裸文件目录。索引代切换使进行中查询scope变化时返回现有409 SEARCH_SCOPE_CHANGED。

页面/问题共享ModelWorker内部stdin/stdout协议及锁，page输出完整BF16 1031×128和float32导出身份；接口不对网络公开。完整特征保留供D，不接受预算压缩代替。实测和错误边界见[2-2手册](stage2-2-runbook.md)。下面2-1表中registered/queued为R14当时出口，当前由上述自动流水线推进；2-3A列表/单文档仍只是设计。

## R14补充：单文档检索接口设计（尚未实现）

规划在2-3A新增`GET /documents?name=...&limit=20&cursor=...`，提供授权分页文档列表和文件名包含式匹配；扩展`GET /search`的可选`document_id`，省略时保持文档库范围，提供时仅检索该文档ready当前版本。单对象`GET /documents/{id}`已实现不代表列表已实现。授权后再筛选/分页，单文档范围在Top-k之前生效，返回前以同一目标重查；未知/无权统一404，已授权未ready明确409，不回退全库。文件名不作唯一ID，不编码文件名向量；索引总点数与查询页面白名单分开。完整建议字段、状态与验收见[设计](单文档检索功能设计与分批计划.md)；实际OpenAPI/SDK本轮未变。

## 2-1实际上传和状态接口（R14，2026-11-07）

本节区分本批已实现接口与后文目标设计。数据库0004新增jobs，复用documents/document_versions；未新增页面、候选或索引。文件尚未渲染时文档保持registered、active_version_id为空、任务queued；不进入现有ready search范围。

| 方法与路径 | 输入/输出 | 授权与状态 |
|---|---|---|
| `POST /index` | 一个multipart字段`file`；UUID头`X-Upload-ID`。202 JobResponse：job/document/version ID、kind/stage/status/progress/attempt/error_code/time/retry_available | 已改密有效会话＋唯一可信Origin＋X-CSRF-Token；owner由后端指定、private固定；幂等冲突409 |
| `GET /jobs/{job_id}` | JobResponse，不返回路径或异常文本 | 仅本人关联文档；跨用户/不存在404 |
| `GET /documents/{document_id}` | document/version ID、展示名、private、registered、版本、PDF SHA256、页数 | 仅本人；跨用户/不存在404 |

`jobs`保存owner_id、document_version_id、upload_key、request_sha256、upload_bytes、kind/stage/status/progress/attempt/error_code、created/updated。owner＋upload_key、document_version_id分别唯一。状态允许receiving/queued/failed/interrupted/running/completed/cancelled；本批仅实际使用receiving/queued/failed/interrupted，attempt=1。接收恢复不代表2-3完整scheduler、retry/cancel已实现。

2-1限额默认为20MiB/100页，配置见[批次手册](stage2-1-runbook.md)。multipart只对/index开放，不影响JSON写边界。OpenAPI/生成SDK含DocumentsService，但前端无上传页面；中央SDK头部在formData时只加CSRF，Content-Type由浏览器生成boundary。所有保护响应private,no-store/Vary Cookie。

**R12 / 1B-6补充：**本轮没有更改API/SDK/迁移；对现有路由完成78项真实生命周期、13项浏览器观察和10项正式恢复检查，5组本次官方评分一致。非空Qdrant与前后端重启、故障503和实际恢复见[汇总](checks/stage1b-6-verification.json)及[部署手册](stage1b-6-runbook.md)。下文R11接口定义继续有效；PDF/区域/完整管理仍为设计。health只是Web存活，不表示依赖就绪。本批结束不推进阶段2。

更新：2026-11-07，北京时间，R11。**1B-5已接入网页登录、首次改密表单、真实检索与授权原图。** 45项后端、3项前端、41项真实HTTP、16项浏览器观察及16项正式恢复检查通过；浏览器改密提交由本人操作，隔离HTTP改密已验证。[手册](stage1b-5-runbook.md)、[证据](checks/stage1b-5-verification.json)。

正式0003、13页ready、profile validated不变，本批无新迁移。上传、PDF、区域与完整管理仍为设计；本批详细记录转[05](过程记录/05_1b技术操作详解.md)/[06](过程记录/06_1b逐步口述稿.md)，03/04不再修改。后续接口按[R13路线图](项目开发阶段规划与任务.md)逐批实施，规划不代表接口已挂载。

## 1. 浏览器—业务后端

沿用 Snappy 的 `/search`、`/index` 命名及生成客户端机制，扩展业务对象，不维护两套请求库。更改 API 后在新项目导出 OpenAPI，再运行 `yarn gen:sdk`；不手改生成文件。

| 方法与路径 | 输入/输出要点 | 授权 | 阶段 |
|---|---|---|---|
| POST /auth/login | 用户名、密码；设置会话 Cookie，返回角色与改密要求 | 同源、限速 | 1B-3已实现 |
| GET /auth/me | 当前账号、角色、CSRF token；响应不缓存 | 当前有效会话 | 1B-3已实现 |
| POST /auth/logout | 撤销服务端会话并清 Cookie | 当前会话＋CSRF | 1B-3已实现 |
| POST /auth/password | 当前密码、新密码；撤销旧会话 | 当前用户＋CSRF | 1B-3已实现 |
| GET /documents | 本人/共享范围、分页、状态 | 服务器限定范围 | 2 |
| POST /index | multipart PDF；202 返回 document_id/job_id | 固定当前 owner、private | 2 |
| GET /jobs/{job_id} | 阶段、进度、错误摘要、可否重试 | 本人或管理范围 admin | 2 |
| POST /jobs/{job_id}/retry、/cancel | 新 attempt 或取消请求 | 本人或管理范围 admin＋CSRF | 2 |
| GET /search?q=...&k=... | q去首尾空白1—2000字，k=1—50；页面列表/配置与索引ID/耗时 | 有效且已改密会话，AllowedScope先过滤 | 1B-4已实现 |
| GET /pages/{page_id}/image?preview=... | 真实PNG，按会话/page/render绑定地址，错误不返回文件路径 | 当前有效已改密会话＋文档可读＋本会话preview | 1B-5已实现 |
| GET /pages/{page_id}/thumbnail | 缩略图 | 文档可读 | 2，未挂载 |
| GET /documents/{id}/pdf | PDF 下载/Range 预览 | 文档可读 | 2 |
| POST /pages/{page_id}/regions/rank | question 或本人 search_record_id；候选排名 | 文档可读＋CSRF | 2 |
| GET /history、/history/{id} | 自己的历史，命中按当前权限再次过滤 | 本人；admin 跨用户留痕 | 3 |
| DELETE /documents/{id} | 202＋删除任务 ID | user 仅本人私有；admin 全库 | 2/3 |
| POST /admin/users | 创建普通用户，临时密码流程 | admin＋CSRF | 3（阶段1用CLI建号） |
| PATCH /admin/users/{id} | 启用/停用；不开放任意属性绑定 | admin＋CSRF | 3 |
| POST /admin/users/{id}/reset-password | 重置、强制改密、撤销会话 | admin＋CSRF | 3 |
| POST /admin/documents/{id}/publish、/unpublish | 共享状态变更、增加 epoch | admin 且为管理员上传的文档 | 3 |
| GET /admin/profiles | name、config_sha256、status；不返回物理路径/密钥 | 已改密admin | 1B-3已实现 |
| GET /admin/jobs、/admin/indexes | 系统任务、索引身份 | admin | 3，设计 |
| POST /admin/indexes/rebuild、/admin/profiles/{id}/activate | 校验过的 profile；返回任务/切换结果 | admin＋CSRF＋审计 | 3 |

初期用鉴权的任务轮询。原 `/progress/stream/{job_id}` 和 OCR 进度流不自动迁入；需要流时必须建立连接及每次发送时复查会话/归属，撤权就终止。原 `/clear/*`、按文件名 `/delete`、任意 `/config/update`、`/config/reset`、裸 `/files/*`、`/api/interpretability`、`/ocr/*` 不挂载为公开兼容入口。`/health` 仅给最少存活信息；依赖错误和详细状态限管理员。

输入边界：`k=1..50`，问题非空且建议最多 2000 字符；PDF 大小、页数和单次文件数采用配置上限并验证真实文件格式。路径、owner、角色、checkpoint、服务 URL 不能由普通请求指定。模型服务不接受客户端任意 URL 或本地路径。

### 1B-3实际认证契约

login/me的200响应均含user_id、username、role、must_change_password、csrf_token；login输入username/password。password输入current_password/new_password，新密码12—128字符且不同；成功204，撤销该用户全部会话并清Cookie，须重新登录。logout成功204，无body仍须JSON Content-Type。未首次改密时受保护业务入口403；普通用户访问admin/profiles403；有效且已改密admin200。当前以profiles/search验证门禁，其他业务随实现接入，不能泛称所有对象已授权。

写请求检查唯一可信Origin与JSON；password/logout增加唯一X-CSRF-Token。认证/admin响应含private,no-store及Vary Cookie。错误使用`{"detail":"错误码"}`，不会回显密码；下节ErrorResponse仍为未来设计。状态码/限速见[1B-3手册](stage1b-3-runbook.md#2-接口与正确顺序)。1B-5已接入SDK及UI内存CSRF生命周期，退出/换号/401清状态，浏览器改密新凭据由用户本人输入提交。

### 1B-4实际检索契约

search返回status=ok/empty、profile_id、index_generation、scope_version、timings_ms、items。每项有document_id/document_version_id/page_id、page_index/page_number、document_name、page_rank/page_score、width_px/height_px/render_sha256、region_status=not_requested；1B-5新增preview_url。尚无search_record_id或持久access_epoch，下方完整SearchResponse仍为目标设计。额外/重复参数422，未认证401、未改密403，范围变化409 SEARCH_SCOPE_CHANGED，依赖/身份异常503 SEARCH_UNAVAILABLE，队列满503 MODEL_BUSY；错误仍为detail字段。所有响应private,no-store及Vary Cookie。

模型/索引只由服务端选择；scope由SQLite生成，不信任客户端owner/profile，也不只信Qdrant的owner/visibility。新问题实际编码，即使重复问题也重新forward；空范围不调用模型/Qdrant。1B-5已接入SearchService和原文预览。

### 1B-5实际预览契约

preview_url是后端相对路径`/pages/{page_id}/image?preview=...`，浏览器只加同源/api前缀，禁止外域和其他路径。preview是本会话CSRF派生的HMAC(page_id/render_sha256)，不是Cookie或独立bearer令牌。GET仍检查有效会话/首次改密/ready当前版本/归属，再核验preview；未知、越权、缺失/错误/重复preview、额外参数都404 PAGE_NOT_FOUND，未登录401、未改密403，文件异常503 PREVIEW_UNAVAILABLE。

成功image/png，Content-Disposition为固定page-N.png，无磁盘路径；private,no-store/Vary Cookie、nosniff、no-referrer，无ETag/Last-Modified。Range/If-None-Match不跳过授权、不产生304。退出旧Cookie401，同账号新会话旧URL404，共享撤回404。文件读取后新事务复查，已经交付的字节不能收回。无PDF/thumbnail或裸files路由。

SDK重新生成PagesService及preview参数，但固定生成器通用实现把非JSON按文本读，不直接用于PNG；UI对服务器preview_url做白名单校验后用原生fetch/Blob/AbortController，统一响应401清理规则。未手改生成代码。

## 2. 结果字段（完整目标设计，非当前完整响应）

```text
SearchResponse
  search_record_id, profile_id, index_generation, access_epoch
  status: ok | empty
  timings_ms: queue, query_encode, page_search, total
  items[]:
    document_id, document_version_id, page_id, page_index, page_number
    document_name, page_rank, page_score
    width_px, height_px, render_sha256, preview_url
    region_status: not_requested | ready | no_candidates | parse_failed | rank_failed

RegionRankResponse
  page_id, render_sha256, parser_profile_id, candidate_hash
  region_profile_id, checkpoint_sha256, method, status, timings_ms
  regions[]: region_id, layout_id, rank, score, bbox_xyxy_px, type, text_source

ErrorResponse
  code, message, request_id, retryable
```

`page_number=page_index+1`。页面分数与区域分数不相互比较，不同 profile 分数不混排。API 不返回 tensor、物理路径、完整异常栈或服务凭据。无候选时返回空数组与 `no_candidates`；非有限区域分数必须有明确无效状态，不能把 `-inf/NaN` 写入 JSON。

## 3. 内部算法边界

下列名称是业务层的目标接口。当前 `ColPaliAdapter.load/encode_page/encode_queries` 以及 `maxsim_scores/top_k` 已实现CLI编码与排序；已有元数据库、auth/search路由与AllowedScope；HTTP query经内部管道调用原adapter，Qdrant授权检索已验证。接入Web后业务层负责权限，算法层只处理已授权输入，不扫描用户目录；输出ID必须属于本次输入。

| 模块 | 输入 | 输出与硬校验 |
|---|---|---|
| DocumentRenderer.render | 服务器解析的 PDF 路径、version、渲染配置 | 全部页面图像、尺寸、页序、哈希、PDF→渲染仿射变换 |
| ParserAdapter.parse | 文档版本/页序、可信资源路径、parser_profile | 固定候选集合：ID、bbox、类型、文本来源、版本；不接收问题/gold |
| PageEncoder.encode_pages | 可信页面图像列表、encoder_profile | 每页完整 `[1031,128]` 向量和 token 布局/身份；失败不可静默少页 |
| QueryEncoder.encode_query | 实际问题、同一 encoder_profile | 有效 `[T,128]` Q、attention/token 规则；必须实际编码新问题 |
| PageRetriever.search | Q、AllowedScope、index_generation、k | 过滤范围内的 Top-k 页与分数；空范围短路；过滤异常直接失败 |
| RegionRanker.prepare_page | 完整视觉 P、该页全部候选、region_profile | D 的 P′ 或缓存引用，不接收问题/gold |
| RegionRanker.rank | Q、P′、相同候选及尺寸、ranking_version | 固定候选排序、ID、分数；不生成新框 |

**`PageEncoder/QueryEncoder` 的CLI基础已通过阶段1A。** Snappy 的 `ColPaliClient` 原来请求 `/embed/queries`、`/embed/images`、`/info`，字段包括完整 embedding、patch 起点/长度/indices。下一阶段用进程内 adapter 和兼容转换连接 Qdrant；不保留一个可被浏览器绕过授权的额外模型服务。

## 4. 原 ColPali 契约与基线

冻结候选模型身份：`vidore/colpali` adapter revision `7754422bfa37f8e3cd771e13d4d7f07de3103c95`，依赖 `vidore/colpaligemma-3b-mix-448-base` revision `6ff0d944ea09c3ead97d2bc57427e3d4f01d192f`。这两个本地缓存目录已找到；不能用 Snappy 的 ColQwen3 fallback 加载。

阶段1A已在独立环境用正确 `ColPali/ColPaliProcessor` 类通过导入、离线加载和真实编码。显式本地base路径及 `adapter_kwargs={"_adapter_model_path": 本地adapter路径, "local_files_only": True}`，同时顶层 `local_files_only=True`；此方式绑定锁定的transformers 5.17.0，不能直接假设其他版本兼容。BF16、页面batch=1、query batch≤2；13个模型文件及实现源码哈希核对通过，不训练。旧环境临时目录/写入问题的系统根因未确定。

已有 Route V2 规定页面 `[1031,128]`：前 1024 行为 row-major 32×32 视觉 patch，最后 7 行为 prompt。严禁旧 `[7:]` 错位切片。区域排序只用前 1024 行；完整页面检索基线保留整个序列，使用 processor 对应的 MaxSim：`sum_i max_j <q_i,p_j>`，归一化及数值精度通过参考实现比对。

查询使用 `process_queries`，只删 `attention_mask=0` 的补齐行，并校验补齐向量全零；保留 processor 的真实增广 token，不自行截断、均值池化或删除特殊 token。`valid_query` 的零向量过滤不是替代 attention_mask 身份检查的理由。

阶段1A直接MaxSim与processor在相同完整向量、CPU float32下对照，容差 `atol=rtol=1e-5`，4题Top-3一致，最大差 `3.8147×10⁻⁶`。阶段1B仍需在相同授权页面集合上验证Qdrant基线，关闭pooling、量化和额外阈值。以后预算策略只改变用于检索的向量集合，必须把完整特征缓存单独保留或测量重新编码成本。

## 5. D-no-text 契约和部署身份

**2026-11-08 R21 / 2-5已实现内部入口。** regions.service.prepare_request(db,user,page_id,task_id,expected_encoder)复核当前活动版本、范围、索引、完整PageFeature与候选整集；rank_regions另外接question/ModelWorker，在真实query编码后调用CPU D，结束读事务并重查授权/auth_version/输入。仅内部principal接口，不替代cookie/session验证；2-6必须前后重新principal。无新HTTP/SDK，SearchHit仍not_requested。

ModelWorker.rank_regions(question,region_input,expected_profile)复用原私有JSON-lines管道，返回真实Q回执及regions状态/全部候选ID/布局ID/排名/有限分数/D身份/cache键/近并列；region_input由服务端组装，不接受浏览器提供路径或候选。DNoTextAdapter.prepare只生成/读取文档侧P′，rank使用当次Q。私有runtime cache键绑定文档版本/PNG/完整tensor/活动索引embedding/解析整集/模型代码；损坏失败、旧cache不覆盖。见[手册](stage2-5-runbook.md)、[同次Q参考](checks/stage2-5-reference.json)。

代码入口：`LayoutPatchD`、`InputAblatedD("text")`、`page_layout`、`patch_scores/region_scores`。参数量273410；早期三seed加载属于历史，R21仅固定seed0/epoch1重新strict load并实际forward。

`page_layout` 输入按 `layout_id` 升序排列的整页候选，每个含 `bbox/page_size/type/layout_id`；文本槽为 `[M,1024]`。D-no-text 在投影前置零文本槽，保留坐标、类型、邻接与 mask，因此无需为这一部署加载 BGE-M3。若改为带文本 D，则必须另外核验 BGE-M3 与节点文本来源，不能静默切换。

布局坐标映射到 448×448 模型空间；`coords=[x1,y1,x2,y2,width,height]` 归一化，邻接 `[1024,M]`。D 得到 P′ 后，patch 分数是 `max_i <q_i,p′_j>`；候选分数为原实现的 patch-IoU 加权均值，不增加阈值、损失、人工重排或按 gold 过滤。分数相同时保留冻结的候选 ID 顺序；接入时以原排序实现为基准核对。

**[R21已验证] 系统固定 seed0 / epoch1**：

```text
runs/retrieval/route_v2_exp3_attribution/20261007_135013/D-no-text/seed_0_epoch_01.pt
SHA256 18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b
```

上方路径相对只读原研究库；R21受控复制到本项目runtime/models/d-no-text，配置configs/d_no_text_local.json绑定SHA/代码，运行时不再读旧源码。选择依据是预先固定最低seed编号，其epoch按source_val选择，不比较外部表现。3开发缓存页及12组真实新Q参考通过；该部署不等同历史三seed均值，不把30.7969%作为此checkpoint系统成绩。

## 6. 解析器与坐标契约（R20 / 2-4已实现）

实际使用独立.venv-parser的MinerU4.0.10/docvortex0.5.10/ONNX Runtime1.30.0，Basic/auto/CPU；8 ONNX及5 YAML的SHA与本地revision358310b4f64b95f9fefc372ad899356e4111f376下载元数据匹配。配置/依赖锁/环境复制回执/实现SHA共同确定ParserProfile，与检索profile分离。11页真实解析/194候选、叠框与故障证据见[手册](stage2-4-runbook.md)。

POST /documents/{document_id}/parsing接JSON{}，本人ready当前版本显式排队；同profile重复幂等，retry_task_id仅重试当前failed/partial/interrupted任务，最多10次。GET同路由返回task/profile/version、每页pending/running/ready/no_candidates/failed/timeout/interrupted、数量/candidate_hash/PNG尺寸与hash，不返回正文/路径/候选框。当前权限逐次校验，写入Origin/CSRF/首改必需，shared只读、普通admin无private旁路。SDK已生成。未实现区域HTTP/rank接口或解析网页按钮。

ParserAdapter的实际内部入口backend.parsing.adapter.parse_page只接可信task/version/page/profile，不接query/gold。新三表parser_profiles/parsing_tasks/page_parses保存固定顶层候选及来源，后续D通过内部read_candidates重新授权/核对整集hash/逐项身份，不用旧候选回放冒充新解析。

docvortex.middle2.0顶层blocks全部导出，类型未知、重复ID、非有限/倒序/越界框失败；不同ID重复框保留，不裁剪或手工造框。省略blocks符合DocVortex默认空列表，真实空白页记no_candidates，显式null仍失败。文本来源native或OCR未区分，不称纯OCR/纯PDF或VLM描述。

返回候选以原PNG像素xyxy左上坐标，附document/version/page/index/number、width/height/render_sha256和parser_profile_sha256；candidate_id=page_id:block:index，canonical整集hash。重渲PDF必须PNG字节SHA与现有Page一致；记录PDF点尺寸/旋转/CropBox/矩阵和pixmap origin。当前仅rotation0、MediaBox起点0且CropBox=MediaBox，points→PNG矩阵[2,0,0,2,-pix.x,-pix.y]；单位框先乘parser页points再变换四角，不能直接乘取整PNG尺寸或448。旋转90/CropBox已实测拒绝，不影响页面检索/原图。

解析失败与页面ready分离，逐页硬子进程上限180秒（渲染复核另180），总900秒为页间检查点。启动running转interrupted且保留完成页；显式新attempt重做全页，旧产物不覆盖。partial/timeout/异常均可查，不把空候选当异常。

前端按实际图像内容矩形计算缩放及留白偏移的设计保持：display_x=offset_x+x*scale_x，y同理。50%/100%/150%、区域/裁剪权限及网页高亮尚待2-6，本轮离线叠框不冒充这些验收。

## 7. profile 变更的验收要求

profile 是不可变配置 ID；前端只能选择管理员激活的已验证配置。测试替身可检验 adapter 切换和错误路径，但必须标记测试运行，不能进入真实演示结果。预算方法未就绪时保持 `colpali_full_v1`，在页面显示“完整向量基线”；不下载第二底座证明可扩展性。
