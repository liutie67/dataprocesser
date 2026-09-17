from __future__ import annotations

import re
import shlex
import subprocess

from .models import (
    ArgumentMode,
    CommandArgument,
    CommandPrefix,
    ProfilePayload,
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


def _tokens(profile: ProfilePayload) -> list[str]:
    prefix = {
        CommandPrefix.PYTHON: ["python"],
        CommandPrefix.UV_RUN_PYTHON: ["uv", "run", "python"],
    }[profile.prefix]
    tokens = [*prefix, profile.script_path]

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


def build_command(profile: ProfilePayload) -> str:
    tokens = _tokens(profile)
    if profile.shell == ShellTarget.POWERSHELL:
        quote = _quote_powershell
    elif profile.shell == ShellTarget.CMD:
        quote = _quote_cmd
    else:
        quote = shlex.quote
    return " ".join(quote(token) for token in tokens)
