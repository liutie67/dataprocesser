import os
import shutil
import sys
from pathlib import Path
from typing import List, Set, Tuple, Optional


def flatten_dataset(src_root: str, dst_root: Optional[str] = None) -> None:
    """
    交互式地将层级化的图像和标签数据集扁平化到目标目录。

    该函数分析源目录中的 'images' 和 'labels' 文件夹结构（Level A -> Level B -> Level C），
    检查对应关系，允许用户交互式选择要处理的子目录（Level B）和类别（Level C），
    并将所有选定的文件扁平化复制到目标目录中。文件名将被重命名以防止冲突。

    Parameters
    ----------
    src_root : str
        源数据集的父目录路径（Level A）。该目录下必须包含 'images' 和 'labels' 两个文件夹。
    dst_root : str, optional
        输出目录的路径。如果为 None（默认），将在 src_root 同级目录下创建一个
        名为 "{src_root_name}_subset1" 的文件夹（如果存在则递增后缀）。

    Returns
    -------
    None
        该函数没有返回值，但会在文件系统中创建新的目录结构并打印处理日志。

    Raises
    ------
    FileNotFoundError
        如果源目录下不存在 'images' 或 'labels' 文件夹。
    """

    src_path = Path(src_root)
    img_root = src_path / "images"
    lbl_root = src_path / "labels"

    if not img_root.exists() or not lbl_root.exists():
        raise FileNotFoundError(f"源路径下必须包含 'images' 和 'labels' 文件夹: {src_root}")

    # ==========================================
    # 步骤 1 & 3: 处理 B 级目录 (Dataset Subsets)
    # ==========================================
    print(f"\n[1/4] 分析 B 级目录 (子数据集)...")

    b_imgs = {d.name for d in img_root.iterdir() if d.is_dir()}
    b_lbls = {d.name for d in lbl_root.iterdir() if d.is_dir()}

    # 找交集和差集
    common_b = sorted(list(b_imgs & b_lbls))
    only_img_b = b_imgs - b_lbls
    only_lbl_b = b_lbls - b_imgs

    # 打印不匹配的情况
    if only_img_b:
        print(f"警告: 以下文件夹仅在 images 中存在 (将被跳过): {', '.join(only_img_b)}")
    if only_lbl_b:
        print(f"警告: 以下文件夹仅在 labels 中存在 (将被跳过): {', '.join(only_lbl_b)}")

    if not common_b:
        print("错误: 没有找到一一对应的 B 级文件夹。程序结束。")
        return

    # 用户选择 B 级目录
    selected_b_names = _interactive_select(common_b, "请选择要合并的 B 级文件夹")
    if not selected_b_names:
        print("未选择任何文件夹。程序结束。")
        return

    # ==========================================
    # 步骤 4: 处理 C 级目录 (Classes)
    # ==========================================
    print(f"\n[2/4] 分析 C 级目录 (类别)...")

    # 收集所有选定 B 级目录下的 C 级目录情况
    # 结构: c_map = { 'class_name': ['b_folder_1', 'b_folder_2'] }
    c_map_img = {}
    c_map_lbl = {}

    for b_name in selected_b_names:
        # 扫描 images/b_name 下的 c级
        for c_dir in (img_root / b_name).iterdir():
            if c_dir.is_dir():
                c_map_img.setdefault(c_dir.name, set()).add(b_name)

        # 扫描 labels/b_name 下的 c级
        for c_dir in (lbl_root / b_name).iterdir():
            if c_dir.is_dir():
                c_map_lbl.setdefault(c_dir.name, set()).add(b_name)

    all_c_names = set(c_map_img.keys()) | set(c_map_lbl.keys())
    valid_c_names = []

    # 分析 C 级对应关系
    print(f"正在检查 {len(selected_b_names)} 个 B 级文件夹内的类别完整性...")
    for c_name in sorted(list(all_c_names)):
        b_with_img = c_map_img.get(c_name, set())
        b_with_lbl = c_map_lbl.get(c_name, set())

        common_parent = b_with_img & b_with_lbl
        missing_lbl = b_with_img - b_with_lbl
        missing_img = b_with_lbl - b_with_img

        if common_parent:
            valid_c_names.append(c_name)

        # 只有当存在不匹配时才打印细节，避免刷屏
        if missing_lbl or missing_img:
            print(f"  - 类别 '{c_name}':")
            if missing_lbl:
                print(f"    在以下 B 级目录中缺少 Labels: {', '.join(missing_lbl)}")
            if missing_img:
                print(f"    在以下 B 级目录中缺少 Images: {', '.join(missing_img)}")

    if not valid_c_names:
        print("没有发现任何具有成对图片和标签的类别。程序结束。")
        return

    # 用户选择 C 级目录
    selected_c_names = _interactive_select(valid_c_names, "请选择要合并的类别 (C级)")
    if not selected_c_names:
        print("未选择任何类别。程序结束。")
        return

    # ==========================================
    # 步骤 5: 确定输出路径
    # ==========================================
    if dst_root:
        out_path = Path(dst_root)
    else:
        # 自动生成名称: parent/name_subset1, subset2...
        counter = 1
        while True:
            candidate = src_path.parent / f"{src_path.name}_subset{counter}"
            if not candidate.exists():
                out_path = candidate
                break
            counter += 1

    out_img_dir = out_path / "images"
    out_lbl_dir = out_path / "labels"

    # 创建目录
    try:
        out_img_dir.mkdir(parents=True, exist_ok=True)
        out_lbl_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[3/4] 输出目录已创建: {out_path}")
    except OSError as e:
        print(f"无法创建目录: {e}")
        return

    # ==========================================
    # 执行扁平化复制
    # ==========================================
    print(f"\n[4/4] 开始复制并扁平化文件...")
    count = 0

    for b_name in selected_b_names:
        for c_name in selected_c_names:
            src_i_dir = img_root / b_name / c_name
            src_l_dir = lbl_root / b_name / c_name

            # 再次确认这对目录都存在 (因为之前是聚合检查的)
            if src_i_dir.exists() and src_l_dir.exists():
                # 获取该C级目录下的所有文件
                # 假设文件名是一一对应的（通常去掉扩展名后一致），这里简单起见分别遍历
                # 为了防止不同文件夹下有同名文件（如 001.jpg），扁平化时需要重命名
                # 命名格式: B名_C名_原文件名

                # 处理 Images
                for f in src_i_dir.iterdir():
                    if f.is_file():
                        new_name = f"{b_name}_{c_name}_{f.name}"
                        shutil.copy2(f, out_img_dir / new_name)

                # 处理 Labels
                for f in src_l_dir.iterdir():
                    if f.is_file():
                        new_name = f"{b_name}_{c_name}_{f.name}"
                        shutil.copy2(f, out_lbl_dir / new_name)
                        count += 1

                # 简单的进度打印
                print(f"  已处理: {b_name}/{c_name}", end='\r')

    print(f"\n\n完成! 共处理了约 {count} 组数据 (以Label文件夹计数)。")
    print(f"结果保存在: {out_path.absolute()}")


def _interactive_select(items: List[str], prompt_text: str) -> List[str]:
    """
    辅助函数：显示列表并解析用户输入的数字选择。
    """
    print(f"\n--- {prompt_text} ---")
    print(f"[0] 全选 (All)")
    for idx, item in enumerate(items, 1):
        print(f"[{idx}] {item}")

    while True:
        choice = input("\n请输入编号 (例如 1,3 或 0 全选): ").strip()
        if not choice:
            continue

        # 处理全选
        if choice == '0':
            return items

        try:
            # 解析输入 "1, 2, 5" -> [0, 1, 4] (indices)
            indices = [int(x.strip()) - 1 for x in choice.replace('，', ',').split(',')]

            # 验证索引范围
            selected = []
            for i in indices:
                if 0 <= i < len(items):
                    selected.append(items[i])
                else:
                    print(f"警告: 编号 {i + 1} 超出范围，已忽略。")

            if selected:
                return selected
            else:
                print("无效的选择，请重新输入。")
        except ValueError:
            print("输入格式错误，请输入数字，用逗号分隔。")


# 使用示例
if __name__ == "__main__":
    # 假设你的数据在当前目录下的 data_root
    # flatten_dataset("./data_root")

    # 或者手动输入路径进行测试
    path = input("请输入A级父目录路径: ").strip()
    if path:
        flatten_dataset(path)