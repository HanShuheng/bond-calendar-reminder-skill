# 卸载与清理指南

本文档用于用户不再使用本 skill 时，清理自动任务、提醒任务和本地运行数据。

默认路径以 `~/cow` 为 CowAgent workspace。如果你设置了 `COW_WORKSPACE`，请先替换为自己的 workspace 路径：

```bash
export COW_WORKSPACE=/path/to/cow
```

## 清理范围

本 skill 可能写入以下内容：

| 类型 | 默认位置 | 说明 |
|---|---|---|
| skill 代码 | `~/cow/skills/bond-calendar-reminder-skill` | 手动安装时的仓库目录 |
| 运行数据 | `~/cow/bond_reminders/` | 配置、申购缓存、中签结果公布缓存、上市追踪、日志 |
| scheduler 任务 | `~/cow/scheduler/tasks.json` | 一次性微信提醒任务 |
| crontab 任务 | 当前系统用户的 crontab | 每日自动检查任务 |

建议先备份，再清理。

## 1. 备份

```bash
mkdir -p ~/cow/backup/bond-calendar-reminder-skill

cp -a ~/cow/bond_reminders ~/cow/backup/bond-calendar-reminder-skill/bond_reminders 2>/dev/null || true
cp -a ~/cow/scheduler/tasks.json ~/cow/backup/bond-calendar-reminder-skill/tasks.json 2>/dev/null || true
crontab -l > ~/cow/backup/bond-calendar-reminder-skill/crontab.txt 2>/dev/null || true
```

如果使用了自定义 workspace：

```bash
mkdir -p "$COW_WORKSPACE/backup/bond-calendar-reminder-skill"

cp -a "$COW_WORKSPACE/bond_reminders" "$COW_WORKSPACE/backup/bond-calendar-reminder-skill/bond_reminders" 2>/dev/null || true
cp -a "$COW_WORKSPACE/scheduler/tasks.json" "$COW_WORKSPACE/backup/bond-calendar-reminder-skill/tasks.json" 2>/dev/null || true
crontab -l > "$COW_WORKSPACE/backup/bond-calendar-reminder-skill/crontab.txt" 2>/dev/null || true
```

## 2. 移除 crontab 自动任务

本 skill 默认写入 3 个 crontab 命令：

- `prepare-daily-reminders`
- `check-tracked-listings`
- `check-listing-limit-up`

先预览当前任务：

```bash
crontab -l 2>/dev/null | grep 'bond_calendar.py' || true
```

确认后移除包含这些命令的行：

```bash
(crontab -l 2>/dev/null || true) \
  | grep -v 'bond_calendar.py prepare-daily-reminders' \
  | grep -v 'bond_calendar.py check-tracked-listings' \
  | grep -v 'bond_calendar.py check-listing-limit-up' \
  | crontab -
```

再次确认：

```bash
crontab -l 2>/dev/null | grep 'bond_calendar.py' || true
```

如果没有输出，表示本 skill 的默认 crontab 任务已经移除。

## 3. 清理 scheduler 提醒任务

本 skill 创建的 scheduler 任务 ID 使用这些前缀：

- `bond-subscribe-`
- `bond-winning-`
- `bond-listing-`

推荐先禁用任务，而不是直接删除：

```bash
python3 - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path

workspace = Path(os.environ.get("COW_WORKSPACE", "~/cow")).expanduser()
tasks_file = workspace / "scheduler" / "tasks.json"
prefixes = ("bond-subscribe-", "bond-winning-", "bond-listing-")

if not tasks_file.exists():
    print(f"未找到 scheduler 文件：{tasks_file}")
    raise SystemExit(0)

data = json.loads(tasks_file.read_text(encoding="utf-8"))
tasks = data.get("tasks", {})
changed = 0
for task_id, task in list(tasks.items()):
    if isinstance(task, dict) and task_id.startswith(prefixes):
        task["enabled"] = False
        task["updated_at"] = datetime.now().isoformat()
        changed += 1

if changed:
    backup = tasks_file.with_suffix(tasks_file.suffix + ".bak")
    backup.write_text(tasks_file.read_text(encoding="utf-8"), encoding="utf-8")
    data["updated_at"] = datetime.now().isoformat()
    tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"已禁用 {changed} 个可转债 scheduler 任务")
PY
```

如果你确认要彻底删除这些 scheduler 任务：

```bash
python3 - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path

workspace = Path(os.environ.get("COW_WORKSPACE", "~/cow")).expanduser()
tasks_file = workspace / "scheduler" / "tasks.json"
prefixes = ("bond-subscribe-", "bond-winning-", "bond-listing-")

if not tasks_file.exists():
    print(f"未找到 scheduler 文件：{tasks_file}")
    raise SystemExit(0)

data = json.loads(tasks_file.read_text(encoding="utf-8"))
tasks = data.get("tasks", {})
remove_ids = [task_id for task_id in tasks if task_id.startswith(prefixes)]

if remove_ids:
    backup = tasks_file.with_suffix(tasks_file.suffix + ".bak")
    backup.write_text(tasks_file.read_text(encoding="utf-8"), encoding="utf-8")
    for task_id in remove_ids:
        tasks.pop(task_id, None)
    data["updated_at"] = datetime.now().isoformat()
    tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"已删除 {len(remove_ids)} 个可转债 scheduler 任务")
PY
```

## 4. 删除运行数据

运行数据目录包含用户配置、申购缓存、中签结果公布缓存、上市追踪和日志。

先查看目录：

```bash
ls -la ~/cow/bond_reminders 2>/dev/null || true
```

确认不再需要后删除：

```bash
rm -i ~/cow/bond_reminders/config.json 2>/dev/null || true
rm -i ~/cow/bond_reminders/daily_subscribe.json 2>/dev/null || true
rm -i ~/cow/bond_reminders/daily_winning.json 2>/dev/null || true
rm -i ~/cow/bond_reminders/update_check.json 2>/dev/null || true
rm -i ~/cow/bond_reminders/watchlist.json 2>/dev/null || true
rm -i ~/cow/bond_reminders/bond_calendar.log 2>/dev/null || true
rmdir ~/cow/bond_reminders 2>/dev/null || true
```

如果使用了自定义 workspace：

```bash
rm -i "$COW_WORKSPACE/bond_reminders/config.json" 2>/dev/null || true
rm -i "$COW_WORKSPACE/bond_reminders/daily_subscribe.json" 2>/dev/null || true
rm -i "$COW_WORKSPACE/bond_reminders/daily_winning.json" 2>/dev/null || true
rm -i "$COW_WORKSPACE/bond_reminders/update_check.json" 2>/dev/null || true
rm -i "$COW_WORKSPACE/bond_reminders/watchlist.json" 2>/dev/null || true
rm -i "$COW_WORKSPACE/bond_reminders/bond_calendar.log" 2>/dev/null || true
rmdir "$COW_WORKSPACE/bond_reminders" 2>/dev/null || true
```

## 5. 删除 skill 代码

如果通过 CowAgent CLI 安装，并且你的 CowAgent 支持卸载命令，优先使用 CowAgent 的卸载命令。

如果是手动 clone 到默认目录：

```bash
rm -i ~/cow/skills/bond-calendar-reminder-skill/SKILL.md 2>/dev/null || true
```

确认目录内没有个人改动后，再删除整个 skill 目录：

```bash
rm -ri ~/cow/skills/bond-calendar-reminder-skill
```

## 6. 验证清理结果

```bash
crontab -l 2>/dev/null | grep 'bond_calendar.py' || true
test ! -e ~/cow/bond_reminders && echo "运行数据目录已清理"
```

如果使用自定义 workspace：

```bash
crontab -l 2>/dev/null | grep 'bond_calendar.py' || true
test ! -e "$COW_WORKSPACE/bond_reminders" && echo "运行数据目录已清理"
```

如果 `grep 'bond_calendar.py'` 仍有输出，说明还有手动添加的相关 crontab 行，请用 `crontab -e` 检查后删除。
