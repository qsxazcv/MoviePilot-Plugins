"""IkuaiAssistant CLI 命令解析与执行辅助模块。"""
import shlex
from typing import Any, Callable


def parse_command(command: str) -> tuple[list[str] | None, str | None]:
    """安全解析命令字符串，返回参数列表或中文错误。"""
    try:
        args = shlex.split(str(command or ""), posix=True)
    except ValueError:
        return None, "命令引号未闭合"
    if not args:
        return None, "请传入 ikuai-cli 命令"
    return args, None


def execute_with_runner(args: list[str], executable: str, timeout: int, environment: dict[str, str], run: Callable[..., Any]) -> Any:
    """通过注入的执行器运行 CLI，便于宿主逻辑测试和后续拆分。"""
    return run([executable, *args], capture_output=True, text=True, timeout=timeout, env=environment, check=False)
