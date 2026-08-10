"""按文件名末尾的 ``_1``、``_2`` 拆分门架正面照及对应标签。

预期输入结构由 ``extract_gantry_records.py`` 生成：

    input_path/
      front_view/
        123_1.jpg
        123_2.jpg
      label/
        123.bmp
        123.inf
        123.txt

输出目录直接创建在 ``input_path`` 内：

    input_path/
      front_view_1/
      front_view_2/
      label_1/
      label_2/

公共标签没有 ``_1``/``_2`` 后缀，因此会根据实际存在的正面照版本分别写入
``label_1`` 和/或 ``label_2``。默认复制文件；移动模式会先完成一个标签的
全部目标写入，再删除源标签，确保同一标签可以同时分配给两个版本。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from tqdm import tqdm


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CHECKPOINT_FILENAME = ".split_gantry_records_checkpoint.sqlite3"


@dataclass(slots=True)
class DataGroup:
    """具有同一逻辑基础文件名的一组正面照和标签。"""

    source_base: str
    fronts: dict[int, list[Path]] = field(
        default_factory=lambda: {1: [], 2: []}
    )
    labels: list[tuple[Path, tuple[int, ...]]] = field(default_factory=list)

    @property
    def variants(self) -> tuple[int, ...]:
        return tuple(variant for variant in (1, 2) if self.fronts[variant])


@dataclass(slots=True)
class SplitResult:
    """一次拆分任务的统计结果。"""

    input_path: Path
    operation: Literal["复制", "移动"]
    resume_enabled: bool
    elapsed_seconds: float = 0.0
    scanned_front_files: int = 0
    recognized_front_files: int = 0
    unrecognized_front_files: int = 0
    scanned_label_files: int = 0
    matched_label_files: int = 0
    orphan_label_files: int = 0
    data_groups: int = 0
    transferred_files: int = 0
    transferred_bytes: int = 0
    resumed_files: int = 0
    deferred_front_files: int = 0
    removed_source_labels: int = 0
    failed_files: int = 0
    variant_fronts: dict[int, int] = field(
        default_factory=lambda: {1: 0, 2: 0}
    )
    variant_labels: dict[int, int] = field(
        default_factory=lambda: {1: 0, 2: 0}
    )
    errors: list[tuple[Path, str]] = field(default_factory=list)


class CheckpointStore:
    """使用 SQLite 记录已完整写入的目标文件。"""

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS completed_files (
                task_id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                source_relative TEXT NOT NULL,
                target_relative TEXT NOT NULL,
                source_size INTEGER NOT NULL,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def completed_size(self, task_id: str, target_relative: str) -> int | None:
        row = self.connection.execute(
            """
            SELECT source_size FROM completed_files
            WHERE task_id = ? AND target_relative = ?
            """,
            (task_id, target_relative),
        ).fetchone()
        return int(row[0]) if row else None

    def mark_completed(
        self,
        task_id: str,
        operation: str,
        source_relative: str,
        target_relative: str,
        source_size: int,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO completed_files (
                task_id, operation, source_relative,
                target_relative, source_size
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                operation = excluded.operation,
                source_relative = excluded.source_relative,
                target_relative = excluded.target_relative,
                source_size = excluded.source_size,
                completed_at = CURRENT_TIMESTAMP
            """,
            (
                task_id,
                operation,
                source_relative,
                target_relative,
                source_size,
            ),
        )
        # 每个目标成功后立即提交，意外中断时可以从最后一个文件继续。
        self.connection.commit()


def _sort_paths(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: str(path).casefold())


def _front_identity(path: Path) -> tuple[str, int] | None:
    """返回正面照的 ``(基础文件名, 版本)``。"""
    if path.suffix.casefold() not in IMAGE_EXTENSIONS:
        return None
    lower_stem = path.stem.casefold()
    for variant in (1, 2):
        suffix = f"_{variant}"
        if lower_stem.endswith(suffix) and len(path.stem) > len(suffix):
            return path.stem[: -len(suffix)], variant
    return None


def _discover_groups(
    front_dir: Path,
    label_dir: Path,
    result: SplitResult,
) -> list[DataGroup]:
    groups: dict[str, DataGroup] = {}
    front_paths = _sort_paths(
        [path for path in front_dir.iterdir() if path.is_file()]
    )
    result.scanned_front_files = len(front_paths)

    for path in front_paths:
        identity = _front_identity(path)
        if identity is None:
            result.unrecognized_front_files += 1
            continue
        source_base, variant = identity
        group = groups.setdefault(
            source_base.casefold(),
            DataGroup(source_base=source_base),
        )
        group.fronts[variant].append(path)
        result.recognized_front_files += 1
        result.variant_fronts[variant] += 1

    label_paths = _sort_paths(
        [path for path in label_dir.iterdir() if path.is_file()]
    )
    result.scanned_label_files = len(label_paths)
    for path in label_paths:
        exact_group = groups.get(path.stem.casefold())
        if exact_group is not None:
            exact_group.labels.append((path, exact_group.variants))
            result.matched_label_files += 1
            continue

        # 兼容标签本身已经带有 _1/_2 后缀的情况；精确基础名匹配优先，
        # 因而不会误拆基础名本身恰好以 _1 或 _2 结尾的数据组。
        matched = False
        lower_stem = path.stem.casefold()
        for variant in (1, 2):
            suffix = f"_{variant}"
            if not lower_stem.endswith(suffix) or len(path.stem) <= len(suffix):
                continue
            group = groups.get(path.stem[: -len(suffix)].casefold())
            if group is not None and variant in group.variants:
                group.labels.append((path, (variant,)))
                result.matched_label_files += 1
                matched = True
            break
        if not matched:
            result.orphan_label_files += 1

    discovered = list(groups.values())
    discovered.sort(key=lambda group: group.source_base.casefold())
    result.data_groups = len(discovered)
    return discovered


def _task_id(
    root: Path,
    operation: str,
    source_relative: str,
    target_relative: str,
) -> str:
    identity = json.dumps(
        [
            str(root).casefold(),
            operation,
            source_relative.casefold(),
            target_relative.casefold(),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def split_gantry_records(
    input_path: str | Path,
    *,
    move: bool = False,
    resume: bool = True,
    show_progress: bool = True,
) -> SplitResult:
    """拆分 ``front_view`` 中的两个版本，并分配其对应标签。

    Args:
        input_path: 同时包含 ``front_view`` 和 ``label`` 的根目录。
        move: ``False``（默认）为复制，``True`` 为移动。
        resume: ``True``（默认）时跳过检查点中已完整写入的目标文件。
        show_progress: 是否显示扫描摘要和文件处理进度。

    Returns:
        本次扫描、处理、续传和失败情况的统计结果。
    """
    root = Path(input_path).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"输入路径不存在或不是文件夹：{root}")

    front_dir = root / "front_view"
    label_dir = root / "label"
    if not front_dir.is_dir():
        raise NotADirectoryError(f"缺少正面照文件夹：{front_dir}")
    if not label_dir.is_dir():
        raise NotADirectoryError(f"缺少标签文件夹：{label_dir}")

    started_counter = time.perf_counter()
    operation = "move" if move else "copy"
    result = SplitResult(
        input_path=root,
        operation="移动" if move else "复制",
        resume_enabled=resume,
    )

    # 先扫描源目录，再创建四个目标目录，目录始终位于 input_path 内。
    groups = _discover_groups(front_dir, label_dir, result)
    front_destinations = {
        1: root / "front_view_1",
        2: root / "front_view_2",
    }
    label_destinations = {
        1: root / "label_1",
        2: root / "label_2",
    }
    for destination in (*front_destinations.values(), *label_destinations.values()):
        destination.mkdir(parents=True, exist_ok=True)

    checkpoint = CheckpointStore(root / CHECKPOINT_FILENAME)
    progress_total = sum(
        sum(len(paths) for paths in group.fronts.values())
        + sum(len(variants) for _, variants in group.labels)
        for group in groups
    )
    if show_progress:
        print(
            f"扫描完成：{result.scanned_front_files} 个正面照文件、"
            f"{result.scanned_label_files} 个标签文件、{result.data_groups} 个数据组。"
        )
        print(
            f"开始{result.operation}，断点续传已{'开启' if resume else '关闭'}……"
        )

    progress = tqdm(
        total=progress_total,
        desc=f"{result.operation}文件",
        unit="个",
        dynamic_ncols=True,
        disable=not show_progress,
    )

    def update_progress() -> None:
        progress.set_postfix(
            成功=result.transferred_files,
            续传跳过=result.resumed_files,
            失败=result.failed_files,
            待续=result.deferred_front_files,
            refresh=False,
        )
        progress.update(1)

    def process_target(source: Path, target: Path, *, move_source: bool) -> bool:
        source_relative = source.relative_to(root).as_posix()
        target_relative = target.relative_to(root).as_posix()
        task_id = _task_id(
            root,
            operation,
            source_relative,
            target_relative,
        )
        try:
            source_size = source.stat().st_size
            if resume:
                recorded_size = checkpoint.completed_size(task_id, target_relative)
                if (
                    recorded_size is not None
                    and target.is_file()
                    and target.stat().st_size == recorded_size
                ):
                    result.resumed_files += 1
                    return True

                # 文件操作可能成功、但程序恰好在写检查点前中断。目标尺寸
                # 与源文件一致时补写检查点，避免重复覆盖。
                if (
                    recorded_size is None
                    and target.is_file()
                    and target.stat().st_size == source_size
                ):
                    checkpoint.mark_completed(
                        task_id,
                        operation,
                        source_relative,
                        target_relative,
                        source_size,
                    )
                    result.resumed_files += 1
                    return True

            if target.exists():
                target.unlink()
            if move_source:
                shutil.move(str(source), str(target))
            else:
                shutil.copy2(source, target)
            checkpoint.mark_completed(
                task_id,
                operation,
                source_relative,
                target_relative,
                source_size,
            )
            result.transferred_files += 1
            result.transferred_bytes += source_size
            return True
        except Exception as exc:  # 单个文件失败不应中断整批任务
            result.failed_files += 1
            result.errors.append((source, f"{type(exc).__name__}: {exc}"))
            if show_progress:
                progress.write(f"处理失败：{source} -> {target}：{exc}")
            return False
        finally:
            update_progress()

    try:
        for group in groups:
            labels_succeeded = True
            for label_path, variants in group.labels:
                label_succeeded = True
                for variant in variants:
                    target = label_destinations[variant] / label_path.name
                    succeeded = process_target(
                        label_path,
                        target,
                        move_source=False,
                    )
                    if succeeded:
                        result.variant_labels[variant] += 1
                    label_succeeded = label_succeeded and succeeded

                # 移动模式下，一个公共标签可能有两个目标，因此全部目标成功后
                # 才删除源文件；中断重跑时已完成目标会由检查点跳过。
                if move and label_succeeded and variants:
                    try:
                        label_path.unlink()
                        result.removed_source_labels += 1
                    except Exception as exc:
                        labels_succeeded = False
                        result.failed_files += 1
                        result.errors.append(
                            (label_path, f"{type(exc).__name__}: {exc}")
                        )
                        if show_progress:
                            progress.write(f"删除源标签失败：{label_path}：{exc}")
                labels_succeeded = labels_succeeded and label_succeeded

            front_count = sum(len(paths) for paths in group.fronts.values())
            if move and not labels_succeeded:
                result.deferred_front_files += front_count
                for _ in range(front_count):
                    update_progress()
                continue

            for variant in (1, 2):
                for front_path in group.fronts[variant]:
                    process_target(
                        front_path,
                        front_destinations[variant] / front_path.name,
                        move_source=move,
                    )
    finally:
        progress.close()
        checkpoint.close()

    result.elapsed_seconds = time.perf_counter() - started_counter
    return result


if __name__ == "__main__":
    # ==================== 直接修改以下配置 ====================
    # 输入根目录：内部应包含 extract_gantry_records.py 生成的
    # front_view 和 label；四个拆分结果文件夹也会创建在此目录内。
    INPUT_PATH = r"C:\Users\imnew\projects\databases\llcom-reid-20260810"

    # False：复制文件（默认，保留 front_view 和 label）；
    # True：移动文件。公共标签写入全部对应目标后才会删除源文件。
    MOVE_FILES = False

    # True：启用断点续传（默认），重复运行时跳过已经完整写入的目标；
    # False：忽略检查点并重新处理，已有的同名目标文件会被替换。
    RESUME = True

    # True：在终端显示扫描摘要和文件处理进度；False：关闭进度显示。
    SHOW_PROGRESS = True
    # =========================================================

    try:
        split_result = split_gantry_records(
            INPUT_PATH,
            move=MOVE_FILES,
            resume=RESUME,
            show_progress=SHOW_PROGRESS,
        )
    except KeyboardInterrupt:
        print("\n任务已中断。检查点已保存，保持相同配置重新运行即可继续。")
        raise SystemExit(130) from None
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"{split_result.operation}完成。")
    print(f"  数据组：{split_result.data_groups}")
    print(f"  `_1` 图片：{split_result.variant_fronts[1]}")
    print(f"  `_2` 图片：{split_result.variant_fronts[2]}")
    print(f"  写入 label_1：{split_result.variant_labels[1]}")
    print(f"  写入 label_2：{split_result.variant_labels[2]}")
    print(f"  成功处理目标：{split_result.transferred_files}")
    print(f"  断点续传跳过：{split_result.resumed_files}")
    print(f"  留待下次继续的正面照：{split_result.deferred_front_files}")
    print(f"  未匹配标签：{split_result.orphan_label_files}")
    print(f"  失败：{split_result.failed_files}")
    print(f"  处理数据量：{_format_bytes(split_result.transferred_bytes)}")
    print(f"  耗时：{split_result.elapsed_seconds:.2f} 秒")
