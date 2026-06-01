from __future__ import annotations

import importlib
import inspect
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from typing import Any

from .formatters import format_error, format_status_message
from .queries import parse_single_date
from .settings import today_local
from .storage import load_config


class TradeCalendarError(RuntimeError):
    pass


def load_python_trade_calendar_adapter(path: str) -> Any:
    if not isinstance(path, str) or ":" not in path:
        raise TradeCalendarError("Python trade calendar adapter must use 'module:attribute' format")
    module_name, attr_name = path.split(":", 1)
    module = importlib.import_module(module_name)
    target = getattr(module, attr_name)
    if inspect.isclass(target):
        return target()
    if callable(target):
        result = target()
        return result if result is not None else target
    return target


class BaostockTradeCalendarAdapter:
    source = "baostock"

    def is_trade_day(self, day: date) -> bool:
        try:
            import baostock as bs
        except ModuleNotFoundError as exc:
            raise TradeCalendarError("缺少 Python 依赖 baostock，请先安装 requirements.txt") from exc

        day_text = day.isoformat()
        with redirect_stdout(StringIO()):
            login_result = bs.login()
        if getattr(login_result, "error_code", "") != "0":
            raise TradeCalendarError(f"baostock login failed: {getattr(login_result, 'error_msg', '')}")

        try:
            result = bs.query_trade_dates(start_date=day_text, end_date=day_text)
            if getattr(result, "error_code", "") != "0":
                raise TradeCalendarError(f"query_trade_dates failed: {getattr(result, 'error_msg', '')}")
            if not result.next():
                raise TradeCalendarError("query_trade_dates returned no rows")
            row = dict(zip(result.fields, result.get_row_data()))
            if "is_trading_day" not in row:
                raise TradeCalendarError("query_trade_dates missing is_trading_day")
            return row.get("is_trading_day") == "1"
        finally:
            with redirect_stdout(StringIO()):
                bs.logout()


def load_trade_calendar_adapter() -> Any:
    config = load_config()
    strategy = config.get("trade_calendar_strategy")
    if isinstance(strategy, dict) and strategy.get("type") == "python":
        return load_python_trade_calendar_adapter(str(strategy.get("adapter") or ""))
    return BaostockTradeCalendarAdapter()


def configured_trade_calendar_source() -> str:
    config = load_config()
    strategy = config.get("trade_calendar_strategy")
    if isinstance(strategy, dict):
        strategy_type = strategy.get("type")
        if isinstance(strategy_type, str) and strategy_type.strip():
            return strategy_type.strip()
    return "baostock"


def trade_calendar_source(adapter: Any) -> str:
    source = getattr(adapter, "source", None)
    if isinstance(source, str) and source.strip():
        return source.strip()
    return type(adapter).__name__


def query_is_trade_day(day: date) -> tuple[bool, str]:
    adapter = load_trade_calendar_adapter()
    if not hasattr(adapter, "is_trade_day"):
        raise TradeCalendarError("trade calendar adapter must provide is_trade_day(day)")
    result = adapter.is_trade_day(day)
    if not isinstance(result, bool):
        raise TradeCalendarError("trade calendar adapter must return bool")
    return result, trade_calendar_source(adapter)


def format_trade_day_result(day: date, is_trade_day: bool, source: str) -> str:
    day_text = day.isoformat()
    return format_status_message(
        "INFO",
        f"{day_text} {'是' if is_trade_day else '不是'} A 股交易日",
        [
            ("详情", [
                f"- 日期：{day_text}",
                "- 市场：中国 A 股",
                f"- 是否交易日：{'是' if is_trade_day else '否'}",
                f"- 数据源：{source}",
            ]),
        ],
    )


def format_trade_day_error(day: date, source: str, error: Exception) -> str:
    return format_status_message(
        "ERROR",
        "交易日历查询失败",
        [
            ("详情", [
                f"- 日期：{day.isoformat()}",
                f"- 数据源：{source}",
                f"- 错误：{error}",
            ]),
            ("建议", ["- 请稍后重试，或检查 trade_calendar_strategy 配置和 baostock 依赖。"]),
        ],
    )


def is_trade_day_command(date_expr: str | None = None) -> int:
    try:
        day = parse_single_date(date_expr, today_local()) if date_expr else today_local()
    except ValueError as exc:
        print(format_error(str(exc)))
        return 2

    source = configured_trade_calendar_source()
    try:
        adapter = load_trade_calendar_adapter()
        source = trade_calendar_source(adapter)
        if not hasattr(adapter, "is_trade_day"):
            raise TradeCalendarError("trade calendar adapter must provide is_trade_day(day)")
        result = adapter.is_trade_day(day)
        if not isinstance(result, bool):
            raise TradeCalendarError("trade calendar adapter must return bool")
    except Exception as exc:
        print(format_trade_day_error(day, source, exc))
        return 1

    print(format_trade_day_result(day, result, source))
    return 0
