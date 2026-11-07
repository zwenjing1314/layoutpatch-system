# AI交接文档


## 当前交接：R17 / 2-3B-1已完成（2026-11-07，北京时间）

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
