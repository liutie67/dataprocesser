"""提取门架抓拍数据中的车辆正面照及对应标签文件。

预期输入结构如下（文件名仅作示例）：

    input_path/
      Ai/
        Record/
          Bj/
            123.bin
            123.bmp
            123.inf
            123.txt
            123_1.jpg
            123_2.jpg
            123_3.jpg

脚本会把 ``*_1.jpg``、``*_2.jpg`` 提取到 ``output_path/front_view``，
把同一基础文件名的 ``.bmp``、``.inf``、``.txt`` 提取到
``output_path/label``。默认复制文件，将文末 ``MOVE_FILES`` 改为 True 后移动。
``.bin`` 和 ``*_3.jpg`` 只参与统计，不会被提取。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from tqdm import tqdm


FRONT_TYPES = ("front_1", "front_2")
LABEL_TYPES = ("bmp", "inf", "txt")
MAX_REPORT_DETAILS = 100
CHECKPOINT_FILENAME = ".extract_gantry_records_checkpoint.sqlite3"


@dataclass(slots=True)
class DataGroup:
    """一个 Bj 文件夹内具有同一基础文件名的一组数据。"""

    ai_name: str
    bj_path: Path
    source_base: str
    files: dict[str, Path] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionResult:
    """一次提取任务的统计结果。"""

    input_path: Path
    output_path: Path
    operation: Literal["复制", "移动"]
    started_at: datetime
    resume_enabled: bool = True
    finished_at: datetime | None = None
    elapsed_seconds: float = 0.0
    ai_folders: int = 0
    record_folders: int = 0
    bj_folders: int = 0
    scanned_files: int = 0
    recognized_files: Counter[str] = field(default_factory=Counter)
    unrecognized_files: int = 0
    data_groups: int = 0
    groups_with_front: int = 0
    groups_without_front: int = 0
    groups_with_all_labels: int = 0
    groups_missing_bmp: int = 0
    groups_missing_inf: int = 0
    groups_missing_txt: int = 0
    groups_only_front_1: int = 0
    groups_only_front_2: int = 0
    groups_with_both_fronts: int = 0
    transferred: Counter[str] = field(default_factory=Counter)
    transferred_bytes: int = 0
    resumed_files: int = 0
    deferred_files: int = 0
    renamed_groups: int = 0
    failed_files: int = 0
    missing_record_folders: list[Path] = field(default_factory=list)
    rename_details: list[tuple[Path, str, str]] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    per_ai: dict[str, Counter[str]] = field(default_factory=dict)
    report_path: Path | None = None

    @property
    def transferred_files(self) -> int:
        return sum(self.transferred.values())


class CheckpointStore:
    """使用 SQLite 持久化数据组命名和已完成文件，支持可靠断点继续。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                group_id TEXT PRIMARY KEY,
                input_path TEXT NOT NULL,
                operation TEXT NOT NULL,
                bj_relative TEXT NOT NULL,
                source_base TEXT NOT NULL,
                destination_base TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS completed_files (
                group_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                target_relative TEXT NOT NULL,
                source_size INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (group_id, file_type)
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def destination_bases(self, input_path: str, operation: str) -> set[str]:
        rows = self.connection.execute(
            """
            SELECT destination_base FROM groups
            WHERE input_path = ? AND operation = ?
            """,
            (input_path, operation),
        )
        return {row[0].casefold() for row in rows}

    def destination_base(self, group_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT destination_base FROM groups WHERE group_id = ?",
            (group_id,),
        ).fetchone()
        return row[0] if row else None

    def save_group(
        self,
        group_id: str,
        input_path: str,
        operation: str,
        bj_relative: str,
        source_base: str,
        destination_base: str,
        *,
        reset_completed: bool,
    ) -> None:
        if reset_completed:
            self.connection.execute(
                "DELETE FROM completed_files WHERE group_id = ?",
                (group_id,),
            )
        self.connection.execute(
            """
            INSERT INTO groups (
                group_id, input_path, operation, bj_relative,
                source_base, destination_base
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                input_path = excluded.input_path,
                operation = excluded.operation,
                bj_relative = excluded.bj_relative,
                source_base = excluded.source_base,
                destination_base = excluded.destination_base
            """,
            (
                group_id,
                input_path,
                operation,
                bj_relative,
                source_base,
                destination_base,
            ),
        )
        self.connection.commit()

    def completed_file(
        self,
        group_id: str,
        file_type: str,
    ) -> tuple[str, int] | None:
        row = self.connection.execute(
            """
            SELECT target_relative, source_size FROM completed_files
            WHERE group_id = ? AND file_type = ?
            """,
            (group_id, file_type),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def completed_target_exists(
        self,
        group_id: str,
        file_type: str,
        output_root: Path,
    ) -> bool:
        completed = self.completed_file(group_id, file_type)
        if completed is None:
            return False
        target_relative, recorded_size = completed
        target = output_root / Path(target_relative)
        try:
            return target.is_file() and target.stat().st_size == recorded_size
        except OSError:
            return False

    def mark_completed(
        self,
        group_id: str,
        file_type: str,
        source_name: str,
        target_relative: str,
        source_size: int,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO completed_files (
                group_id, file_type, source_name, target_relative,
                source_size, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id, file_type) DO UPDATE SET
                source_name = excluded.source_name,
                target_relative = excluded.target_relative,
                source_size = excluded.source_size,
                completed_at = excluded.completed_at
            """,
            (
                group_id,
                file_type,
                source_name,
                target_relative,
                source_size,
                datetime.now().astimezone().isoformat(timespec="seconds"),
            ),
        )
        # 每成功处理一个文件就提交，确保突然中断时已完成记录不会丢失。
        self.connection.commit()


def _sort_paths(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: str(path).casefold())


def _find_record_folder(ai_path: Path) -> Path | None:
    """查找 Ai 下名称为 Record 的直接子文件夹（忽略大小写）。"""
    try:
        children = ai_path.iterdir()
        return next(
            (
                child
                for child in children
                if child.is_dir() and child.name.casefold() == "record"
            ),
            None,
        )
    except OSError:
        return None


def _classify_file(path: Path) -> tuple[str, str] | None:
    """返回 ``(基础文件名, 文件类型)``；无法识别时返回 None。"""
    name = path.name
    lower_name = name.casefold()

    for variant in (1, 2, 3):
        suffix = f"_{variant}.jpg"
        if lower_name.endswith(suffix) and len(name) > len(suffix):
            file_type = f"front_{variant}" if variant in (1, 2) else "side_3"
            return name[: -len(suffix)], file_type

    suffix = path.suffix.casefold()
    if suffix in {".bin", ".bmp", ".inf", ".txt"} and path.stem:
        return path.stem, suffix[1:]
    return None


def _discover_ai_folders(source_root: Path) -> list[tuple[str, Path, Path | None]]:
    """发现输入根目录下的 Ai，并兼容直接传入单个 Ai 目录。"""
    root_record = _find_record_folder(source_root)
    if root_record is not None:
        return [(source_root.name, source_root, root_record)]

    ai_paths = _sort_paths([path for path in source_root.iterdir() if path.is_dir()])
    return [(path.name, path, _find_record_folder(path)) for path in ai_paths]


def _scan_groups(
    source_root: Path,
    result: ExtractionResult,
    *,
    show_progress: bool,
) -> list[DataGroup]:
    groups: list[DataGroup] = []
    ai_entries = _discover_ai_folders(source_root)
    result.ai_folders = len(ai_entries)
    bj_entries: list[tuple[str, Path]] = []

    for ai_name, ai_path, record_path in ai_entries:
        ai_stats: Counter[str] = Counter()
        result.per_ai[ai_name] = ai_stats
        if record_path is None:
            result.missing_record_folders.append(ai_path)
            ai_stats["missing_record"] += 1
            continue

        result.record_folders += 1
        bj_paths = _sort_paths(
            [path for path in record_path.iterdir() if path.is_dir()]
        )
        result.bj_folders += len(bj_paths)
        ai_stats["bj_folders"] += len(bj_paths)
        bj_entries.extend((ai_name, bj_path) for bj_path in bj_paths)

    if show_progress:
        print(
            f"发现 {result.ai_folders} 个 Ai、{result.record_folders} 个 Record、"
            f"{result.bj_folders} 个 Bj，开始扫描文件……"
        )

    bj_progress = tqdm(
        bj_entries,
        desc="扫描 Bj",
        unit="个",
        dynamic_ncols=True,
        disable=not show_progress,
    )
    for ai_name, bj_path in bj_progress:
        ai_stats = result.per_ai[ai_name]
        grouped_files: dict[str, DataGroup] = {}
        files = _sort_paths([path for path in bj_path.iterdir() if path.is_file()])
        result.scanned_files += len(files)
        ai_stats["scanned_files"] += len(files)

        for path in files:
            classified = _classify_file(path)
            if classified is None:
                result.unrecognized_files += 1
                ai_stats["unrecognized_files"] += 1
                continue

            source_base, file_type = classified
            result.recognized_files[file_type] += 1
            ai_stats[file_type] += 1
            key = source_base.casefold()
            group = grouped_files.setdefault(
                key,
                DataGroup(
                    ai_name=ai_name,
                    bj_path=bj_path,
                    source_base=source_base,
                ),
            )
            # Windows 文件系统通常不会出现仅大小写不同的同名文件。若在
            # 其他文件系统上遇到，保留排序后的第一个并把其余文件计为未识别。
            if file_type in group.files:
                result.unrecognized_files += 1
                ai_stats["unrecognized_files"] += 1
                continue
            group.files[file_type] = path

        groups.extend(grouped_files.values())

    groups.sort(
        key=lambda group: (
            group.ai_name.casefold(),
            str(group.bj_path).casefold(),
            group.source_base.casefold(),
        )
    )
    return groups


def _destination_name(file_type: str, destination_base: str, source: Path) -> str:
    if file_type == "front_1":
        return f"{destination_base}_1{source.suffix}"
    if file_type == "front_2":
        return f"{destination_base}_2{source.suffix}"
    return f"{destination_base}{source.suffix}"


def _existing_destination_bases(front_dir: Path, label_dir: Path) -> set[str]:
    """从既有输出中恢复已占用的逻辑基础文件名。"""
    bases: set[str] = set()
    if front_dir.is_dir():
        for path in front_dir.iterdir():
            classified = _classify_file(path)
            if path.is_file() and classified and classified[1] in FRONT_TYPES:
                bases.add(classified[0].casefold())
    if label_dir.is_dir():
        for path in label_dir.iterdir():
            classified = _classify_file(path)
            if path.is_file() and classified and classified[1] in LABEL_TYPES:
                bases.add(classified[0].casefold())
    return bases


def _choose_destination_base(source_base: str, used_bases: set[str]) -> str:
    candidate = source_base
    number = 2
    while candidate.casefold() in used_bases:
        candidate = f"{source_base}__{number}"
        number += 1
    used_bases.add(candidate.casefold())
    return candidate


def _group_id(
    source_root: Path,
    operation: str,
    group: DataGroup,
) -> tuple[str, str]:
    bj_relative = group.bj_path.relative_to(source_root).as_posix()
    identity = json.dumps(
        [
            str(source_root).casefold(),
            operation,
            bj_relative.casefold(),
            group.source_base.casefold(),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest(), bj_relative


def _checkpoint_says_completed(
    checkpoint: CheckpointStore,
    group_id: str,
    file_type: str,
    source: Path,
    target: Path,
    output_root: Path,
) -> bool:
    """检查目标文件是否已经完整写入，并补记意外中断前的成功结果。"""
    target_relative = target.relative_to(output_root).as_posix()
    completed = checkpoint.completed_file(group_id, file_type)
    if completed is not None:
        recorded_target, recorded_size = completed
        try:
            return (
                recorded_target == target_relative
                and target.is_file()
                and target.stat().st_size == recorded_size
            )
        except OSError:
            return False

    # 文件操作可能已成功、但进程恰好在写入检查点前中断。尺寸一致时将其
    # 视为已完成，避免再次覆盖；copy2/move 都会完整保留文件尺寸。
    try:
        source_size = source.stat().st_size
        if target.is_file() and target.stat().st_size == source_size:
            checkpoint.mark_completed(
                group_id,
                file_type,
                source.name,
                target_relative,
                source_size,
            )
            return True
    except OSError:
        return False
    return False


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def _escape_markdown(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _next_report_path(output_root: Path, started_at: datetime) -> Path:
    base = output_root / f"extraction_report_{started_at:%Y%m%d_%H%M%S}.md"
    if not base.exists():
        return base
    number = 2
    while True:
        candidate = base.with_name(f"{base.stem}__{number}{base.suffix}")
        if not candidate.exists():
            return candidate
        number += 1


def _render_report(result: ExtractionResult) -> str:
    finished_at = result.finished_at or datetime.now().astimezone()
    lines = [
        "# 门架数据提取统计报告",
        "",
        f"- 开始时间：{result.started_at:%Y-%m-%d %H:%M:%S %z}",
        f"- 完成时间：{finished_at:%Y-%m-%d %H:%M:%S %z}",
        f"- 耗时：{result.elapsed_seconds:.2f} 秒",
        f"- 操作方式：{result.operation}",
        f"- 断点继续：{'启用' if result.resume_enabled else '禁用'}",
        f"- 输入路径：`{result.input_path}`",
        f"- 输出路径：`{result.output_path}`",
        f"- 检查点：`{result.output_path / CHECKPOINT_FILENAME}`",
        "",
        "## 提取结果",
        "",
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| 有正面照的数据组 | {result.groups_with_front} |",
        f"| 成功{result.operation}的文件 | {result.transferred_files} |",
        f"| 断点继续跳过的已完成文件 | {result.resumed_files} |",
        f"| 因标签失败留待下次移动的正面照 | {result.deferred_files} |",
        f"| 成功处理的数据量 | {_format_bytes(result.transferred_bytes)} |",
        f"| `_1.jpg` | {result.transferred['front_1']} |",
        f"| `_2.jpg` | {result.transferred['front_2']} |",
        f"| `.bmp` | {result.transferred['bmp']} |",
        f"| `.inf` | {result.transferred['inf']} |",
        f"| `.txt` | {result.transferred['txt']} |",
        f"| 因重名而整组改名 | {result.renamed_groups} |",
        f"| 处理失败文件 | {result.failed_files} |",
        "",
        "## 扫描概况",
        "",
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| Ai 文件夹 | {result.ai_folders} |",
        f"| 找到的 Record 文件夹 | {result.record_folders} |",
        f"| 缺少 Record 的 Ai 文件夹 | {len(result.missing_record_folders)} |",
        f"| Bj 文件夹 | {result.bj_folders} |",
        f"| 扫描文件总数 | {result.scanned_files} |",
        f"| 识别到的数据组 | {result.data_groups} |",
        f"| 没有 `_1.jpg`/`_2.jpg` 的数据组 | {result.groups_without_front} |",
        f"| 未识别文件 | {result.unrecognized_files} |",
        f"| `_1.jpg` 源文件 | {result.recognized_files['front_1']} |",
        f"| `_2.jpg` 源文件 | {result.recognized_files['front_2']} |",
        f"| `.bmp` 源文件 | {result.recognized_files['bmp']} |",
        f"| `.inf` 源文件 | {result.recognized_files['inf']} |",
        f"| `.txt` 源文件 | {result.recognized_files['txt']} |",
        f"| `.bin`（未提取） | {result.recognized_files['bin']} |",
        f"| `_3.jpg`（未提取） | {result.recognized_files['side_3']} |",
        "",
        "## 数据完整性（仅统计有正面照的数据组）",
        "",
        "| 指标 | 数据组数 |",
        "|---|---:|",
        f"| 同时有 `_1.jpg` 和 `_2.jpg` | {result.groups_with_both_fronts} |",
        f"| 只有 `_1.jpg` | {result.groups_only_front_1} |",
        f"| 只有 `_2.jpg` | {result.groups_only_front_2} |",
        f"| `.bmp/.inf/.txt` 均存在 | {result.groups_with_all_labels} |",
        f"| 缺少 `.bmp` | {result.groups_missing_bmp} |",
        f"| 缺少 `.inf` | {result.groups_missing_inf} |",
        f"| 缺少 `.txt` | {result.groups_missing_txt} |",
        "",
        "## 按 Ai 文件夹统计",
        "",
        "| Ai | Bj 数 | 扫描文件 | 正面照源文件 | 标签源文件 | 未识别文件 |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for ai_name, stats in result.per_ai.items():
        front_count = stats["front_1"] + stats["front_2"]
        label_count = stats["bmp"] + stats["inf"] + stats["txt"]
        lines.append(
            f"| {_escape_markdown(ai_name)} | {stats['bj_folders']} | "
            f"{stats['scanned_files']} | {front_count} | {label_count} | "
            f"{stats['unrecognized_files']} |"
        )

    if result.missing_record_folders:
        lines.extend(["", "## 缺少 Record 的目录", ""])
        for path in result.missing_record_folders[:MAX_REPORT_DETAILS]:
            lines.append(f"- `{path}`")
        omitted = len(result.missing_record_folders) - MAX_REPORT_DETAILS
        if omitted > 0:
            lines.append(f"- 其余 {omitted} 项已省略。")

    if result.rename_details:
        lines.extend(
            [
                "",
                "## 重名改名明细",
                "",
                "同一数据组的正面照和标签会使用相同的新基础文件名。",
                "",
                "| 来源 Bj | 原基础名 | 输出基础名 |",
                "|---|---|---|",
            ]
        )
        for bj_path, old_base, new_base in result.rename_details[:MAX_REPORT_DETAILS]:
            lines.append(
                f"| {_escape_markdown(bj_path)} | {_escape_markdown(old_base)} | "
                f"{_escape_markdown(new_base)} |"
            )
        omitted = len(result.rename_details) - MAX_REPORT_DETAILS
        if omitted > 0:
            lines.append(f"\n其余 {omitted} 项已省略。")

    if result.errors:
        lines.extend(
            [
                "",
                "## 处理错误",
                "",
                "| 源文件 | 错误 |",
                "|---|---|",
            ]
        )
        for path, message in result.errors[:MAX_REPORT_DETAILS]:
            lines.append(
                f"| {_escape_markdown(path)} | {_escape_markdown(message)} |"
            )
        omitted = len(result.errors) - MAX_REPORT_DETAILS
        if omitted > 0:
            lines.append(f"\n其余 {omitted} 项已省略。")

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- `.bin` 与 `_3.jpg` 不会被复制或移动。",
            f"- 启用断点继续时，成功记录保存在 `{CHECKPOINT_FILENAME}`；请勿在任务完成前删除该文件。",
            "- 输出采用扁平目录；发生重名时会为整个数据组添加 `__2`、`__3` 等后缀，避免覆盖且保持图片与标签的名称对应关系。",
            "- 某个文件处理失败不会中断整个任务，失败详情见上方“处理错误”。",
            "",
        ]
    )
    return "\n".join(lines)


def extract_gantry_records(
    input_path: str | Path,
    output_path: str | Path,
    *,
    move: bool = False,
    resume: bool = True,
    show_progress: bool = True,
) -> ExtractionResult:
    """提取车辆正面照及对应标签，并在输出目录生成 Markdown 报告。

    Args:
        input_path: 包含多个 Ai 文件夹的输入根目录，也可直接传入单个 Ai。
        output_path: 输出根目录。
        move: ``False``（默认）为复制，``True`` 为移动。
        resume: ``True``（默认）时使用检查点跳过已成功处理的文件。
        show_progress: 是否在终端显示扫描和提取进度，默认显示。

    Returns:
        包含数量、数据完整性、错误和报告路径的统计结果。
    """
    source_root = Path(input_path).expanduser().resolve()
    destination_root = Path(output_path).expanduser().resolve()
    if not source_root.is_dir():
        raise NotADirectoryError(f"输入路径不存在或不是文件夹：{source_root}")
    if source_root == destination_root:
        raise ValueError("输入路径和输出路径不能相同")

    started_at = datetime.now().astimezone()
    started_counter = time.perf_counter()
    result = ExtractionResult(
        input_path=source_root,
        output_path=destination_root,
        operation="移动" if move else "复制",
        started_at=started_at,
        resume_enabled=resume,
    )

    # 先扫描再创建输出目录，避免 output_path 位于 input_path 内部时把本次
    # 新建的 front_view/label 误计为源数据目录。
    groups = _scan_groups(source_root, result, show_progress=show_progress)
    result.data_groups = len(groups)

    destination_root.mkdir(parents=True, exist_ok=True)
    front_dir = destination_root / "front_view"
    label_dir = destination_root / "label"
    front_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    used_bases = _existing_destination_bases(front_dir, label_dir)
    transfer = shutil.move if move else shutil.copy2
    operation_key = "move" if move else "copy"
    normalized_input = str(source_root).casefold()
    checkpoint = CheckpointStore(destination_root / CHECKPOINT_FILENAME)
    if resume:
        used_bases.update(
            checkpoint.destination_bases(normalized_input, operation_key)
        )

    eligible_groups = [
        group
        for group in groups
        if any(file_type in group.files for file_type in FRONT_TYPES)
    ]
    progress_total = sum(
        sum(file_type in group.files for file_type in (*LABEL_TYPES, *FRONT_TYPES))
        for group in eligible_groups
    )
    if show_progress:
        print(
            f"扫描完成：{result.scanned_files} 个文件、{len(groups)} 个数据组，"
            f"其中 {len(eligible_groups)} 个数据组有正面照。"
        )
        print(
            f"开始{result.operation}，断点继续已{'开启' if resume else '关闭'}……"
        )

    extraction_progress = tqdm(
        total=progress_total,
        desc=f"{result.operation}文件",
        unit="个",
        dynamic_ncols=True,
        disable=not show_progress,
    )

    def update_progress() -> None:
        extraction_progress.set_postfix(
            成功=result.transferred_files,
            续传跳过=result.resumed_files,
            失败=result.failed_files,
            待续=result.deferred_files,
            refresh=False,
        )
        extraction_progress.update(1)

    try:
        for group in groups:
            has_front_1 = "front_1" in group.files
            has_front_2 = "front_2" in group.files
            if not (has_front_1 or has_front_2):
                result.groups_without_front += 1
                continue

            result.groups_with_front += 1
            if has_front_1 and has_front_2:
                result.groups_with_both_fronts += 1
            elif has_front_1:
                result.groups_only_front_1 += 1
            else:
                result.groups_only_front_2 += 1

            group_id, bj_relative = _group_id(source_root, operation_key, group)
            destination_base = (
                checkpoint.destination_base(group_id) if resume else None
            )
            if destination_base is None:
                destination_base = _choose_destination_base(
                    group.source_base,
                    used_bases,
                )
                checkpoint.save_group(
                    group_id,
                    normalized_input,
                    operation_key,
                    bj_relative,
                    group.source_base,
                    destination_base,
                    reset_completed=not resume,
                )
            else:
                used_bases.add(destination_base.casefold())

            missing_labels = [
                kind
                for kind in LABEL_TYPES
                if kind not in group.files
                and not (
                    resume
                    and checkpoint.completed_target_exists(
                        group_id,
                        kind,
                        destination_root,
                    )
                )
            ]
            if not missing_labels:
                result.groups_with_all_labels += 1
            for kind in missing_labels:
                attribute = f"groups_missing_{kind}"
                setattr(result, attribute, getattr(result, attribute) + 1)

            if destination_base != group.source_base:
                result.renamed_groups += 1
                result.rename_details.append(
                    (group.bj_path, group.source_base, destination_base)
                )

            def process_file(file_type: str) -> bool:
                source = group.files.get(file_type)
                if source is None:
                    return True
                target_dir = front_dir if file_type in FRONT_TYPES else label_dir
                target = target_dir / _destination_name(
                    file_type,
                    destination_base,
                    source,
                )
                try:
                    if resume and _checkpoint_says_completed(
                        checkpoint,
                        group_id,
                        file_type,
                        source,
                        target,
                        destination_root,
                    ):
                        result.resumed_files += 1
                        result.per_ai[group.ai_name]["resumed"] += 1
                        return True

                    source_size = source.stat().st_size
                    # 仅清理由中断产生且未被检查点确认成功的不完整目标文件。
                    if target.exists():
                        target.unlink()
                    transfer(str(source), str(target))
                    checkpoint.mark_completed(
                        group_id,
                        file_type,
                        source.name,
                        target.relative_to(destination_root).as_posix(),
                        source_size,
                    )
                    result.transferred[file_type] += 1
                    result.transferred_bytes += source_size
                    result.per_ai[group.ai_name]["transferred"] += 1
                    return True
                except Exception as exc:  # 单文件失败不应中断整批数据
                    result.failed_files += 1
                    result.per_ai[group.ai_name]["failed"] += 1
                    result.errors.append((source, f"{type(exc).__name__}: {exc}"))
                    if show_progress:
                        extraction_progress.write(f"处理失败：{source}：{exc}")
                    return False
                finally:
                    update_progress()

            # 移动模式先处理标签，最后才移动正面照。若标签移动失败，保留正面照
            # 作为下次扫描该数据组的锚点，防止中断后剩余标签无法被发现。
            label_results = [
                process_file(kind) for kind in LABEL_TYPES if kind in group.files
            ]
            labels_succeeded = all(label_results)
            if move and not labels_succeeded:
                for kind in FRONT_TYPES:
                    if kind in group.files:
                        result.deferred_files += 1
                        update_progress()
                continue
            for kind in FRONT_TYPES:
                process_file(kind)
    finally:
        extraction_progress.close()
        checkpoint.close()

    result.finished_at = datetime.now().astimezone()
    result.elapsed_seconds = time.perf_counter() - started_counter
    report_path = _next_report_path(destination_root, result.started_at)
    report_path.write_text(_render_report(result), encoding="utf-8")
    result.report_path = report_path
    return result


if __name__ == "__main__":
    # ==================== 直接修改以下配置 ====================
    # 输入根目录：其中可以包含多个 Ai/Record/Bj，也可以直接指向单个 Ai。
    INPUT_PATH = r"D:\门架摄像头视频（抓拍图+视频）\内宜数据20260718"

    # 输出根目录：脚本会在这里创建 front_view、label 和统计报告。
    OUTPUT_PATH = r"C:\Users\imnew\projects\databases\llcom-reid-20260807"

    # False：复制文件（默认，保留源文件）；True：移动文件。
    MOVE_FILES = False

    # True：启用断点继续（默认），重复运行时跳过已经成功处理的文件；
    # False：忽略上次检查点，作为新任务提取（重名文件仍不会被覆盖）。
    RESUME = True

    # True：在终端显示扫描和文件处理进度；False：关闭进度显示。
    SHOW_PROGRESS = True
    # =========================================================

    try:
        extraction_result = extract_gantry_records(
            INPUT_PATH,
            OUTPUT_PATH,
            move=MOVE_FILES,
            resume=RESUME,
            show_progress=SHOW_PROGRESS,
        )
    except KeyboardInterrupt:
        print("\n任务已中断。检查点已保存，保持相同路径重新运行即可继续。")
        raise SystemExit(130) from None
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"{extraction_result.operation}完成。")
    print(f"  有正面照的数据组：{extraction_result.groups_with_front}")
    print(f"  成功处理文件：{extraction_result.transferred_files}")
    print(f"  断点续传跳过：{extraction_result.resumed_files}")
    print(f"  留待下次继续：{extraction_result.deferred_files}")
    print(f"  失败文件：{extraction_result.failed_files}")
    print(f"  输出数据量：{_format_bytes(extraction_result.transferred_bytes)}")
    print(f"  统计报告：{extraction_result.report_path}")
