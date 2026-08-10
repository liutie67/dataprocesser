"""从目录 A 随机复制或移动指定数量的文件到目录 B。"""

from __future__ import annotations

import random
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm


@dataclass(slots=True)
class TransferResult:
    """一次随机文件抽取任务的统计结果。"""

    input_dir: Path
    output_dir: Path
    requested_files: int
    available_files: int
    operation: str
    selected_files: list[Path] = field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    transferred_bytes: int = 0
    errors: list[tuple[Path, str]] = field(default_factory=list)


def _next_available_path(path: Path) -> Path:
    """避免覆盖已有文件，重名时添加 ``__2``、``__3`` 等后缀。"""
    if not path.exists():
        return path
    number = 2
    while True:
        candidate = path.with_name(f"{path.stem}__{number}{path.suffix}")
        if not candidate.exists():
            return candidate
        number += 1


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def random_transfer_files(
    input_dir: str | Path,
    output_dir: str | Path,
    count: int = 100,
    *,
    move: bool = False,
    random_seed: int | None = None,
    show_progress: bool = True,
) -> TransferResult:
    """从目录 A 的直接子文件中随机复制或移动 ``count`` 个到目录 B。

    Args:
        input_dir: 输入目录 A，仅扫描其直接子文件。
        output_dir: 输出目录 B，不存在时自动创建。
        count: 随机抽取数量，默认 100。
        move: ``False``（默认）为复制，``True`` 为移动。
        random_seed: 随机种子。默认为 ``None``，每次运行随机结果不同；设置
            为固定整数后，相同文件集合会得到可重复的抽样结果。
        show_progress: 是否显示文件处理进度。

    Returns:
        包含抽取文件、成功数、失败数和数据量的统计结果。
    """
    source_root = Path(input_dir).expanduser().resolve()
    destination_root = Path(output_dir).expanduser().resolve()
    if not source_root.is_dir():
        raise NotADirectoryError(f"目录 A 不存在或不是文件夹：{source_root}")
    if source_root == destination_root:
        raise ValueError("目录 A 和目录 B 不能是同一个文件夹")
    if count < 0:
        raise ValueError(f"抽取数量不能小于 0：{count}")

    # 先收集文件再创建目录 B，避免目录 B 位于目录 A 内时影响候选文件集合。
    candidates = sorted(
        (path for path in source_root.iterdir() if path.is_file()),
        key=lambda path: str(path).casefold(),
    )
    available_files = len(candidates)
    if available_files < count:
        raise ValueError(
            f"目录 A 只有 {available_files} 个文件，无法抽取 {count} 个文件"
        )

    rng = random.Random(random_seed)
    selected_files = rng.sample(candidates, count)
    destination_root.mkdir(parents=True, exist_ok=True)
    result = TransferResult(
        input_dir=source_root,
        output_dir=destination_root,
        requested_files=count,
        available_files=available_files,
        operation="移动" if move else "复制",
        selected_files=selected_files,
    )
    transfer = shutil.move if move else shutil.copy2

    progress = tqdm(
        selected_files,
        desc=f"{result.operation}文件",
        unit="个",
        dynamic_ncols=True,
        disable=not show_progress,
    )
    for source in progress:
        target = _next_available_path(destination_root / source.name)
        try:
            source_size = source.stat().st_size
            transfer(str(source), str(target))
            result.succeeded += 1
            result.transferred_bytes += source_size
        except Exception as exc:  # 单个文件失败不应中断其余文件
            result.failed += 1
            result.errors.append((source, f"{type(exc).__name__}: {exc}"))
            if show_progress:
                progress.write(f"处理失败：{source}：{exc}")
        progress.set_postfix(
            成功=result.succeeded,
            失败=result.failed,
            refresh=False,
        )

    return result


if __name__ == "__main__":
    # ==================== 直接修改以下配置 ====================
    # 输入目录 A：只随机抽取此目录下的直接子文件，不递归扫描子文件夹。
    INPUT_DIR_A = r"C:\Users\imnew\projects\databases\llcom-reid-20260810\front_view_1"

    # 输出目录 B：不存在时自动创建。
    OUTPUT_DIR_B = r"C:\Users\imnew\projects\databases\llcom-reid-20260810\front_view_test10000"

    # 随机抽取的文件数量。
    C = 10000

    # False：复制文件（默认，保留目录 A 中的源文件）；True：移动文件。
    MOVE_FILES = False

    # None：每次运行使用不同的随机结果；设置为固定整数（如 2026）后，
    # 对相同的候选文件集合可重复得到相同抽样结果。
    RANDOM_SEED = 67

    # True：显示处理进度；False：关闭进度显示。
    SHOW_PROGRESS = True
    # =========================================================

    try:
        transfer_result = random_transfer_files(
            INPUT_DIR_A,
            OUTPUT_DIR_B,
            C,
            move=MOVE_FILES,
            random_seed=RANDOM_SEED,
            show_progress=SHOW_PROGRESS,
        )
    except KeyboardInterrupt:
        print("\n任务已由用户中断。")
        raise SystemExit(130) from None
    except (OSError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"{transfer_result.operation}完成。")
    print(f"  目录 A 文件数：{transfer_result.available_files}")
    print(f"  随机抽取：{transfer_result.requested_files}")
    print(f"  成功：{transfer_result.succeeded}")
    print(f"  失败：{transfer_result.failed}")
    print(f"  处理数据量：{_format_bytes(transfer_result.transferred_bytes)}")
    print(f"  输出目录：{transfer_result.output_dir}")

