# 阶段 0：源代码、环境与资源核查

核查日期：2026-11-05（Asia/Shanghai）。本报告只描述本轮看到或执行的内容，不把历史启动记录、文件存在、权重加载混同为系统运行成功。

**同日后续记录（R03）：**阶段1A已在独立环境解决当前项目的ColPali离线加载，完成13页与4个新问题的真实检索，见 [阶段1A验收](stage1a-verification.md)。下文保留阶段0当时的失败和未知，不代表最新运行状态；旧环境写入失败的系统根因仍未查明。

## 1. 事实等级和结论

- **[事实]**：实际读取本地代码、配置、包元数据、设备信息或执行有限检查所得。
- **[设计]**：拟在新项目实现的选择，尚未开发。
- **[待核实]**：尚缺运行证据、完整身份或业务材料。
- **[历史记录]**：旧文档/manifest 的陈述，本轮未重新计算其效果。

**结论：[设计] 有条件复用 Snappy 前后端工程；当前不能宣称“本机完整 Snappy 可直接运行”。** 认证/元数据库/任务持久化需要新建，原 ColPali 加载器必须适配，文件与检索必须加归属隔离。最先解除原 ColPali 的环境导入阻塞，然后做真实编码小验证。不要先启动上游的 ModernVBERT 与 DeepSeek-OCR 栈。

## 2. 目录、规则与仓库状态

独立目标为 `C:/Users/WenJing/Documents/WorkTransfer/layoutpatch-system`，开始时仅有 `.git`，分支 `main` 尚无提交，Git 输出上游 `origin/main [gone]`；未 fetch、改远程或推送。目标及 `C:/` 到父目录链未发现 AGENTS.md；读取了 Snappy 根目录的 AGENTS.md，用于理解其复用规范。

完整读入用户指定交接说明：
[系统开发交接说明_用户管理员权限_20261104.md](C:/Users/WenJing/Documents/WorkTransfer/layoutpatch/docs/thesis/系统开发交接说明_用户管理员权限_20261104.md)。

| [事实] 源仓库 | 本轮 HEAD | 工作区已有变化 |
|---|---|---|
| layoutpatch | `5dd4e5c98c3cabc1f20e84a3d9cceee2c978301c` | `.gitignore` 修改；4个`.chart-data-*`目录内共8个未跟踪PPTX/JSON |
| Snappy | `acde4a1fdfd75f31d4ff13a04c03b1f06706b6f1` | `backend/Dockerfile` 修改；4个未跟踪文件 |
| layoutpatch-evidence | `4a2c006fb25699a16ca67c33e0bbbad951a24cd0` | tracked/untracked 状态干净 |

Snappy 未跟踪文件为 `GitHub-Fork-操作笔记.md`、`docker-compose.local.yml`、`docs/local-ui-notes.md`、`docs/local-ui-setup.md`。Dockerfile 的现有差异是 Debian apt 源从 HTTP 改为 HTTPS，未修改它。

状态与已有变化文件哈希见 [开始快照](checks/source-state-before.json) 和 [结束快照](checks/source-state-after.json)，二者一致。检查 `git status --short --untracked-files=all` 不覆盖 ignored 数据/模型/环境；本轮没有全量哈希旧数据，也不据此声称整盘逐字节核验。

## 3. Snappy 可复用内容及缺口

以下路径均相对 `C:/Users/WenJing/Documents/WorkTransfer/Snappy`。

| 编号 | [事实] 直接核查 | 来源 | 对新项目的影响 |
|---|---|---|---|
| S01 | Next.js 16.0.7、React 19.2.0、TypeScript、yarn.lock；gen:sdk使用openapi-typescript-codegen | `frontend/package.json`、`frontend/yarn.lock` | 选择性复用界面/依赖，按SDK流程扩展 |
| S02 | FastAPI创建app，挂载retrieval/indexing/maintenance/config/ocr/interpretability/files；中间件是request-id/timing/CORS | `backend/api/app.py`、`backend/main.py` | 未见全局身份认证或授权中间件 |
| S03 | `GET /search` 仅q/k/include_ocr；上传`POST /index`未接收登录用户 | `backend/api/routers/retrieval.py:16`、`indexing/upload.py:29` | 需显式加入当前用户与AllowedScope |
| S04 | files只校验bucket/路径，返回`public,max-age=86400` | `backend/api/routers/files.py:38` | 防目录越界不是用户授权；替换资源访问与缓存头 |
| S05 | ProgressManager为内存字典，终态延迟300秒清理 | `backend/api/progress.py:10` | 不能用它证明任务重启可恢复 |
| S06 | Qdrant points有document_id/page_id/filename等，无用户归属字段；删除客户端可按filename | `backend/clients/qdrant/indexing/points.py`、`collection.py` | 新增版本/owner/配置身份，按对象ID删除 |
| S07 | search支持可选filter，但构造异常会退为None；预取分支未显式传filter | `backend/clients/qdrant/search.py` | 必须改为强制过滤、失败拒绝；基线先关闭预取 |
| S08 | 数据库用Qdrant+文件；requirements未列SQLAlchemy/SQLite元数据层；审计范围未发现用户/会话模型 | `backend/requirements.txt`、api/middleware/clients/domain | 新增SQLite元数据库；不假设现有认证可复用 |
| S09 | SDK静态OpenAPI有26个operation，无securitySchemes/root security/operation security | `frontend/docs/openapi.json` | 与入口代码共同支持“当前无业务认证”的结论；不是HTTP漏洞测试 |
| S10 | SDK client区分浏览器与内部URL；lightbox提供原图与热力图界面；SSE使用EventSource | `frontend/lib/api/client.ts`、`components/lightbox.tsx`、`lib/hooks/use-upload-sse.ts` | 可复用布局；热力图不等于D候选框排序；统一同源并改授权 |
| S11 | 默认模型为ModernVBERT；加载器非modernvbert时走ColQwen3 | `colpali/app/core/config.py`、`services/model_service.py:13` | 仅改成vidore/colpali会走错误类，必须新增正确adapter |
| S12 | 默认OCR为DeepSeek-OCR-2；compose两模型都请求GPU并映射端口 | `deepseek-ocr/app/core/config.py:19`、`docker-compose.yml` | 本项目不启用这两个默认GPU服务 |
| S13 | 后端Dockerfile基于Python3.10；AGENTS称3.11+且运行示例与实际flat imports有差异 | `backend/Dockerfile`、`backend/main.py`、`AGENTS.md` | 新项目用3.11独立环境，实际入口以代码验证 |
| S14 | 后端requirements多数未锁版本，colpali依赖来自Git地址 | `backend/requirements.txt`、`colpali/requirements.txt` | 不能无审计直接升级安装到旧环境 |

旧维护路由包含 `/clear/qdrant`、`/clear/storage`、`/clear/all`、`/initialize`、`/delete`、`/status`；config含 `/config/schema/values/update/reset`；OCR含处理与进度/取消。它们不能因隐藏菜单就保留原样。新项目只挂载已明确保护的路由，清库等危险通用入口不迁入。

**[历史记录]** `docs/local-ui-setup.md` 写于2026-10-10，记录曾启动Qdrant/后端/前端，模型关闭、搜索不可用、health degraded。该历史记录不能代替11月5日的启动验收。

## 4. 区域算法和精简仓库

研究根目录 `C:/Users/WenJing/Documents/WorkTransfer/layoutpatch`；精简根目录为同父目录下 `layoutpatch-evidence`。

**[事实]** 阅读了 `configs/experiments/route_v2_exp2_D.yaml`、`route_v2_exp3_attribution.yaml`、`route_v2_external_eval_v1.yaml`；核查以下入口：

- `src/layoutpatch/retrieval/colpali.py` 使用 `ColPali/ColPaliProcessor`、process_images/process_queries 和 score_multi_vector，但其旧在线包装不具备本项目的完整版本/权限契约。
- `colpali_layout.py` 明确 image-first `[0:1024]` patch、`[1024:1031]` prompt，指出旧`[7:]`切片错误。
- `route_v2_layout.py` 的 `page_layout` 检查layout_id排序和`[M,1024]`文本槽；D不接收query或gold。
- `route_v2_attribution.py` 的 `InputAblatedD("text")` 在forward前置零文本，保留其他输入。
- `route_v2_scoring.py` 定义每patch对query取max、候选IoU加权均值；`route_v2_query_cache.py`按attention_mask去补齐并保留增广token。
- `layout/nodes.py`、`layout/correspondence.py`、`retrieval/fusion/sparse_fusion.py` 提供节点、32×32/448坐标和融合。

上述 D/消融/评分/token布局/坐标/节点/融合共7个核心文件在两个仓库中SHA256一致。`layoutpatch-evidence/README.md`明确它是精简研究代码、未附许可证、没有打包数据与权重；`SOURCE_PROVENANCE.json`也未声称行为等价或完整复现。新系统可按模块受控复用，不据目录名推断它已是Web系统。

**[待核实]** 定向检查原库 `src/configs/scripts` 的budget/allocation/compress/pruning文件名及实验配置，未发现可确认的页面预算研究实现。此范围有限，不能断言其他位置没有新研究；预算模块保持未完成状态，不阻塞完整向量基线。

## 5. 本机环境

| [事实] 项目 | 本轮观察 | 限制 |
|---|---|---|
| OS | Windows 11专业版，10.0.26200，64位 | 未测Linux部署 |
| CPU / 内存 | i5-14600KF，14核20逻辑处理器；34180530176字节，约31.8GiB | 未做负载测试 |
| C盘 | 总1999318806528字节；采样剩785933660160字节，约732GiB | 非容量/吞吐保证 |
| GPU | RTX3080Ti，12288MiB，驱动610.88；采样空闲5131MiB | 空闲随其他进程变化，未释放用户进程 |
| 系统Python | Anaconda Python3.12.4 | 不作为研究依赖已满足的证据 |
| 研究.venv | CPython3.11.16；torch2.13.0+cu130、torchvision0.28.0+cu130、transformers5.17.0、colpali-engine0.3.18、accelerate1.15.0 | 包存在不等于ColPali可加载 |
| 研究.venv其他依赖 | PyMuPDF1.28.2、Pillow12.3.0、pytest9.1.1、argon2-cffi25.1.0 | FastAPI/uvicorn/qdrant-client/SQLAlchemy/Alembic/pwdlib未检出 |
| Node/npm/uv | Node24.14.0、npm11.9.0、uv0.12.5 | 未build前端 |
| Yarn/Poppler | 未找到yarn命令；corepack存在；pdftoppm/pdfinfo在当前PATH | 未安装包；Poppler路径属Codex运行依赖，正式部署需稳定提供 |
| Docker | CLI29.8.0，Compose5.5.1 | `docker info`失败：dockerDesktopLinuxEngine管道不存在 |
| WSL | docker-desktop，WSL2，Stopped | 没有启动Docker Desktop |
| 常用端口 | 3000/8000/6333/6334/7000/8200的监听查询无返回记录 | 仅当时采样 |

**环境阻塞的实测细节**：

1. 直接导入torch时，在dill调用`tempfile.gettempdir()`处报 `No usable temporary directory found`。
2. 仅在诊断Python进程内把 `tempfile.tempdir` 指向新项目现有目录后，torch导入成功，`torch.cuda.is_available()`为true。未修改系统环境、旧依赖或原库源码，这不算一般运行环境已修好。
3. 同样条件下加载三个D-no-text权重均成功；随后导入ColPali类未结束，手动终止该诊断。
4. 用`faulthandler.dump_traceback_later(20, exit=True)`做有界复查，20秒后退出码1。堆栈停在 `filelock/_strict.py:_probe_link_follow_symlinks → tempfile.TemporaryDirectory → mkdtemp`，由huggingface_hub/transformers导入触发。

**[待核实]** 临时目录/文件锁问题的根因及独立环境修复方式，不能据此断言模型权重损坏、CUDA不兼容或显存不足。未进入ColPali大模型加载，也未获得processor加载成功输出。新项目阶段1A先复现并修复，不直接改旧.venv。

## 6. 真实模型、解析器与数据资源

### 原 ColPali

缓存根 `C:/Users/WenJing/.cache/huggingface/hub`：

| [事实] 组件 | snapshot | 本轮文件检查 |
|---|---|---|
| `models--vidore--colpali` | `7754422bfa37f8e3cd771e13d4d7f07de3103c95` | 9个文件，含adapter_config、adapter_model.safetensors及tokenizer/processor文件；权重78625112字节 |
| `models--vidore--colpaligemma-3b-mix-448-base` | `6ff0d944ea09c3ead97d2bc57427e3d4f01d192f` | config、index和2个safetensors分片；分片总5849312816字节；index列出的分片均存在 |

adapter_config确实指向上述base。历史编码manifest中的revision与这两个目录一致，并记录了原模型/处理器文件哈希和类身份。**本轮未重新计算这两个模型所有文件哈希，未验证离线加载**；完整身份校验与显式本地base解析放在阶段1A。缓存体积约5.52GiB不等于运行显存需求。

### D-no-text

只读清单：`layoutpatch/artifacts/route_v2_external/preparation_v1/20261007_152240/weights.json`；实算SHA256为 `5a1bc2a05dfdd5b7287862a6b04928f30b0d90612b6cc2abb77aad7c4bebbe0f`，匹配冻结配置。D-no-text的训练配置和checkpoint_selection.json哈希也匹配。

checkpoint共同前缀：`layoutpatch/runs/retrieval/route_v2_exp3_attribution/20261007_135013/D-no-text/`。

| [事实] 文件 | SHA256 | CPU加载 |
|---|---|---|
| seed_0_epoch_01.pt | `18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b` | strict keys全匹配 |
| seed_1_epoch_01.pt | `e4883a87804dfff5d0623a4b77c9b10a01b7e18ab5ca8d79ba9f5444174fb95b` | strict keys全匹配 |
| seed_2_epoch_05.pt | `8b509981c9d85cbbff3feb4f0523c050b4bb08fde69a415a07e4d188f0567cb5` | strict keys全匹配 |

每份1099555字节，`torch.load(weights_only=True,map_location="cpu")`后用`InputAblatedD("text").load_state_dict(...,strict=True)`加载，273410参数。未forward、未评分、未重算指标。建议固定seed0部署的理由与边界见 [接口契约](interfaces.md)。

### MinerU 与数据

实际工具根：`layoutpatch/artifacts/route_v2_external/preparation_v1/mineru_tool_v1`。其中`.venv`元数据为MinerU4.0.10、onnxruntime1.30.0、docvortex0.5.10；`mineru_home/models/MinerU-4_models_onnx`下有8个ONNX文件，总855806337字节。默认HF同名缓存目录没有snapshots，真实模型在工具目录，不能只凭HF文件夹名找模型。

冻结parser配置指定Basic ONNX CPU、model revision `358310b4f64b95f9fefc372ad899356e4111f376`、顶层blocks、真实解析文本来源和坐标校验。当前`datasets/mineru.py`包含PDF/渲染映射与CropBox检查。**本轮仅检查文件和包元数据；未启动解析、未复验ONNX哈希或新PDF坐标。**

SciEGQA的PDF.tar（132444160字节）、标注JSONL（695934字节）及历史candidates.jsonl（6754364字节）存在，页面/查询缓存manifest也存在。未解包全PDF、未重新审计完整页面检索库和标签映射。837证据页仍不等于完整库。阶段1A可用开发PDF全页做功能验证，正式效果评价需另建冻结清单。

## 7. 依赖与来源清单

| 项目 | 决策/状态 |
|---|---|
| Snappy | 当前本地LICENSE为MIT，Copyright(c)2025 athosg；复用源码时原样保留许可和版权，记录提交及本地差异 |
| layoutpatch / layoutpatch-evidence | 受控复用研究代码；精简仓库明确未附许可证；公开分发前核实原作者代码/参考实现归属，不擅自标MIT |
| ColPali及PaliGemma派生base | 本地权重存在；模型卡/许可和分发条件未在本轮完整核实；不打包进Git |
| MinerU/ONNX模型 | 现有本地候选解析路径；代码与模型许可分别核实，不以Snappy MIT覆盖 |
| Qdrant / FastAPI / Next.js / React | 技术栈确定；实际新环境安装版本、镜像digest、前端build待阶段1锁定 |
| SQLAlchemy/Alembic、pwdlib/会话库 | 设计新增；本轮不安装，兼容性及会话生命周期需测试 |
| SciEGQA/MMDocIR/PDF材料 | 本地研究材料不整体复制到新Git；公开展示/分发和评价身份单独记录 |

一手来源入口：[Snappy](https://github.com/athrael-soju/Snappy)。本轮未联网更新源码或模型，也未以最新上游覆盖本地已有差异。

## 8. 实际命令与结果索引

这些是本轮执行或对应检查的命令模式，不是启动指南。只读Python用`-B`/`PYTHONDONTWRITEBYTECODE=1`，模型相关诊断设`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`；未执行uv sync、pip install、yarn install、compose up。

| 命令/检查 | 实际结果 |
|---|---|
| Get-Content -Raw 指定交接文档 | 完整读入 |
| git -C <三个源库> rev-parse HEAD / status --short --untracked-files=all / diff --stat | 见第2节；后续状态检查禁用可选Git锁 |
| rg 定向检查app、routers、middleware、客户端及模型入口 | 见S01—S14；不存在的猜测路径改为实际路径后读取 |
| Get-CimInstance / Get-Volume / Get-Command | OS、CPU、内存、磁盘与程序路径见第5节 |
| nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv | RTX3080Ti/12288MiB/空闲5131MiB |
| docker --version / docker compose version / docker info | CLI存在；引擎连接失败；未检查镜像/卷 |
| wsl --status / wsl --list --verbose | docker-desktop为WSL2且Stopped；终端有UTF-16显示问题，可辨认状态 |
| python/node/npm/uv --version | 见第5节 |
| 研究Python importlib.metadata.version | 已安装包与缺失项见第5节 |
| hashlib.sha256 权重/清单/训练配置/选择文件 | D-no-text 3/3匹配及关联身份匹配 |
| torch CPU strict load | 3/3成功，未运行推理 |
| ColPali import + faulthandler 20秒上限 | 失败，堆栈停在临时目录/文件锁初始化 |
| 7个核心源码SHA256对照 | 7/7相同 |

完整应用启动、权限HTTP测试、模型forward、索引查询、解析、高亮和性能测试均未运行。检查失败如实保留；不把整个批处理最后一个命令的退出码当所有子检查都通过。
