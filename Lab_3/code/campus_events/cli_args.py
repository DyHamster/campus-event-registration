"""共用的命令行参数校验。"""

import argparse

from .event_input import SQLITE_MAX_INTEGER


def positive_id(value: str) -> int:
    """解析可传给 SQLite 的正整数编号。"""
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("编号必须是正整数。") from error
    if not 0 < number <= SQLITE_MAX_INTEGER:
        raise argparse.ArgumentTypeError("编号超出允许范围。")
    return number
