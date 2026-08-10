"""检查正面照与 ``.bmp/.inf/.txt`` 标签是否完整对应。

照片记录号格式为 ``14 位日期时间_8 位编号``，例如：

    20260717121842_00077582.jpg
    20260717121842_00077582_1.jpg
    20260717121842_00077582_2.jpg
    20260717121842_00077582_其他后缀.jpg

以上照片都使用 ``20260717121842_00077582`` 作为记录号，并要求标签目录
中同时存在：

    20260717121842_00077582.bmp
    20260717121842_00077582.inf
    20260717121842_00077582.txt

发现任何不完整记录后，脚本会把全部明细输出到终端，并提示输入 ``y`` 或
``n``。输入 ``y`` 后，不完整记录在照片目录和标签目录中已有的文件会分别
移入各自目录下的 ``unmatched`` 文件夹；输入 ``n`` 不修改任何文件。
"""

from __future__ import annotations

import re
import shutil
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
REQUIRED_LABEL_EXTENSIONS = (".bmp", ".inf", ".txt")
RECORD_ID_PATTERN = re.compile(r"^(?P<record_id>\d{14}_\d{8})(?:_.+)?$")
STRICT_RECORD_ID_PATTERN = re.compile(r"^\d{14}_\d{8}$")


@dataclass(slots=True)
class UnmatchedFile:
    """一个需要报告并可选择移动的不匹配文件。"""

    path: Path
    reason: str


@dataclass(slots=True)
class AuditResult:
    """照片和标签对应关系检查结果。"""

    image_dir: Path
    label_dir: Path
    scanned_images: int = 0
    scanned_labels: int = 0
    ignored_image_files: int = 0
    ignored_label_files: int = 0
    complete_records: int = 0
    incomplete_records: int = 0
    unmatched_a: list[UnmatchedFile] = field(default_factory=list)
    unmatched_b: list[UnmatchedFile] = field(default_factory=list)
    moved_a: int = 0
    moved_b: int = 0
    failed_moves: int = 0
    elapsed_seconds: float = 0.0
    move_errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def unmatched_files(self) -> int:
        return len(self.unmatched_a) + len(self.unmatched_b)


def _sort_paths(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: str(path).casefold())


def _image_record_id(path: Path) -> str | None:
    """从照片名提取记录号，忽略记录号后的任意下划线后缀。"""
    match = RECORD_ID_PATTERN.fullmatch(path.stem)
    return match.group("record_id") if match else None


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


def audit_gantry_record_matches(
    image_dir: str | Path,
    label_dir: str | Path,
) -> AuditResult:
    """检查目录 A 中的照片是否与目录 B 中的三类标签完整对应。

    完整记录必须至少有一张照片，并且恰好具有一个 ``.bmp``、一个
    ``.inf`` 和一个 ``.txt`` 标签。标签缺失、重复、没有对应照片或文件名
    格式错误时，相关文件都会被归入不匹配列表。
    """
    started_counter = time.perf_counter()
    image_root = Path(image_dir).expanduser().resolve()
    label_root = Path(label_dir).expanduser().resolve()
    if not image_root.is_dir():
        raise NotADirectoryError(f"目录 A 不存在或不是文件夹：{image_root}")
    if not label_root.is_dir():
        raise NotADirectoryError(f"目录 B 不存在或不是文件夹：{label_root}")
    if image_root == label_root:
        raise ValueError("目录 A 和目录 B 不能是同一个文件夹")

    result = AuditResult(image_dir=image_root, label_dir=label_root)
    images_by_id: dict[str, list[Path]] = defaultdict(list)
    labels_by_id: dict[str, dict[str, list[Path]]] = defaultdict(
        lambda: defaultdict(list)
    )
    unmatched_a: dict[Path, str] = {}
    unmatched_b: dict[Path, str] = {}

    # 仅检查两个目录的直接子文件；各自已有的 unmatched 子目录不会被重扫。
    for path in _sort_paths(
        [candidate for candidate in image_root.iterdir() if candidate.is_file()]
    ):
        if path.suffix.casefold() not in IMAGE_EXTENSIONS:
            result.ignored_image_files += 1
            continue
        result.scanned_images += 1
        record_id = _image_record_id(path)
        if record_id is None:
            unmatched_a[path] = (
                "照片名不符合“14位日期时间_8位编号[_任意后缀]”格式"
            )
            continue
        images_by_id[record_id].append(path)

    for path in _sort_paths(
        [candidate for candidate in label_root.iterdir() if candidate.is_file()]
    ):
        extension = path.suffix.casefold()
        if extension not in REQUIRED_LABEL_EXTENSIONS:
            result.ignored_label_files += 1
            continue
        result.scanned_labels += 1
        if STRICT_RECORD_ID_PATTERN.fullmatch(path.stem) is None:
            unmatched_b[path] = "标签名不符合“14位日期时间_8位编号”格式"
            continue
        labels_by_id[path.stem][extension].append(path)

    all_record_ids = sorted(
        set(images_by_id) | set(labels_by_id),
        key=str.casefold,
    )
    for record_id in all_record_ids:
        images = images_by_id.get(record_id, [])
        labels = labels_by_id.get(record_id, {})
        missing_extensions = [
            extension
            for extension in REQUIRED_LABEL_EXTENSIONS
            if not labels.get(extension)
        ]
        duplicate_extensions = [
            extension
            for extension in REQUIRED_LABEL_EXTENSIONS
            if len(labels.get(extension, [])) > 1
        ]

        if images and not missing_extensions and not duplicate_extensions:
            result.complete_records += 1
            continue

        result.incomplete_records += 1
        reason_parts: list[str] = []
        if not images:
            reason_parts.append("目录 A 中没有对应照片")
        if missing_extensions:
            reason_parts.append(f"缺少标签：{', '.join(missing_extensions)}")
        if duplicate_extensions:
            reason_parts.append(f"标签重复：{', '.join(duplicate_extensions)}")
        reason = "；".join(reason_parts)

        for path in images:
            unmatched_a[path] = reason
        for paths in labels.values():
            for path in paths:
                unmatched_b[path] = reason

    result.unmatched_a = [
        UnmatchedFile(path=path, reason=reason)
        for path, reason in sorted(
            unmatched_a.items(),
            key=lambda item: str(item[0]).casefold(),
        )
    ]
    result.unmatched_b = [
        UnmatchedFile(path=path, reason=reason)
        for path, reason in sorted(
            unmatched_b.items(),
            key=lambda item: str(item[0]).casefold(),
        )
    ]
    result.elapsed_seconds = time.perf_counter() - started_counter
    return result


def print_audit_result(result: AuditResult) -> None:
    """把检查摘要和全部不匹配文件输出到终端。"""
    print("\n==================== 对应关系检查结果 ====================")
    print(f"目录 A：{result.image_dir}")
    print(f"目录 B：{result.label_dir}")
    print(f"扫描照片：{result.scanned_images}")
    print(f"扫描标签：{result.scanned_labels}")
    print(f"完整记录：{result.complete_records}")
    print(f"不完整记录：{result.incomplete_records}")
    print(f"目录 A 不匹配文件：{len(result.unmatched_a)}")
    print(f"目录 B 不匹配文件：{len(result.unmatched_b)}")
    print(f"目录 A 忽略的非照片文件：{result.ignored_image_files}")
    print(f"目录 B 忽略的非标签文件：{result.ignored_label_files}")

    if result.unmatched_a:
        print("\n-------------------- 目录 A 不匹配文件 --------------------")
        for item in result.unmatched_a:
            print(f"[A] {item.path.name}")
            print(f"    原因：{item.reason}")

    if result.unmatched_b:
        print("\n-------------------- 目录 B 不匹配文件 --------------------")
        for item in result.unmatched_b:
            print(f"[B] {item.path.name}")
            print(f"    原因：{item.reason}")

    if result.unmatched_files == 0:
        print("\n检查通过：目录 A 中的所有照片均具有完整对应标签，目录 B 中也没有孤立标签。")
    print("==========================================================")


def _confirm_move() -> bool:
    """只接受 y 或 n；输入无效时继续询问。"""
    while True:
        try:
            answer = input(
                "\n是否把上述不匹配文件移入各自目录下的 unmatched 文件夹？[y/n]："
            ).strip().casefold()
        except EOFError:
            print("\n未收到输入，本次不移动文件。")
            return False
        if answer == "y":
            return True
        if answer == "n":
            return False
        print("请输入 y 或 n。")


def move_unmatched_files(
    result: AuditResult,
    *,
    show_progress: bool = True,
) -> None:
    """把不匹配文件分别移入 A、B 目录下的 ``unmatched``。"""
    if result.unmatched_files == 0:
        return

    unmatched_a_dir = result.image_dir / "unmatched"
    unmatched_b_dir = result.label_dir / "unmatched"
    unmatched_a_dir.mkdir(parents=True, exist_ok=True)
    unmatched_b_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        *((item, unmatched_a_dir, "A") for item in result.unmatched_a),
        *((item, unmatched_b_dir, "B") for item in result.unmatched_b),
    ]

    progress = tqdm(
        tasks,
        desc="移动不匹配文件",
        unit="个",
        dynamic_ncols=True,
        disable=not show_progress,
    )
    for item, destination_dir, directory_name in progress:
        target = _next_available_path(destination_dir / item.path.name)
        try:
            shutil.move(str(item.path), str(target))
            if directory_name == "A":
                result.moved_a += 1
            else:
                result.moved_b += 1
        except Exception as exc:  # 单个文件失败不应中断其余文件
            result.failed_moves += 1
            result.move_errors.append(
                (item.path, f"{type(exc).__name__}: {exc}")
            )
            if show_progress:
                progress.write(f"移动失败：{item.path}：{exc}")
        progress.set_postfix(
            成功=result.moved_a + result.moved_b,
            失败=result.failed_moves,
            refresh=False,
        )


def check_and_prompt_move(
    image_dir: str | Path,
    label_dir: str | Path,
    *,
    show_progress: bool = True,
) -> AuditResult:
    """检查对应关系，输出全部异常，并询问是否移动不匹配文件。"""
    result = audit_gantry_record_matches(image_dir, label_dir)
    print_audit_result(result)
    if result.unmatched_files == 0:
        return result
    if not _confirm_move():
        print("已取消移动，所有文件保持原位。")
        return result

    move_unmatched_files(result, show_progress=show_progress)
    print("\n移动完成。")
    print(f"  目录 A -> unmatched：{result.moved_a}")
    print(f"  目录 B -> unmatched：{result.moved_b}")
    print(f"  移动失败：{result.failed_moves}")
    if result.move_errors:
        print("\n移动失败明细：")
        for path, message in result.move_errors:
            print(f"  {path}：{message}")
    return result


if __name__ == "__main__":
    # ==================== 直接修改以下配置 ====================
    # 目录 A：待检查的照片目录。
    IMAGE_DIR_A = (
        r"C:\Users\imnew\projects\databases\llcom-reid-20260810\front_view_1"
    )

    # 目录 B：与目录 A 对应的标签目录。
    LABEL_DIR_B = (
        r"C:\Users\imnew\projects\databases\llcom-reid-20260810\label_1"
    )

    # True：移动文件时显示进度；False：关闭进度显示。
    SHOW_PROGRESS = True
    # =========================================================

    try:
        audit_result = check_and_prompt_move(
            IMAGE_DIR_A,
            LABEL_DIR_B,
            show_progress=SHOW_PROGRESS,
        )
    except KeyboardInterrupt:
        print("\n任务已由用户中断。")
        raise SystemExit(130) from None
    except (OSError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error

