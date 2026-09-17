from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CommandPrefix(StrEnum):
    PYTHON = "python"
    PY = "py"
    UV_RUN_PYTHON = "uv_run_python"


class ShellTarget(StrEnum):
    POWERSHELL = "powershell"
    CMD = "cmd"
    BASH = "bash"


class ShellDialect(StrEnum):
    AUTO = "auto"
    POWERSHELL = "powershell"
    CMD = "cmd"
    BASH = "bash"


class InvocationMode(StrEnum):
    SCRIPT = "script"
    MODULE = "module"


class ArgumentMode(StrEnum):
    NAMED = "named"
    POSITIONAL = "positional"


class ValueType(StrEnum):
    STRING = "str"
    PATH = "path"
    INTEGER = "int"
    FLOAT = "float"
    CHOICE = "choice"
    BOOLEAN = "bool"


class CommandArgument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    position: int = Field(ge=0)
    mode: ArgumentMode = ArgumentMode.NAMED
    token: str = Field(default="", max_length=128)
    value_type: ValueType = ValueType.STRING
    value: str | int | float | bool | None = None
    choices: list[str] = Field(default_factory=list, max_length=100)
    enabled: bool = True

    @field_validator("token")
    @classmethod
    def strip_token(cls, value: str) -> str:
        return value.strip()

    @field_validator("choices")
    @classmethod
    def normalize_choices(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            normalized = item.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    @model_validator(mode="after")
    def validate_shape(self) -> "CommandArgument":
        if self.mode == ArgumentMode.NAMED and not self.token.startswith("-"):
            raise ValueError("命名参数必须以 - 或 -- 开头")
        if self.mode == ArgumentMode.POSITIONAL and self.value_type == ValueType.BOOLEAN:
            raise ValueError("布尔开关只能用作命名参数")
        if self.value_type == ValueType.BOOLEAN and not isinstance(self.value, bool):
            raise ValueError("布尔开关的值必须为 true 或 false")
        if self.value_type == ValueType.CHOICE and not self.choices:
            raise ValueError("choices 参数至少需要一个候选值")
        return self


class CommandDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_path: str = Field(min_length=1, max_length=4096)
    invocation_mode: InvocationMode = InvocationMode.SCRIPT
    prefix: CommandPrefix = CommandPrefix.PYTHON
    shell: ShellTarget = ShellTarget.POWERSHELL
    arguments: list[CommandArgument] = Field(default_factory=list, max_length=200)

    @field_validator("script_path")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("该字段不能为空")
        return normalized


class ProfilePayload(CommandDraft):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("该字段不能为空")
        return normalized


class Profile(ProfilePayload):
    id: str
    created_at: datetime
    updated_at: datetime


class HistoryEntry(BaseModel):
    id: str
    created_at: datetime
    profile_id: str | None
    profile_name: str
    shell: ShellTarget
    command: str
    snapshot: dict[str, Any]


class GenerateResult(BaseModel):
    command: str
    history: HistoryEntry


class PreviewResult(BaseModel):
    command: str


class RecordCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = Field(default=None, max_length=64)
    profile_name: str = Field(min_length=1, max_length=120)
    draft: CommandDraft

    @field_validator("profile_name")
    @classmethod
    def strip_profile_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("配置名称不能为空")
        return normalized


class ParseCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1, max_length=32768)
    dialect: ShellDialect = ShellDialect.AUTO
    fallback_shell: ShellTarget = ShellTarget.POWERSHELL

    @field_validator("command")
    @classmethod
    def strip_command(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("命令不能为空")
        return normalized


class ParseCommandResult(BaseModel):
    draft: CommandDraft
    detected_shell: ShellTarget
    warnings: list[str] = Field(default_factory=list)


class BackupData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    exported_at: datetime
    profiles: list[Profile]
    history: list[HistoryEntry]

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: int) -> int:
        if value not in {1, 2}:
            raise ValueError("仅支持 schema_version 1 或 2")
        return value

    @model_validator(mode="after")
    def validate_unique_records(self) -> "BackupData":
        profile_ids = [item.id for item in self.profiles]
        history_ids = [item.id for item in self.history]
        profile_names = [item.name.casefold() for item in self.profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("备份中存在重复的配置 ID")
        if len(history_ids) != len(set(history_ids)):
            raise ValueError("备份中存在重复的历史 ID")
        if len(profile_names) != len(set(profile_names)):
            raise ValueError("备份中存在重复的配置名称")
        return self


class ImportMode(StrEnum):
    MERGE = "merge"
    REPLACE = "replace"


class ImportRequest(BaseModel):
    mode: ImportMode
    backup: BackupData


class ImportResult(BaseModel):
    profiles_imported: int
    history_imported: int
