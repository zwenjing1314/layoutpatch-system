# 模块与接口契约

更新：2026-11-07，北京时间，R09。**已实现并验证：1A离线算法、1B-1运行骨架、1B-2元数据、1B-3认证会话。** 23项认证/数据库测试、17项真实代理检查通过，正式库0002_auth迁移与六项冒烟通过。[本批手册](stage1b-3-runbook.md)、[汇总证据](checks/stage1b-3-verification.json)。

登录/改密网页、检索HTTP、对象授权和受保护预览尚未实现；profile/index仍pending。下文完整业务蓝图仍是设计，已实现部分以明确标记和证据为准。R05/R06/R08历史及失败保存在[03过程记录](过程记录/03_1b技术操作详解.md)。浏览器统一走同源`/api`，表内为后端路径。

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
| GET /search?q=...&k=... | 页面列表、profile/index ID、分阶段耗时 | AllowedScope 先过滤 | 1B |
| GET /pages/{page_id}/image、/thumbnail | 授权文件响应、原图尺寸与版本 | 文档可读 | 1B/2 |
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

login/me的200响应均含user_id、username、role、must_change_password、csrf_token；login输入username/password。password输入current_password/new_password，新密码12—128字符且不同；成功204，撤销该用户全部会话并清Cookie，须重新登录。logout成功204，无body仍须JSON Content-Type。未首次改密时受保护业务入口403；普通用户访问admin/profiles403；有效且已改密admin200。当前以profiles验证门禁，其他业务随实现接入，不能泛称所有对象已授权。

写请求检查唯一可信Origin与JSON；password/logout增加唯一X-CSRF-Token。认证/admin响应含private,no-store及Vary Cookie。错误使用`{"detail":"错误码"}`，不会回显密码；下节ErrorResponse仍为未来检索业务设计，尚未统一到此格式。状态码、字段及失败限速见[手册第2节](stage1b-3-runbook.md#2-接口与正确顺序)。SDK已生成并集中注入JSON/CSRF头，UI调用与状态清理留1B-5。

## 2. 结果字段（结构定义，非运行样例）

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

下列名称是业务层的目标接口。当前 `ColPaliAdapter.load/encode_page/encode_queries` 以及 `maxsim_scores/top_k` 已实现CLI编码与排序；已有元数据库及auth路由，尚无 `AllowedScope` 或检索服务路由。接入Web后业务层负责权限，算法层只处理已授权输入，不扫描用户目录；输出ID必须属于本次输入。

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

代码入口：`LayoutPatchD`、`InputAblatedD("text")`、`page_layout`、`patch_scores/region_scores`。参数量 273410；三个既有 seed 的 checkpoint 本轮均通过 CPU strict load。

`page_layout` 输入按 `layout_id` 升序排列的整页候选，每个含 `bbox/page_size/type/layout_id`；文本槽为 `[M,1024]`。D-no-text 在投影前置零文本槽，保留坐标、类型、邻接与 mask，因此无需为这一部署加载 BGE-M3。若改为带文本 D，则必须另外核验 BGE-M3 与节点文本来源，不能静默切换。

布局坐标映射到 448×448 模型空间；`coords=[x1,y1,x2,y2,width,height]` 归一化，邻接 `[1024,M]`。D 得到 P′ 后，patch 分数是 `max_i <q_i,p′_j>`；候选分数为原实现的 patch-IoU 加权均值，不增加阈值、损失、人工重排或按 gold 过滤。分数相同时保留冻结的候选 ID 顺序；接入时以原排序实现为基准核对。

**[设计] 系统默认固定 seed0 / epoch1**：

```text
runs/retrieval/route_v2_exp3_attribution/20261007_135013/D-no-text/seed_0_epoch_01.pt
SHA256 18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b
```

路径相对只读原研究库；运行时通过环境变量连接或受控复制到仓库外。选择依据是预先固定最低 seed 编号，其 epoch 已按 source_val 规则选择；不比较外部表现选择 seed。此部署不等同于历史三 seed 均值，不把 30.7969% 作为该单 checkpoint 的系统成绩。激活前必须通过小规模真实缓存一致性测试。

## 6. 解析器与坐标契约

建议使用本机已有 MinerU 4.0.10 / ONNX Runtime 1.30.0 / docvortex 0.5.10、Basic CPU，模型记录 revision `358310b4f64b95f9fefc372ad899356e4111f376`。本轮确认包版本及 8 个 ONNX 文件存在，未运行新 PDF 解析，未重新校验全部模型哈希；属于可用候选，不能称解析路径验收通过。

沿用 `docvortex.middle 2.0` 顶层 block 导出思路。解析输入不含 query/gold；类型映射不明、ID 重复、框非法、坐标溢出时记录解析失败，不默默裁剪或伪造候选。空页面允许零候选。既有内部候选原解析器追溯不完整，应区分“旧固定候选回放”和“新 PDF 解析”。

系统统一返回原始渲染图像素 `[x1,y1,x2,y2]`，左上为原点，附 width/height/render_sha256。解析单位框需结合 PDF 尺寸、旋转、裁剪、渲染矩阵映射；不能直接把单位坐标乘 448 当成前端框。首版仅接受已验证几何输入，旋转/CropBox 特例未测试则明确拒绝区域解析并保留页面检索。

前端按实际图像内容矩形计算缩放及留白偏移：`display_x=offset_x+x*scale_x`，y 同理。图像、裁剪、候选必须绑定同一渲染版本；验证 50%/100%/150% 缩放、不同长宽比，不能只看一张成功截图。

## 7. profile 变更的验收要求

profile 是不可变配置 ID；前端只能选择管理员激活的已验证配置。测试替身可检验 adapter 切换和错误路径，但必须标记测试运行，不能进入真实演示结果。预算方法未就绪时保持 `colpali_full_v1`，在页面显示“完整向量基线”；不下载第二底座证明可扩展性。
