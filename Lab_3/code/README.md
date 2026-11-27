# 校园活动票务与报名系统

程序使用 Python 命令行和 SQLite。举办方创建活动、设置场次和票价并提交审核。平台管理员审核通过后，所有角色都可以查询公开活动。

在本文件所在的 `code` 目录执行下列命令。需要 Python 3.10 或更高版本和 Make。程序使用 Python 标准库。

```sh
make build
make test
python3 -B -m campus_events init --demo
python3 -B -m campus_events login organizer
```

`make build` 将程序编译为 Python 字节码，产物位于 `build/pycache/`。默认数据库位于 `data/campus_events.sqlite3`。运行 `init` 会创建或升级数据库表，加上 `--demo` 会添加缺失的演示账号。已有第一阶段数据库可直接执行 `python3 -B -m campus_events init` 升级，账号和密码会保留。

四个演示账号共用本地演示密码 `campus-demo`。请在终端密码提示后输入。

| 账号 | 角色 | 可访问的功能 |
| --- | --- | --- |
| `student` | 普通参与者 | 公开活动 |
| `organizer` | 活动举办方 | 公开活动、活动管理 |
| `admin` | 平台管理员 | 公开活动、活动审核 |
| `checker` | 现场检票人员 | 公开活动、检票签到入口 |

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

## 代码对应关系

实验二类图的用户对应 `access.py` 中的 `User`。活动、场次和报名类别对应 `event_models.py` 中的 `Event`、`Session` 和 `RegistrationCategory`，分别存入 SQLite 的 `events`、`event_sessions` 和 `registration_categories` 表。`events.py` 负责状态变更和按角色限定查询范围。
