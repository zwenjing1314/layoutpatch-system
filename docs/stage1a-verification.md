# 阶段1A｜ColPali离线加载与真实页面检索验收

日期：2026-11-05（Asia/Shanghai）。对应过程记录 **R03**。工作目录：`C:/Users/WenJing/Documents/WorkTransfer/layoutpatch-system`。

## 1. 结论与范围

**[已验证] 阶段1A通过。** 新项目独立环境离线加载现有原 ColPali，对两份完整 PDF 的 13 页及 4 个新问题实际执行编码，返回 Top-3。页面完整性、模型身份、query 有效 token 和参考评分一致性均通过。

**这次通过的是命令行算法链路。** 尚无登录、HTTP业务接口、Qdrant、上传任务、区域排序或高亮。小规模功能样例不构成检索准确率、中文效果、并发能力或端到端系统验收。

证据入口：[结构化验收包](checks/stage1a-verification.json)、[原始报告](../runtime/verification/20261105-gpu-first/report.json)、[完整语料清单](../runtime/corpus/manifest.json)。原始报告 SHA256：`d1b025f09734c10c0c17083425b46f7040c33c3bd84e89c080b05dad78621920`。

## 2. 环境阻塞如何解除

| 检查/操作 | 实际结果 | 结论边界 |
|---|---|---|
| 原研究 `.venv` 对新项目临时目录进行创建/写入诊断 | 普通写文件也出现 PermissionError | 不能只归因于 ColPali 或临时目录变量 |
| 系统 Anaconda Python、已有规范路径 Python 在相同目录写入 | 成功 | 错误与执行环境有关；底层系统原因未查明 |
| 用已有 Python 3.11.16 新建独立 `.venv` | 临时目录和文件写入成功 | 没有修改旧环境或系统权限 |
| 尝试 `uv pip install --offline` | 本地缓存缺部分依赖，未完成 | 未改用联网安装；不把尝试写成成功 |
| 从旧环境的已安装发行包复制最小依赖闭包 | 49个包、22,461个文件哈希校验通过 | 独立文件副本，运行时不引用旧研究路径 |
| 新环境导入 torch/ColPali/processor、本地处理器加载 | 通过，CUDA可用 | 后续 GPU 实测另行通过 |
| `uv pip check` | 全部49个包兼容 | 不代替实际推理；真实推理也已执行 |

依赖脚本根据发行包元数据解析依赖，验证可用的 RECORD SHA256，再验证目标副本哈希；排除 pyc、包目录外启动器及旧项目可编辑安装。排除记录共25条，命令工具通过 `python -m` 调用。详见 [环境原始记录](../runtime/checks/environment-seed.json)。

这是一套本机离线构建办法，**不是通用离线 wheel 安装包**。当前运行与旧 `.venv` 隔离；从零重建仍需同一套可用的已安装包、已有基础 Python 和模型缓存。未把旧研究项目加入 `sys.path`，未复制旧实验代码或更改第三方模型源码。

| 核心组件 | 实测版本 |
|---|---|
| Python / torch / torchvision | 3.11.16 / 2.13.0+cu130 / 0.28.0+cu130 |
| colpali-engine / transformers | 0.3.18 / 5.17.0 |
| peft / accelerate | 0.20.0 / 1.15.0 |
| PyMuPDF / Pillow / pytest | 1.28.2 / 12.3.0 / 9.1.1 |

直接依赖见 [requirements-colpali.in](../requirements-colpali.in)，全部版本见 [锁文件](../requirements-colpali.lock.txt)。

## 3. 加载与评分实现

- **模型身份：**adapter 为 `vidore/colpali`，revision `7754422bfa37f8e3cd771e13d4d7f07de3103c95`；base 为 `vidore/colpaligemma-3b-mix-448-base`，revision `6ff0d944ea09c3ead97d2bc57427e3d4f01d192f`。13个配置/词表/权重文件均重新计算 SHA256，与历史 manifest 一致；模型类及处理器源码哈希也匹配。
- **加载方式：**使用 `ColPali/ColPaliProcessor`，显式传本地 base 和 adapter 路径及 `local_files_only=True`。当前锁定 Transformers 通过 `adapter_kwargs._adapter_model_path` 接收本地 adapter；这是与锁定版本相关的加载行为，升级后必须重新验收。
- **推理方式：**BF16、`cuda:0`、页面 batch=1、query batch≤2；`.eval()` 与 `inference_mode()`，全部参数不求梯度。没有训练、量化、卸载或更换底座。缺失/多余/形状不符参数和加载错误列表均为空。
- **完整页面：**每页 `[1031,128]`，前1024行为图像 token，后7行为prompt；完整页面检索使用全部1031行。以后区域排序才使用前1024行，不使用旧的错误 `[7:]` 切片。
- **有效问题：**只移除 `attention_mask=0` 的补齐行，并检查这些输出为零。4个问题各保留10个 pad-ID 的有效增广 token，不能看到 token ID 为0就删除。
- **评分：**在 CPU float32 上计算 `sum_i max_j <q_i,p_j>`。每个问题 token 在一页中找最相似 token，再将这些最大值相加；分数用于排序，不是概率。所有13页一起竞争 Top-k，同分按 page_id 稳定排序。
- **对照：**相同完整向量输入官方 `processor.score_multi_vector`，比较全部13页分数及 Top-3；预设 `atol=1e-5, rtol=1e-5`。这是评分接入一致性，尚未比较未来 Qdrant。
- **离线：**脚本在导入依赖前设置 HF/Transformers offline 与禁遥测；Python审计钩子拒绝 socket连接/域名解析。本次审计记录为0次尝试，这是进程级检查，不是系统级网络抓包。

主要实现：[算法适配器](../backend/algorithms/colpali_adapter.py)、[张量与排序契约](../backend/algorithms/contracts.py)、[验证入口](../scripts/verify_colpali_local.py)。profile ID 是 [配置文件](../configs/colpali_local.json) 的 SHA256，实测为 `da132ccca44fd3964eea940881be0f30663f7b48957f09925cce19c5df9b0f99`。

## 4. 语料与结果，包含失败样例

从本地 SciEGQA PDF.tar 按归档文件名排序，选前两份页数为2—8的PDF；**在检索前固定规则**，没有读 gold/相关页标签筛页。两份文档分别为 tuGEMM（5页）和 Frechet Music Distance（8页），全部13页包括参考文献页都以144 DPI渲染，保留源PDF、页序、图片哈希。已人工查看 [全页缩略图](../runtime/corpus/contact-sheet.png)。提取文本只辅助阅读，不输入视觉编码器。

问题在阅读文档后新写，见 [固定问题清单](../configs/development_queries.json)；没有加载旧问题预测表。此数据来源此前已参与研究，只能称开发/功能验证，不能称未见测试集。

下表页码从1开始，排名顺序从左到右；手工相关内容观察不等同于完整gold标注。

| 新问题（实际英文输入） | Top-3 文档与页码 | 人工观察 |
|---|---|---|
| Which page illustrates the serial temporal-unary matrix multiplication hardware? | tuGEMM：1、2、3 | 第2页串行结构图排第2 |
| Where can I compare the parallel tuGEMM design and its power, area, and latency plots? | tuGEMM：1、2、4 | 含并行结构图的第3页未进前三 |
| How is Frechet Music Distance computed? | Music：1、2、6 | 第2页计算示意图排第2 |
| Which page shows how transposing pitch changes the music evaluation distance? | Music：7、6、1 | 第6页相关图表排第2；第1名是第7页参考文献 |

4组 Top-3 与官方参考全部一致，最大绝对分数差 `3.814697265625e-06`。实际 page forward 13次，query forward 2批。没有按结果修改问题、筛掉失败页或加入人工重排；不从这4题计算或宣称系统准确率。

## 5. 实际成本与检查

| 项目 | 本次单进程实测 |
|---|---|
| 模型加载 | 8.3363秒 |
| 13页编码合计 | 3.7536秒；首张约1.613秒，包含首次开销 |
| 2批问题编码 | 0.03984秒、0.02703秒，每批2题 |
| 13页精确评分 | 每题约0.0032—0.0041秒，不含query编码与参考对照 |
| 验证进程总时长 | 24.1793秒，包含导入、哈希、加载、编码、评分及写报告；不含此前PDF渲染 |
| GPU | RTX 3080 Ti；PyTorch峰值 allocated 8.10 GiB、reserved 8.32 GiB |
| 完整页面/查询特征文件 | 3,436,308 / 27,703字节；不包含模型和页面图 |
| 自动化契约测试 | 4/4通过，3.33秒 |
| 三个旧源仓库 | HEAD、状态及列出改动文件哈希与本轮开始一致 |

峰值是 PyTorch 分配器口径，不是整机占用；不同时间的空闲显存快照不能相减解释模型大小。本次只有一个小负载，没有测并发、p50/p95、OCR或浏览器响应，也没有终止用户其他进程。

契约测试覆盖有效增广/补齐区别、完整页面prompt参与评分、非法输入/重复ID、稳定同分排名。旧仓库保护证据：[开始](checks/source-state-r03-before.json)、[结束](checks/source-state-r03-after.json)，未穷举 ignored 数据文件。

## 6. 如何自己复现

以下命令在 PowerShell 中运行。环境和语料已就绪时，直接从“实际验证”开始；**不要在现有 `.venv` 或已存在的输出目录重复初始化**。示例追加输出名须尚未存在。

```powershell
Set-Location 'C:\Users\WenJing\Documents\WorkTransfer\layoutpatch-system'

# 实际已执行并通过的命令；保留原输出，不覆盖它。
.\.venv\Scripts\python.exe -B -u scripts/verify_colpali_local.py --queries-file configs/development_queries.json --output runtime/verification/20261105-gpu-first --device cuda:0 --k 3

# 再次复现时改用新的目录，例如以下名称（本示例尚未执行）。
.\.venv\Scripts\python.exe -B -u scripts/verify_colpali_local.py --queries-file configs/development_queries.json --output runtime/verification/20261105-recheck-01 --device cuda:0 --k 3

# 自己输入新问题的形式，问题与输出名均可修改（本示例尚未执行）。
.\.venv\Scripts\python.exe -B -u scripts/verify_colpali_local.py --question 'What are the limitations of Frechet Music Distance?' --output runtime/verification/20261105-my-question-01 --device cuda:0 --k 3

# 已执行的轻量检查。
.\.venv\Scripts\python.exe -B -m pytest tests/test_retrieval_contract.py -q -p no:cacheprovider
uv pip check --python .venv/Scripts/python.exe
```

每次 CLI 都重新编码全部13页和本次问题。结果在对应目录的 `report.json`，状态应为 `passed`；`queries[].top_k` 给页码与分数，`query_token_audit` 给有效token，两个 `.pt` 文件保留新特征。失败会记录 `status=failed` 和 `error.txt`，不会回放旧预测。

以下是**本次已执行的初始化命令**，供理解环境来源；只在新的独立环境/语料输出目录重建时使用。系统 `python` 是已有、可导入 packaging 的引导解释器；没有从旧环境复制 Python 可执行文件。

```powershell
uv venv --offline --python 'C:\Users\WenJing\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none\python.exe' .venv
python -B -u scripts/seed_local_environment.py --source-site 'C:\Users\WenJing\Documents\WorkTransfer\layoutpatch\.venv\Lib\site-packages'
.\.venv\Scripts\python.exe -B scripts/prepare_development_corpus.py --archive 'C:\Users\WenJing\Documents\WorkTransfer\layoutpatch\data\raw\sciegqa_bench\9bdca77be633cc3259d7e3739d35b38ab00bf5d9\PDF.tar'
```

## 7. 下一步与待核实事项

**下一轮唯一主要任务：阶段1B，完成登录后在授权文档范围内真实检索并预览页面的网页闭环。** 先建立admin/A/B、后端会话与归属，再接独立Qdrant和网页；退出后的原预览URL必须失效。

当前1A无剩余阻塞。旧环境写入根因未查明，但已不阻塞独立环境。Web/容器依赖、两用户隔离、Qdrant一致性、MinerU新PDF解析、D区域推理、正式评价库、预算方法与再分发许可仍待后续核实；详见 [进度与阻塞](progress.md)。`.env.example` 尚不参与运行，`/docs` 现有Git忽略规则保留，文档需要单独保留本地副本。
