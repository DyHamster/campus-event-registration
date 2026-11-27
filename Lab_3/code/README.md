# 校园活动票务与报名系统

第一阶段提供命令行入口、SQLite 初始化、四类演示账号、密码验证和角色权限检查。业务命令目前用于验证能否进入相应功能。

在本文件所在的 `code` 目录执行下列命令。需要 Python 3.10 或更高版本和 Make。程序使用 Python 标准库。

```sh
make build
make test
python3 -B -m campus_events init --demo
python3 -B -m campus_events login organizer
```

`make build` 将程序编译为 Python 字节码，产物位于 `build/pycache/`。默认数据库位于 `data/campus_events.sqlite3`。运行 `init` 会创建数据库和用户表，加上 `--demo` 会添加缺失的演示账号。重复初始化会保留已有账号。

四个演示账号共用本地演示密码 `campus-demo`。请在终端密码提示后输入。

| 账号 | 角色 | 可访问的功能 |
| --- | --- | --- |
| `student` | 普通参与者 | 公开活动 |
| `organizer` | 活动举办方 | 公开活动、活动管理 |
| `admin` | 平台管理员 | 公开活动、活动审核 |
| `checker` | 现场检票人员 | 公开活动、检票签到 |

给 `login` 传入功能名可直接验证访问权限。举办方可以进入活动管理，普通参与者会收到拒绝提示，命令以状态码 `1` 退出。

```sh
python3 -B -m campus_events login organizer manage-events
python3 -B -m campus_events login student manage-events
```

可以在子命令前传入 `--database`，用独立数据库进行多次演示。

```sh
python3 -B -m campus_events --database data/review.sqlite3 init --demo
python3 -B -m campus_events --database data/review.sqlite3 login admin review-events
```

实验二类图中的「用户」对应 `access.py` 的 `User` 和 SQLite 的 `users` 表。`access.py` 管理角色权限，`database.py` 负责数据库连接和初始化，`cli.py` 在进入业务功能前执行身份与权限检查。
