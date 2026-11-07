# 视觉文档检索与证据定位系统

**2026-11-07 / R09：阶段1A、1B-1至1B-3已验收。** 当前具备独立前后端骨架、SQLite文档归属、登录/改密/退出、角色检查和持久会话撤销。23项认证与数据库测试、17项真实代理检查通过；正式库迁移至0002_auth，原有账号密码与文档归属不变。[本批手册](docs/stage1b-3-runbook.md)、[验收证据](docs/checks/stage1b-3-verification.json)。

网页目前仍为健康检查壳页，登录/改密界面尚未开发；检索HTTP、授权预览、上传及区域高亮尚未实现。profile/index仍pending，向量尚未导入Qdrant。下一批只做1B-4，等待用户继续，不自动推进。

新AI先读[交接文档](docs/AI交接.md)与根[AGENTS.md](AGENTS.md)，核对实际代码、数据与端口后再操作。阶段1B学习资料统一维护在[03技术详解](docs/过程记录/03_1b技术操作详解.md)和[04逐步口述稿](docs/过程记录/04_1b逐步口述稿.md)；早期历史留在[01技术操作](docs/过程记录/01_技术操作详解.md)与[02口述](docs/过程记录/02_逐步口述稿.md)。

## 运行和学习

PowerShell在项目根目录使用独立Web环境；端口已占用时先核对进程，不重复启动：

```powershell
.venv-web/Scripts/python.exe -m scripts.inspect_database
.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

前端另开终端进入frontend目录，已有生产build时执行：

```powershell
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
```

浏览器访问`http://127.0.0.1:3000`；同源`/api`转发至8000。Qdrant独立容器只监听loopback6333，命令见[1B-1手册](docs/stage1b-1-runbook.md)。数据库初始化、密码私密位置见[1B-2手册](docs/stage1b-2-runbook.md)；认证流程、CSRF、测试和安全停止见[1B-3手册](docs/stage1b-3-runbook.md)。不要将初始密码、Cookie或CSRF贴入日志或聊天。

`.env.example`区分当前实际读取的进程变量和后续设计；后端不自动加载该文件。模型使用独立`.venv`，不能用Web安装操作更新模型锁。

## 已验证与后续设计

| 内容 | 状态与证据 |
|---|---|
| 原ColPali离线算法 | 1A通过，两份完整PDF共13页、4题真实编码；与参考Top-3一致，最大分数差约3.8×10⁻⁶；仍有未命中，不能称准确率达标。[详情](docs/stage1a-verification.md) |
| 独立运行骨架 | 1B-1通过，Docker/Qdrant密钥与停止重启已验；R05引擎失败、R06恢复事实均保留。[补验收](docs/checks/r06-stage1b-1-completion.json) |
| 数据库与归属 | 1B-2通过，A-tuGEMM5页、B-Music8页均private，初始化不覆盖已有密码/身份。[证据](docs/checks/stage1b-2-verification.json) |
| 认证与会话 | 1B-3通过，HTTP认证/CSRF/角色/撤销；没有登录网页。[证据](docs/checks/stage1b-3-verification.json) |
| 授权真实检索、页面预览 | 1B-4/5待实施，不能用CLI检索替代Web授权验收 |
| 新PDF入库、区域排序/高亮、完整管理 | 后续阶段设计；不提前宣称可用 |

[需求与权限](docs/requirements.md)、[架构](docs/architecture.md)、[接口](docs/interfaces.md)、[分阶段验收](docs/testing.md)、[进度](docs/progress.md)区分已验证、设计与待核实。系统整体目标为登录→PDF入库→授权真实检索→候选证据定位，目标交付日期2026-12-03。

仅修改本项目；旧layoutpatch、layoutpatch-evidence、Snappy只读。选择性复用Snappy工程机制并保留来源与MIT，不整体搬上游栈；不下载模型、不训练、不换底座、不覆盖旧研究结果、不擅自提交或推送。运行数据和秘密位于Git忽略的runtime目录。
