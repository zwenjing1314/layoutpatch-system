# R05＋R06 / 1B-1：独立运行骨架

开发跟学见[03技术专册](过程记录/03_1b技术操作详解.md)，汇报练习见[04口述专册](过程记录/04_1b逐步口述稿.md)。

日期：2026-11-06（北京时间）。**1B-1已验收通过：R05前后端检查＋R06 Qdrant与浏览器补验。** 本批没有登录、SQLite业务表、检索或区域高亮。

## 实际结构与关键原理

- `backend/main.py`：FastAPI仅提供`GET /health`，返回`{"status":"ok"}`和`Cache-Control: no-store`。不导入算法或加载模型；存活不等于依赖就绪。
- `frontend/app`：Next.js/React/TypeScript壳页，有真实连接检查按钮。
- `frontend/next.config.ts`：`127.0.0.1:3000/api/*`转发到`127.0.0.1:8000/*`。浏览器只请求同源`/api`；本轮仅证明JSON及no-store转发，Cookie/Set-Cookie、CSRF、二进制与Range留对应业务批次验证。
- OpenAPI是接口定义；`scripts/export_openapi.py`导出，`yarn gen:sdk`生成TypeScript客户端。壳页通过`SystemService.getHealth()`调用，不手改生成代码。
- `.venv-web`独立安装FastAPI/Uvicorn；原`.venv`继续专用于已通过1A的模型代码。未来连接模型时再明确进程边界，本轮未证明Web与GPU集成。
- `compose.yaml`仅运行Qdrant v1.16.2：端口仅loopback，项目名`layoutpatch-system`、独立卷`layoutpatch-system-qdrant-data`、随机服务端API key、关闭遥测。未运行任何旧研究栈。
- 本轮选择性沿用Snappy框架版本、Yarn Classic锁与SDK生成机制；锁文件按最小依赖重新裁剪。来源和差异见`checks/r05-provenance.json`，MIT保留在`third_party/Snappy/LICENSE`。

## 安装与生成（项目根目录PowerShell）

已完成以下Web依赖安装，后续只在需要恢复环境时执行；不要重建模型`.venv`。

```powershell
uv venv .venv-web --python .venv/Scripts/python.exe
uv pip sync --python .venv-web/Scripts/python.exe requirements-web.lock.txt
corepack yarn --cwd frontend install --frozen-lockfile --non-interactive
.venv-web/Scripts/python.exe -m scripts.export_openapi
corepack yarn --cwd frontend gen:sdk
corepack yarn --cwd frontend typecheck
corepack yarn --cwd frontend build
```

本轮Web包精确版本见`requirements-web.lock.txt`、`frontend/yarn.lock`；Yarn为1.22.22。增加/改依赖才重新生成锁文件。

## 启动、停止与重启

先确认3000/8000/6333无人占用；冲突时不终止用户进程，应协调新端口并同步代理配置。

终端A（项目根目录）：

```powershell
.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

终端B（项目根目录，已build）：

```powershell
corepack yarn --cwd frontend start
```

开发时可替换为`corepack yarn --cwd frontend dev`。不要同时运行dev/start；本轮验收的是生产start。浏览器打开`http://127.0.0.1:3000`，按钮应显示“服务连接正常”；**R06已实际点击浏览器按钮，显示“服务连接正常”**；[截图](checks/r06-browser-health.png)已保存，当前窄视口下文字和按钮可见。

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:3000/api/health
```

停止：在A/B各按Ctrl+C；重启：重复同一启动命令。自动验收工具会自行启动、停止其创建的进程，连续跑两轮，结束释放端口：

```powershell
.venv-web/Scripts/python.exe -m scripts.check_web_skeleton
```

## Qdrant：R06真实验收通过

`.env`已用`./scripts/init-local.ps1`生成随机key，Git忽略。脚本拒绝覆盖已有文件；不要打印或提交key。`.env.example`仅Qdrant密钥项已消费，其余仍是后续设计。

R06实查Docker29.8.0正常后，已执行以下真实启动/停止/重启及密钥检查：

```powershell
docker info
docker compose config --quiet
docker compose up -d qdrant
.venv-web/Scripts/python.exe -m scripts.check_qdrant
docker compose stop qdrant
docker compose up -d qdrant
.venv-web/Scripts/python.exe -m scripts.check_qdrant
docker image inspect qdrant/qdrant:v1.16.2 --format '{{json .RepoDigests}}'
```

保留卷，不使用`down -v`或全局prune。镜像已固定版本及摘要：`qdrant/qdrant:v1.16.2@sha256:dab6de32f7b2cc599985a7c764db3e8b062f70508fb85ca074aa856f829bf335`。检查工具验证ready、正确key访问集合、匿名及错误key被拒；不创建集合或写页面向量。

**R05历史失败（R06已不再阻塞）：**`docker info`与`docker compose up -d qdrant`均报`dockerDesktopLinuxEngine`管道不存在。`docker desktop start/status/restart`未返回就绪。Docker宿主日志2026-11-06 02:10:29（UTC日志18:10:29）报告初始化Ingest server时`sailor-ingest.sock`重命名失败，`The file cannot be accessed by the system`；这是当时日志给出的启动错误，底层原因及恢复原因尚未确认。R06无需修复引擎即已正常响应，不能沿用旧失败判断当前不可用。未删除Docker全局socket、重置Docker、停止WSL或操作旧库卷。

## 验收证据与边界

- `checks/stage1b-1-web.json`：两轮各6项真实检查全通过；直接/代理200、HTML、no-store、仅health路由、后端停机代理500、停止释放端口。
- `corepack yarn typecheck`和生产build退出0；构建有浏览器兼容数据过期提示，未因此升级无关依赖。
- Qdrant就绪/密钥/停止/重启与镜像身份见`checks/r06-stage1b-1-completion.json`；匿名及错误key为401。停止退出码143对应SIGTERM，实际容器exited、端口关闭、无OOM/error；最初额外断言退出码必须0失败，已按实际状态复核并记录。未创建业务集合/向量，未证明非空数据持久性。
- 当前总状态为`checks/stage1b-1-status.json`；R05原失败JSON完整保存在`checks/r05-stage1b-1-status.json`。
- 旧源库与模型环境边界快照见`checks/source-state-r05-before.json`和`after.json`；开始快照在骨架文件新增/Web安装后取得、任何源库操作前，不能据此宣称全过程全盘哈希。忽略目录未穷举。
- R06源库与模型环境快照为`checks/source-state-r06-before.json`和`after.json`，前后相同。未提交、推送、下载模型或训练，未修改/清理Docker全局资源。

## 当前服务与下一批

R06收尾保留前后端与Qdrant供本机查看：前端PID50056（3000）、后端PID51084（8000），均绑定loopback。浏览器页面为`http://127.0.0.1:3000`。

在对应启动终端按Ctrl+C停止原生服务；如使用下面本轮PID，先确认仍为本项目进程，防止PID被重用。6333是Docker转发进程，使用Compose停止容器，不终止转发进程：

```powershell
Get-CimInstance Win32_Process | Where-Object ProcessId -in 50056,51084 | Select-Object ProcessId,CommandLine
# 确认命令行为本项目Next.js和Uvicorn后：
Stop-Process -Id 50056,51084
docker compose stop qdrant
```

重新启动使用上文A/B命令与`docker compose up -d qdrant`。下一批是**1B-2 数据身份与初始化**，等待用户说继续，本轮不开发。
