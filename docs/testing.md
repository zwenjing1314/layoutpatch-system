# 分阶段验收与检查记录

## 2026-11-08｜R25 / 3-1B实际验收

[手册](stage3-1b-runbook.md)、[新运行/保护报告](checks/stage3-1b-verification.json)。新基线在runtime/verification/r25，R22/R23/R24均为历史。

| 范围 | 本轮新结果 | 适用限制 |
|---|---|---|
| 后端/模型 | 139后端62.309秒；13 CPU契约2.74秒 | 既有适用并发/事务/错误检查，本批无后端修改 |
| 前端 | 46项537.6499毫秒，含13新增；tsc通过 | 组件SSR与hook小型调度器；不替代真实React浏览器 |
| 构建/SDK | 隔离副本生产build11.320秒；实际OpenAPI相同、临时重新生成43文件相同 | 正式.next没有执行本轮构建；未改依赖或API |
| 隔离管理 | 新0008克隆→0009仅增加事件表、重复相同；33真实localhost HTTP＋4 CLI | 普通用户、首改、Origin/CSRF、最后管理员、reset/revoke和事件；正式未迁移 |
| 原检索/区域 | 46真实ASGI，6新Q同冻结原模型BF16/CPU、A/B库/原文档/PNG/区域/crop/撤销后拒绝 | 两次既有P′命中，D forward0，页面编码0/MinerU0/network0；非新GPU/PDF/准确率/容量 |
| 页面 | 25项真实本机浏览器检查：管理员列表/10+5分页、取消/焦点、最后管理员409、启停/revoke200、本人退出、换号/角色403清状态、迟到/503 | 3秒列表/503/角色变化为显式隔离夹具；没有产品测试后门 |
| 浏览器密码边界 | 查看空建号/重置表单、默认普通角色、影响和确认，取消后草稿清空；写入分派/一致性/重复锁由前端测试及真实HTTP覆盖 | 未在浏览器输入/提交新密码，不冒称浏览器建号/改密完成 |
| 窄屏/保护 | 默认1280及390/320无body横溢出，320原生弹窗/键盘/Escape；正式0008/2文档13页、完整Qdrant、原服务/01—08/旧证据/HEAD/空暂存 | 未宣布完整BFCache/跨标签/无障碍认证；旧库仅Git可见及选定资源/模型依赖，不是ignored全盘审计 |

失败：属性顺序断言、隔离辅助import遗漏、Origin配置不符、浏览器label歧义、cwd误置及停服务全机CIM输出GBK解码，均修验法/隔离配置后复验；停服务前重查限定PID/创建/命令。原模型/授权/事务约束未放宽。仅既有构建提示，无本批产品阻塞。

T02/T05管理网页适用子项完成，完整阶段3/T01—T15整表和正式部署未完成。09/10 R25六步配对，01—08与R24历史保留；下一唯一3-2，用户指定后再开始。

## 2026-11-08｜R24 / 3-1A实际验收

[手册](stage3-1a-runbook.md)、[新运行汇总/保护](checks/stage3-1a-verification.json)，原始命令/日志与随机隔离凭据分开保存在`runtime/verification/r24`。R22/R23仍为历史，本轮未覆盖旧证据。

| 范围 | R24实际新结果 | 适用限制 |
|---|---|---|
| 后端 | 139项，60.700秒，含17项新增账号测试 | 真实迁移SQLite/cookie/PNG；既有路由替身不冒充真实模型 |
| 模型CPU契约 | 13项，2.55秒 | 既有合成D/检索契约；真实原模型另列 |
| 前端/SDK | 33项，423.6665毫秒；tsc通过，OpenAPI及SDK新生成 | 无网页新增/浏览器/生产build，正式前端保持 |
| 迁移 | 非空正式克隆0008→0009，只增account_events；旧表行不变，重复迁移相同，ORM无漂移 | 正式不迁移，正式仍0008 |
| T02/T05管理 | 33项实际localhost8001 HTTP＋4实际CLI：角色/首改/Origin/CSRF、建号/重复、启停/noop、重置/撤销、最小事件 | 原库/密码未用；普通user五类请求403由新增测试逐个覆盖 |
| 并发/故障 | 两连接CLI自停、两管理员HTTP自停/交叉停、同名并发建号、cookie加载后撤销、事件触发器回滚、写锁超时503 | 受控真实SQLite竞争；不称多机并发/容量/自然故障验收 |
| 原检索/区域 | 46项真实ASGI：6次原ColPali新Q，A/B库＋原文档，PNG SHA，真实候选区域/D/crop，管理撤销后全部旧入口401与旧签名404 | 同冻结权重/实现BF16在CPU执行；D float32 1前向23.895ms/1缓存命中；复用R22完整PDF/特征/候选，页面编码0/MinerU0/network0 |
| 保护 | 正式全表/schema/原13PNG/完整Qdrant/服务身份，旧项目Git可见状态/选定文件和模型依赖，01—08/旧报告/HEAD/空暂存 | 正式凭据未用；旧ignored内容非全盘审计；正式GPU驻留树保持 |

首次账号测试因seed修订白名单漏0009在setup失败，修正兼容并清理16个已知残留临时库。第二轮Cookie重放jar冲突是验法问题；同轮锁超时暴露数据库错误响应再次心跳写库掩盖503，修产品错误处理后第三轮16项通过，补禁用管理员计数后最终17项并入139。原日志保留，未降低断言；PowerShell rg通配路径失败改明确目录。

这是T02/T05的3-1A适用子项与原链回归，不宣布完整管理网页、T01—T15整表、研究准确率、GPU/浏览器重跑或并发容量通过。管理事件只记录已授权业务成功/noop/拒绝，安全边界拒绝与库故障不伪造该表事件；完整审计查询/保留策略在3-4C。09/10配对，01—08保留；下一唯一3-1B待用户明确指定。

## 2026-11-08｜R23 / 阶段2完成复核（非新开发批）

[复核结论/问题](stage2-review-r23.md)、[机器报告](checks/r23-stage2-review.json)。本轮新运行：122后端54.866秒、13模型CPU契约2.54秒、32前端420.9181毫秒、tsc通过。命令与日志在`runtime/verification/r23/tests.json`；前端未重build，旧生产服务保持；没有再次执行R22真实PDF/模型/浏览器/重启验收。

正式只读0008_parsing/2文档13页、integrity ok/FK0；13点13403向量与DB成员/embedding一致。新查端口与CIM身份，七个匿名请求检查含health/首页200、保护接口401和Qdrant匿名401；health不代表模型就绪。核对R22清单84个不同路径存在、六类条目数及passed标志；对隔离23页重新算完整特征/导出/PNG/候选哈希，450候选保持，隔离活动36页不计入正式。

**新增发现F01：**临时库里调用现有本地账号业务层可把最后启用管理员从1改为0，证据`runtime/verification/r23/admin-gap.json`。列为3-1A公开管理接口前必修，不冒称阶段2远程越权或本轮已修复。首次探针因连接未关闭导致临时库清理WinError32；修正为closing后复跑成功；一条含递归清理的组合命令被策略拒绝未执行。随后核实仅剩一个SQLite文件，按明确文件/空目录分别清理成功，失败原因保留。产品代码未改。

R23是已有阶段2出口的复核；T项不扩大覆盖，研究效果、任意PDF、并发与外部部署仍未验。旧R22报告保持，新增报告不能与各轮次数相加解释为覆盖率。下一唯一开发批3-1A，等待用户指定。

## 2026-11-08｜R22 / 2-6实际验收与阶段2出口

收尾另跑[69项资料一致性](checks/r22-document-checks.json)：检查Markdown链接、07/08六步配对与60—100字、01—06/.gitignore哈希、HEAD/空暂存和git diff --check。实际Qdrant网络body日志只覆盖后6次检索，Top-k前目标白名单页数12/5/8/12/11/12，版本/profile/index、exact/limit及返回子集均核对；最初8001的4次没有该wrapper日志，不能冒称十次均有网络body审计。页面官方参考进程page编码0与整轮实际23页已分字段，原分数/容差保持。未重复GPU/回归，只检查已有运行证据及收尾资料。

[汇总/修改清单](checks/stage2-6-verification.json)、[手册](stage2-6-runbook.md)、[HTTP109](checks/stage2-6-http.json)、[网页26](checks/stage2-6-browser.json)、[重启前6](checks/stage2-6-recovery-before.json)/[重启后21](checks/stage2-6-recovery-after.json)、[旧链18](checks/stage2-6-legacy.json)、[保护86](checks/stage2-6-protection.json)、[测试](checks/stage2-6-tests.json)、[成本](checks/stage2-6-cost.json)为本轮新证据。

| 目标 | 本轮实际覆盖 | 范围与限制 |
|---|---|---|
| T01 | 三条区域路由schema合法匿名请求401/private,no-store；正式代理匿名/Origin检查 | 空JSON在数据校验先返回422，非法Origin先403，不泛称所有畸形请求401；PDF/历史完整权限仍后批 |
| T03 | A/B状态/区域/crop404，普通admin无private裁剪旁路；篡改签名/旧会话签名拒绝；共享撤回单测 | 真实HTTP跨用户/6页裁剪；共享区域为单元真实cookie/PNG＋推理替身；新前端Qdrant实际query body日志含Top-k前白名单 |
| T06 | 两份新完整12/11页、23次page forward、双模式新Q/PNG/真实D/crop；重启后另一问题重新编码；旧13页A/B各真搜一次 | 共10检索Q＋14区域Q含重复/取消，非24独立题；显式模型失败夹具不等同自然硬件故障 |
| T07 | 固定D身份严格273410参数，原PNG像素SVG；50/100/150%、1920/1366/390/320图框，误差<0.003px；类型/候选/物理页序与HTTP一致 | 23页450真实候选；四类坐标抽查，首text为arXiv边栏，不宣称阅读顺序/召回/定位准确率 |
| T08 | 真实路由空候选/解析失败回空items；模型失败网页保图/重试定位，非法框/非有限分数/篡改模型身份拒绝 | no_candidates和网页错误为明确隔离夹具且复原；R20真实空白/异常/超时为历史，未冒充本轮重跑 |
| T09 | 真实守卫重启后session/status/crop仍可读；撤销后401，新会话不能重放旧crop；网页断连隐藏/重连撤销、显式过期清私有状态 | running→interrupted/retry/cancel在本轮回归单测保留，R19真实硬停为历史；过期用合法过去时间夹具，不等满8小时 |
| T11 | 本轮四组同次Q、精确单文档/库范围官方processor＋CPU float32 MaxSim，排名一致，最大差3.7001953110404884e-6；23份BF16与精确导出 | 原atol1e-4/rtol1e-5保持，只是固定小样本评分，不是正式效果评价 |
| T12 | 本轮14组真实Q/新PDF候选与只读原D定义P′/分数最大差0、排序一致；冻结权重/profile/代码保持，13模型契约通过 | 原atol1e-6/rtol1e-5保持；三固定source_dev开发页一致性为R21历史，本轮未重复该三页 |

最终122后端57.472秒、13模型2.76秒、32前端415.3864毫秒、tsc/生产build通过。两次延迟请求均真实完成计成本；第二次精确验证在入口0.523秒清空、6秒后执行D不回填。重启时网页auth/me先遇断连，转unavailable并清私有状态；重连后看到撤销，不冒称区域HTTP直接触发该界面。

23真实MinerU页450候选（text301/title42/equation96/image8/table3），294 ONNX、回执374.123秒；7实际D forward/7缓存命中，D CPU24.359毫秒不含准备/加载；参考初6+终14共20另计。完整特征1031×128与1024视觉行保留，预算序列未送D。固定语料选择仅按archive名称/完整页数，无gold/预存预测；不称未见测试集。

阶段2通过本轮适用应用集成出口，**不宣布T01—T15整表或研究准确率通过**。仅支持既定PDF几何；未新做完整BFCache/跨标签、10分钟墙钟轮询、GPU抢占、并发容量/性能或外部机器部署。正式0008/全表/原13页与旧资源不变、服务恢复；[失败](checks/stage2-6-failures.json)无未解项。下一唯一3-1，等待用户指定。

## 2026-11-08｜R21 / 2-5实际验收

T12适用项通过：预先固定3个source_dev缓存页，迁入前后候选ID、P′、区域分数/排序一致，最大绝对差0；CPU float32、atol1e-6/rtol1e-5与精确并列layout_id升序规则未变。权重seed0/epoch1 SHA一致、strict load273410参数。参考只执行原定义，不读gold/predictions构造输入。见[开发对照](checks/stage2-5-consistency.json)、[来源](checks/stage2-5-sources.json)。

T07/T08本批子项：R19上传5/6页完整PDF＋R20真实MinerU候选只读复用，11页194候选、11 D forward、12次当次真实Q，原实现同Q参考P′/分数最大差0、排序一致。新问题重编码、P′磁盘cache可复用，跨进程cache命中D0；全特征/模型/候选身份变化、损坏cache、非法框、短序列、非有限值与推理中撤权均有适用检查。不是R21新上传或未见测试，也不等于区域效果通过。

最终112后端53.141秒，9 D/缓存＋4原模型契约2.58秒通过。[32项实际ASGI原链](checks/stage2-5-search.json)含A/B两模式、4次真实query/Qdrant/PNG；合计16真实新query、两个顺序worker/network0，新页面编码0、MinerU0。测试替身明确独立，不当真实D证据。[65项保护](checks/stage2-5-protection.json)确认正式0008/2文档13页/全表/完整Qdrant和旧资源不变；[失败记录](checks/stage2-5-failures.json)保留错误测试环境/公开health缓存断言等，未放宽授权或算法。完整成本与范围见[手册](stage2-5-runbook.md)。

区域HTTP/cookie会话边界、裁剪权限、网页高亮及50%/100%/150%缩放仍属于2-6，未宣布整阶段2或T07/T08全项通过；未新跑前端build/浏览器、区域准确率、容量或官方研究效果评价。

## 2026-11-08｜R20 / 2-4实际验收

[手册](stage2-4-runbook.md)、[汇总](checks/stage2-4-verification.json)、[来源坐标61项](checks/stage2-4-output.json)、[故障15项](checks/stage2-4-faults.json)、[HTTP46项](checks/stage2-4-http.json)、[视觉](checks/stage2-4-visual.json)、[特征24份](checks/stage2-4-features.json)、[迁移19项](checks/stage2-4-migration.json)、[匿名HTTP5项](checks/stage2-4-formal-http.json)、[保护42项](checks/stage2-4-protection.json)、[失败](checks/stage2-4-failures.json)与[文档保护](checks/r20-document-checks.json)。

104后端44.447秒、25前端411.3375毫秒、4原算法CPU契约3.95秒、tsc和Next生产build通过。后端须显式列出unittest模块，算法pytest用.venv；首轮Web unittest discover误收pytest模块的失败保留。日志runtime/verification/r20，旧报告不当新证据。

| 适用子项 | 本轮实际覆盖 | 限制 |
|---|---|---|
| T07/T08解析与坐标子集 | 真MinerU Basic CPU，完整5/6页、194顶层候选；source/profile/raw/receipt/PNG hash可追溯，有限合法框及页码；11页总览与A4/B5原尺寸叠框 | 只支持零旋转/零MediaBox原点/Crop=Media；不同长宽比内容样本未测，纵横空白fixture已真跑；无召回/区域效果声明 |
| 空候选/故障 | 真空白no_candidates、旋转90/CropBox明确拒绝，实际子进程0.25秒注入超时、实际坏PDF异常；逐页/持久状态分开 | 故障为明确隔离注入；未等满默认180/900秒，900秒是页间检查点；重启恢复/撤权竞态为SQLite契约测试 |
| T01/T03/T06授权链 | 实际localhost HTTP46，A/B两模式6次真实query/授权PNG，解析failed注入时仍真搜2次；Origin/CSRF、退出与private无旁路 | shared read-only/停用/首改及候选读取损坏由单元覆盖；无网页高亮或缩放验收 |
| T09/T14持久/数据 | 0008只新三表，profile冻结/幂等/失败任务ID重试/中断；原表/13页全向量保护；24既有BF16完整特征CPU验证 | 不做自动旧库解析；没有解析cancel网页；复用24集合末尾新算fingerprint，不能当开工快照 |

最终11页168次ONNX run/89.671秒；所有开发重跑、探针和失败记录合计44入口/38回执/552次ONNX run/332.170秒。HTTP首轮3query+最终6共9次、两棵顺序模型树network0，本轮页编码0/D0。6个无worker回执入口的未完成成本不按0推断。完整阶段2/T07/T08剩余D与区域授权/50%-150%缩放仍待2-5/2-6。

## 2026-11-08｜R19 / 2-3C实际验收

[手册](stage2-3c-runbook.md)、[汇总](checks/stage2-3c-verification.json)、[HTTP39](checks/stage2-3c-http.json)、[网页36](checks/stage2-3c-browser.json)、[运行30](checks/stage2-3c-runtime.json)、[正式29](checks/stage2-3c-formal.json)、[非空旧任务迁移](checks/stage2-3c-migration.json)、[完整特征](checks/stage2-3c-features.json)与[文档保护](checks/r19-document-checks.json)。最终87后端38.671秒、25前端377.422毫秒、4原模型CPU契约2.35秒、tsc和Next生产build通过，原始日志runtime/verification/r19。

| 适用子项 | 新运行证据 | 限制 |
|---|---|---|
| T01/T03归属与上传 | 真网页5/6页完整PDF、private/版本1、本人列表/明细/控制；A/B越权404、首改403、Origin/CSRF403、未知/重复参数422；正式匿名401/no-store | 正式身份未使用，admin首改只观察；普通admin无旁路有单元回归 |
| T06新PDF闭环 | A/B两种模式四次实际query与四份PNG；Top-k前Qdrant白名单5/10/6/14；24活动页、11新完整特征、每版本一套Page | 16次页面forward含取消5次，两棵顺序worker，network0；未重跑官方参考评分或研究准确率 |
| T09/T14持久与竞态 | A最后checkpoint之后/激活事务之前取消，候选failed且原13页不变；B显式渲染失败、真实CPU渲染后硬停、重启interrupted与第三次重试完成；attempt保留 | gate/渲染失败/8秒延迟为隔离注入，不是自然故障；未强杀当前GPU算子；默认总时限的检查点有单测，未墙钟等满900秒 |
| 幂等与网页恢复 | 停止HTTP等待明确结果不确定，同ID重发返回同任务，三份真实任务而非四份；queued取消无编码、非法PDF422、刷新/换号恢复、退出清文件/任务 | 文件/ID只内存；关闭网页丢失发送预留，但服务端任务保留。10分钟轮询上限代码/契约核对，未真实等待10分钟 |
| 展示/故障 | 1920/1366/390/320无横向溢出；长名、10+2任务分页、Enter记录、断连清卡→auth定时门禁→重连恢复、首改不挂任务页 | 10条额外元数据明确为分页夹具；未新做完整无障碍、BFCache/跨标签/PNG断流或损坏图实验 |
| 数据保护 | 正式0007仅增列/新attempt表；其它表/原列、原13/复用21页完整向量/配置、旧8份BF16/R15源库不变；非空旧任务迁移回填与重复迁移通过 | 旧库保护为Git/选定文件/模型依赖指纹，不是ignored全盘审计 |

[失败与修正](checks/stage2-3c-failures.json)包含seed revision、测试lifespan锁、精确路由白名单、prepare不足、正式探测错误Content-Type及工具编码/断连竞态；不降低授权或评分容差。仅既有baseline-browser-mapping提示，无依赖升级。正式服务已恢复，测试模型停止；只宣布2-3C适用子集完成，下一唯一2-4。

## 2026-11-08｜R18 / 2-3B-2实际验收

[手册](stage2-3b2-runbook.md)、[汇总/修改清单](checks/stage2-3b2-verification.json)、[HTTP16项](checks/stage2-3b2-http.json)、[浏览器65项](checks/stage2-3b2-browser.json)、[正式21项](checks/stage2-3b2-formal.json)及[文档保护](checks/r18-document-checks.json)。75后端29.435秒、4原模型CPU契约2.39秒、最终18前端306.7414毫秒、tsc和生产build通过；日志runtime/verification/r18，最终以后缀final2为准。

| 适用子项 | 本轮实际证据 | 限制 |
|---|---|---|
| T01/T05客户端 | 退出/换号清私有状态、首改不挂工作台、撤销后auth/me401、断连先清选择再由会话复核隐藏工作台、重启重连；正式匿名401/no-store/上传Origin403 | 未输入/提交改密；浏览器/search401计划先被auth/me401处理，另有匿名HTTP/search401；未新做完整BFCache/跨标签实验 |
| T03/T04列表与范围 | 真授权10+5分页、中英文/全半角/%_字面筛选、同名ID区分、本人未ready禁选、共享撤回404/目标非ready409/游标快照409/刷新，不回退全库 | 12个未ready对象、重名/共享为隔离元数据fixture，不冒充新上传；未新做推理中精确撤权 |
| T06/T11网页 | A库10/选5/选4、共享4、B选8的HTTP/UI/PNG对应；Qdrant实际完整页面白名单在Top-k前；10次query同PID41392/network0、0页编码 | 含一次取消后完成及一次依赖失败；未重跑官方参考评分/准确率/预算实验，R16参考仅历史 |
| 异步/故障 | 3秒列表晚于新筛选完成不覆盖；筛选不取消query；5秒检索迟到不跨文档；隔离Qdrant本机拒连503/恢复 | 显式延迟，不称GPU被取消；PNG迟到/断流/损坏图未新注入，保留Abort/Blob保护 |
| 布局/焦点 | 1920/1366/390/320；最终展开列表回顶部并聚焦，刷新清旧提示，320输入边界/390预览焦点/宽屏阅读 | 65项分三构建：初版28、焦点版16、最终21；最终再跑18前端/类型/build，不称全部浏览器同一构建；非完整无障碍审计 |

正式全部表/schema、原13/复用21页完整float32/payload/config、8份BF16及R15源库不变；后端/SDK/迁移/算法/锁/登录CSS不变。服务已恢复，测试模型停止，正式凭据未读取使用更改。[失败记录](checks/stage2-3b2-failures.json)保留修正和工具等待竞态，无未解阻塞。仅B-2适用子集通过，不宣布T01—T15整表或阶段2结束；下一唯一2-3C。

## 2026-11-07｜R17 / 2-3B-1实际验收

[手册](stage2-3b1-runbook.md)、[汇总/文件清单](checks/stage2-3b1-verification.json)、[浏览器30项](checks/stage2-3b1-browser.json)、[正式14项](checks/stage2-3b1-formal.json)和[文档保护](checks/r17-document-checks.json)为本轮入口。最终9前端269.0387毫秒、tsc/Next生产build、75后端28.629秒、4算法CPU契约2.28秒通过；原始日志runtime/verification/r17。构建仅既有baseline-browser-mapping提示，未升级依赖。

| 适用子项 | 本轮实际证据 | 未覆盖/不能扩大声明 |
|---|---|---|
| T01/T05前端子集 | 真实登录、退出/换号、跨标签退出、首改门禁、撤销后的auth/me401及断连恢复；正式匿名401/no-store、上传Origin403；已有CSRF回归 | 不自动输入/提交改密；本批没有上传UI |
| T03/T04/T06/T11前端子集 | 隔离21页库A/B真实query与PNG，最终UI文件名/页码/分数对应HTTP；7次query前6次同PID50060、追加复核后共两棵先后启动的模型树（50060、58436）/network0、0page encoding | 两种范围UI仍到B-2；算法/SDK未变，未重跑官方评分/准确率 |
| 生命周期 | 新检索取消和6秒迟到不复活；409返回前改名注入、503隔离Qdrant端口拒连、空授权范围；图片切页与Blob展示；退出卸载工作台 | 不称GPU被取消、真实并发撤权/断电/容量；PNG404已有追加真实浏览器检查；断流/损坏图重试未验；未新做BFCache实验 |
| 布局/键盘 | 1920×1080、1366×768、390×844及320×700；无横向溢出/输入覆盖，长名换行，导航展开/收起焦点、Enter选页阅读；[截图](checks/stage2-3b1-laptop-final.jpg) | 人工结构/阅读宽度检查，不是完整视觉精度或无障碍审计 |

正式schema/全部表、原13及复用21页完整向量/payload/config、8份BF16全特征及R15源库不变；后端/SDK/迁移/依赖锁未改。隔离测试助手不进入正式启动。服务已恢复、测试模型树已停，正式凭据未用未改。[失败记录](checks/stage2-3b1-failures.json)保留命令cwd、守卫、亚像素精确比较和异步观察过早；文档检查首轮的自身报告生成顺序失败另存attempt1，修正后复查。无本批阻塞。仅B-1完成，不宣布T01—T15整表或整个B阶段通过；下一唯一B-2。

## 2026-11-07｜R16 / 2-3A实际验收

[手册](stage2-3a-runbook.md)、[汇总/增量文件](checks/stage2-3a-verification.json)、[文档保护](checks/r16-document-checks.json)为入口。75后端（旧63＋新12）30.352秒、4算法CPU契约2.26秒、前端5项、tsc、SDK生成和Next生产build通过。新增测试明确使用模型/向量替身；推理中撤回/版本改变、列表返回前撤回为精确单元注入，不当作真实GPU竞态。

| 适用子项 | 实际本轮证据 | 不包括 |
|---|---|---|
| T01/T05 | 新路由401/首改403、参数422/no-store；游标绑定会话/筛选/limit/快照，跨会话/篡改拒绝；上传Origin/CSRF旧回归保留，正式Origin403 | 工作台/浏览器选择尚未实现 |
| T03/T04 | 同名A/B及admin无私有旁路；本人非ready显示原因不可搜，启用管理员ready共享/撤回/停用；Top-k前实际版本/页过滤、PNG独立授权；库9页与目标5/4页区分 | UI切换与处理中真实GPU撤权竞态；单元已注入 |
| T06/T11 | 复用R15完整21页/8份BF16特征，真实6次新query（含重复）、同PID/network0，page forward0；官方6组精确范围排名一致、最大差6.072998047557121e-6，原容差不变 | 本批不重编码页面，不计准确率或预算/区域成绩 |
| T09子集 | 真实重启会话、分页游标和选中文档PNG保留；正式0006重复迁移无变动、integrity ok/FK0 | retry/cancel/运行中断电和容量未验 |

[隔离HTTP第二轮94项](checks/stage2-3a-http-attempt2.json)、[6组官方参考](checks/stage2-3a-reference.json)、[正式27项](checks/stage2-3a-formal.json)通过。正式只增加documents归一化列及索引，原列和另11张业务/认证表逐行等于R16备份；正式仍原13页，原13/复用21集合全向量/payload/config及R15源库和8份完整特征不变。正式HTTP只匿名，不使用正式凭据。名称/未ready元数据fixture不能冒充新PDF入库。

[首轮真实失败](checks/stage2-3a-http-attempt1.json)：历史指纹助手固定13页拒绝21页，GPU前终止，新增动态助手后另轮通过，旧助手未改。[正式首轮断言失败](checks/r16-formal-first-failure.json)：Vary实际Cookie, Accept-Encoding，改按token列表验证，不改保护。编译时缺括号已修；构建只有既有baseline-browser-mapping陈旧提示，不升级依赖。没有2-3A阻塞；服务器全快照分页成本、UI/容量/完整T矩阵未验边界保留，下一唯一2-3B-1。

## 2026-11-07｜R15 / 阶段2-2实际验收

本轮仅验完整页面入库与安全激活，不宣布T01—T15整表通过。入口：[手册](stage2-2-runbook.md)、[增量修改清单/汇总](checks/stage2-2-verification.json)、[收尾保护](checks/r15-document-checks.json)，学习记录[07](过程记录/07_2技术操作详解.md)/[08](过程记录/08_2逐步口述稿.md) R15-S01—S05。

| T项适用子集 | 本轮实际证据 | 未覆盖 |
|---|---|---|
| T03 | A/B同名新PDF独立归属、跨用户文档/job/PNG404；动态A5→9/B8→12页白名单；原授权回归仍通过 | history/crop未实现；新单文档模式尚未接入 |
| T06 | 两份新完整PDF各4页经HTTP上传、144dpi/RGB渲染、原ColPali真实8次page forward，4次真实query（含重复问题），同一PID/network0；新图和完整特征身份通过 | 不计准确率、不含MinerU/D；模型关闭失败是旧回归而非本轮新GPU停机实验 |
| T09 | 实际停止/重启后completed、活动代、会话和新PNG保留；queued自动领取，running→interrupted和building→failed有单元模拟 | 没有真实运行中断电/杀进程试验，显式retry/cancel与清理未实现 |
| T11 | 4组同次query向量、同一授权完整页面库，对官方processor＋CPU float32 MaxSim，非并列排名一致；最大差2.625610351358887e-6，原atol1e-4/rtol1e-5不变；8份BF16完整1031×128/1024patch | 区域算法、预算策略、正式评价集和大库性能未验 |

最终63后端（旧55＋新8）在最终错误码补丁后25.749秒通过，日志runtime/verification/r15/backend-final-after-error-code.log；4个原模型环境CPU算法契约、4前端node测试与tsc通过。新增失败测试使用明确encoder/vector替身，覆盖中途编码、部分Qdrant写入、SQLite激活回滚、停用、身份篡改与恢复，不能替代真实GPU证据。OpenAPI与frontend/docs/openapi.json完全相同，未改SDK/前端，不重复生产build。

[真实HTTP第二轮48项](checks/stage2-2-http-attempt2.json)通过：13→17→21且旧集合全向量/payload/config不变；[官方4组](checks/stage2-2-reference.json)通过。实际查看8页contact-sheet，无明显缺页/黑块/裁切，只是缩略视觉QA。[正式首次19项](checks/stage2-2-formal.json)保留；最终补丁重启后[正式20项](checks/stage2-2-formal-final.json)通过：0005只增加2表、原10业务/认证表等于R15备份、jobs/features空、正式原13页、integrity ok/FK0/重复迁移无变化，匿名/Origin保护仍正确；未用正式凭据。T01/T05只沿用回归及正式匿名/同源子项，不扩大覆盖声明。

[首轮选样失败](checks/stage2-2-http-attempt1.json)保留：新PDF没有2—3页，GPU前终止；改为按文件名首两份2—4页，无gold/标签参与。单测import重复收集已修，原日志保留；pypdf xref提示未改源SHA；一次GBK读取错误已显式UTF-8重查。没有2-2阻塞；全代复制存储/写放大、失败私有残留、并发容量与断电属于限制。下一唯一任务2-3A，不自动推进。

## 2026-11-07｜R14补充：工作台改版待验收计划

[前端改版方案](前端工作台改版方案与复用评估.md)要求在2-3B-1/B-2保留身份五态、首改、CSRF、代号/取消、Blob清理、跨标签失效及签名图片行为；执行生命周期回归、typecheck/build，并实际检查两种范围、同名文档、故障、迟到请求和宽窄屏。历史到3-4按当前权限重开。本轮仅源码/报告静态阅读与文档检查，未启动参考仓库、改应用或重跑服务测试；[本轮检查](checks/r14-workspace-redesign-checks.json)不增加应用通过项。

## 2026-11-07｜R14补充：单文档检索待验收计划

[新增设计第6节](单文档检索功能设计与分批计划.md)列2-3A/B的范围、名称、权限和UI检查：同一账号至少可见两份ready文档；单文档Top-k在目标页集合中产生并做真实参考对照；同名A/B隔离，未ready/无权不回退全库；中英文/大小写/全半角/通配字符字面量及分页；模式切换和迟到请求不串结果。T01/T03/T04/T05/T06/T11仅列计划，不新增任何通过项。本轮只静态阅读和文档检查，未重跑2-1服务/算法测试；[文档结果](checks/r14-single-document-design-checks.json)。

## 2026-11-07｜R14 / 阶段2-1

本轮实际覆盖受保护multipart、服务端归属/private、版本1、持久upload job与状态查询。没有把既有T项整项判通过：T01适用部分是匿名访问新路由401；T03为A/B文档/job隔离404；T05为该multipart Origin/CSRF/首改保护；T06仅验证PDF输入和任务排队、不含全页入库/编码/真实问题；T09仅文档/job可持久、queued/failed保留及receiving→interrupted，不含retry，不代表完整生命周期目标。

[本批汇总与修改清单](checks/stage2-1-verification.json)、[收尾文档和保护检查](checks/r14-document-checks.json)为最终入口；技术与口稿使用[07](过程记录/07_2技术操作详解.md)/[08](过程记录/08_2逐步口述稿.md)。

- [预检](checks/stage2-1-preflight.json)：初始状态、端口、包、正式0003快照及R14在线备份。
- [隔离真实HTTP](checks/stage2-1-http-attempt2.json)：29项，第二次尝试成功；首轮脚本错误[单独保留](checks/stage2-1-http.json)。验证20MiB边界、A/B同名不同内容、重启、写盘失败和旧scope/Qdrant指纹。
- [正式迁移与Next代理](checks/stage2-1-formal.json)：18项；0004只增空jobs，旧九表逻辑行指纹一致、integrity ok/FK0/重复迁移不变；匿名/Origin/上传body边界通过，未使用正式凭据。
- 自动：Web环境55项unittest；模型环境4项CPU算法接口契约pytest；前端4项node测试＋tsc；OpenAPI/SDK生成和Next build通过。首轮发现及修正写在runtime/verification/r14日志与stage2-1-runbook。

通过仅限2-1后端及隔离存储任务基础。不含浏览器上传UI、页面渲染/编码/GPU、MinerU、D、区域、重试取消、并发容量、断电、全阶段准确率；不得据此宣布T01/T03/T05/T06/T09整项通过。

更新：2026-11-07，R12。下面T01—T15是 **[设计] 总体验收目标**，不能整表视作通过。阶段0/1A历史保留；1B-3认证、1B-4检索、1B-5网页/图片及1B-6整体启停实际覆盖分别见第6/7/8/9节，PDF和完整管理仍待后续。

## 1. 验收方法

每阶段交付可复查的命令、版本、预期、实际结果、失败记录；通过一项记一项。验收数据使用开发材料，测试账号至少 admin、user_A、user_B。A/B 上传同名 PDF 但内容不同，共享库另有文档，以暴露仅按文件名/ID 管理的错误。成功和失败案例均保留，数据和账号不写入公开 Git。

| ID | 场景和可观察通过条件 | 阶段 |
|---|---|---|
| T01 | 未登录直接 HTTP 访问搜索、图片、PDF、区域、任务、历史均为401；没有裸 files/OCR/旧维护绕行路由 | 1B起，逐路由扩展 |
| T02 | user 构造管理请求（建号、配置、重建、清库）得到403/未挂载；前端菜单隐藏不算证据 | 1B/3 |
| T03 | A 不能读 B 的 document/page/job/history/裁剪；改ID仍404；Qdrant调用实参显示过滤先于Top-k；空白名单与非法过滤不变成全库；重复查询缓存不泄露 | 1B/2/3 |
| T04 | A/B 均能检索与预览共享文档，但不能删除/取消其管理任务；管理员撤下共享后旧结果/预览/历史访问也失效 | 2/3 |
| T05 | 退出、超时、改密、重置和停用后的旧Cookie请求失败；角色不能自改；跨站写请求/缺CSRF被拒；不能停用最后管理员 | 1B/3 |
| T06 | 新 PDF 全页入库；输入非预存预测表问题，真实调用ColPali返回页面；更换问题实际重新编码；关闭模型应明确失败而非回放假结果 | 1A/1B/2 |
| T07 | 实际D-no-text加载身份写入记录；候选框与原图同页同版本；50/100/150%缩放位置一致；类型/ID/页码正确 | 2 |
| T08 | 无候选、解析失败、非法坐标、区域模型异常时仍能看检索页；状态明确，无编造框；非有限分数不进入JSON | 2 |
| T09 | 重启后账号/文档/配置还在；处理中任务变interrupted；重试可追踪attempt且不重复激活页面 | 2/3 |
| T10 | 删除先阻止检索/预览，再清索引/文件/候选/缓存；模拟清理失败仍不可读且可重试；同名另一用户文档保留 | 2/3 |
| T11 | 固定小页面集合：processor参考评分与新adapter/Qdrant基线分数及排名一致；有效query token、1031/1024拆分均核验 | 1A/1B |
| T12 | 固定开发缓存样本：迁移前后候选ID、P′、区域分数/排序一致；原checkpoint哈希一致；不调用gold生成输入 | 2 |
| T13 | profile变更写新索引；身份不匹配时拒用；切换前检查，失败保持旧代可用；后台身份与界面一致 | 3 |
| T14 | GPU/OCR/索引失败、排队、取消与重启均有有限等待和错误；单并发不重复加载模型；峰值/耗时有真实日志 | 3/4 |
| T15 | 按部署说明在独立环境启动，完成登录→新PDF→检索→区域→删除；保存真实截图；旧源仓库状态未被系统写入 | 4 |

T03 额外检查两个排序层面：即使 B 文档相关性最高，A 的 Top-k 仍从其可访问全集产生；不能先全库 Top-k 再删 B。共享撤回与查询同时发生时响应须重查 epoch；权限过滤错误默认拒绝。

阶段 1A 的 CLI 检索只是算法检查，不能替代 T01—T05 的后端授权。测试替身只用于路由隔离、错误路径和接口切换，T06/T07/T11/T12 的真实调用必须单独通过。

## 2. 算法一致性与效果评价

接入一致性：使用固定开发样本、模型/候选/输入哈希、同一计算精度和稳定 tie 规则。CPU float32 区域比较建议 `atol=1e-6, rtol=1e-5`；页面评分的容差在运行前设定，并同时报告最大差异、Top-k 排名及近似并列。超过阈值时解释根因，不修改评分规则来使测试通过。阶段1A对BF16编码所得向量统一转CPU float32评分，预设 `atol=rtol=1e-5`，实测最大绝对差 `3.814697265625e-06`。

功能样例至少两份完整 PDF 的全部页面，不能只导入已知证据页制造容易的检索库；选材、问题与分母固定记录。小样例用于证明程序执行，不用于报告泛化指标。

| 评价层 | 数据要求 | 可报告内容及限制 |
|---|---|---|
| 页面检索 | 完整候选页面集合、稳定page ID、相关性标签 | Recall@k、适用的nDCG；报告多相关页和未命中规则 |
| 条件区域排序 | 正确页已给定、固定候选与gold协议 | 原有区域指标；新解析器输入与冻结历史实验分开 |
| 端到端 | 真实授权检索库、问题—页—框标注 | 从全部问题统计页面命中及区域命中；明确多页/多gold/失败分母 |

不得用两项平均指标相乘充当端到端实测；837 个历史证据页不能自动作为完整检索库。SciEGQA 已被查看/使用，不能重新称未见确认集。部署 checkpoint、阈值和示例不按外部结果挑选。

## 3. 成本与运行证据

记录硬件、依赖/profile、语料规模、每页向量数与总向量数、索引字节、完整特征字节、候选/原图字节。时延至少拆为排队、页面渲染、解析、页面编码/入库、query编码、检索、D融合、区域评分、端到端。报告首次/预热后、重复查询、请求并发、是否包括OCR。阶段4建议固定工作负载下不少于20次串行查询，报告样本数、p50/p95；无实测前不承诺性能。

真实记录按阶段放入新项目忽略的数据目录；可脱敏的摘要纳入 docs。失败不能只出现在终端而没有任务状态。最终截图必须来自真实页面；论文的系统贡献如实写算法接入、权限与版本管理、任务恢复和评价，声明 Snappy 来源。

## 4. 本轮阶段 0 已执行

| 检查 | 结果 | 证据/限制 |
|---|---|---|
| 完整阅读交接说明及适用AGENTS | 已完成 | 目标目录及父目录无AGENTS；只读Snappy指引 |
| 三源仓库HEAD、tracked/untracked状态 | 已完成 | [核查记录](source-audit.md)，不含ignored目录完整审计 |
| Snappy入口、26项静态OpenAPI、认证/存储/任务/模型 | 已完成静态审计 | 没有把静态审计记成HTTP测试 |
| Windows/CPU/RAM/磁盘/GPU/运行时/WSL | 已完成 | GPU空闲值为瞬时快照 |
| Docker引擎 | 未就绪 | API管道不存在，未启动Desktop |
| D-no-text 3份权重、manifest/config/selection哈希 | 通过 | 与冻结身份一致，每份1099555字节 |
| D-no-text CPU strict load | 3/3通过 | 273410参数；未执行forward/评分 |
| 原研究torch CUDA可见性 | 有条件通过 | 默认temp初始化失败；仅诊断进程指定tempfile.tempdir后import成功、CUDA true |
| ColPali类/processor/基座加载 | 未通过 | 类导入20秒诊断超时：filelock→TemporaryDirectory→mkdtemp；未进入大模型加载 |
| MinerU安装元数据/ONNX文件 | 已核实存在 | 未解析新PDF、未重验全部ONNX哈希 |
| 7个核心算法文件源/精简版字节比较 | 7/7一致 | 不等于端到端行为等价 |
| Web启动、权限回归、真实查询/区域、高亮、性能 | 未运行 | 本轮没有应用实现 |

本轮不运行原研究测试套件以制造“系统通过”的印象，也不在原仓库生成pytest缓存或实验产物。设计文档最终检查记录见 [进度](progress.md)。

## 5. 阶段1A实际验收｜2026-11-05，R03

| 检查 | 实际结果 | 范围/限制 |
|---|---|---|
| 独立环境 | 49包、22,461文件副本哈希通过；uv pip check通过 | 本机离线复制方法，非通用wheel发布包 |
| 模型身份与离线加载 | 13文件哈希匹配；processor/base/adapter加载通过 | BF16原ColPali，参数冻结；未改底座 |
| 完整PDF与实际新问题（T06子集） | 两份PDF全部13页编码；4个新问题，page forward=13、query forward=2 | 未通过上传HTTP入库；关闭服务的失败路径未测试 |
| token规则与评分（T11子集） | 页面1031×128；4题均保留10个有效pad-ID token；参考Top-3全部一致 | 比较CPU float32 MaxSim与官方processor；尚未比较Qdrant |
| 4项契约测试 | 4 passed，3.33秒 | 覆盖有效mask、prompt参与评分、非法输入、稳定同分排序 |
| 离线与训练状态 | Python网络审计0次连接/解析尝试；可训练参数0 | 不是系统级网络抓包 |
| 性能观察 | 加载8.3363秒；13页编码3.7536秒；进程总24.1793秒；峰值allocated约8.10 GiB | 单次小负载；不含预先PDF渲染、OCR或Web |
| 旧源仓库保护 | HEAD、状态及已列出变化文件哈希前后一致 | ignored文件未全盘哈希 |

真实结果保留了并行结构图目标页未进Top-3、参考文献页排第1的例子。当前不计算Recall/nDCG，不声称准确率通过。T06/T11只通过上述算法子集；T01—T05授权、T07—T10区域/持久化、T12—T15等业务验收仍未执行。

命令、4题完整结果、版本与文件身份见 [验收说明](stage1a-verification.md) 和 [结构化证据](checks/stage1a-verification.json)。后续变更在其对应场景重新验收，本轮文档收尾不重复GPU推理。

## 6. 2026-11-07｜R09 / 1B-3实际覆盖

- 真实SQLite上的14项认证＋9项数据库回归，共23项通过；包含401/403、可信Origin、CSRF、首次改密、角色、会话哈希/轮换、撤销/停用/重置、重启持久化、DB故障503及注入时钟的空闲/绝对过期。[测试报告](checks/stage1b-3-tests.json)。
- 生产Next＋真实Uvicorn使用隔离账号经代理完成17项检查，含Cookie/Set-Cookie、缺CSRF/跨Origin拒绝、改密/退出及旧Cookie失效、真实后端重启、admin200且只返回脱敏字段。[代理报告](checks/stage1b-3-http.json)。
- 正式库备份后重复迁移0002，原六表（含密码/归属）不变；完整性ok、外键0违例。正式代理六项冒烟通过，测试会话全撤销，正式密码未更改。[正式报告](checks/stage1b-3-formal.json)。
- SDK重新生成、TypeScript与生产构建通过；logout无body仍有JSON头。认证网页尚未开发，本轮没有登录页面浏览器截图。

覆盖T01的现有受保护me/profiles路径、T02最小profiles角色及T05认证相关子项；**不宣布T01/T02/T05整项通过**。检索/图片等尚无路由，最后管理员保护、完整管理审计及端到端页面清理仍留后续。过期用可注入时钟验证，不是实际等待8小时；真实重启验证与应用重建测试分开记录。最终汇总见[1B-3证据](checks/stage1b-3-verification.json)，复现命令及失败解释见[手册](stage1b-3-runbook.md)。

## 7. 2026-11-07｜R10 / 1B-4实际覆盖

36项自动测试通过（13项检索/身份、14项认证、9项数据库）；测试替身用于路由故障/竞态契约，不能替代下面真实计算。真实Next/Uvicorn＋Qdrant＋原ColPali GPU的59项检查通过，最终9次实际forward：8次正常结果和一次故障依赖场景的新编码。[真实报告](checks/stage1b-4-http.json)。

- A私有5页/B私有8页互不混入；对更相关的B音乐问题，A的k=3仍从自己5页产生。服务端过滤含版本/profile/index及page白名单，禁止客户端指定owner/global范围。
- admin无私有/共享时empty，不调用模型和Qdrant查询。共享测试另建管理员文档/页面，A/B私有文档未转共享；撤回后即使Qdrant visibility仍shared也不能命中。查询中撤权/范围变化用真实SQLite加测试替身验证丢弃结果。
- 原模型实际编码两个新问题和重复请求，单worker连续forward计数，联网尝试0；实际终止本轮模型进程后503，重启后端且Qdrant端口不可达时503，退出后的旧Cookie搜索401。
- 8组实际HTTP结果用同次query向量与官方CPU float32参考对照，最大绝对差约2.3301×10⁻⁶，预设atol=1e-4、rtol=1e-5；非并列Top-k一致。共享重复向量允许并列交换，Top-k分数集合一致。[评分](checks/stage1b-4-reference.json)。
- 正式备份后重复迁移0003、13页/13403向量导入并回读float32字节哈希一致，重复导入不upsert；原密码/归属/页面身份保持，SQLite完整性及外键通过。[正式证据](checks/stage1b-4-formal.json)。

覆盖T01搜索、T03检索隔离/先过滤/空范围、T04共享撤回检索子项、T05退出/失效搜索、T06新query、T11 Qdrant参考子项。**不宣布整表通过**。这是R10历史出口，网页/图片在下节R11补验；PDF、完整管理、非空容器重启、GPU并发和正式效果评价仍待后续。失败保留[float32回读首轮](checks/r10-http-first-failure.json)、[代理超时](checks/r10-http-proxy-timeout.json)；复现见[1B-4手册](stage1b-4-runbook.md)。

## 8. 2026-11-07｜R11 / 1B-5实际覆盖

- 45项后端测试通过（9预览＋13检索/身份＋14认证＋9数据库），14.622秒；最后补OpenAPI preview参数后9项图片测试复查通过，2.995秒。9项新增覆盖真实SQLite/PNG、改ID/会话、退出/改密/撤销/停用、共享撤回、当前版本、越界/损坏、读取途中撤权和无裸文件旁路。模型/排名替身仅用于这些授权契约，不代替真实检索。
- 3项前端请求生命周期测试通过，包含取消与迟到返回竞争、操作代号失效、禁止外域/裸文件预览地址。SDK重新生成、TypeScript与最终生产build通过。没有安装或升级依赖。
- 41项真实生产Next/Uvicorn/Qdrant/GPU HTTP通过，8张B原图逐张哈希及no-store检查；首次门禁、旧Cookie401、同账号新会话旧URL404、admin不能读私有图、独立共享媒体夹具与撤回通过。[报告](checks/stage1b-5-http.json)。
- 16项实际浏览器观察通过：初始改密门禁/字段、A/B真实查询和图片、切页、退出/换号/撤销清理、空admin、停止本测试模型后503、390窄屏、另一标签退出同步。[报告与截图](checks/stage1b-5-browser.json)。浏览器未注入模型/向量或预存结果。
- **人工边界：**浏览器工具要求新凭据由用户本人输入提交，故本轮没有自动填写/点击改密提交。隔离A/B/admin通过非UI HTTP完成改密、旧会话撤销及重新登录；正式密码/首次改密标志保持。表单页和门禁的观察不能冒充浏览器提交验收。
- 测试进程/唯一集合清理后恢复正式服务，16项恢复检查通过；七张原业务表与R11备份逐行一致、SQLite完整性ok/FK0、未撤销测试会话0、正式Qdrant13点不变。[正式证据](checks/stage1b-5-formal.json)。

新增覆盖T01 PNG、T03页面改ID/归属/无裸目录、T04共享媒体撤回、T05图片及客户端退出失效、T06真实网页新问题/模型故障子项；不宣称T01—T15整表通过。未测浏览器正式改密提交、BFCache实际导航恢复、共享撤回实时推送、PDF、非空容器重启或并发容量。已交付字节无法收回，后续请求仍重新授权。命令与原理见[1B-5手册](stage1b-5-runbook.md)，本批学习记录在[05](过程记录/05_1b技术操作详解.md)/[06](过程记录/06_1b逐步口述稿.md)，03/04保持原内容。

## 9. 2026-11-07｜R12 / 1B-6实际覆盖与阶段出口

本轮[78项生命周期](checks/stage1b-6-lifecycle.json)、[45后端＋3前端回归](checks/stage1b-6-tests.json)、[13项浏览器观察](checks/stage1b-6-browser.json)、[10项正式恢复](checks/stage1b-6-formal.json)通过；[5组本次官方评分](checks/stage1b-6-reference.json)最大绝对差2.284912110184223e-6，atol1e-4/rtol1e-5不变，非并列Top-k全部一致。R11的SDK/typecheck/build历史保留，本轮API/前端未改，不称本轮重建。

真实非空Qdrant实际stop/start，13点/13403 token向量、全部点ID/payload/float32字节哈希/完整配置一致，同容器/镜像/卷且启动时间变化；无导入/upsert/删除。重启后原ColPali新问题与PNG恢复成功。前后端实际停止重启后会话和预览保留；撤销后重启旧Cookie仍401。停止模型树先503，下一请求实际重新加载恢复，不回放旧结果。最终轮9份真实forward audit联网尝试均0，分母详见[汇总](checks/stage1b-6-verification.json)。

| 验收ID | 本轮适用覆盖 | 未宣称完成 |
|---|---|---|
| T01 | me/search/image/profiles未认证401；裸files/OCR/clear/config/admin-users未挂载404 | PDF/区域/任务/历史未实现，不能称其401已验 |
| T02 | 普通user profiles403、admin200，管理路由未挂载 | 完整管理/最后管理员保护 |
| T03 | A5/B8私有范围、相同B相关问题各自Top-k对照、交叉PNG404、owner注入422、admin空范围不forward | job/history/crop不存在；共享撤回为本轮回归和R10/R11真实历史证据 |
| T05 | 隔离首改与旧会话401、Origin/CSRF403、重启会话保留、撤销不复活、旧preview404、网页退出清理 | 浏览器新密码本人提交；超时/重置/停用为回归证据，未等待8小时 |
| T06 | 已有完整13页，新问题/重复问题真实编码，模型/Qdrant故障503及恢复 | 新PDF上传入库、正式准确率评价 |
| T11 | 5组本次真实HTTP/向量与官方processor＋CPU float32同范围评分、排名一致 | 区域/预算策略和大库评价 |

浏览器包含10项DOM自动检查及3项AX/截图观察，实际停Qdrant后明确错误且旧图/结果清除，恢复后重新显示3页与原图，刷新保留会话、退出清理，正式登录页恢复。原checkbox角色计数错误保存在[失败报告](checks/r12-browser-first-check.json)；最终卡片数量根据已观察AX和[实际截图](checks/stage1b-6-recovered.png)，不声称原自动断言通过。漏“时”文案定位也记录，未重复提交原故障请求。

首轮生命周期的Windows venv双层进程误判保存在[原失败](checks/r12-lifecycle-first-failure.json)；改按一棵模型树核验后完整重跑。正式7张业务表＋2张认证表与R12在线备份完全相同，integrity ok/FK0、全量Qdrant指纹一致、测试进程/模型清理、正式前后端恢复；本轮未使用或更改正式凭据。

阶段1B只在上述本机现有13页链路范围收尾，不宣布T01—T15整表或外部新环境部署通过。03/04保留原内容，R12六步写[05](过程记录/05_1b技术操作详解.md#r12)/[06](过程记录/06_1b逐步口述稿.md#r12)，命令和建议边界见[1B-6手册](stage1b-6-runbook.md)。本批停止，阶段2等待用户继续。

## 10. 2026-11-07｜R13文档规划检查

新增[阶段规划与任务](项目开发阶段规划与任务.md)，将阶段2/3/4细化为6/5/4批并映射适用T项。这些是待实施的验收条件，不增加任何应用测试通过项。本轮仅检查文档编码、链接/锚点、步骤配对、口稿长度和文件保护，结果见[R13文档报告](checks/r13-document-checks.json)；未启停服务、运行模型、迁移数据库或重跑R12验收。03/04、代码和既有报告保留，过程记录仍按原规则在本地忽略。
