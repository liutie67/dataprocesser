from __future__ import annotations

import re
import shlex
import subprocess
import uuid

from .models import (
    ArgumentMode,
    CommandArgument,
    CommandDraft,
    CommandPrefix,
    InvocationMode,
    ParseCommandRequest,
    ParseCommandResult,
    ShellDialect,
    ShellTarget,
    ValueType,
)


_POWERSHELL_SAFE = re.compile(r"^[A-Za-z0-9_./\\:@%+=,-]+$")
_CMD_SAFE = re.compile(r"^[A-Za-z0-9_./\\:@+=,-]+$")


def _validated_value(argument: CommandArgument) -> str:
    value = argument.value
    if value is None or (isinstance(value, str) and value == ""):
        raise ValueError(f"参数 {argument.token or argument.position} 已启用但没有值")

    if argument.value_type == ValueType.INTEGER:
        if isinstance(value, bool):
            raise ValueError(f"参数 {argument.token} 必须是整数")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"参数 {argument.token} 必须是整数") from exc
        if isinstance(value, float) and value != parsed:
            raise ValueError(f"参数 {argument.token} 必须是整数")
        if isinstance(value, str) and str(parsed) != value.strip():
            raise ValueError(f"参数 {argument.token} 必须是整数")
        return str(parsed)

    if argument.value_type == ValueType.FLOAT:
        if isinstance(value, bool):
            raise ValueError(f"参数 {argument.token} 必须是数字")
        try:
            return str(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"参数 {argument.token} 必须是数字") from exc

    rendered = str(value)
    if argument.value_type == ValueType.CHOICE and rendered not in argument.choices:
        raise ValueError(f"参数 {argument.token} 的值不在 choices 中")
    return rendered


def _tokens(profile: CommandDraft) -> list[str]:
    prefix = {
        CommandPrefix.PYTHON: ["python"],
        CommandPrefix.PY: ["py"],
        CommandPrefix.UV_RUN_PYTHON: ["uv", "run", "python"],
    }[profile.prefix]
    tokens = [*prefix]
    if profile.invocation_mode == InvocationMode.MODULE:
        tokens.append("-m")
    tokens.append(profile.script_path)

    for argument in sorted(profile.arguments, key=lambda item: item.position):
        if not argument.enabled:
            continue
        if argument.value_type == ValueType.BOOLEAN:
            if bool(argument.value):
                tokens.append(argument.token)
            continue

        value = _validated_value(argument)
        if argument.mode == ArgumentMode.NAMED:
            tokens.append(argument.token)
        tokens.append(value)
    return tokens


def _quote_powershell(value: str) -> str:
    if value and _POWERSHELL_SAFE.fullmatch(value):
        return value
    return "'" + value.replace("'", "''") + "'"


def _quote_cmd(value: str) -> str:
    if value and _CMD_SAFE.fullmatch(value):
        return value
    rendered = subprocess.list2cmdline([value])
    if not (rendered.startswith('"') and rendered.endswith('"')):
        rendered = f'"{rendered}"'
    return rendered


def build_command(profile: CommandDraft) -> str:
    tokens = _tokens(profile)
    if profile.shell == ShellTarget.POWERSHELL:
        quote = _quote_powershell
    elif profile.shell == ShellTarget.CMD:
        quote = _quote_cmd
    else:
        quote = shlex.quote
    return " ".join(quote(token) for token in tokens)


_INTEGER = re.compile(r"^[+-]?(?:0|[1-9]\d*)$")
_FLOAT = re.compile(
    r"^[+-]?(?:(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)$"
)
_NEGATIVE_NUMBER = re.compile(r"^-\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")


def _normalize_multiline(command: str, dialect: ShellTarget) -> str:
    """Fold shell line continuations while leaving quoted newlines intact."""
    marker = {
        ShellTarget.POWERSHELL: "`",
        ShellTarget.CMD: "^",
        ShellTarget.BASH: "\\",
    }[dialect]
    normalized: list[str] = []
    quote: str | None = None
    index = 0

    while index < len(command):
        char = command[index]

        marker_is_active = (
            char == marker
            and not (
                dialect in {ShellTarget.POWERSHELL, ShellTarget.BASH}
                and quote == "'"
            )
            and not (dialect == ShellTarget.CMD and quote == '"')
        )
        if marker_is_active:
            newline_index = index + 1
            if dialect in {ShellTarget.POWERSHELL, ShellTarget.CMD} and quote is None:
                while (
                    newline_index < len(command)
                    and command[newline_index] in " \t"
                ):
                    newline_index += 1
            if (
                newline_index < len(command)
                and command[newline_index] in "\r\n"
            ):
                if (
                    command[newline_index] == "\r"
                    and newline_index + 1 < len(command)
                    and command[newline_index + 1] == "\n"
                ):
                    newline_index += 1
                normalized.append(" ")
                index = newline_index + 1
                continue

            # Escaped quotes must not change the quote state used by this scanner.
            if index + 1 < len(command):
                normalized.extend((char, command[index + 1]))
                index += 2
                continue

        if char in {"'", '"'} and (dialect != ShellTarget.CMD or char == '"'):
            if quote is None:
                quote = char
            elif quote == char:
                if (
                    dialect == ShellTarget.POWERSHELL
                    and quote == "'"
                    and index + 1 < len(command)
                    and command[index + 1] == "'"
                ):
                    normalized.extend(("'", "'"))
                    index += 2
                    continue
                quote = None
            normalized.append(char)
            index += 1
            continue

        normalized.append(char)
        index += 1

    return "".join(normalized)


def _find_unsupported_operator(command: str, dialect: ShellTarget) -> str | None:
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            if char == quote:
                if dialect == ShellTarget.POWERSHELL and quote == "'" and index + 1 < len(command) and command[index + 1] == "'":
                    index += 2
                    continue
                quote = None
            elif (dialect == ShellTarget.BASH and char == "\\") or (
                dialect == ShellTarget.POWERSHELL and quote == '"' and char == "`"
            ):
                index += 1
            index += 1
            continue
        if char == '"' or (char == "'" and dialect != ShellTarget.CMD):
            quote = char
        elif char in {"|", ";", ">", "<"}:
            return char
        elif char == "&" and index + 1 < len(command) and command[index + 1] == "&":
            return "&&"
        index += 1
    if quote:
        raise ValueError("命令中存在未闭合的引号")
    return None


def _split_windows(command: str, dialect: ShellTarget) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None
    token_started = False
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            if char == quote:
                if dialect == ShellTarget.POWERSHELL and quote == "'" and index + 1 < len(command) and command[index + 1] == "'":
                    current.append("'")
                    index += 2
                    continue
                quote = None
            elif dialect == ShellTarget.POWERSHELL and quote == '"' and char == "`":
                index += 1
                if index >= len(command):
                    raise ValueError("命令末尾的 PowerShell 转义符不完整")
                current.append(command[index])
            else:
                current.append(char)
            token_started = True
            index += 1
            continue
        if char.isspace():
            if token_started:
                tokens.append("".join(current))
                current = []
                token_started = False
        elif char in {"'", '"'} and dialect == ShellTarget.POWERSHELL:
            quote = char
            token_started = True
        elif char == '"' and dialect == ShellTarget.CMD:
            quote = char
            token_started = True
        elif dialect == ShellTarget.CMD and char == "^":
            index += 1
            if index >= len(command):
                raise ValueError("命令末尾的 cmd 转义符不完整")
            current.append(command[index])
            token_started = True
        elif dialect == ShellTarget.POWERSHELL and char == "`":
            index += 1
            if index >= len(command):
                raise ValueError("命令末尾的 PowerShell 转义符不完整")
            current.append(command[index])
            token_started = True
        else:
            current.append(char)
            token_started = True
        index += 1
    if quote:
        raise ValueError("命令中存在未闭合的引号")
    if token_started:
        tokens.append("".join(current))
    return tokens


def _tokenize(command: str, shell: ShellTarget) -> list[str]:
    command = _normalize_multiline(command, shell)
    operator = _find_unsupported_operator(command, shell)
    if operator:
        raise ValueError(f"暂不支持包含 {operator} 的多命令、管道或重定向")
    if shell == ShellTarget.BASH:
        if "$(" in command or "`" in command:
            raise ValueError("暂不支持 Bash 命令替换")
        try:
            return shlex.split(command, posix=True)
        except ValueError as exc:
            raise ValueError("命令中的 Bash 引号或转义不完整") from exc
    return _split_windows(command, shell)


def _detect_shell(command: str, fallback: ShellTarget) -> tuple[ShellTarget, list[str]]:
    newline = r"(?:\r\n|\r|\n)"
    if re.search(rf"%[^%\s]+%|(?:^|\s)\^|\^[ \t]*{newline}", command):
        return ShellTarget.CMD, []
    if re.search(rf"\$env:|`[^`]|`[ \t]*{newline}", command, re.IGNORECASE):
        return ShellTarget.POWERSHELL, []
    if (
        re.search(r"\$[A-Za-z_{]|(?:^|\s)(?:\./|/usr/|~/)", command)
        or re.search(rf"\\{newline}", command)
        or "'" in command
    ):
        return ShellTarget.BASH, []
    return fallback, [f"未发现明确的终端语法，已按 {fallback.value} 解析。"]


def _inferred_value(value: str) -> tuple[ValueType, str | int | float]:
    if _INTEGER.fullmatch(value):
        return ValueType.INTEGER, int(value)
    if _FLOAT.fullmatch(value):
        return ValueType.FLOAT, float(value)
    return ValueType.STRING, value


def _argument(position: int, *, mode: ArgumentMode, token: str = "", value: str | bool) -> CommandArgument:
    if isinstance(value, bool):
        value_type = ValueType.BOOLEAN
        rendered: str | bool | int | float = value
    else:
        value_type, rendered = _inferred_value(value)
    return CommandArgument(
        id=str(uuid.uuid4()),
        position=position,
        mode=mode,
        token=token,
        value_type=value_type,
        value=rendered,
        enabled=True,
    )


def _parse_arguments(tokens: list[str]) -> list[CommandArgument]:
    arguments: list[CommandArgument] = []
    positional_only = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        position = len(arguments)
        if positional_only:
            arguments.append(_argument(position, mode=ArgumentMode.POSITIONAL, value=token))
            index += 1
            continue
        if token == "--":
            arguments.append(_argument(position, mode=ArgumentMode.POSITIONAL, value=token))
            positional_only = True
            index += 1
            continue
        is_named = token.startswith("-") and token != "-" and not _NEGATIVE_NUMBER.fullmatch(token)
        if not is_named:
            arguments.append(_argument(position, mode=ArgumentMode.POSITIONAL, value=token))
            index += 1
            continue
        if "=" in token:
            flag, value = token.split("=", 1)
            arguments.append(_argument(position, mode=ArgumentMode.NAMED, token=flag, value=value))
            index += 1
            continue
        next_value = tokens[index + 1] if index + 1 < len(tokens) else None
        next_is_option = bool(
            next_value
            and next_value.startswith("-")
            and next_value != "-"
            and not _NEGATIVE_NUMBER.fullmatch(next_value)
        )
        if next_value is not None and next_value != "--" and not next_is_option:
            arguments.append(_argument(position, mode=ArgumentMode.NAMED, token=token, value=next_value))
            index += 2
        else:
            arguments.append(_argument(position, mode=ArgumentMode.NAMED, token=token, value=True))
            index += 1
    return arguments


def parse_command(request: ParseCommandRequest) -> ParseCommandResult:
    if request.dialect == ShellDialect.AUTO:
        shell, warnings = _detect_shell(request.command, request.fallback_shell)
    else:
        shell = ShellTarget(request.dialect.value)
        warnings = []
    tokens = _tokenize(request.command, shell)
    if not tokens:
        raise ValueError("命令不能为空")

    normalized = [item.lower() for item in tokens]
    if normalized[:3] in (["uv", "run", "python"], ["uv", "run", "python.exe"]):
        prefix = CommandPrefix.UV_RUN_PYTHON
        cursor = 3
    elif normalized[0] in {"python", "python.exe"}:
        prefix = CommandPrefix.PYTHON
        cursor = 1
    elif normalized[0] in {"py", "py.exe"}:
        prefix = CommandPrefix.PY
        cursor = 1
    else:
        raise ValueError("仅支持 python、py 或 uv run python 命令")

    if cursor >= len(tokens):
        raise ValueError("命令中缺少脚本路径或模块名")
    if tokens[cursor] == "-c":
        raise ValueError("暂不支持 python -c 内联代码")
    if tokens[cursor] == "-m":
        invocation_mode = InvocationMode.MODULE
        cursor += 1
        if cursor >= len(tokens) or tokens[cursor].startswith("-"):
            raise ValueError("-m 后必须提供模块名")
    elif tokens[cursor].startswith("-"):
        raise ValueError(f"暂不支持解释器选项 {tokens[cursor]}")
    else:
        invocation_mode = InvocationMode.SCRIPT

    script_path = tokens[cursor]
    arguments = _parse_arguments(tokens[cursor + 1 :])
    draft = CommandDraft(
        script_path=script_path,
        invocation_mode=invocation_mode,
        prefix=prefix,
        shell=shell,
        arguments=arguments,
    )
    return ParseCommandResult(draft=draft, detected_shell=shell, warnings=warnings)
