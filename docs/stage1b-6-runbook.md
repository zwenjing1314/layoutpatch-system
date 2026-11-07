# 1B-6 学习与本机部署手册

2026-11-07，北京时间；R12。范围为阶段1B的启停、故障恢复、非空索引持久化和适用验收收尾。没有新迁移、上传、解析或区域高亮。最终结果以[汇总](checks/stage1b-6-verification.json)为准；历史R10/R11证据不会冒充本轮运行。

## 1. 先理解三个服务和两份数据

```text
浏览器 → Next 127.0.0.1:3000 → /api代理 → Uvicorn 127.0.0.1:8000
                                              ├─ SQLite runtime/metadata.sqlite3
                                              ├─ 原ColPali本地子进程（无TCP端口）
                                              └─ Qdrant 127.0.0.1:6333
                                                  Docker命名卷 qdrant_data
```

SQLite保存账号、会话、归属、页面、配置和索引身份；Qdrant保存完整页面的多向量。SQLite的ready记录不能证明Qdrant仍有数据，Qdrant有点也不能代替SQLite授权。图片在runtime/corpus，已有页特征在runtime/indexes及verification；不需要为重启重新编码页面。

`/health`只表示Web存活，刻意不泄露依赖细节。本轮实际停止Qdrant时health仍200，搜索503；PNG从磁盘和SQLite读取，仍可200。这三者不矛盾。模型按需启动，首次真实问题包含离线文件校验与加载耗时。

## 2. 启动前只读检查

以下命令在本项目根目录PowerShell执行，复用已有环境，不安装依赖、不下载模型：

```powershell
git status --short
docker version --format '{{.Server.Version}}'
docker compose config --quiet
docker compose ps
Get-NetTCPConnection -State Listen -LocalPort 3000,8000,6333 -ErrorAction SilentlyContinue
.venv-web/Scripts/python.exe -m scripts.inspect_database
```

不要执行会展开密钥的`docker compose config`或输出完整`docker inspect`；本脚本内部读取后只留下容器ID/镜像ID/卷名/启动时间。端口被占用时先查所属进程，不能直接再启一套。当前数据应为0003、3账号、2private文档、13页、profile validated/index ready、13403 token向量；以后以当时真实库为准。

## 3. 正式启动顺序

1. 已有独立Qdrant容器，先`docker compose start qdrant`，用`docker compose ps`确认running。
2. 在干净终端启动正式后端。
3. 另开终端启动已有生产build的Next。
4. 访问3000，完成本人登录/首次改密，重新登录后提问并打开原图。

根目录后端命令：

```powershell
Remove-Item Env:LAYOUTPATCH_DATABASE_PATH -ErrorAction SilentlyContinue
Remove-Item Env:LAYOUTPATCH_QUERY_AUDIT_DIR -ErrorAction SilentlyContinue
$env:APP_ORIGIN = 'http://127.0.0.1:3000'
$env:SESSION_COOKIE_SECURE = 'false'
$env:QDRANT_URL = 'http://127.0.0.1:6333'
.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

前端终端：

```powershell
Set-Location frontend
$env:NEXT_TELEMETRY_DISABLED = '1'
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
```

第三个根目录终端：

```powershell
curl.exe --silent http://127.0.0.1:3000/api/health
```

如果Qdrant容器尚未创建，仅在本地已存在固定镜像/正确.env时用`docker compose up -d --pull never qdrant`；缺镜像就停下检查，不隐式拉取。固定身份见[compose.yaml](../compose.yaml)。不要反复执行初始化、索引激活或导入来“修复”重启；ready集合缺失时应核查数据卷和身份，不能静默建空集合。

如实际修改前端/API，先停止生产Next，再按[1B-5手册](stage1b-5-runbook.md#5-本人跟做先只读再隔离测试)生成SDK、typecheck和build，最后重启。本轮应用代码/接口未改，复用既有构建；后端只修正只读检查脚本的一句过时说明，新增验收脚本。

正式初始凭据位于忽略文件`runtime/secrets/development-initial-passwords.json`，由本人在本机查看；若已改密，不再使用初始值。浏览器新密码的输入、确认和提交由本人操作。密码、Cookie、CSRF、密钥不进入截图或公开记录。

## 4. 正确停止与恢复

先在各自终端Ctrl+C停止Next和Uvicorn，确认模型子进程退出，再`docker compose stop qdrant`。此命令保留卷；恢复用`docker compose start qdrant`后重启后端、前端。容器为restart:no，不会自动随Windows重启，需要手动按顺序启动。

若所属终端不可用，先查真实PID与命令：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 3000,8000 -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter 'ProcessId=实际PID' | Select-Object ProcessId,ParentProcessId,CommandLine
```

将`实际PID`换成刚查出的数字；确认是本次项目的进程后才使用`taskkill /PID 实际PID /T /F`。`/T`包含模型子进程。不要照抄交接中的旧PID，不终止Docker Desktop后端，不使用删除卷命令。验收脚本另外比对创建时间，避免PID复用。

## 5. 为什么这样验证持久化

- 用SQLite backup API生成一致备份，而不是复制一个仍在WAL写入的sqlite文件；本轮基线在`runtime/verification/r12/metadata-before.sqlite3`。
- 复制该备份为隔离库，只在隔离库设置随机临时密码并清测试会话；页面ID、索引和归属仍对应同一个正式集合。所有向量操作只有读取与查询，没有导入、upsert、清集合或删卷。
- 读取全部13点，逐行将JSON数值重构为little-endian float32后哈希，再连同点ID/payload规范化哈希；另比较完整collection config。不能直接用Python float64列表和原float32做字面相等。
- 对真实非空容器执行stop/start；确认容器/镜像/卷身份相同、StartedAt变化，随后再次读取全部点比较，而不只检查13这个数量。
- 同一问题在重启前后都重新做原ColPali forward并查询；模型停止时先503，下一次请求实际重载恢复，不回放上次成功结果。

本轮的[生命周期报告](checks/stage1b-6-lifecycle.json)和[正式恢复](checks/stage1b-6-formal.json)分别证明功能恢复和正式数据保护；指纹摘要写入最终汇总。私密原始状态、query向量、进程日志只留runtime。

## 6. 本轮验收脚本如何阅读和复现

阅读[scripts/check_stage1b_acceptance.py](../scripts/check_stage1b_acceptance.py)，依次看`prepare → run → stop → verify_formal`。它要求本轮保护/SQLite基线先存在；不是通用一键安装器。当前R12 state已经存在，**不要直接再prepare/run覆盖证据或重复改密**。需要再次练习时使用新的轮次/目录及报告名，先保留原证据，重新核对正式基线，再运行。

本轮实际流程为：先prepare隔离库，核对并停止正式前后端，让3000/8000空闲，再run；run会管理测试进程、重启Qdrant并保留隔离服务供浏览器观察。浏览器完成后stop只停止记录中的测试进程树，然后按第3节恢复正式服务，最后verify-formal。核心命令如下，仅用于理解已经执行的R12：

```powershell
.venv-web/Scripts/python.exe -m scripts.check_stage1b_acceptance prepare
.venv-web/Scripts/python.exe -m scripts.check_stage1b_acceptance run
# 浏览器QA结束后：
.venv-web/Scripts/python.exe -m scripts.check_stage1b_acceptance stop
# 按第3节在独立终端恢复正式服务后：
.venv-web/Scripts/python.exe -m scripts.check_stage1b_acceptance verify-formal
```

评分核验使用本次真实HTTP forward得到的query和返回分数，调用原环境中的官方processor与CPU float32 MaxSim；预设容差仍atol1e-4/rtol1e-5，没有放宽。给旧参考脚本增加output/round参数，以免覆盖R10报告：

```powershell
.venv/Scripts/python.exe -B scripts/check_search_reference.py --input runtime/verification/r12/reference-cases.json --output docs/checks/stage1b-6-reference.json --round R12
```

回归命令：

```powershell
.venv-web/Scripts/python.exe -m unittest tests.test_previews tests.test_search tests.test_auth tests.test_database_initialization -v
Push-Location frontend
node --test tests/workspace-lifecycle.test.cjs
Pop-Location
```

## 7. 故障应怎样判断

| 实际触发 | 应看到什么 | 恢复及边界 |
|---|---|---|
| 停后端，Next仍在 | 代理5xx；页面明确服务异常，不能伪报搜索成功 | 启后端；未过期且未撤销会话仍可用 |
| 停Next，后端仍在 | 3000端口关闭 | 启Next；Cookie仍由浏览器保留，后端重新检查 |
| 停Qdrant | 真实搜索503 SEARCH_UNAVAILABLE；health仍200 | start同一容器/卷，指纹比对后真实搜索恢复 |
| 终止本测试模型树 | 下一次搜索503，无旧items | 再次请求重新启动原本地模型，真实forward成功 |
| CLI撤销后重启后端 | 旧Cookie仍401 | 重新登录；同用户新会话也不能用旧preview |

原始失败也保留：首版脚本引用未安装psutil，在运行前探测发现后改CIM、未安装包。首轮正式验收在模型进程计数处失败，因为Windows venv启动器与实际Python是同一棵树的两层；保存[首轮失败](checks/r12-lifecycle-first-failure.json)及私密attempt1状态后，修正为一棵树再重跑。不是启动了第二个模型，不改算法/评分阈值。失败前的部分通过不冒充整轮通过。

浏览器最终13项观察为10项DOM自动检查＋3项AX/截图观察。AX把结果toggle按钮显示成checkbox，DOM实际是button，原角色计数失败保留在[原报告](checks/r12-browser-first-check.json)；最终根据已经返回的AX与[真实恢复截图](checks/stage1b-6-recovered.png)确认3条结果和原图，不声称错误自动计数已通过。文案定位漏“时”纠正后读取实际错误，没有重复提交原请求。

## 8. 本机运行与外部部署的界线

已验收的是本机Windows、既有离线环境、loopback HTTP、固定镜像和卷。依赖可看requirements锁与frontend/yarn.lock，但没有重装到另一台机器，也没有验证镜像/模型的公开再分发许可。

外部部署仍为建议：入口用HTTPS并设SESSION_COOKIE_SECURE=true，APP_ORIGIN精确对应入口源；8000/6333继续只允许内部访问；单后端worker避免重复GPU实例；建立进程监管、SQLite在线备份、Qdrant快照与原图/模型身份的协同恢复演练。错误代理日志可能包含GET问题，应另审日志脱敏，不能把关闭Uvicorn access log当成完整日志治理。

本轮证明现有13页登录后检索/原图、授权与重启恢复链路；不等于全新PDF入库、区域模型、完整管理、长时负载或准确率评价已通过。T01—T03/T05/T06/T11按适用子集列证据，未实现路由明确标“未挂载”，不能把404写成已有功能401。完成1B-6后停止，阶段2等用户继续。
