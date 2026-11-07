# 1B-3｜认证与会话开发学习手册

日期：2026-11-07，北京时间；轮次R09。**本批已通过HTTP验收**，实现登录、首次改密、退出、角色检查和会话撤销。登录/改密网页属于1B-5，检索属于1B-4，本轮都没有开发。配套[技术记录R09](过程记录/03_1b技术操作详解.md#r09)、[口述R09](过程记录/04_1b逐步口述稿.md#r09)、[验收汇总](checks/stage1b-3-verification.json)。

## 1. 先理解一次请求

浏览器向Next.js的`/api/auth/login`发送JSON，代理转成FastAPI的`/auth/login`。密码用Argon2id核验，通过后starsessions生成随机128位会话ID，Cookie只携带这个ID。SQLite的auth_sessions只保存ID的SHA256和会话状态，不保存原始Cookie。

再次访问时，后端不只相信Cookie存在，还要检查数据库中的撤销标志、用户active、auth_version、空闲和绝对有效期。用户改密或管理员撤销后，复制的旧Cookie也不能恢复权限。中间件迟到的写入只允许更新仍有效的已有行，不能重新创建撤销的会话。

| 文件 | 学习重点 |
|---|---|
| [main.py](../backend/main.py) | 工厂函数、可注入时钟、中间件、健康接口、释放连接池 |
| [settings.py](../backend/auth/settings.py) | 本机默认值与进程环境配置 |
| [store.py](../backend/auth/store.py) | starsessions的SQLite适配、每次有效性检查、迟到写入保护 |
| [routes.py](../backend/auth/routes.py) | 密码核验、事务、CSRF、首次改密与角色门禁 |
| [boundary.py](../backend/auth/boundary.py) | 可信Origin、JSON、请求大小、错误响应也禁止缓存 |
| [accounts.py](../backend/auth/accounts.py) | 本地撤销/停用/重置操作，不提供账号管理网页 |
| [0002迁移](../migrations/versions/0002_auth.py) | 新增会话和失败计数表，保留0001与六张原表 |

Cookie设置：`HttpOnly; SameSite=Lax; Path=/`，不设Domain。本机HTTP的Secure=false；HTTPS配置必须Secure=true。默认空闲1800秒、绝对28800秒；请求可刷新last_seen，但不能延长绝对期限。会话存SQLite，因此重启后端不会自动让有效会话丢失，重启也不会使撤销会话复活。

## 2. 接口与正确顺序

下面是后端路径；浏览器统一加`/api`前缀。所有认证及admin响应（包括错误）都有`Cache-Control: private, no-store`和`Vary: Cookie`。

| 方法与路径 | 输入与结果 |
|---|---|
| POST /auth/login | JSON含username、password；200返回user_id、username、role、must_change_password、csrf_token，并设置Cookie |
| GET /auth/me | 有效Cookie返回同样五项字段；未登录/撤销/超时401 |
| POST /auth/password | JSON含current_password、new_password；有效Cookie及CSRF；204清Cookie、撤销此用户全部会话，须重新登录 |
| POST /auth/logout | 有效Cookie及CSRF；204清Cookie并撤销当前会话；允许空请求体但仍须JSON Content-Type |
| GET /admin/profiles | 有效且已改密的管理员200；只返回name、config_sha256、status，不包含磁盘路径或配置秘密 |

首次登录得到`must_change_password=true`时，允许查看自身、改密、退出，受保护业务入口拒绝访问；目前用admin/profiles实际验证门禁。改密要求当前密码正确、新密码12—128字符且不同于原密码。改密204后原CSRF与Cookie一并失效，须用新密码登录获取新会话。普通用户即使完成改密，访问admin/profiles仍为403。

每个写请求必须只有一个可信`Origin: http://127.0.0.1:3000`及`Content-Type: application/json`。登录没有已建立会话，使用Origin/JSON边界；改密、退出还须唯一的`X-CSRF-Token`，值来自当前会话的login或me结果。不能借用另一个会话的token。不要混用localhost和127.0.0.1，因为它们属于不同Origin。

理解CSRF：浏览器会自动带Cookie，恶意网页可能诱导请求；因此Cookie之外还核验来源及本会话专属token。HttpOnly负责禁止脚本读取会话Cookie；它不能替代CSRF检查。

| 状态码 | 本批含义 |
|---|---|
| 400 | 当前密码错误，或新旧密码相同 |
| 401 | 登录信息无效，或没有有效会话；错误密码/不存在/停用账号统一提示 |
| 403 | Origin/CSRF拒绝、尚未首次改密、普通用户访问管理员接口 |
| 413 / 415 / 422 | 请求体超过8192字节 / 写请求非JSON / 字段校验失败（不回显密码） |
| 429 | 300秒窗口内账号失败达到5次或客户端达到20次，含Retry-After |
| 503 | 数据库不可用，明确失败；health仍只是应用存活检查 |

失败计数也持久化到SQLite，重启不会清空；客户端计数使用ASGI的request.client，应用代码不直接读取转发IP头。该地址仍可能受Uvicorn代理头配置影响；当前只验收loopback开发环境，不声称已验证生产IP防伪造或限速部署边界，部署前须明确可信代理策略。

## 3. 数据迁移与本轮正式操作

PowerShell在项目根目录执行，使用Web环境而非模型环境：

```powershell
.venv-web/Scripts/python.exe -m scripts.migrate_database
.venv-web/Scripts/python.exe -m scripts.inspect_database
```

第一条改变结构；第二条只读检查元数据。默认库为`runtime/metadata.sqlite3`，覆盖用CLI的`--database runtime/某检查目录/metadata.sqlite3`。只改models.py不能替代迁移；服务启动不会自动迁移或初始化。

**本轮实际执行：**先用SQLite backup API备份到`runtime/verification/r09/metadata-before-0002.sqlite3`，再迁移到0002_auth，重复迁移成功。以六张原表的逐行逻辑指纹核对密码哈希、UUID、归属及页面内容，均未改变；完整性ok，外键0违例。没有复制运行中的单个主库文件来假充完整备份，备份也不提交Git。

正式服务仅做未登录、登录、me、首次改密门禁、退出及旧Cookie重放六项检查，全部通过；测试会话已撤销。**正式admin/A/B的初始密码没有被测试重置**，仍需首次改密。私密凭据文件仍为`runtime/secrets/development-initial-passwords.json`，不要把内容贴到聊天、命令参数、截图或Git。

改密、重置、停用等完整生命周期修改只在隔离数据库和随机测试账号上验证；正式数据未执行这些操作。[正式库证据](checks/stage1b-3-formal.json)。

## 4. 自己跟做：先检查，再读代码和跑测试

所有命令均在根目录，除前端命令显式指定`--cwd frontend`。下面是可复现练习，不代表用户本人已执行。

```powershell
git status --short
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object LocalPort -In 3000,8000,6333 |
  Select-Object LocalAddress,LocalPort,OwningProcess
Invoke-RestMethod http://127.0.0.1:3000/api/health
.venv-web/Scripts/python.exe -m scripts.inspect_database
.venv-web/Scripts/python.exe -m unittest tests.test_auth tests.test_database_initialization -v
```

预期：health为ok，库版本0002_auth；原业务计数为3账号、2文档、2版本、13页、1profile、1index。只读检查脚本刻意不列Cookie、密码哈希或认证表秘密。单元测试在真实的隔离SQLite执行14项认证＋9项数据回归，共23项，包含注入时钟的空闲/绝对过期检查，不必真的等待8小时；无GPU或Qdrant调用。

建议按顺序读：routes.login→store.valid→routes.principal→check_csrf→password/logout，再打开test_auth.py找同名场景。用自己的话解释“创建会话”和“每次检查会话”为什么都需要；看看迟到写入为何只能UPDATE而不能INSERT。

真实进程集成命令：

```powershell
corepack yarn --cwd frontend typecheck
corepack yarn --cwd frontend build
.venv-web/Scripts/python.exe -m scripts.check_auth_http
```

前两条已在本轮通过。第三条要求3000/8000空闲；当前正式服务正在运行，**不要直接重复启动**。脚本遇占用会拒绝，不会替用户结束现有进程。端口释放后，它自建临时数据库、启动生产Next/Uvicorn、实际重启后端、最后停止自建服务；本轮17项通过，结果在[代理报告](checks/stage1b-3-http.json)。它会覆盖对应本轮检查报告，学习时先保留历史证据。不声称本轮有登录网页截图。

## 5. SDK生成与后续UI连接点

```powershell
.venv-web/Scripts/python.exe -m scripts.export_openapi
corepack yarn --cwd frontend gen:sdk
```

本轮已重新生成OpenAPI/AuthService/AdminService，不能手工编辑generated目录。[中央client配置](../frontend/lib/api/client.ts)使用`/api`、同源Cookie，并对写方法添加JSON Content-Type和已设置的CSRF；即使logout没有body，也会携带JSON头，避免415。

**下面仅说明1B-5的连接方式，本批没有编写登录页面：**页面导入中央client后，调用AuthService.login/getMe得到csrf_token，再传给setCsrfToken；token只在内存，不能存localStorage。成功退出、改密、401及换号时应清token与用户结果，页面生命周期处理留1B-5。当前只建立了SDK配置点，不宣称已完成自动清理或页面跳转。

## 6. 本地账号管理与配置

管理员CLI的动作是`disable / enable / revoke / reset`，每次都会增加auth_version并撤销该用户全部会话；enable不会恢复旧会话，reset通过隐藏输入获取新临时密码并设置首次改密。示例仅供理解，请对已迁移、已初始化的隔离练习库执行：

```powershell
.venv-web/Scripts/python.exe -m scripts.manage_account revoke A --database runtime/verification/自己的练习库/metadata.sqlite3
.venv-web/Scripts/python.exe -m scripts.manage_account reset A --database runtime/verification/自己的练习库/metadata.sqlite3
```

这些命令会修改指定库，不是只读检查；本轮正式库未执行。此CLI依赖本地操作系统权限，没有账号管理HTTP接口；完整管理流程及最后管理员保护不在本批验收范围。

auth只读三个**进程环境变量**：LAYOUTPATCH_DATABASE_PATH、APP_ORIGIN、SESSION_COOKIE_SECURE。`.env.example`不是自动加载器；数据库必须在本项目runtime内。SameSite、空闲/绝对时间目前是AuthSettings固定默认值，同名环境项尚不解析。若修改进程环境，应在启动后端的同一PowerShell设置再重启，不要以为改模板会影响已运行进程。

后端启动（仅当8000空闲时）：

```powershell
.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

前端启动（新终端进入frontend目录，仅当3000空闲且已有build时）：

```powershell
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
```

本轮结束保留127.0.0.1:3000与8000服务；进程号见[交接](AI交接.md)，可能随重启变化。在所属终端Ctrl+C即可停止；需要用Stop-Process时，先用`Get-CimInstance Win32_Process -Filter 'ProcessId=实际PID'`核对命令行。Qdrant未参与本轮验证，仍沿用1B-1服务；停止用`docker compose stop qdrant`，保留卷。

## 7. 失败记录与验收限制

首次SDK headers回调让TypeScript将空对象推断为含undefined的可选header，导致类型/构建失败；明确返回`Promise<Record<string,string>>`后均通过。扩展数据库故障测试又发现starsessions2.2.1在store.read完成前先置is_loaded，读取失败后错误响应触发LoadGuard异常；现在用公开handler访问函数复位加载标志并返回通用503，针对固定2.2.1有回归覆盖。升级该依赖时需重验，不能删掉失败事实。初次失败日志`runtime/verification/r09/unittest.log`，最终日志`unittest-final.log`。

本轮验证的是后端HTTP认证与角色检查，不代表文档/图片/检索授权已完成，也不代表总验收T01—T05全通过。过期使用可注入时钟检查存储层判定；真实代理测试验证后端重启，不声称等待实际8小时。starsessions Cookie元数据仍使用库的墙上时钟。没有下载模型、训练、换底座、写旧仓库或提交推送。

下一批为1B-4；本批交付后停止，等待用户继续。
