from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import requests
except ModuleNotFoundError:
    requests = None  # type: ignore[assignment]
    RequestException = Exception
else:
    RequestException = requests.RequestException

from .settings import (
    DEFAULT_HEADERS, DEFAULT_UPDATE_CHECK_URL, PROJECT_ROOT, UPDATE_CHECK_FILE,
    now_local, today_local,
)
from .formatters import format_error, format_status_message
from .storage import read_json, write_json

def extract_skill_version(text: str) -> str | None:
    in_metadata = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped == "metadata:":
            in_metadata = True
            continue
        if in_metadata and line and not line.startswith((" ", "\t")):
            in_metadata = False
        if in_metadata:
            match = re.match(r"^\s+version:\s*['\"]?([^'\"\s]+)", line)
            if match:
                return match.group(1)
    match = re.search(r"(?m)^version:\s*['\"]?([^'\"\s]+)", text)
    return match.group(1) if match else None

def local_skill_version() -> str:
    skill_file = PROJECT_ROOT / "SKILL.md"
    try:
        version = extract_skill_version(skill_file.read_text(encoding="utf-8"))
    except Exception:
        version = None
    return version or "unknown"

def version_key(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts) if parts else (0,)

def compare_versions(current: str, latest: str) -> int:
    current_parts = list(version_key(current))
    latest_parts = list(version_key(latest))
    width = max(len(current_parts), len(latest_parts))
    current_parts.extend([0] * (width - len(current_parts)))
    latest_parts.extend([0] * (width - len(latest_parts)))
    if current_parts < latest_parts:
        return -1
    if current_parts > latest_parts:
        return 1
    return 0

def load_update_state() -> dict[str, Any]:
    data = read_json(UPDATE_CHECK_FILE, {})
    return data if isinstance(data, dict) else {}

def save_update_state(data: dict[str, Any]) -> None:
    data["updated_at"] = now_local().isoformat()
    write_json(UPDATE_CHECK_FILE, data)

def skipped_update_versions(state: dict[str, Any]) -> set[str]:
    raw = state.get("skipped_versions")
    if isinstance(raw, list):
        return {str(item) for item in raw if str(item).strip()}
    raw_single = state.get("skipped_version")
    if isinstance(raw_single, str) and raw_single.strip():
        return {raw_single.strip()}
    return set()

def fetch_latest_skill_version(remote_url: str = DEFAULT_UPDATE_CHECK_URL) -> str:
    if requests is None:
        raise RuntimeError("缺少 requests 依赖，无法检查远端版本")
    response = requests.get(remote_url, headers=DEFAULT_HEADERS, timeout=10)
    response.raise_for_status()
    latest = extract_skill_version(response.text)
    if not latest:
        raise RuntimeError("远端 SKILL.md 中未找到版本号")
    return latest

def update_available_sections(current: str, latest: str) -> list[tuple[str, list[str]]]:
    return [
        ("详情", [
            f"- 当前版本：{current}",
            f"- 最新版本：{latest}",
            f"- 今日检查日期：{today_local().isoformat()}",
        ]),
        ("建议", [
            "- 是否现在更新？如果更新，请在 skill 目录执行 git pull，并按 README 重新验证。",
            f"- 如果暂不更新，请回复“不更新”；系统会执行 skip-update --version {latest}，并跳过这个版本。",
        ]),
    ]

def show_version() -> int:
    print(format_status_message(
        "INFO",
        "当前 Skill 版本",
        [("详情", [f"- 当前版本：{local_skill_version()}"])],
    ))
    return 0

def check_update(remote_url: str = DEFAULT_UPDATE_CHECK_URL) -> int:
    current = local_skill_version()
    try:
        latest = fetch_latest_skill_version(remote_url)
    except RuntimeError as exc:
        print(format_error(
            str(exc),
            "请先安装 requirements.txt 后再重试。" if "requests" in str(exc) else None,
        ))
        return 1
    except RequestException as exc:
        print(format_error(f"检查远端版本失败：{exc}"))
        return 1

    comparison = compare_versions(current, latest)
    if comparison < 0:
        summary = "建议更新可转债提醒 Skill"
        sections = update_available_sections(current, latest)
    elif comparison == 0:
        summary = "当前已是最新版本"
        sections = [("详情", [f"- 当前版本：{current}", f"- 最新版本：{latest}"])]
    else:
        summary = "当前版本高于远端版本，可能正在使用本地开发版"
        sections = [("详情", [f"- 当前版本：{current}", f"- 最新版本：{latest}"])]
    print(format_status_message("INFO", summary, sections))
    return 0

def maybe_prompt_update_once_per_day(remote_url: str = DEFAULT_UPDATE_CHECK_URL) -> bool:
    state = load_update_state()
    today = today_local().isoformat()
    if state.get("last_checked_date") == today:
        return False

    current = local_skill_version()
    try:
        latest = fetch_latest_skill_version(remote_url)
        comparison = compare_versions(current, latest)
        status = "update_available" if comparison < 0 else "no_update"
        state.update({
            "last_checked_date": today,
            "last_checked_at": now_local().isoformat(),
            "last_status": status,
            "current_version": current,
            "latest_version": latest,
        })
        save_update_state(state)
    except Exception as exc:
        state.update({
            "last_checked_date": today,
            "last_checked_at": now_local().isoformat(),
            "last_status": "error",
            "last_error": str(exc),
            "current_version": current,
        })
        save_update_state(state)
        return False

    if comparison >= 0:
        return False
    if latest in skipped_update_versions(state):
        return False

    print(format_status_message(
        "INFO",
        f"发现可转债提醒 Skill 新版本 {latest}",
        update_available_sections(current, latest),
    ))
    return True

def skip_update_version(version: str) -> int:
    version = version.strip()
    if not version:
        print(format_error("缺少要跳过的版本号", "请使用 skip-update --version <版本号>。"))
        return 1
    state = load_update_state()
    skipped = skipped_update_versions(state)
    skipped.add(version)
    state["skipped_versions"] = sorted(skipped, key=version_key)
    state["last_skipped_version"] = version
    state["last_status"] = "skipped"
    state["last_checked_date"] = today_local().isoformat()
    save_update_state(state)
    print(format_status_message(
        "INFO",
        f"已跳过版本 {version}",
        [
            ("详情", [
                f"- 已跳过版本：{version}",
                "- 之后不会再为这个版本提示更新。",
                "- 如果发布了更高版本，下一次每日检查仍会提示。",
            ])
        ],
    ))
    return 0
