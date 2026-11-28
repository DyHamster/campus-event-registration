# 校园活动票务与报名系统

程序提供 Python 命令行和本地网页界面，两个入口共享 SQLite 数据。举办方创建活动并提交审核，也可以查看本人场次的统计和导出名单。平台管理员审核并发布活动，分配检票授权并查询操作日志。参与者报名成功后可领取电子票，由获授权的检票员核验并签到。

需要 Python 3.10 或更高版本。以下命令适用于 macOS、Linux 的终端，在本文件所在的 `Lab_3/code` 目录执行。Make 用于简化安装、启动、构建和测试，未安装 Make 时可使用下方等价命令。

## 启动图形界面

首次运行先安装依赖，再启动界面。

```sh
make setup
make demo
```

浏览器打开 [集会活动广场](http://127.0.0.1:8000/)。以后在本目录执行 `make demo` 即可，Make 会自动使用 `.venv` 内的 Python。保持终端运行，在终端按 `Ctrl+C` 停止服务。依赖更新后重新执行 `make setup`。

界面使用独立演示库 `data/web-demo.sqlite3`，首次运行预置公开活动、一个待审核活动和检票授权。登录页可以选择四类演示账号，密码均为 `campus-demo`。重复启动会继续使用已有业务记录；活动只在数据库尚无活动时预置，示例日期按首次初始化时间生成。

端口被占用时执行 `make demo PORT=8001`，并打开 [备用端口地址](http://127.0.0.1:8001/)。服务监听本机地址 `127.0.0.1`。

未安装 Make 时，等价命令如下。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B -m campus_events.web --database data/web-demo.sqlite3 --demo
```

要打开命令行已有的默认数据库，执行 `.venv/bin/python -B -m campus_events.web`。也可以用 `--database 路径` 选择其他数据库、用 `--port 8001` 更换端口。界面和命令行操作同一数据库文件时可以互相看到变更。

参与者可以搜索活动、选场次、报名或候补，并在「我的活动」查看二维码电子票。举办方可编辑草稿、提交审核、取消活动和导出名单。管理员可审核、授权和查询日志。检票员可粘贴票码或上传二维码图片检票。

以下演示账号的密码均为 `campus-demo`。

| 账号 | 角色 | 可访问的功能 |
| --- | --- | --- |
| `student`、`student2`、`student3` | 校内参与者 | 公开活动、报名与候补、本人电子票 |
| `visitor` | 校外参与者 | 公开活动、不限资格的报名与候补、本人电子票 |
| `organizer` | 活动举办方 | 公开活动、活动管理、本人场次名单和统计 |
| `admin` | 平台管理员 | 公开活动、活动审核、检票授权、操作日志 |
| `checker` | 现场检票人员 | 公开活动、授权场次的检票签到 |

## 命令行入口

业务命令和按票码检票使用 Python 标准库。执行下列命令创建演示账号并登录，在终端密码提示后输入 `campus-demo`。

```sh
python3 -B -m campus_events init --demo
python3 -B -m campus_events login organizer
```

默认数据库位于 `data/campus_events.sqlite3`。运行 `init` 会创建或升级数据库表，保留已有账号、密码和活动。在旧演示库上执行 `init --demo` 会补齐新增参与者，并为仍使用原演示凭据的校内账号补上演示资格。可用 `python3 -B -m campus_events --help` 查看命令入口。

给 `login` 传入功能名可直接验证访问权限。举办方可以进入活动管理，普通参与者会收到拒绝提示，命令以状态码 `1` 退出。

```sh
python3 -B -m campus_events login organizer manage-events
python3 -B -m campus_events login student manage-events
```

## 演示活动从创建到取消

下面的命令使用独立数据库 `data/stage2-demo.sqlite3`。每次登录时输入演示密码。将示例中的 `1` 换成创建命令输出的活动编号。

```sh
campus() { python3 -B -m campus_events --database data/stage2-demo.sqlite3 "$@"; }

campus init --demo
campus login organizer manage-events create examples/campus-lecture.json
campus login organizer manage-events show 1
campus login student browse-events list
campus login organizer manage-events submit 1
campus login admin review-events show 1
campus login admin review-events approve 1
campus login student browse-events list --search 摄影 --kind 讲座
campus login student browse-events show 1
campus login organizer manage-events cancel 1
campus login student browse-events list
```

活动在审核通过后出现在公开列表。取消后，公开列表和详情都无法再访问它，举办方仍可查看自己的取消记录。公开查询支持按名称搜索和按活动分类筛选。

管理员也可以用 `campus login admin review-events reject 1 --reason "请补充场地信息"` 驳回待审活动。举办方用 `show` 查看原因，通过 `edit 1 配置文件路径` 用完整配置替换草稿或驳回活动的内容，再次送审。待审核和已发布活动的内容锁定，举办方仍可以取消自己的活动。运行 `campus login organizer manage-events --help` 可以查看所有子命令。

## 活动配置

以 `examples/campus-lecture.json` 为模板。创建草稿时至少提供活动名称 `name` 和分类 `kind`。活动介绍和报名条件可省略。送审时活动至少有一个场次，每个场次至少有一个报名类别。

场次需要名称、地点、正整数容量、开始时间和报名截止时间。时间填写带时区的 ISO 8601 格式，截止时间须早于开始时间。报名类别的 `price_cents` 以分为单位，免费填写 `0`。例如示例中的 `1250` 在详情中显示为 ¥12.50。

## 演示最后一个名额和候补递补

示例活动的两个场次各有一个名额。下面使用一份新数据库。若你复用已有数据库，请以公开详情显示的场次编号和报名类别编号替换示例参数，并以取消对象对应的报名记录编号为准。

```sh
campus() { python3 -B -m campus_events --database data/stage3-demo.sqlite3 "$@"; }

campus init --demo
campus login organizer manage-events create examples/last-seat.json
campus login organizer manage-events submit 1
campus login admin review-events approve 1
campus login student browse-events show 1

campus login student registrations apply 1 1 --name 甲 --contact a@example.com
campus login student2 registrations apply 1 1 --name 乙 --contact b@example.com --waitlist
campus login student3 registrations apply 1 1 --name 丙 --contact c@example.com --waitlist
campus login student registrations cancel 1
campus login student2 registrations list
campus login student3 registrations list
```

甲取消后，乙的原候补记录转为报名成功，丙变为候补第 1 位。第二场的名额保持独立。满额时由参与者通过 `--waitlist` 表示愿意候补。

报名条件支持空值或「不限」，也支持根据数据库身份核验「校内师生」。旧活动的其他条件仍显示在详情中，系统会拒绝自动核验不了的报名。

同一用户在同一场次重复提交时，系统返回有效的原记录。报名事务取得 SQLite 写入权时视为系统收到申请，使用当时的时间判断是否截止，并用数据库分配的报名编号记录先后。截止时刻起停止接收新报名或候补。参与者可以在场次开始前取消，截止前已入队的合格候补仍可递补。举办方取消整个活动时，已有报名和候补一并取消。

## 电子票和检票

报名成功或候补转正时会自动出票，每条报名最多对应一张票。旧版数据库升级时，`init` 会为已发布活动中仍有效的报名补发电子票，保留已有报名编号。

导出或识别二维码图片前，先在虚拟环境中安装依赖。使用该虚拟环境运行 `make test` 也会执行二维码图片的集成测试。

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

用新的演示库按上一节创建活动、发布并完成甲乙丙的报名，先停在甲取消之前。使用同一个 `campus` 函数继续。这里活动、场次和报名编号取自新库示例，复用已有库时请以程序显示的编号为准。

```sh
campus login student registrations ticket 1 --qr data/original.png
campus login student registrations cancel 1
campus login student2 registrations ticket 2 --qr data/promoted.png
campus login admin checker-access grant 1 checker
campus login checker check-in list

# 原票被作废，新票可以签到，重复核验返回首次签到时间。
campus login checker check-in verify 1 --qr data/original.png
campus login checker check-in verify 1 --qr data/promoted.png
campus login checker check-in verify 1 --qr data/promoted.png
campus login student2 registrations list
```

`ticket` 省略 `--qr` 时，终端显示电子票信息和票码。核验命令 `check-in verify 1` 可以接收扫码枪输入或手动粘贴的票码，也可以通过 `--qr 路径` 读取 PNG 或 JPEG 图片。每张票只记录首次签到，参与者可以在自己的报名列表中查看签到状态。

每个场次分别授权。管理员可以用 `checker-access list` 查看分配，用 `checker-access revoke 1 checker` 撤销授权。已发布活动的有效票可在授权场次核验。已签到的报名不能自行取消。举办方取消活动会作废所有电子票并保留历史签到。

有效报名的签到时间为空时，表示该报名尚无签到记录。系统保留其报名状态，名单导出同时提供报名状态和签到时间供举办方核对。缺席认定、累计次数和限制期限仍是待确认规则，当前功能不执行缺席处罚。

## 名单、容量统计和操作日志

在上面的示例中，乙完成签到后，第一个场次有 1 个有效报名、1 个候补、1 条取消记录和 1 条签到记录。第二个场次仍有一个名额。继续使用同一演示库执行：

```sh
campus login organizer rosters list
campus login organizer rosters stats 1
campus login organizer rosters show 1 --search 乙 --status checked-in
campus login organizer rosters export 1 data/roster.csv
campus login organizer rosters export 1 data/signed-in.csv --status checked-in

campus login admin audit --limit 10
campus login admin audit --action roster.export
campus login admin audit --action ticket.check-in --outcome duplicate
```

举办方只能访问自己活动的场次名单。导出采用带 BOM 的 UTF-8 CSV，默认包含各状态的报名，可按状态和姓名筛选。导出会保留已存在的同名文件。容量统计中的有效报名包含已签到人员，历史签到仍会显示在已取消活动的统计里。

管理员可以按操作和结果查询日志。日志记录活动创建、修改、送审、审核与取消，以及检票授权、核验和名单导出的时间、操作者、目标编号和结果。核验失败和重复签到单独标记，日志省去票码、联系方式和导出文件路径。升级后从新操作开始记录。

## 构建和打包

```sh
make setup
make build
make test
```

`make build` 使用当前 Python 将软件编译为字节码，产物位于 `build/pycache/`。`make test` 执行全部自动化测试，包括网页和二维码集成测试。先完成 `make setup` 可安装这些测试所需的 Flask、Pillow 和 zxing-cpp；缺少可选依赖时，对应测试会显示 `skipped`，验收时应确认无跳过项。可用 `make test PYTHON=/指定路径/python` 选择解释器。

没有 Make 时，可在依赖安装后执行以下命令。

```sh
.venv/bin/python -m compileall -q campus_events
.venv/bin/python -B -m unittest discover -s tests -v
```

源码规模可以使用下面的递归统计。范围为 `campus_events/` 下全部 Python 源文件，包含网页服务端，排除测试和工具。第二个数字按空行和以 `#` 开头的纯注释行进行过滤，保留文档字符串。

```sh
python3 -B - <<'PY'
from pathlib import Path

files = sorted(Path("campus_events").rglob("*.py"))
lines = [line for path in files for line in path.read_text().splitlines()]
nonempty = sum(bool(line.strip()) and not line.lstrip().startswith("#") for line in lines)
print(f"Python 源文件 {len(files)} 个，总行数 {len(lines)}，去除空行与纯注释行 {nonempty}")
PY
```

最终的四张 UML 图和对应的 PlantUML 源文件位于 [UML 目录](../UML/)，组件图包含命令行和网页两个入口。

完成本人撰写的实验报告后，在本目录运行以下命令。打包工具会将报告、四组 UML 图片和源文件，以及源码、示例和构建说明放进同名目录，再压缩成 `实验3_241870097_丁瀚铭.zip`。

```sh
python3 -B tools/package_submission.py --report ../实验报告.pdf
```

默认输出到 `Lab_3`，可用 `--directory` 指定输出目录。打包只选取交付文件，排除运行数据库、二维码、导出的名单、构建缓存以及虚拟环境。

打包工具会检查报告 PDF 文件头及 UML 图片、源文件是否齐全。同名 ZIP 已存在时会提示失败，可用 `--directory` 选择另一个已存在的输出目录。实验报告须本人独立撰写，覆盖 UML 到代码的实现、源码规模、大模型辅助过程、编译运行结果和 Git 远程管理展示。提交截止时间为 2026 年 11 月 29 日 23:59，通过 cslab-cms 提交。

## 目录与本地数据

| 路径 | 内容 |
| --- | --- |
| `campus_events/*.py` | 权限、活动、报名、电子票、统计、数据库和命令行 |
| `campus_events/web/` | Flask 入口、网页路由、表单与演示数据 |
| `campus_events/web/templates/` | Jinja 页面和共用组件 |
| `campus_events/web/static/` | 界面 CSS 与表单交互 JavaScript |
| `tests/` | 自动化测试，使用临时数据库 |
| `examples/` | 命令行活动配置示例 |
| `tools/` | 课程提交包生成工具 |
| `data/` | 运行数据库和用户导出文件 |
| `build/`、`.venv/` | 本机构建缓存和依赖环境 |

仓库忽略本机数据库、构建缓存、虚拟环境和 Finder 元数据。数据库保存账号、报名、票据和日志，删除数据库文件会清除对应数据。

## 常见问题

- 提示找不到 `campus_events` 时，确认终端位于本 README 所在的 `Lab_3/code` 目录。
- 提示缺少 Flask、Pillow 或 zxing-cpp 时，在本目录重新执行 `make setup`，随后用 `make demo` 启动；命令行二维码操作可先 `source .venv/bin/activate`。
- 提示地址已被占用时，使用 `make demo PORT=8001`，同时调整浏览器中的端口。
- 若演示活动均已截止，可在举办方工作台新建活动并由管理员审核发布；也可以用 `--database data/另一份演示库.sqlite3 --demo` 启动一份新库。
- 服务重启会要求重新登录。演示凭据适用于预置演示账号，原有数据库中的其他账号继续使用各自密码。

## 代码对应关系

实验二类图的用户对应 `access.py` 中的 `User`。活动、场次和报名类别对应 `event_models.py` 中的 `Event`、`Session` 和 `RegistrationCategory`，分别存入 SQLite 的 `events`、`event_sessions` 和 `registration_categories` 表。`events.py` 负责状态变更和按角色限定查询范围。报名活动图和最后名额时序图的规则由 `registrations.py` 实现，报名记录和候补状态保存在 `registrations` 表中。

电子票和签到分别由 `tickets.py` 和 `check_in.py` 管理。票据关联报名记录，签到记录关联票据，检票权限通过 `session_checkers` 关联账号和场次。

`rosters.py` 按场次统计和导出报名数据。`audit.py` 中的 `AuditEntry` 对应 `audit_logs` 表。
