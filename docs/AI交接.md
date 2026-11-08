# AI交接文档

## 当前交接：R29 / 3-4B历史侧栏与重新打开完成（2026-11-08，北京时间）

仅完成用户指定3-4B，停止于3-4C之前。见[网页手册](stage3-4b-runbook.md)、[本轮新运行与保护汇总](checks/stage3-4b-verification.json)。R28及更早报告只属历史。新基线runtime/verification/r29/before.json：HEAD af61ca794475cfc5e36923c74006f3edbacf868b，开工Git干净/空暂存、590选定文件；正式0008_parsing/2文档13页/13点13403向量与3000/8000/6333创建/命令身份，3001/8001开工空闲。

网页使用现有HistoryService POST /search及每次明确提交的新UUID；未知结果保留原输入/同ID，阻止新提交，只能显式同ID核对，无自动重试或换ID重算。同步重复锁、独立提交/列表/详情/写入代号，检索240秒/其他15秒有限等待，停止等待不等于服务端取消。本人历史每页10条、置顶/日期分组、重命名/置顶/删除菜单和原生确认；携带原version，无乐观写入，未知写只读刷新。取消默认焦点、删除需勾选，菜单方向/Home/End/Escape可用。

打开只GET详情，恢复原q/k/范围、原rank-score/身份/耗时及失效计数，以当前授权新签PNG，不推理/补Top-k/重放旧签名。显式重新检索才新ID/新编码。单文档目标只保留后端已授权标量，不伪造DocumentListItem；目标失效仍单文档、禁止自动切库/重算，不返旧名称/页/链接。选择历史、新检索、离页、换号/退出/401清旧选中、区域和Blob，迟到响应不能回填。原区域仅自动取状态，定位仍需明确点击。表/API/事务/迁移/产品SDK/算法/依赖均未改。

新运行196后端92.956秒（195通过、1既有Windows symlink权限跳过，真实junction通过）、13 CPU契约3.34秒、93前端953.301毫秒与tsc；修订后隔离生产build7.538秒通过。新非空0008/0011克隆迁0012，旧数据/事件/原文档列保持、重复一致/ORM无漂移，实际OpenAPI及重新生成62份SDK逐字节相同。89真实ASGI原链/19实际localhost HTTP通过；14新原ColPali冻结BF16 CPU query、3旧P′缓存命中/D0，A/B两模式、PNG、原区域/crop、保存重放/跨owner/admin拒绝、共享撤回/ABA/墓碑失效及历史删除410覆盖。

47真实浏览器检查通过：本人范围/10+2分页/五日期组、取消焦点/键盘、真实重命名和置顶刷新保留、已保存响应丢失后同ID核对不重算、PATCH未知只读确认、删除no-write503只发一次及中性清理反馈、3秒详情/列表迟到不回填、A/B换号/401清理、390/320与原生dialog。3次额外真实CPU网页检索验证文档库、显式重检索和单文档k5；打开/刷新/重登无新增forward，授权PNG可读。合计17新Q，network/页面编码/MinerU0；浏览器仅取区域状态，原区域/crop由本轮ASGI回归。console error空，4截图/browser.json留r29，临时页关闭/视口复原。

12条空历史由真实POST创建，仅日期/首条置顶在新库明确调整作分组夹具；503/延迟只在隔离middleware。浏览器永久删除成功未执行，真实成功由HTTP删除新空历史验证；浏览器覆盖取消/勾选与明确不写库503。文档失效仅在新ASGI/web克隆真实墓碑，cleanup关闭且专属根/集合前缀guard，不清源PDF/索引。原产物只读复用R22，不冒称新PDF/GPU/D/准确率/容量/完整BFCache/跨标签/无障碍认证。

失败保留：hook渲染时机/HTML属性顺序/旧退出提示断言修正后93通过；浏览器发现未知提交按钮误呈忙碌、删除清理反馈易误称已删，修产品/补断言/重建/重验。重建helper在taskkill后立即查端口发生关闭竞争，确认旧PID已无/3001空闲后加有限轮询恢复，8001身份保持。范围按钮误用radio、单文档check后控件卸载导致辅助验证失败，读新DOM确认已选，不重复提交；只读缺路径/rg通配和日期字符串夹具修订均留手册，没有放宽产品边界。

正式/留存保护、旧库可见Git/选定资源/模型依赖、761留存文件/源3完整集合、01—08/旧报告/AGENTS/.gitignore、HEAD/空暂存逐项见汇总；不是ignored全盘审计。09/10仅追加R29六步，R24—R28原字节前缀保留。8001/3001本批树按创建/命令/父身份核对后已停，CPU树结束，正式GPU树未启停；ignored文档/学习/runtime须另带，私密凭据及原始向量不公开。

**正式未部署：仍0008/原GET服务与旧前端构建。当前源码已接POST/历史，不能直接接0008。** 未来启用需另行新备份、迁移0012（经0009—0011）、单worker后端与前端构建重启并新验收。无正式凭据、旧库写入、下载、训练、换底座、暂存、提交或推送。

**下一唯一任务：3-4C管理审计与任务查询，等待用户另行明确指定。本轮停止，不进入主题或预算。** 下方旧轮次“下一步”均为各轮历史。

## 当前交接：R28 / 3-4A个人查询历史后端与SDK完成（2026-11-08，北京时间）

仅完成用户指定3-4A，停止于3-4B之前。见[历史后端手册](stage3-4a-runbook.md)、[本轮新运行与保护汇总](checks/stage3-4a-verification.json)。R27及以下均为历史，不替代本轮证据。新基线runtime/verification/r28/before.json：开工Git干净/空暂存，HEAD bbc37188976cc88dc1bc18fab0b9e9ac91e9f402、570选定文件；正式0008_parsing/2文档13页/13点13403向量和3000/8000/6333原创建时间/命令身份，3001/8001开工空闲。

0012仅新增query_requests/query_histories/query_history_hits/history_events四表，POST /search复用原真实检索。先短BEGIN IMMEDIATE预约，模型/Qdrant锁外，再锁内重查会话/首改/CSRF/完整scope，成功或合法空范围与全部命中/create事件/completed原子保存，失败不落半条正文。本人request_id并发一次执行、另一个409；完成同输入重放不推理，异输入409，failed/interrupted同ID409，删历史后同ID410不复活。启动将遗留running中断、不自动推理。每人1000条含预约，无静默过期，显式删除释放；无正文请求标记/最小事件仍保留，期限留3-4C制定。

本人列表/详情/重命名/置顶/删除与SDK完成，普通admin没有私人历史旁路。锁内版本/会话/CSRF复核，元数据/删除/事件同事务，事件失败全回滚；两连接同版本仅一人成功，锁前已加载但被撤销的会话仍拒绝。命中只存标量ID/hash/授权代次/原rank-score，不存名称/路径/URL/区域/crop/Blob、不以文档/版本/页FK阻碍物理删除。打开/重放用当前授权和版本重新过滤、新签当前会话PNG，不调用模型、不补Top-k；撤回/删除/ABA失效项只计数、不返回旧名称/页ID/分数/链接。历史删除移除本人问题/标题及命中，不删PDF。

本轮新运行196后端103.756秒（195通过、1既有Windows symlink权限跳过，真实junction保护通过）、13 CPU契约3.20秒、71前端785.323毫秒与tsc；非空0008/0011新克隆迁0012，旧表/原文档列/事件保留、重复一致、ORM无漂移；实际OpenAPI和62份重新生成SDK逐字节一致。89真实ASGI原链与35实际localhost8001检查通过；14新原ColPali冻结BF16 CPU query，一棵顺序worker，3旧P′命中/D forward0，network/页面编码/MinerU0。覆盖A/B原GET两模式/PNG、新POST保存与重放、跨owner/admin拒绝、12真实空范围/10+2分页、元数据、共享撤回/ABA/墓碑、历史删后410及原区域/crop。只读复用R22既有产物；文档仅实测墓碑，物理清理关闭并加专属根/集合前缀保护，不冒称本轮物理删除、新PDF/GPU/D/准确率/容量。

HTTP在新克隆两次真实停启后端，Cookie、原问题、标题/置顶/版本和幂等仍保留。非空模型guard仅一次明确503，无伪成功分数；成功非空由真实CPU原链覆盖。running标记在停机时显式插入再启动恢复，不是自然长推理硬杀；本批没有网页/浏览器/生产build运行，不把R27当新运行。产品自动/迁移/原链均首轮通过，原symlink跳过和既有Git换行提示保留，无本批未解阻塞。

49项最终保护检查通过：正式全表/schema/0008/原13PNG/完整Qdrant及原服务创建/命令身份与新基线保持；761份留存文件、源三集合完整向量/payload/config、R22及R27源DB保持。旧库可见Git/选定资源及模型依赖、01—08/旧报告/AGENTS/.gitignore、HEAD和空暂存不变；既有网页/组件/hook/client及旧SearchService字节不变。09/10仅追加R28六步，R24—R27原字节前缀保留，口稿96/100/99/100/100/95字；交接/progress/testing/规划/接口/架构/手册同步。不是ignored全盘审计，ignored资料/runtime须另带，私密凭据和原始向量不入公开报告。

8001两棵测试树均核对本轮PID创建/命令/父进程身份后停止，3001本轮未启动，CPU树结束，正式GPU树未启停。**正式仍0008，新增历史功能未部署；当前网页仍调用GET、不生成历史。** 启用须另行新备份、迁移0012（经0009—0011）、单worker后端及前端构建重启并新验收，新代码不能直接接0008。无正式凭据、旧库写入、下载、训练、换底座、暂存、提交或推送。

**下一唯一任务：3-4B历史侧栏与重新打开，等待用户另行明确指定。本轮停止，不做3-4C审计查询、主题或预算。** 下方旧轮次“下一步”均为各轮历史。

## 当前交接：R27 / 3-3完整删除与清理重试完成（2026-11-08，北京时间）

仅完成用户指定3-3，停在3-4A之前。见[删除手册](stage3-3-runbook.md)、[本轮新运行与51项收尾检查](checks/stage3-3-verification.json)。R26及以下均历史，不能替代本轮证据。新基线runtime/verification/r27/before.json：HEAD ecb66972a079cabea5c3be25148891cac56fae30，开工干净/空暂存、551选定文件；正式0008/2文档13页/完整13点13403向量、3000/8000/6333原创建/命令身份；3001/8001开工空闲。

仅本人可删，普通admin无跨owner旁路，共享接收者不可删。0011只加document_cleanups/deletion_events，新增本人列表/delete/cleanup状态/retry四API与SDK/网页。BEGIN IMMEDIATE锁后重查会话/首改/CSRF/归属/文档和授权版本；先deleted/private/access_version+1、任务取消意图和最小事件原子提交，202不代表物理完成。事件失败回滚，同输入精确重放noop、过期409，失败清理才增加attempt重试；完成后仍保留原删除身份幂等。旧列表/检索/PNG/区域/crop/上传解析和共享管理立即拒绝墓碑，不能被再次发布复活。

CleanupRunner先全量校验路径/根/reparse/跨文档引用/缓存归属，再逐索引代按精确点wait=true删除并核对保留点；清PDF/PNG、完整BF16/导出、job/解析/候选/P′及派生行。失败持久仍不可读，可重试/启动恢复running；完成将原名改通用墓碑、manifest去路径和候选。upload/ingest/parse/regions产物租约等已有写入退出再独占清理，墓碑不等长模型；每数据库仅支持单后端worker，不把进程内锁宣称多进程互斥。正式/留存库只读，实际清理只在专属副本根/集合。

新运行174后端90.363秒（173通过、1因Windows无symlink权限跳过，真实junction通过）、13模型CPU契约3.15秒、68前端689.253毫秒和tsc；隔离build7.192秒，实际OpenAPI与53份重新生成SDK一致。非空0008/0010新克隆→0011旧表/文档原列/事件保持、默认授权1/ORM无漂移/重复一致；正式未迁移。82真实ASGI原链及27 localhost HTTP：A/B两模式、PNG SHA、真实候选region/crop、共享接收者/admin跨owner拒绝、删除后旧入口404、存储失败不可读/重试、所有代精确点/文件/派生行清除和同名他人保持。14新原ColPali冻结BF16 CPU query，一棵成功顺序worker，4次旧P′命中、D0；network/页面编码/MinerU0。只读复制R22产物，不冒称新PDF/GPU/D/准确率/容量。恢复测试为持久running标记＋生产recover，不是硬杀重启。

28项真实浏览器通过：普通用户入口、10+2分页、取消默认焦点/勾选/Escape，真实删除202→清理失败→重试202→完成及副本PDF消失，503只发一次/未知提示、3秒迟到离页/换号隔离和390/320布局；console error空，4截图在r27，最后B已退出至登录页。网页一份已复制未入库研究PDF＋11明确元数据分页夹具，空索引专属集合；故障/503/延迟仅验收middleware。发现删除面板顶层重复挂载，已修产品、补SSR单main断言并重建/重验。没有浏览器建号/新密码或正式凭据使用，也不称完整BFCache/跨标签/无障碍认证。

51项最终检查通过：正式所有表/schema/0008/原13PNG/完整Qdrant与原服务创建/命令身份和新基线一致；616留存文件、源三集合完整向量/payload/config与R22/R26源DB保持。核对本批PID创建/命令后停止8001/3001，CPU树已结束；正式GPU树未启停。旧库Git可见/选定资源与模型依赖、01—08/旧报告/AGENTS/.gitignore/HEAD及空暂存保持，不是ignored全盘审计。09/10只追加R27六步，R24—R26原字节前缀完整，口稿96/99/95/98/95/98字；交接/progress/testing/接口/架构/规划及手册同步，新docs/学习/runtime受原忽略规则影响须另带。

失败保留：fixture自动runner竞争、PNG位置/旧分页409、SDK导出/列表参数、hook渲染及cwd、CPU helper误导入SQLAlchemy（无forward）、网页重复挂载均修复后复验。续接只读探查缺文件/GBK、通配误读单行向量audit进入工具输出后改键级摘要（未写公开报告）、口稿102/101字在学习追加前缩短、收尾凭据键误读退出和旧动态/documents/deletion先认证401被误期望404均留说明。首次完整保护失败报告保留，最终改核实际运行OpenAPI不含四删除API、原动态路由保留及401正确，再通过全部检查；没有放宽产品边界。仅既有构建/换行提示，无未解本批阻塞。

**正式仍0008，新增管理/共享/删除均未部署。** 未来启用须另行新备份、迁移0011（经0009/0010）、单worker后端及前端构建重启并新验收；新代码不能直接接0008。已交付字节和独立备份不能远程收回，不清历史证据。无下载、训练、换底座、旧库写入、暂存、提交或推送。本轮到此停止；**下一唯一3-4A个人查询历史后端/SDK，等待用户另行明确指定**，不做历史侧栏、审计查询、主题或预算。

## R26历史交接：R26 / 3-2共享发布与撤回完成（2026-11-08，北京时间）

仅完成用户指定3-2，停在3-3之前。见[共享手册](stage3-2-runbook.md)、[本轮新运行/保护汇总](checks/stage3-2-verification.json)。下一唯一3-3删除与残留清理，等待另行明确指定；下方旧“下一步”均为历史。

管理范围限定当前admin本人非删除文档，其他用户/管理员private及他人shared不进入管理范围，普通用户不能发布/撤回。发布须ready/有效当前版本/活动索引全页；撤回未ready仍允许且不删除文件/特征/向量/解析。0010新增documents.access_version默认1和sharing_events；BEGIN IMMEDIATE拿锁后重查当前会话/首改/admin/CSRF与文档/授权版本，真实改变加版本、当前同状态noop、过期409、最小事件同事务、事件失败全回滚。

授权版本进入scope/普通列表指纹/PageFile与v2 PNG/crop签名，搜索/区域推理、PNG/crop读取后新事务复查，撤回再发布ABA不会复活旧链接或回传处理中旧结果。内部regions.service另查目标文档scope；D输入/缓存键不改，原算法/配置/权重/profile保持。SDK已生成，管理员网页/每页10份/原生明确确认/取消默认焦点/独立代号/同步重复锁/15秒有限等待已接入；身份变化/离页清管理，成功或未知写结果清旧检索/Blob，未知写不自动重试。

新基线重新核实正式0008/2文档13页、全表/完整Qdrant与3000/8000/6333创建/命令身份；开工Git干净、HEAD e5e5a0d39a310605a4f7fddbd0af0c9b982e6024、534文件，见runtime/verification/r26/before.json。新运行151后端76.602秒（12新增）、13模型CPU契约2.51秒、58前端608.3835毫秒（12新增）、tsc/隔离生产build9.754秒通过；实际OpenAPI一致，新生成48份SDK逐字节相同。

新非空0008克隆→0010保留旧文档列/默认1、ORM无漂移/重复相同，另非空0009新克隆保留旧账号事件。24真实localhost共享HTTP、63真实ASGI原检索/共享区域及另12共享文档库检查通过；A/B两模式、PNG hash、区域/crop、非本人解析/管理拒绝、撤回/ABA旧链接404与新链接有效。总12次原ColPali新Q同冻结权重/实现BF16 CPU编码，两棵顺序worker，3次既有P′命中/D forward0，network/页面编码/MinerU0。R22 PDF/完整特征/候选只读复用，owner仅新克隆转admin，不是新管理员上传，不冒称新GPU/D/PDF/准确率/容量。

真实浏览器24项含10+2分页、未勾选阻断/取消/焦点/Escape、实际隔离非敏感研究文档发布/撤回200、503只发一次与未知反馈、3秒列表离页不回填、退出/A换号无共享入口和390/320无横溢出。11分页行是明确未入库元数据夹具；503/延迟只在验收middleware。console error空，4截图/browser.json留r26；已退出、关闭临时页和复原视口，没有建号/重置新凭据或正式/云端授权。

68项最终检查通过，437处本地文档链接有效；正式全表/schema/0008/原13PNG/完整Qdrant及原服务身份与本轮基线保持。已核对本批PID创建/命令后停止8001/3001，CPU树结束；正式GPU树未启停，正式凭据未使用。旧库Git可见状态/选定资源与模型依赖、01—08、旧报告、AGENTS/.gitignore和HEAD/空暂存保持；09/10原R24/R25字节前缀保留，R26六步配对口稿94/97/94/99/99/95字。不是旧库ignored全盘审计，ignored资料/runtime须另带，口令及向量audit不公开。

失败保留：首轮路由白名单漏三个共享接口后151重跑通过；验收解析路径误写在最终测试/真实链前改为/parsing，拒绝来自原权限；一次编排JS括号错误未执行、只读猜测文件不存在、口稿101字精简到99后只补10、浏览器默认窄屏隐藏退出后重新观察展开导航、收尾助手摘要函数名误记在import处退出后按真实函数修正，均未放宽产品边界。仅既有构建/换行提示，无本批未解阻塞。

**正式仍0008，新增管理与共享未部署。** 未来启用须另行新备份、迁移0010（经0009）、单worker后端与前端构建重启并新验收；新代码不可直接接0008库，v2链接须重新获取。本轮不做删除、个人历史、审计查询、主题或预算，无下载/训练/换底座/暂存/提交/推送；资料已同步，本轮到此停止。

## R25历史交接：R25 / 3-1B用户管理网页完成（2026-11-08，北京时间）

用户写“接下来完成2-1B”，结合上一轮3-1A及规划唯一下一批，已在开工说明按3-1B用户管理网页理解，仅完成此批。见[网页手册](stage3-1b-runbook.md)、[本轮新运行/64项保护汇总](checks/stage3-1b-verification.json)。下一唯一3-2共享发布与撤回，等待用户另行指定；下方旧“下一步”均为各轮历史。

实现管理员专属入口/每页10条安全账号卡片、建号/启停/重置/撤销原生确认弹窗，接原SDK；无新表/API/迁移/算法/依赖/产品SDK改动。新密码由本人两次输入，仅本次非受控表单/请求，提交清空，不入React状态/应用存储或提示，不获取/显示已有密码/哈希。独立管理列表/写入代号、同步防重复和15秒等待上限；结果未知不自动重试写入。离页/新检索/退出/换号/首改/401/403清管理，角色变化重查，本人停用/重置/撤销成功清全工作台/Blob并退出，未知本人结果先查身份；最后管理员保护仍在后端公共事务。

新基线`runtime/verification/r25/before.json`重新核实正式0008/2文档13页、完整Qdrant、端口/CIM与524文件；开工Git干净、HEAD e7765bfdbcff962623c96903d5cf2de32904ce50，不能沿用R24当时42行改动或旧测试结果。新运行通过139后端62.309秒、13模型CPU契约2.74秒、46前端537.6499毫秒（13新增）、tsc及隔离生产build11.320秒；实际OpenAPI相同、重新生成到隔离目录的43个SDK文件逐字节相同。

新非空正式克隆0008→0009仅加事件表、旧表保持/重复相同，33实际localhost管理HTTP＋4 CLI；46真实ASGI原链发6次新Q，同冻结原ColPali BF16在CPU编码，A/B两模式、PNG哈希、区域/crop与管理撤销后的旧入口拒绝均通过。两次既有P′缓存命中、D forward0，network/页面编码/MinerU0；只读复用R22既有产物，不冒称本轮新D/GPU/PDF/准确率/容量。

真实浏览器在新web.sqlite3及独立8001/3001生产前端副本执行25项：10+5分页、取消清草稿/焦点、真实启停/revoke200、最后管理员409、本人撤销退出、A换号无管理、角色403重查、3秒迟到列表不回填、503未知反馈、390/320无横溢出与原生弹窗键盘/Escape。503/延迟/角色变化是明确隔离夹具，未加入产品后门。浏览器没有输入/提交建号或重置的新凭据；其写入分派/一致性/提交清空/防重复由前端契约和隔离真实HTTP覆盖，不冒称完整浏览器改密验收。console error为空，三份截图及browser.json在r25；临时标签已关、视口复原。

64项最终检查通过，424本地文档链接有效；正式全表/schema/原13PNG/完整Qdrant及3000/8000/6333创建/命令身份与新基线一致。隔离角色夹具已恢复，重查本批PID创建时间/命令后停8001/3001，两端口空闲；正式GPU树未启停，未用正式凭据。旧库Git可见状态/选定资源及模型依赖、01—08/旧报告/AGENTS/.gitignore和HEAD/空暂存保持；09/10原R24字节前缀完整，新增R25六步口稿88/92/95/95/98/97字。不是ignored全盘审计。

失败保留：辅助命令cwd误置未写入；属性顺序断言过严；验收辅助import遗漏；原链隔离Origin配置不符在登录处拒绝、无模型forward；浏览器label歧义；停服务时全机CIM输出GBK解码。均修验法/隔离配置后复验，停服务改限定已保存PID并核对身份；没有放宽产品权限/算法/事务。完整失败/命令见手册和报告。

**正式仍0008，管理API和本批新页面未正式部署。** 未来启用须另行新备份、0009迁移、单worker后端及前端构建重启并单独留证据，不能把本轮隔离验收当部署。交接/progress/testing/接口/架构/规划及09/10已同步，01—08和R24留历史，ignored资料/runtime须另带，私密口令/审计向量不公开。只完成3-1B，不做共享/删除/个人历史/主题/预算，无下载/训练/换底座/暂存/提交/推送；本轮到此停止。

## R24历史交接：3-1A用户管理后端与SDK完成（2026-11-08，北京时间）

仅完成用户指定3-1A，停止于3-1B之前。见[本批手册](stage3-1a-runbook.md)、[新运行/保护汇总](checks/stage3-1a-verification.json)。新增0009_account_events仅一张最小事件表，五类管理API及生成SDK；原账号/会话表和算法配置不变。建号强制首改；启停同状态noop、真实变更/重置/撤销提升auth_version并撤销所有旧会话。API和CLI共用BEGIN IMMEDIATE，锁内重查操作者/CSRF和最后启用管理员；业务拒绝记固定事件，账号/撤销/成功事件同事务，事件失败全回滚。修复R23的F01，覆盖双管理员自停/交叉停用及锁前已加载cookie后撤销的竞争；不只是前端按钮保护。

本轮新运行：139后端（含17新增）、13模型CPU契约、33前端、tsc；非空0008克隆→0009旧表不变及重复迁移；33真实localhost管理HTTP、4实际CLI；46真实ASGI原检索/区域回归。A/B两模式、原13页PNG与unavailable、新完整特征页D/crop、管理撤销后search/PNG/status/rank/crop401及新会话旧签名404通过。6次新问题由原ColPali冻结权重/实现BF16在CPU编码，1次D前向23.895ms/1次既有缓存命中；network0、页面编码0/MinerU0。只读复用R22产物，不冒充新PDF/GPU/浏览器/准确率/容量或官方评分验收。正式GPU驻留树未停。

新基线`runtime/verification/r24/before.json`确认正式0008_parsing/2文档13页、integrity ok/FK0及Qdrant13点13403向量，开工42行未提交状态已保存并保留。正式全表/schema/PNG/完整Qdrant与本轮基线一致，3000/8000/6333监听身份保持、8001验收后已停；正式凭据未用。**正式仍运行原0008服务，未部署管理API；正式启用新代码前需备份、迁移0009和单worker重启，本轮不执行。** 进程身份见R24汇总，未来操作仍须重查CIM创建时间/命令，不能只复用PID。

失败如实保留：首次seed修订白名单漏0009，setup失败留下16个已知临时库，逐文件/空目录清理完成；第二次Cookie重放jar冲突改测试，锁超时发现错误响应又写心跳掩盖503，修产品错误处理后复验通过。未放宽权限/事务/模型约束。日志及隔离口令/向量仅在忽略runtime，不打印公开。09/10六步配对，01—08/旧报告/.gitignore及旧库可见Git/选定资源、模型依赖保护；不是ignored全盘审计。新docs/学习文件仍被忽略，交接须单独携带。无下载、训练、换底座、暂存、提交、推送。

**下一唯一任务：3-1B用户管理网页，等待用户明确指定。本轮停止；共享/删除/个人历史/主题/预算均未实施。** 下方旧轮次计划不覆盖本段。

## R23历史交接：阶段2复核与阶段3规划（2026-11-08，北京时间）

本轮仅核查/规划，不开发阶段3。阶段2仍为R22完成适用应用出口；[R23复核与问题](stage2-review-r23.md)、[本轮证据](checks/r23-stage2-review.json)、[最新路线图](项目开发阶段规划与任务.md#stage3)。重新通过122后端/13 CPU契约/32前端/tsc；未重跑GPU/MinerU、浏览器/build或服务重启。历史R22检查不冒充本轮运行。

只读核实正式0008_parsing/2文档13页、integrity ok/FK0，Qdrant13点13403向量与DB身份一致；R22隔离36页中的新增23页特征/导出/PNG/候选哈希、450候选保持。原13页PageFeature仍空，区域unavailable符合旧页约定；正式未新增23页。3000/8000/6333已新查监听/身份，8001无监听；匿名保护正常，health不代表模型就绪。开工已有42行Git改动状态，全部保留；未用正式用户凭据，未启停正式服务。

**明确缺口F01：**本地`auth/accounts.change_account`可停用最后启用管理员，临时库实测1→0；尚无管理HTTP，不是普通用户远程越权证据。必须在3-1A公共业务事务中修复、覆盖CLI/API与并发；本轮未修产品代码。几何/准确率/容量/外部部署/方法二等原限制保持。核查脚本一次SQLite临时清理失败及执行策略拒绝已如实记入复核，修正探针后复现成功。

用户新增的查询历史重命名/置顶/删除安排3-4A后端、3-4B侧栏，审计查询另3-4C；主题切换独立3-6，不重做阶段2。原3-1细拆A后端/SDK、B网页。建议阶段3开工创建09/10并同步AGENTS规则；本轮收尾在07/08续写，01—06及旧报告保留，新docs仍忽略须单独带。

收尾：正式全表/schema/原13页PNG及完整Qdrant、本轮基线中应用代码、01—06/旧报告、HEAD/空暂存保持；386本地链接有效，07/08四步口稿92/88/93/93字。核查探针连接清理已修正，策略拒绝后改为核对过的明确单文件/空目录清理成功；未残留该临时库。服务前后身份另留runtime/verification/r23。没有暂存、提交、推送。

**下一唯一任务：3-1A——用户管理后端/SDK。等待用户明确指定。本轮停止，不实现历史、主题或其它阶段3代码。** 下方均为各自日期的历史记录，旧“下一步”不覆盖本段。

## R22历史交接 / 2-6完成阶段2适用出口（2026-11-08，北京时间）

用户授权的下一唯一2-6已完成，停止于阶段3之前。见[手册](stage2-6-runbook.md)、[汇总/修改文件](checks/stage2-6-verification.json)、[HTTP109项](checks/stage2-6-http.json)、[网页26项](checks/stage2-6-browser.json)、[重启前6项](checks/stage2-6-recovery-before.json)/[重启后21项](checks/stage2-6-recovery-after.json)、[原13页18项](checks/stage2-6-legacy.json)、[86项保护](checks/stage2-6-protection.json)、[实际成本](checks/stage2-6-cost.json)。开工Git干净，旧同范围窗口未活动；中断增量接续，未重复2-5。新基线在stage2-6-preflight.json、source-state-r22-before.json及runtime/verification/r22/metadata-before.sqlite3，历史报告未冒充新运行。

实现GET /pages/{id}/regions/status、POST /pages/{id}/regions及签名crop GET；复核cookie/首改/Origin/CSRF、当前document/version/page/render/index/parser/task/候选整集/D身份，推理或读PNG后新事务重查会话和全部输入。裁剪按原PNG像素向外取整，绑定当前会话，不公开路径/正文/静态目录；admin普通接口无private旁路。无表/迁移/算法/config/权重/依赖变更，正式仍0008。原13页未自动编码/解析，缺PageFeature显式unavailable，原检索/PNG仍可用。

隔离随机账号A/B同名两份此前未选完整新PDF12/11页，真实上传→23页原ColPali编码→36页活动库→23页真实MinerU→450候选（文字301/标题42/公式96/图8/表3）→新Q/Top-k→真实D/授权crop。均private/版本1；23份完整BF16[1031,128]/1024视觉行及精确float32导出新核验。[特征/解析回执](checks/stage2-6-artifacts.json)、[四类视觉抽查](checks/stage2-6-visual.json)可追溯，无gold或预测表构造输入。state/recovery-private含隔离凭据禁止打印；正式凭据未使用。

网页独立区域/crop代号与Blob回收、显式解析/定位、Top5类型/编号/分数、同frame SVG及50/100/150%缩放。实际1920/1366/390/320无body横向溢出，三档原像素框误差<0.003px；A/B真实问题/PNG/crop对应，选页/新检索/退出/换号/过期清旧证据。未提交草稿不会替换已提交Q。显式失败/6秒延迟/过期夹具与正常推理分开；第二次精确延迟验证0.523秒清空，实际D继续完成但不回填。真实重启时auth/me碰到断连先隐藏工作区，重连再见撤销；不冒称浏览器区域请求直接401，区域HTTP撤销另有证据。解析/模型失败原图保留，模型失败只重试定位。

最终122后端57.472秒、13模型CPU契约2.76秒、32前端415.3864毫秒、tsc/生产build通过。[4组页面官方参考](checks/stage2-6-page-reference.json)最大差3.7001953110404884e-6；[14组同Q原定义D参考](checks/stage2-6-D-reference.json)P′/分数最大差0、排序一致。容差与严格273410参数/seed0/epoch1/checkpoint/profile保持。固定3开发样本一致性是R21历史，未冒充本轮复跑；本轮不是区域准确率评价。

实际23页面forward、10检索Q＋14区域Q共24次query编码（含重复/两次清空后仍完成）、7 D forward/7缓存命中，3棵先后worker，network0。MinerU294次ONNX/回执374.123秒，D CPU forward24.359毫秒不含输入/hash/cache/加载；两轮原定义参考6+14共20 forward另计。CUDA peak allocated8696922624字节不是进程总内存。解析几何仍限制零旋转/零MediaBox原点/CropBox=MediaBox；物理页序与论文印刷页码区分。不宣布T01—T15整表、研究效果、并发容量或任意PDF通过。

86保护确认正式全表/schema/原2文档13页及完整Qdrant、复用24页、R19/R20/R21源库、11份旧BF16/导出、旧项目Git/选定资源/模型环境、锁与01—06/.gitignore不变；非ignored全盘审计。正式已恢复新backend.main:app（监听59748/启动器55848）、生产前端3340，6333 Docker49880保持；8001/隔离模型树已停，浏览器回正式登录页/视口复原。PID仅快照，启停前重查CIM命令/创建时间。

[失败记录](checks/stage2-6-failures.json)保留SDK可选items、旧白名单、UI选中即卸载、首次延迟时序未定、过期夹具触发约束及匿名空JSON422等；分别修正/复测，未放宽安全/算法/数据库约束。仅既有构建/换行提示，无本批未解阻塞。资料及07/08六步已同步，01—06保留；新docs受原忽略规则影响须另带。无下载/训练/换底座/暂存/提交/推送。

**下一唯一任务：3-1——用户管理。等待用户明确指定；本轮停止，不自动进入阶段3。**

R22收尾新检查：[69项资料一致性](checks/r22-document-checks.json)通过，07/08六步同日期/轮次/标题，口稿86/90/88/94/91/98字，链接存在、01—06/.gitignore哈希、HEAD及空暂存保持。Qdrant网络body审计仅后6次真实检索，Top-k前完整目标白名单12/5/8/12/11/12及版本/profile/index、exact/limit和返回子集已复核；早先8001的4次无该wrapper日志，不扩大证据范围。页面参考0次编码明确是参考进程自身复用输入，R22全轮实际23次另列，原分数/容差未改。收尾只改资料/验收脚本，未重复推理或进入3-1。

## 以下为R21历史交接 / 2-5（2026-11-08，北京时间）

本轮只完成D-no-text真实内部推理适配，停止于2-6之前。见[手册](stage2-5-runbook.md)、[汇总/修改清单](checks/stage2-5-verification.json)、[来源22项](checks/stage2-5-sources.json)、[开发缓存](checks/stage2-5-consistency.json)、[真实输入](checks/stage2-5-real.json)、[同次Q参考](checks/stage2-5-reference.json)、[回归](checks/stage2-5-tests.json)、[原链32项](checks/stage2-5-search.json)、[最终保护65项](checks/stage2-5-protection.json)。

新基线/在线备份在checks/stage2-5-preflight.json、source-state-r21-before.json及runtime/verification/r21/metadata-before.sqlite3；正式0008、2文档13页、解析三表空。初读Git干净，预检脚本创建后的status如实另存；未发现同范围活动修改。8份核心源码两旧库哈希一致，最小推理闭包受控迁入d_core，SOURCE.json记录来源/裁剪/哈希，生产不依赖旧sys.path或实验CLI。源码未附许可证，不宣称分发授权。

固定seed0/epoch1，checkpoint SHA18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b，本地副本runtime/models/d-no-text/seed_0_epoch_01.pt，1099555字节；严格加载273410参数。source_val选择文件/config/weights清单本轮互相核对，未训练/按外部表现选seed。配置configs/d_no_text_local.json当前SHA3da9cc23feb53c53a3d5a59cecf2d02be1836afe14adfa9ed66495f253c9b437绑定checkpoint及算法代码。

内部regions.service组装授权活动页/版本/索引/完整BF16/真实候选，原持久ModelWorker编码本次新问题后同Q接CPU float32 D。只用前1024视觉patch，1031全序列及原检索底座保持，不用[7:]或预算序列，不加载BGE-M3。rank后结束读事务，重查principal状态/auth_version/授权/输入。该内部入口没有cookie会话边界；2-6必须调用前后复核会话，不能直接当公开API。

不可变P′缓存runtime/regions/d-no-text/{key}，float32[1024,128]，身份含文档/版本/页/活动索引、PNG尺寸/hash、encoder/完整tensor/索引embedding、parser/task/候选整集、D profile/checkpoint/源码。问题不入键，损坏拒绝、不覆盖旧缓存；11页含manifest共5800284字节，完整BF16和导出另存保留。无新表/迁移/公开API/SDK/网页改动，SearchHit.region_status仍not_requested。

预设CPU float32/4线程/确定性/atol1e-6 rtol1e-5，精确并列layout_id升序；近似并列仅记录不改排。冻结开发manifest首3个source_dev页/每页首query_id的候选ID/P′/分数/排序一致，最大绝对差0。原定义仅离线参考命名空间执行，无gold/预测输入。

只读复用R19真实上传5/6页完整PDF及R20真实MinerU候选：11页194候选、11真实D forward、12当次真实query；第12次新问题复用P′。全部12组同Q原定义参考P′/分数最大差0、排序一致；独立进程cache命中D0。不是R21新上传、未见测试集或区域效果达标。区域query编码回执1008.566毫秒，D CPU forward29.963毫秒不含布局/hash/cache/加载；CUDA峰值allocated6006474240字节不是总进程内存。开发对照3轮原9＋迁入9 forward；真实Q参考12原定义forward，合成测试调用另见日志。

最终112后端53.141秒、9 D/缓存＋4原模型契约2.58秒通过。非法候选/短特征/损坏cache/非有限分数/精确并列/空候选/严格加载及推理中撤权有适用检查；替身不冒充真实D。32实际ASGI检查另含A/B双模式4次真实原ColPali检索与PNG；共16真实新query，顺序worker32612/57424、network0，页面编码0/MinerU0/训练0。未新跑浏览器/build/区域HTTP/高亮/缩放/准确率/容量或完整阶段2验收。

65最终保护确认正式全部表/0008、原13与复用24页完整向量/payload/config、R19/R20源库、11份BF16/导出及旧库Git/选定资源/依赖、01—06/.gitignore不变；不是ignored全盘审计。正式仅匿名localhost检查、未用正式身份。8000实际54984（启动器47100）、3000 55840、6333 Docker49880保持，8001空闲、测试模型已停，未启停正式服务；PID启停前重查CIM身份。

[失败记录](checks/stage2-5-failures.json)保留旧环境临时/写入限制、Web discover误加载pytest、测试fixture重复计数、公开health误用private缓存断言及读取/文档补丁错误；均定位，未放宽算法/容差/授权。隔离R21口令和认证行因验收改变，不声称该克隆全表保持。资料及07/08六步同步，01—06保留，docs按原规则忽略须另带；runtime副本/缓存不随Git。无下载/训练/换底座/暂存/提交/推送，无本批未解阻塞。

**下一唯一任务：2-6——授权区域接口、高亮与阶段2整体验收。用户指定后才开始，本轮停止。**

## 以下为R20历史交接 / 2-4（2026-11-08，北京时间）

只完成真实MinerU解析与坐标契约，停止，不进入2-5/D/区域网页。详见[本批手册](stage2-4-runbook.md)、[汇总/修改清单](checks/stage2-4-verification.json)、[来源坐标61项](checks/stage2-4-output.json)、[视觉抽查](checks/stage2-4-visual.json)、[故障15项](checks/stage2-4-faults.json)、[真实HTTP46项](checks/stage2-4-http.json)及[最终保护42项](checks/stage2-4-protection.json)。

本轮新核实0007、原2文档13页、端口/依赖/原模型资源及可见同项目窗口未加载；初始Git干净。[预检](checks/stage2-4-preflight.json)及runtime/verification/r20/metadata-before.sqlite3为新基线。历史报告不冒充新运行，正式凭据未输入、使用或更改。

新建独立.venv-parser：已有112包17208文件按RECORD/SHA复制，无源sys.path/.pth/launchers，无下载。MinerU4.0.10/docvortex0.5.10/ORT1.30.0 Basic ONNX CPU；8个ONNX共855806337字节及5YAML新哈希与本机缓存revision/etag相符，revision358310b4f64b95f9fefc372ad899356e4111f376。模型仍只读原路径，上游锁改到私有attempt/home。Python层禁网/禁额外子进程/attempt外写入，非OS沙箱；精确NUL设备可作空流，3次cmd.exe平台探测仍拦截，不能混称网络。

0008仅新增parser_profiles/parsing_tasks/page_parses，不动原表/检索profile/索引代。候选以固定canonical JSON整集存储，不宣称Region派生表已接D。POST /documents/{id}/parsing为本人ready当前版本显式排队；同profile重复请求幂等，retry_task_id绑定当前失败/partial/interrupted尝试，最多10次，旧产物保留。GET同路由按当前身份/版本授权，只回状态/数量/hash/尺寸，无路径/正文/框。共享只读，普通admin无private旁路；Origin/CSRF/首改保留。没有自动扫描旧13页或新网页按钮。

每页独立真实CPU子进程；重渲同版PDF须PNG字节hash/尺寸一致。DocVortex2.0全部顶层块经points→PNG矩阵映射；首版仅rotation0、零MediaBox原点、CropBox=MediaBox，旋转/裁剪明确拒绝，页检索不受影响。ID重复/未知类型/非法框失败，不裁剪或造候选；真实空白省略blocks按上游默认空列表记no_candidates，null仍失败。文本来源native或OCR未区分，不称VLM文本。内部read_candidates重新授权并核对版本/配置/整集与每项身份。

持久页状态pending/running/ready/no_candidates/failed/timeout/interrupted，部分失败task=partial。启动running→interrupted、保留已完成页；重试新task全页执行。渲染复核/解析各180秒硬子进程上限，900秒总时限在页间检查，不称强中断算子。候选提交前检查当前归属/版本/PDF及页面身份，解析从不修改Document.ready/Index/PageFeature。

隔离复用R19真实上传5/6页完整PDF（不是R20新上传或未见测试），当前profile11页194候选：text152/title31/image5/table5/equation1，168次ONNX run，回执合计89.671秒。61来源/坐标检查和11页总览＋A4/B5原尺寸图表文字叠框通过。两种长宽比空白页真实no_candidates；90度/CropBox拒绝、0.25秒强制子进程超时/损坏PDF异常15项通过，明确夹具且未入索引。前端缩放、区域排序/高亮、检测召回、任意PDF支持均未宣布通过。

104后端44.447秒、25前端411.3375毫秒、4原模型CPU契约3.95秒、tsc/生产build通过。46项真实localhost HTTP：最终6次真实原ColPali query与授权PNG，含解析failed注入后的2次实际检索，状态后恢复；A/B/管理员无越权。首轮漏JSON退出探测失败前另3query仍计成本，共9次、两棵顺序worker、network0。24份旧完整BF16 1031×128/1024patch及精确float32导出CPU新核验；本轮页编码0，D0。未重跑官方评分/准确率/容量。

开发探针/重复解析成本保留：44页请求入口、38worker回执、记录552次ONNX run/332.170秒；6个无worker回执含几何拒绝/异常/超时，未推断未完成成本为0。首版旧guard混计cmd.exe为network的失败已保留，最终11页网络/越界写为0。

正式0008的19迁移检查、5匿名HTTP及42保护检查通过：原各表指纹/2文档13页/完整Qdrant不变，新三表空，integrity ok/FK0/重复迁移不变；原解析源码/13资源及下载元数据、旧项目Git/选定文件/模型环境、R19源库不变。复用24页集合在末尾新算指纹，不能声称有R20开工时的24页指纹。正式仅匿名首页/health/401/no-store及上传Origin403，不用正式身份。

最终8000实际监听PID54984（启动器47100）、3000 PID55840、6333 Docker PID49880；8001/解析/测试模型树已停。按CIM创建时间/命令守卫重启，PID仅快照。运行记录runtime/verification/r20；正式无需重建原13页。SDK已生成；页面SearchHit.region_status仍not_requested。

[失败记录](checks/stage2-4-failures.json)含Windows长路径、NUL/平台探测计数、开发中profile变化拒绝、空blocks默认值、错误unittest discover环境及HTTP退出请求缺JSON；无未解本批阻塞。仅既有baseline-browser-mapping/util._extend提示，无升级。资料同步交接/progress/testing/需求/架构/接口/路线图/指南/source-audit及07/08六步。01—06/旧证据/.gitignore保持，旧库检查不是ignored全盘审计；无下载/训练/换底座/暂存/提交/推送，新docs仍被忽略须另带。

**下一唯一任务：2-5——D-no-text真实推理适配。用户指定后才开始，本轮停止。**

## 以下为R19历史交接 / 2-3C（2026-11-08，北京时间）

本轮只完成上传/任务网页、恢复与重试（含取消检查点）。见[手册](stage2-3c-runbook.md)、[汇总/修改清单](checks/stage2-3c-verification.json)、[网页36项](checks/stage2-3c-browser.json)、[HTTP39项](checks/stage2-3c-http.json)、[运行30项](checks/stage2-3c-runtime.json)、[正式29项](checks/stage2-3c-formal.json)和[文档保护](checks/r19-document-checks.json)。不进入2-4/MinerU/D/高亮/历史/预算方法。

重新读取必读文档并核实0006/原2文档13页、依赖、端口、Git干净及可见同项目窗口idle/notLoaded；新预检/在线备份在checks/stage2-3c-preflight.json及runtime/verification/r19，旧项目边界为source-state-r19-before/final。历史报告未冒充新运行证据，正式凭据未读取/使用/更改。

0007只在jobs追加nullable cancel_requested_at并增加job_attempts，已有任务仅回填当前attempt，不虚构历史。本人GET /jobs游标列表、GET /jobs/{id}明细及POST retry/cancel使用同一job/document/version；写入须Origin/CSRF/已首改身份和当前attempt，迟到操作409；admin普通接口无跨用户旁路。最多10次显式尝试，重试核验原PDF大小/SHA；缺失不允许重试，损坏需重新上传。

取消receiving/queued可立即终止；running保存请求并在渲染后、页间、候选写入间与最终激活事务复核。当前GPU算子可继续，不能称已强杀。默认总时限900秒（1—7200可配），检查点执行，单次操作仍有原有限超时；重启running/receiving标interrupted，已请求取消则cancelled；候选保留但不激活。旧attempt/产物不覆盖。

工作台接上传与本人任务，文件和幂等ID仅内存，不用localStorage存私有任务。上传45秒，列表/控制15秒，2.5秒轮询且10分钟暂停可手动刷新；停止HTTP等待明确提示服务端可能已收，同标识重发不重复创建。任务状态从服务器恢复；退出/换号/隐藏/401清状态，列表/上传/控制代号独立于query；任务变化清旧结果/图并刷新授权范围。completed只回真实列表按名称筛选，仍需显式选择ready文档。

实际最终87后端38.671秒、25前端377.422毫秒、tsc/Next生产build、4原模型CPU契约2.35秒通过。首轮聚焦的seed revision白名单/测试嵌套lifespan锁，完整回归旧路由白名单均已修，失败日志保留；仅既有baseline-browser-mapping提示，无依赖升级。OpenAPI重新导出，SDK由生成器生成。

隔离克隆原13页，按文件名/页数选两份此前未选的完整5/6页PDF，无gold。A在真实编码/候选核验结束且最终检查点已过、激活事务前请求取消，释放显式gate后cancelled、原13页仍活动且候选failed；同job attempt2完成。B真实CPU渲染后显式RENDER_FAILED，attempt2渲染后真正硬停后台树；重启interrupted、attempt3完成。网页/DB保留[取消,完成]及[失败,中断,完成]，每版本只一套Page。两模式A/B4次真实query与4个PNG对应，Qdrant Top-k前白名单页数5/10/6/14。

共16次page forward（A取消尝试5次仍计成本）、激活11份新完整特征、4次成功query；因实际重启先后两棵worker PID40440/36316，network0。16份BF16完整1031×128/1024patch及float32导出CPU核验通过；不把预算序列给D。算法未变，未重跑官方评分/准确率/容量或GPU算子中断实验。8秒上传响应延迟、渲染失败和gate为明确隔离注入；另10个cancelled元数据仅分页/长名夹具，不冒充上传。发送等待中止/同ID重发仍三份真实任务、queued取消无编码、非法PDF422；1920/1366/390/320、Enter展开记录、换号/刷新恢复/首改门禁通过。首改未输入新密码；断连先清任务，定时auth复核后转unavailable，重连恢复，不冒充直接刷新路径。未新做完整BFCache/跨标签/损坏PNG或10分钟墙钟等待。

正式0007迁移/恢复29项：只增列/attempt表，原列与其它表逐行指纹不变；仍原2文档13页、jobs/attempts/features空、integrity ok/FK0、重复迁移不变。原13/复用21页完整float32/payload/config、旧8份BF16与R15源库不变。正式仅匿名401/no-store及Origin403、首页/health200，不用正式凭据。8000实际监听PID54888（启动器33448）、3000 PID15240、6333 Docker PID49880，8001空闲且测试模型已停；PID仅快照，启停先核对CIM身份。浏览器恢复正式登录页、重置视口。

[失败记录](checks/stage2-3c-failures.json)保留prepare选样不足、旧白名单、测试锁和正式首轮JSON错误请求（415，改合法multipart再验401）；错误报告另存formal-attempt1。没有未解阻塞；测试注入未进正式启动。交接/progress/testing/需求/架构/接口/路线图/指南/方案及07/08六步已同步，01—06/旧报告/.gitignore保留，旧库保护限Git/选定文件/模型依赖而非ignored全盘审计；无下载、训练、换底座、暂存/提交/推送。新增docs按原规则被忽略，跨机器须另带。

**下一唯一任务：2-4，真实MinerU解析与坐标契约。等待用户明确指定，本轮停止。**

## 以下为R18历史交接 / 2-3B-2已完成（2026-11-08，北京时间）

本轮只完成“双模式与授权文档选择网页”。见[手册](stage2-3b2-runbook.md)、[汇总/修改清单](checks/stage2-3b2-verification.json)、[65项浏览器](checks/stage2-3b2-browser.json)、[21项正式恢复](checks/stage2-3b2-formal.json)及[文档保护](checks/r18-document-checks.json)。不提前接上传/任务恢复、MinerU、D、高亮、历史或预算方法。

先重新读取必读文档/设计和实际代码，核实0006、原2文档/13页、依赖、端口及可见窗口；其他同项目窗口idle/notLoaded。[新基线](checks/stage2-3b2-preflight.json)、runtime/verification/r18/metadata-before.sqlite3和source-state-r18-before为本轮证据，未复用旧运行结论。开工Git干净，正式凭据未读取/使用/更改。

前端新增ScopeSwitch/DocumentPicker及document-selection契约，复用生成SDK。默认library；document模式真实授权列表、10条游标分页、300毫秒文件名防抖、本人/共享/页数/状态/短ID单选，未选/未ready不提交。筛选不暗换目标，独立范围提示保留选择。列表与query独立取消/代号；切模式/文档清结果/PNG，锁定/退出清列表/选择。第三参只传稳定ID；返回核对mode/document/每页version，不做全库Top-k事后过滤。后端/表/SDK/代理/算法/依赖锁与登录CSS未改。

实际75后端29.435秒、4原模型CPU契约2.39秒、最终18前端306.7414毫秒、tsc与生产build通过；16项真实HTTP元数据检查无模型操作。65项浏览器分三次构建记录，最终构建补验21项。隔离只读克隆R15完整21页、随机凭据；两份A就绪文档同名，B私有同名、管理员共享4页和12个未ready元数据为明确fixture。真实A库10/选5/选4、共享4和B选8对应HTTP顺序/页码/分数与PNG；实际Qdrant白名单在Top-k前匹配授权范围。

10次新query同worker PID41392/network_attempts=0，0页编码；含一次取消后仍完成和一次依赖失败，不是十次成功展示。算法/SDK未变，未重跑官方评分，R16参考仅历史。3秒列表/5秒搜索延迟为显式注入，记录确认旧列表晚于新响应完成但未覆盖UI，筛选不取消内容query。真实撤共享404、目标非ready409、游标快照409/刷新、隔离Qdrant本机拒连503/恢复通过；Qdrant未启停。撤销先被定时auth/me401处理，不冒充浏览器/search401，另测匿名HTTP/search401。断连先清选择，后由会话复核锁到unavailable；重启重连保留会话但不恢复私有工作区。

1920/1366/390/320布局检查；修复更换文档展开仍停旧滚动位置，滚到选择器并聚焦文件名；修复刷新成功后旧列表提示残留。最终320选择器可见、390预览焦点、宽屏阅读/输入边界补验。首改仅观察门禁，未输入/提交新密码。未新做完整BFCache/跨标签/PNG迟到或损坏图注入、容量/完整无障碍审计；原Abort/Blob/广播保护及后端回归保留，不扩大声明。

21项正式检查确认全部表/schema逻辑内容、原13/复用21页完整float32/payload/config、8份完整BF16特征及R15源库不变；匿名401/no-store、上传Origin403、首页/health200。当前8000实际监听PID34092（启动器58492）、3000 PID54972、6333 Docker PID49880，8001无监听、测试模型已停；正式模型按需加载。PID是快照，启停前重查CIM命令/创建时间；浏览器回正式登录页并重置视口。

[失败修正](checks/stage2-3b2-failures.json)保留SSR属性顺序断言、Job错误字段准备失败（ui-prepare-attempt1保留）、只读路径错误及UI等待/视图/定时器竞态；文档批量补丁首轮因错误标题安全拒绝、未写文件。无本批未解阻塞，只有既有baseline-browser-mapping提示，未升级。旧项目保护是Git/选定文件/模型依赖指纹，不是ignored全盘审计；01—06、旧报告/.gitignore不变，无下载、训练、换底座、暂存/提交/推送。

交接/progress/testing和需求/架构/接口/方案/路线图/指南同步；07/08续写R18-S01—S05，日期/步骤配对、每步口稿60—100字。新增docs受原忽略规则影响，跨机器需另带。

**下一唯一任务：2-3C，上传/任务网页、恢复与重试（含取消检查点）。等待用户指定；本轮停止。**

## 以下为R17历史交接（不能替代顶部R18当前状态）

本轮只做工作台外壳与展示组件拆分。见[交付手册](stage2-3b1-runbook.md)、[汇总/修改文件](checks/stage2-3b1-verification.json)、[30项浏览器检查](checks/stage2-3b1-browser.json)、[14项正式恢复](checks/stage2-3b1-formal.json)和[文档保护](checks/r17-document-checks.json)。没有提前接双模式/文档列表、名称筛选网页、上传/任务恢复、历史、MinerU、D或高亮。

重新核实现有0006、原13页、Git干净和端口后，保存[R17基线](checks/stage2-3b1-preflight.json)、runtime/verification/r17/metadata-before.sqlite3及source-state-r17-before。历史报告没有冒充新证据。仅前端app改动；正式表/后端/SDK/迁移/算法/代理配置/依赖锁未变。

frontend/components/workspace/workspace.tsx导出Shell、Sidebar、QueryComposer、RetrievalResults、EvidencePanel；workspace.css只作用于工作台，登录/首改/断连沿用原样式。身份五态、CSRF、SDK代号/取消、图片Abort/PNG检查/Blob释放、visibility/pagehide/BFCache和广播仍集中Home。新检索清理旧结果/图/问题并聚焦；结果态中央滚动、输入置底；窄屏独立问题/预览视图、收起导航、键盘开关与焦点恢复。仍真实调用searchPages(q,k)，不传document_id、不写历史或假数据。

最终9前端测试269.0387毫秒、tsc与Next生产build通过；75后端28.629秒、4原模型CPU契约2.28秒通过。隔离克隆R15已完成21页库，A/B真实查询和授权原图；最终UI名称/页码/分数顺序对应实际HTTP。1920×1080、1366×768、390×844及320×700检查无横向溢出/输入覆盖，长文件名换行、切页、折叠、键盘、新检索、退出/换号、跨标签、首改门禁、撤销后的401及断连恢复通过。7次真实query前6次共用worker PID50060，追加修正复核重启后共涉及PID50060、58436、network0、page encoding0；包括取消/故障查询，不把7次都说成成功展示。算法没改，未重跑官方参考评分，不把R16评分当本轮。

故障边界：6秒延迟和实际query后、返回前改名是显式隔离注入；Qdrant适配器只在隔离服务指向本机拒绝连接端口得到503，未停止容器；空态使用非ready元数据fixture。首次改密只观察门禁，未输入/提交新密码。最终复核补修窄屏预览时错误提示可能被隐藏的问题；notice使视图返回检索，提交也回到检索，并实测真实PNG404后提示可见/焦点恢复。隐藏/BFCache逻辑和既有单测保留，没有新做完整BFCache或GPU中断/容量实验；追加撤销隔离文档ready资格后的真实PNG404，窄屏自动返回结果区、清图并聚焦输入；未验网络断流/损坏图重试。

正式恢复14项通过：全部表/schema逻辑内容、原13及复用21页完整float32/payload/config、8份BF16完整特征、R15源库不变；匿名代理401/no-store、首页/health200、上传Origin403。正式凭据未用未改。当前8000监听PID59524（venv启动器39432）、3000 PID31164、6333 Docker PID49880；8001无监听，隔离模型树已停，正式按需加载。PID仅快照，启停前重新核对CIM命令和创建时间。

[失败修正](checks/stage2-3b1-failures.json)保留cwd/守卫拒绝、亚像素精确断言及过早notice观察；最终通过，未放松授权/评分。文档检查首轮因先校验自身链接、后创建报告而失败，原失败及building摘要保留为attempt1，调整生成顺序后复查；首轮及最终构建/测试日志分开保留；只有既有baseline-browser-mapping提示，未升级依赖。截图是隔离真实查询，长文件名是fixture，非正式改名。无本批未解决阻塞。

已同步progress/testing/需求架构接口入口、改版方案/路线图/指南与[07技术](过程记录/07_2技术操作详解.md)/[08口述](过程记录/08_2逐步口述稿.md) R17-S01—S05；01—06、旧证据/.gitignore保留。新增docs受原忽略规则影响，显式检查本地文件，跨机器另带。旧库保护是Git/选定配置/模型依赖指纹，不是ignored全盘审计。无下载、训练、换底座、暂存/提交/推送。

**下一唯一任务：2-3B-2，接授权列表、文件名筛选/分页/状态/单选及文档库/单文档双模式。等待用户指定；本轮停止。** C仍为上传任务恢复，历史到3-4。

## 以下为R16历史交接（不能替代顶部R17当前状态）

用户明确授权本批，只实现授权文档列表、文件名筛选、单文档检索后端/SDK。见[手册](stage2-3a-runbook.md)、[本轮汇总/增量文件清单](checks/stage2-3a-verification.json)、[文档保护检查](checks/r16-document-checks.json)。没有提前实现2-3B工作台/选择网页、2-3C上传恢复、MinerU、D或高亮。

开工重新核实正式0005、原13页、3000/8000/6333监听、8001空闲、无已加载模型，其他可见同项目窗口idle；实际状态/文件哈希及在线备份见[预检](checks/stage2-3a-preflight.json)、runtime/verification/r16/metadata-before.sqlite3。只在独立系统修改，既有状态按本轮基线保护，旧报告不覆盖。

0006只给documents追加NFKC＋casefold名称键和索引，回填旧键，不改展示名/原列、不重建表、不编码页面。ORM名称赋值同步键，直接SQL维护须同步键；当前无重命名API。GET /documents先授权本人非删除元数据＋启用管理员ready/shared，再字面instr包含筛选和created_at/id倒序单页；%/_不作通配符。本人非ready可见不可搜，共享不暴露任务错误。searchable是DB当前版本/活动索引完整资格，不保证运行依赖在线。游标HMAC绑定当前会话、规范名称、limit和可见快照，跨会话/篡改/参数不符422，列表/权限变化409；返回前新事务复核。服务器完整快照计算有O(可见元数据/页)成本，不称大库分页方案。

GET /search可选UUID document_id；未提供保持library，提供则先授权/ready检查，限定当前版本页面白名单，整索引计数仍全局。Qdrant在Top-k前过滤，返回前同一目标复核；未知/越权404，未ready409，非法/空/重复422，变化409/身份撤销401/依赖503，绝不扩大到全库。SearchResponse增加search_mode和document_id；OpenAPI已导出、SDK生成，原两参调用兼容。PNG继续同会话签名及当前对象授权，未挂裸目录。

实际验收：75后端（旧63＋新增12）30.352秒、4原模型CPU契约2.26秒、前端5项＋tsc＋Next生产build通过；前端app展示不改，build仅既有baseline-browser-mapping提示，未升级包。[真实HTTP第二轮94项](checks/stage2-3a-http-attempt2.json)：只读克隆R15的21页与完整特征，6次query同一模型PID46980/network0、page forward0；A库9页/所选旧5页/新4页，实际Qdrant过滤参数、另一文档更高分不能挤占目标、新图、同名/Unicode/分页、共享撤回/停用及重启会话游标通过。[6组官方参考](checks/stage2-3a-reference.json)：同次query精确范围，对官方processor＋CPU float32 MaxSim，非并列排名一致，最大差6.072998047557121e-6，原atol1e-4/rtol1e-5不变。元数据名称/未ready对象为明确fixture，不冒充新上传入库；推理中撤回精确竞态是单元测试，真实HTTP撤回发生在请求之间。

正式迁移/恢复[27项](checks/stage2-3a-formal.json)：0006仅加名称键/索引，documents原列及另11业务/认证表逐行等于R16备份；仍2文档/原13页/原活动代，jobs/features空、integrity ok/FK0/重复迁移不变。原13页/复用21页集合全向量/payload/config和8份BF16文件哈希、R15源库逻辑内容不变。正式只匿名检查Next代理401/no-store/Origin403及首页/health，不使用/改变正式凭据。

运行快照：后端8000 PID27136（工具会话41706）、前端3000 PID16000（会话82573）、Qdrant6333 PID49880。8001与隔离模型树已停止，正式模型按需加载。PID仅快照，启停前核对CIM命令/创建时间，不杀Docker Desktop或删卷。

失败保留：scope链式调用括号在静态编译时修复；[真实首轮](checks/stage2-3a-http-attempt1.json)因旧助手固定13页校验21页失败，GPU前终止，新增动态指纹助手后另轮成功。正式首轮误将Vary当单值，实际Cookie, Accept-Encoding合法；[失败记录](checks/r16-formal-first-failure.json)保留，改按token检查含Cookie后通过，应用保护未变。所有日志runtime/verification/r16。无本批阻塞。

已同步progress/testing/接口架构/需求/路线图/新窗口指南；[07](过程记录/07_2技术操作详解.md)/[08](过程记录/08_2逐步口述稿.md)续写R16-S01—S05，01—06和旧证据保留。.gitignore仍忽略新docs，显式检查本地文件，跨机器需另带。旧库可检查Git状态/选定算法配置/模型依赖不变，不是ignored全盘审计；无模型下载、训练、换底座、暂存/提交/推送。

**下一唯一任务：2-3B-1，工作台外壳与展示组件拆分，接回真实文档库检索及身份/图片生命周期，完成布局检查即停。** B-2再接双模式与列表选择，C再做上传恢复。本轮停止，等待用户指定。

## 以下为R15历史交接（不能替代顶部R16当前状态）

用户明确启动2-2，已按最新[工作台改版方案](前端工作台改版方案与复用评估.md)保留后续A/B-1/B-2/C拆分。本批只完成完整页面渲染、原ColPali编码及索引安全激活；没有提前做文档列表、单文档范围、前端改版、MinerU、D或高亮。详见[2-2手册](stage2-2-runbook.md)、[汇总/增量文件清单](checks/stage2-2-verification.json)及[文档保护检查](checks/r15-document-checks.json)。

实际开工核实：正式0004、2文档/2版本/13页、jobs0、单ready索引；integrity ok/FK0；3000/8000/6333监听，已有一棵正式按需模型树。其他可见同项目窗口idle；所有既有2-1/设计及.gitignore改动保留。[R15基线](checks/stage2-2-preflight.json)、runtime/verification/r15/metadata-before.sqlite3在线备份和source-state-r15-before快照为本轮起点，不复用R14报告冒充新证据。

实现：0005只增system_state活动指针和page_features完整特征来源。单调度线程自动领取持久queued任务，rendering→encoding→indexing→activating→completed；失败/中断不激活。复用本地PyMuPDF1.28.2 CPU子进程，144dpi/RGB/PNG，记录裁剪/旋转/页码/尺寸/哈希；页面与query共用原adapter、同一ModelWorker和锁。每页保留BF16完整1031×128及1024视觉patch身份，另存float32索引导出，D以后读完整特征；没有预算压缩或底座变化。

采用新索引代：只读核验并复制当前Qdrant点表示，加入新页，候选集合全部核验后，SQLite短事务原子提交Page/IndexPage/Feature、文档ready、任务completed与活动指针。旧13页没有重编码或从旧缓存重新导入，旧集合不变。所有旧代/失败候选保留；全代复制有存储/写放大，仅验证小样本，不声称大库方案。文件与DB非同一事务，私有孤儿产物清理和显式retry/cancel留后批。

本轮证据：最终63后端（旧55＋新8）通过25.749秒；原模型环境4个CPU算法契约、前端4测试和tsc通过。OpenAPI实际比较未变，无SDK/前端代码变化，未重复build。[隔离真实HTTP第二轮48项](checks/stage2-2-http-attempt2.json)：两份新完整PDF各4页，实际8页forward＋4query，同一模型PID、network0，13→17→21动态规模，A5→9/B8→12授权、跨用户job/文档/PNG404、新图及completed重启保持通过。[4组官方参考](checks/stage2-2-reference.json)：同次query、同一授权完整页面库，CPU float32/官方processor排名一致，最大差2.625610351358887e-6，原容差不变。8份完整张量身份核验；8页contact-sheet已实际查看，无明显裁切/缺页/黑块，非OCR/坐标精度验收。

正式恢复：[首次19项](checks/stage2-2-formal.json)保留；最终错误码补丁加载后[20项复查](checks/stage2-2-formal-final.json)通过。正式0005仅新增2表，原10业务/认证表逻辑行指纹与R15基线完全相同，jobs/features仍空、正式仍原13页；integrity ok/FK0、重复迁移无变化、原集合float32/payload/config指纹不变。未使用或更改正式凭据，正式只测匿名/Origin保护及首页/health；真实新上传在隔离环境。

当前运行快照：后端8000 PID45388（工具会话44815，已加载最终补丁），前端3000 PID30652，Qdrant6333 PID49880。隔离8001及其模型树已停，正式模型按需启动。PID仅当时快照，启停前重查CIM命令/创建时间；只停止本项目树，不杀Docker Desktop，不删卷。

失败保留：首轮选样无新2—3页PDF，GPU前终止，改按文件名首两份2—4页，无gold；[首轮报告](checks/stage2-2-http-attempt1.json)及独立目录保留。单元import重复收集旧测试已修；pypdf xref/object-stream提示未改源SHA；临时GBK读取错误改显式UTF-8。中途编码/部分Qdrant/SQLite激活/停用/身份篡改和running恢复是单元替身/模拟，不能冒充真实GPU故障、断电或并发容量验收。没有2-2未解决阻塞。

学习记录续写[07技术](过程记录/07_2技术操作详解.md)、[08口述](过程记录/08_2逐步口述稿.md) R15-S01—S05；01—06、旧报告及.gitignore不改。当前docs规则会忽略新文档/报告，均显式检查本地文件，跨机器要另带。旧库可检查Git状态/选定算法配置/模型依赖保护，不是ignored全盘审计；无下载、训练、换底座、暂存、提交或推送。

**下一唯一任务：2-3A，授权文档列表、文件名包含式筛选、单文档检索后端/SDK，等待用户指定。** 此后B-1/B-2分批改工作台，C再做上传/任务网页与恢复；本轮到此停止。

## 以下为R14历史交接（不能替代顶部R15当前状态）

**R14工作台设计补充（同日，未改应用）：**已只读核对本机deepseek-webui，HEAD为0857074e2f9fca30b82a7fac1df7769ef98bbf25；它是HTML/JS＋PHP聊天代理，default_user目录历史和上传地址不用于替代本系统授权链。建议在现有Next.js做侧栏＋中央检索＋右侧证据，使用LayoutPatch品牌；2-3B分B-1外壳/组件和B-2双模式选择，持久历史仍到3-4，未增加聊天模型或答案生成。见[改版方案](前端工作台改版方案与复用评估.md)及[文档/只读保护检查](checks/r14-workspace-redesign-checks.json)。07/08追加S08/S09；下一唯一开发仍2-2。参考仓库只读，README称MIT但LICENSE为Apache2，未复制代码或运行PHP。

**R14补充设计（同日）：**用户新增单文档检索、可见文档列表和文件名模糊搜索需求；本轮仅核对代码/报告并写[设计与分批计划](单文档检索功能设计与分批计划.md)，没有实现接口/UI。下一唯一开发仍是2-2；原2-3拆为2-3A列表/名称筛选/限定检索后端、2-3B双模式网页、2-3C原上传/任务网页与恢复。文件名只展示，ID关联复用；ready前不可搜，授权和所选文档交集在Top-k前过滤，不能扩大成全库。07/08追加S06/S07，01—06与R14旧报告不改；[补充检查](checks/r14-single-document-design-checks.json)只验证文档。

本次实际`git check-ignore -v`显示`.gitignore:26:docs`会忽略新增设计/检查文件，不仅过程记录；本轮保持规则不变。新文档在本机存在，跨机器交接另行携带；旧Git状态中的业务改动属于开工前已有内容，本轮未改。

初始核实：Git干净，其他可见同项目窗口idle，上传/jobs尚未实现；正式0003、2文档/2版本/13页、integrity ok/FK0。见[预检](checks/stage2-1-preflight.json)。在线备份runtime/verification/r14/metadata-before.sqlite3保留，未打印或使用正式凭据。01—06及.gitignore保持原字节；阶段2记录使用用户指定[07技术](过程记录/07_2技术操作详解.md)、[08口述](过程记录/08_2逐步口述稿.md)，本轮S01—S05对应。

已实现：0004只新增jobs；复用documents/document_versions建版本1。POST /index单PDF multipart、Origin/CSRF/首改保护；服务端owner且private，UUID路径，默认20MiB/100页、严格PDF可读/加密/几何检查；GET /jobs/{id}、/documents/{id}仅本人（admin普通接口无旁路）。先receiving预约、写盘并复核身份后queued；失败failed，重启receiving转interrupted。本人X-Upload-ID同输入复用，异输入409，新key新文档，不跨用户去重。文档registered且active_version_id空，不进入ready搜索。render_profile为pending标记，不代表执行渲染。无上传UI、retry/cancel、编码、MinerU、D、高亮。

实际验证：55后端unittest＋4原模型环境CPU算法契约pytest，4前端测试、typecheck、SDK生成和Next生产build通过；[真实HTTP第二轮29项](checks/stage2-1-http-attempt2.json)，[正式迁移/代理18项](checks/stage2-1-formal.json)。旧13页scope及Qdrant13点/13403向量的完整float32/payload/config指纹不变；正式0004仅增空jobs，旧9表逻辑指纹等于备份，integrity ok/FK0、迁移重复无变化。Web只增python-multipart0.0.20，原30包版本不变，模型环境未改。没有新GPU forward/官方评分重跑；上传成功是隔离后端直连，正式Next代理是匿名/Origin/20MiB边界，未测浏览器上传UI。

失败保留：首轮unittest误发现Web未装pytest、旧路由白名单、Windows文件名测试预期；次轮额外表单暴露Starlette异常基类捕获问题，修复后全回归通过。前端第一次cwd错误已纠正；[HTTP首轮失败](checks/stage2-1-http.json)为验收脚本join歧义，显式条件后用新目录重跑。日志在runtime/verification/r14，未覆盖旧批报告。构建只有baseline-browser-mapping陈旧提示，未升级。见[手册](stage2-1-runbook.md)。无2-1未解决阻塞。

当前运行：生产前端3000 PID30652（会话24251），后端8000 PID56496（会话26638），Qdrant6333 PID49880；8001隔离验收已停止。停止前重查PID/命令/创建时间，不复用快照。正式凭据/首改要求未变，未跑模型。数据库/文件非单一事务，崩溃可能留下内部孤儿文件，receiving只标中断、不自动激活或清理；完整调度重试在后批实现。

[本批汇总和修改文件清单](checks/stage2-1-verification.json)、[文档/保护检查](checks/r14-document-checks.json)已交付；5对口稿89—98字、63个Python语法、163处本地文件链接检查通过。无本批阻塞，01—06/旧报告保留；无提交或推送。

**下一唯一任务：R15 / 2-2，完整页面渲染、原ColPali全页编码与索引安全激活，等待用户指定。** 先核对本批证据和pending render身份，设计增量索引如何保留旧13页。完整页面特征须保留供D使用，预算表示另存。本轮到此停止，不进入2-2。

## 以下为R13及更早历史（不能替代R14当前状态）

本文件用于AI换窗口或上下文恢复：先了解当前背景、约束与证据，再核实现状。重要操作、修改、测试、故障或决策后须更新；可精简过时内容，保留仍影响接手的失败和限制。

最近更新：**2026-11-07（北京时间），R13仅完成后续阶段文档规划。** 最后代码验收为R12 / 1B-6；阶段1B在现有13页登录→授权检索→PNG→启停恢复范围收尾，阶段2尚未开始。[路线图](项目开发阶段规划与任务.md)把阶段2/3/4拆为6/5/4批；下一唯一开发任务为2-1，等待用户明确指定。本轮未启停服务、运行模型、迁移数据库或重跑应用测试。先读根AGENTS，再核对实际代码/端口/库；历史记录不能替代新运行证据。

**R13补充：**方法一=页内证据定位D-no-text，方法二=预算约束视觉文档检索；目前接通的是原ColPali页面基线，两项方法的系统完整接入都不能提前宣称完成。先做系统及方法一，方法二成熟后改检索/索引层；保留完整页面特征供D使用，预算向量另存，现有代码不是即插即用插件。新增[阶段2新窗口指南](阶段2新窗口接手指南.md)，含6.1 Sol分批建议、可选Astra专项复核及2-1首轮提示词；未创建窗口、修改模型设置或开始开发。

## 1. 用户约束与学习入口

- 只修改独立layoutpatch-system；旧layoutpatch、layoutpatch-evidence、Snappy只读。不下载模型、不训练、不换底座、不覆盖旧研究结果、不暂存/提交/推送。
- 每轮只做指定批次，先讲目标/改动/验收，边做讲关键技术，完成讲结果/口述后停止。重要操作/失败/验证及时更新本交接。
- R11起写[05技术详解](过程记录/05_1b技术操作详解.md)及[06口述稿](过程记录/06_1b逐步口述稿.md)，**03/04不得再修改**。R12-S01—S06历史保留；R13-S01—S04日期编号配对，S03/S04为本次交接补充，每步口稿60—100字。原.gitignore忽略过程记录，保留设置，05/06实际在本地，检查时显式包含。阶段2起建议新建07/08，尚未创建。
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

本次R13补充的检查独立保存于[补充文档检查](checks/r13-handoff-supplement-checks.json)；原R13检查是其时版本的历史快照，不覆盖旧报告。05/06追加研究对应关系和模型/新窗口交接两步记录。

**下一唯一开发批：建议R14 / 2-1，新PDF上传、服务端归属、文档版本、持久任务与授权状态查询。** 先核对实际基线和迁移/接口设计，再在用户明确指定后实施；本批不做页面编码、MinerU、D或高亮。详细依赖、出口和交接提示见[路线图下一步](项目开发阶段规划与任务.md#next)。MinerU/D新输入、动态索引一致性、评价材料与预算方法仍待核实；外部HTTPS/Secure Cookie、日志脱敏、监管/协同备份尚非已执行部署。
