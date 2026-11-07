# 1B-5 学习手册：网页登录、检索与授权预览

2026-11-07，北京时间；R11 / 1B-5。实现与本批已覆盖验收通过；浏览器改密提交由本人操作，以下明确区分实际验证和人工操作。后端45项测试、前端3项生命周期测试、41项真实HTTP、16项浏览器观察、16项正式恢复检查通过。原始报告见[后端与前端](checks/stage1b-5-tests.json)、[HTTP](checks/stage1b-5-http.json)、[浏览器](checks/stage1b-5-browser.json)、[正式恢复](checks/stage1b-5-formal.json)。本批不推进1B-6，不做区域高亮。

## 1. 现在可以怎么使用

打开 <http://127.0.0.1:3000>。先登录，首次使用会进入“设置新密码”；设置后旧会话全部撤销，回到登录页，使用新密码重新登录。工作空间支持输入问题、选择3/5/10页、查看相关分数，点击命中页面查看完整原图。分数是排序依据，不是可信概率；结果仍要结合原文核对。

现有正式账号admin、A、B；A有tuGEMM5页，B有Music8页，均私有。admin的普通检索也只有本人＋共享范围，当前正式admin没有文档，所以会显示空文档提示。初始随机凭据保存在本机忽略文件`runtime/secrets/development-initial-passwords.json`，由本人在编辑器查看并输入；本文不收录密码。本轮没有更改正式账号密码或发布共享文档。

正式首次改密应由本人完成：输入当前密码、新密码12—128字符、再确认新密码，点击更新，再用新密码登录。浏览器工具规则要求用户本人输入并提交新凭据，本轮自动化只观察了改密页、minLength12、门禁与退出；A/B/admin的完整密码业务流程是在隔离数据库通过HTTP运行，未声称自动点击过浏览器改密按钮。

建议先问A：“Where does the paper compare hardware area and energy for temporal unary matrix multiplication?”，再退出，换B问“What does Frechet Music Distance measure when generated audio is compared with reference music?”。这些是开发验证问题，不能当作正式效果评价集。

## 2. 本批改变了什么

| 文件 | 阅读时关注 |
|---|---|
| [page.tsx](../frontend/app/page.tsx) | checking/login/password/workspace/unavailable五种状态；输入、搜索、预览、换号与错误处理 |
| [globals.css](../frontend/app/globals.css) | 登录双栏、结果列表和原文预览；650/900宽度断点与减少动画支持，无外部字体/图片依赖 |
| [client.ts](../frontend/lib/api/client.ts) | 同源Cookie、JSON写请求与仅在内存保存的CSRF；不写localStorage |
| [workspace-lifecycle.ts](../frontend/lib/workspace-lifecycle.ts) | 请求代号与取消回调；只接受当前代号的返回，预览地址白名单 |
| [access.py](../backend/documents/access.py) | 检索与图片共用“本人＋启用管理员共享”权限表达式，ready且未删除 |
| [previews.py](../backend/documents/previews.py) | 页面ID、渲染哈希与本会话CSRF派生HMAC；不是裸文件地址 |
| [documents/routes.py](../backend/documents/routes.py) | page→version→当前document→owner检查；受限读取、原图哈希与返回前复核 |
| [search/routes.py](../backend/search/routes.py) | 原有真实检索不变；最后复核通过后为每个命中签出preview_url |
| [test_previews.py](../tests/test_previews.py) | 真实SQLite/PNG上的9项对象授权测试，模型/排名替身仅复用隔离夹具 |
| [check_workspace_http.py](../scripts/check_workspace_http.py) | 隔离数据库/唯一集合、真实代理/GPU/图片验收，私密状态留runtime |

前端通过生成SDK调用auth/search；OpenAPI重新生成SearchHit.preview_url及PagesService，不手改生成源码。图片需要二进制Blob、取消及HTTP状态处理，单独用浏览器原生fetch；固定版SDK生成器虽然声明Blob返回类型，通用实现按文本解析非JSON，因此页面不使用该生成方法读取图片。不新增请求库或依赖，不修改模型算法。

## 3. 为什么图片还要授权

```text
search → SQLite授权范围 → 原ColPali新问题编码 → Qdrant范围内Top-k
       → 返回前复查 → 每条命中附本会话preview_url
浏览器选择命中 → GET /api/pages/{page_id}/image?preview=...
       → 会话/首次改密 → 文档归属及当前版本 → 校验preview
       → 受限读取同一份PNG字节与哈希 → 新事务复核 → image/png
```

preview值是HMAC-SHA256，由本会话CSRF作为密钥，对命名空间、page_id和render_sha256计算。它不能反推出CSRF，且不是独立授权凭证：必须同时有签发它的有效Cookie和当前页面权限。页面令牌没有单独TTL，生命周期受会话有效期控制；退出/改密/撤销后401，新会话即使同一用户也不能用旧URL，返回404；共享页面换成另一个仍有权限的账号，也需该账号新签出的地址。

图片接口每次回溯数据库，而非相信搜索结果、请求中的owner、Qdrant payload或文件名。未知页面与越权页面均404；未登录401、未改密403；来源文件缺失/损坏/越界503 PREVIEW_UNAVAILABLE。只读取解析到本项目`runtime/corpus`下的PNG，最多20MiB，核对RGB格式/尺寸/完整哈希；不将绝对磁盘路径返回网页。

返回`private, no-store`、`Vary: Cookie`、`image/png`、`nosniff`、`no-referrer`；不返回ETag/Last-Modified，不走304或Range捷径。客户端请求亦cache:no-store，不经Next Image优化或静态public目录。没有裸/files、PDF或thumbnail路由。本批未实现PDF下载、缩略图和区域高亮。

读取文件期间可能发生撤权，因此读完后开新SQLite会话再次检查用户、会话、文档和页面身份；不能在读文件前授权一次就直接流式发出。授权决定发生在响应前检查点，已经交付给浏览器/用户的字节无法远程收回，界面会在退出、失效、切页或再次访问时清理/重查；未实现共享撤回实时推送。

## 4. 网页怎样避免串号

`RequestGeneration.reset()`先递增代号、取消未完成SDK请求，再清结果、选中页、图片与等待状态。每个异步返回必须满足其代号仍为当前值；取消即使已经来不及，也不能显示上一代结果。图片另用AbortController＋独立序号，避免快速点第1/2页后第1张迟到覆盖第2张。

图片转为Blob URL展示，切页、检索、退出、401、卸载时revokeObjectURL；签发地址不直接挂到img或对外链接。401清身份和内存CSRF；409/图片404清结果并提示重新检索；503明确提示服务故障，不返回空文档或旧结果。退出请求失败时隐藏内容并显示“尚未确认”，不会声称已经退出。

BroadcastChannel只广播“session-changed”，不广播账号密码或token。另一个标签页退出后本页重新确认身份。页面隐藏/pagehide先清理私有内容，恢复显示/BFCache回来重新调用me；可见会话每30秒核验一次，外部撤销也会在后续请求或轮询时被识别。没有在localStorage/sessionStorage持久保存问题、结果、CSRF、Cookie或预览。

## 5. 本人跟做：先只读，再隔离测试

在项目根目录PowerShell执行；不会更改正式密码：

```powershell
.venv-web/Scripts/python.exe -m scripts.inspect_database
curl.exe --silent http://127.0.0.1:3000/api/health
.venv-web/Scripts/python.exe -m unittest tests.test_previews tests.test_search tests.test_auth tests.test_database_initialization -v
corepack yarn --cwd frontend typecheck
Push-Location frontend
node --test tests/workspace-lifecycle.test.cjs
Pop-Location
```

第一条看3账号、13页、ready/validated和13403个token向量。health只说明连接存活，不说明模型已启动。后端测试使用runtime中的临时数据库，9个新预览＋13个检索/身份＋14个认证＋9个数据库测试；模型/Qdrant替身仅用于授权/故障契约。前端3个测试证明迟到返回拒绝、代号失效和地址白名单，不等于浏览器端到端测试。

修改API后才重新导出/生成；修改网页后重新构建并重启生产Next。已有服务正在运行时不要一边构建一边把产物当旧服务验收：

```powershell
.venv-web/Scripts/python.exe -m scripts.export_openapi
corepack yarn --cwd frontend gen:sdk
corepack yarn --cwd frontend typecheck
corepack yarn --cwd frontend build
```

API定义是源，SDK是生成产物。不要直接改SearchHit.ts或PagesService.ts。构建中baseline-browser-mapping提示数据较旧，本轮没有为了消除提示升级依赖，最终构建通过。

## 6. 真实验收如何复现

本节会启动模型、改隔离账号密码并写唯一测试集合；适合看懂第5节以后练习。先按下一节核对进程、停止当前正式前后端，保持Qdrant；不要直接在3000/8000占用时启动另一套服务。

```powershell
.venv-web/Scripts/python.exe -m scripts.check_workspace_http prepare
$workspaceCheck = Get-Content -Raw -Encoding UTF8 runtime/verification/r11/workspace-state.json | ConvertFrom-Json
$env:LAYOUTPATCH_DATABASE_PATH = $workspaceCheck.database
$env:LAYOUTPATCH_QUERY_AUDIT_DIR = Join-Path $workspaceCheck.folder 'queries'
.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

该终端保持后端运行；另开终端在frontend目录启动`node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000`；第三个终端根目录执行`.venv-web/Scripts/python.exe -m scripts.check_workspace_http check`。脚本先核验初始门禁，再为隔离B/admin经HTTP改密和重新登录，真实B问题编码、8页逐图哈希比对；退出旧Cookie401，同用户新会话旧URL404，另建共享媒体夹具验证撤回。A仍保持初始状态，用于浏览器观察改密页。

`prepare`只允许无现有state时创建。已有state则先检查其collection、服务和cleanup状态，保留证据，不直接覆盖；再次练习需把已清理完成的workspace-state.json另存到同一个runtime/verification/r11目录后再prepare。该脚本没有自动启动/停止服务；不读取正式初始密码。`change-a`是本轮隔离HTTP改密辅助动作，不代表用户在浏览器提交过密码。

停止属于本次测试的前后端后执行`.venv-web/Scripts/python.exe -m scripts.check_workspace_http cleanup`，只删除state中含_r11test_的集合，不删除正式集合/文件。本轮测试集合已清理，真实运行目录在`runtime/verification/r11/workspace-state.json`中；凭据、查询向量、日志留忽略目录，公共报告不含这些值。

实际网页观察包括：初始改密页、A三条tuGEMM/原图、切第2页、退出清理、B三条Music、撤销B后点预览401、空admin、停止本测试模型后503、390窄屏和另一个标签页退出同步。5张截图见[登录](checks/stage1b-5-login.png)、[改密门禁](checks/stage1b-5-password-gate.png)、[真实结果](checks/stage1b-5-results.png)、[故障](checks/stage1b-5-outage.png)、[窄屏](checks/stage1b-5-mobile.png)。

## 7. 正式服务如何启动和停止

正式后端必须是未设置隔离数据库变量的新终端；如复用测试终端，先明确清除测试变量：

```powershell
Remove-Item Env:LAYOUTPATCH_DATABASE_PATH -ErrorAction SilentlyContinue
Remove-Item Env:LAYOUTPATCH_QUERY_AUDIT_DIR -ErrorAction SilentlyContinue
.venv-web/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

前端另一个终端进入frontend后执行`node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000`。浏览器只访问3000，Qdrant key不交给浏览器。模型按需启动，health/初始改密门禁不会加载GPU。

停止优先所属终端Ctrl+C；PID不能照抄历史值。先`netstat -ano -p tcp`查监听，再用`Get-CimInstance Win32_Process -Filter "ProcessId=实际PID"`核对CommandLine；只终止本项目且属于当前操作的进程。本轮Stop-Process报空引用，确认未停止后才改用taskkill。不要删除Qdrant卷，Qdrant非空容器重启持久性留1B-6。

本轮正式收尾：前端127.0.0.1:3000 PID36376，后端8000 PID32432，Qdrant6333仍原PID49880；它们是本轮观测，不是永久ID。正式SQLite仍0003，七张原业务表与R11备份逐行一致，完整性ok、外键0违例、未撤销测试会话0；正式集合仍13点。

## 8. 实际失败与如何理解

| 失败 | 定位与处理 |
|---|---|
| PowerShell中文stdin写辅助脚本UnicodeEncodeError | 不是Python业务故障；改apply_patch直接写UTF-8，避免默认GBK解释中文 |
| 同文件delete/add补丁被拒 | 整体未写入；分成删除和新增两个补丁完成 |
| 预览测试CookieConflict | 测试手工重放Cookie与自动Cookie域重复，循环前清jar；测试类导入也改模块引用，去掉重复计数，最终45项独立测试通过 |
| make_engine收到str而非Path | 辅助脚本先构造Path；修正后真实41项通过 |
| Stop-Process空引用 | netstat确认仍监听，CIM核对原项目命令后taskkill成功；不把尝试当已停止 |
| 浏览器首次打开连接拒绝 | 发生在服务启动前；旧错误页绑定又触发data URL策略，服务就绪后新开标签成功，不绕过浏览器安全提示 |
| alert定位到两个元素 | 页面提示与Next路由播报器均role=alert；改精确可见文案，原故障请求没有重复提交 |

1B-4的float32回读与冷启动代理超时仍保留在原手册；本批没有改评分阈值、模型或锁文件。旧库/模型/03/04/.gitignore保护快照对照和收尾文档检查见[汇总](checks/stage1b-5-verification.json)。

## 9. 本批出口

网页登录、改密表单、授权真实检索与图片预览已实现；授权/故障/换号清理已有上述证据。浏览器手动输入并提交正式新密码仍由本人完成；不得把HTTP改密说成浏览器按钮已由自动化点通。

尚未实施：1B-6非空Qdrant重启/整体验收，PDF/上传/解析/区域高亮，完整共享发布管理和审计，持续并发容量与正式准确率评价。5张截图不代表T01—T15整表通过。完成本批后停止，等待用户明确继续。
