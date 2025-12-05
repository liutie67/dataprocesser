import os


def batch_rename_sequential(source_dir, new_prefix, start_index=0, dry_run=True):
    """
    将目录下的文件按顺序重命名为 "前缀_序号.后缀" 的格式。

    参数:
        source_dir (str): 源目录路径
        new_prefix (str): 新文件名的前缀
        start_index (int): 起始序号，默认从0开始
        dry_run (bool): 默认为 True，只打印不执行。确认无误后改为 False 执行。
    """
    if not os.path.exists(source_dir):
        print(f"目录不存在: {source_dir}")
        return

    # 1. 获取并排序所有文件
    files = []
    for f in os.listdir(source_dir):
        # 排除隐藏文件
        if f.startswith('.'):
            continue

        full_path = os.path.join(source_dir, f)
        # 排除文件夹
        if os.path.isfile(full_path):
            files.append(f)

    # 按原始文件名排序，保证重命名顺序的一致性
    files.sort()

    total_files = len(files)
    print(f"找到 {total_files} 个文件，准备重命名...")

    # 计算序号的填充长度 (例如 100 个文件，就需要 3 位数: 001, 002...)
    # 至少保留 3 位 (001)，如果文件更多则自动增加
    padding = max(3, len(str(total_files + start_index)))

    count = 0
    for i, filename in enumerate(files):
        # 获取原文件后缀 (包含点，例如 .jpg)
        _, ext = os.path.splitext(filename)

        # 构建新文件名
        current_idx = start_index + i
        new_filename = f"{new_prefix}_{str(current_idx).zfill(padding)}{ext}"

        old_path = os.path.join(source_dir, filename)
        new_path = os.path.join(source_dir, new_filename)

        # 检查是否需要重命名 (防止重名或无需修改)
        if filename == new_filename:
            continue

        # 防止覆盖已存在的同名文件
        if os.path.exists(new_path) and new_filename not in files:
            print(f"[跳过] 目标文件名已存在: {new_filename}")
            continue

        if dry_run:
            print(f"[预览] {filename}  -->  {new_filename}")
        else:
            try:
                os.rename(old_path, new_path)
                print(f"[成功] {filename}  -->  {new_filename}")
                count += 1
            except Exception as e:
                print(f"[失败] {filename}: {e}")

    if dry_run:
        print("\n--- 这是一个预览 (Dry Run) ---")
        print("请将 dry_run=False 传入函数以执行实际重命名。")
    else:
        print(f"\n完成！共重命名了 {count} 个文件。")

# 使用示例：
# batch_rename_sequential(r"C:\MyPhotos", "holiday", dry_run=True)


def batch_rename_replace(source_dir, old_str, new_str, dry_run=True):
    """
    将文件名中的指定字符串进行替换。
    """
    if not os.path.exists(source_dir):
        return

    count = 0
    for filename in os.listdir(source_dir):
        # 排除隐藏文件
        if filename.startswith('.'):
            continue

        full_path = os.path.join(source_dir, filename)

        # 排除文件夹
        if not os.path.isfile(full_path):
            continue

        # 检查文件名是否包含要替换的字符
        if old_str in filename:
            new_filename = filename.replace(old_str, new_str)
            new_path = os.path.join(source_dir, new_filename)

            if dry_run:
                print(f"[预览] {filename}  -->  {new_filename}")
            else:
                try:
                    os.rename(full_path, new_path)
                    print(f"[成功] {filename}  -->  {new_filename}")
                    count += 1
                except Exception as e:
                    print(f"[失败] {filename}: {e}")

    if dry_run:
        print("\n--- 预览模式 --- (设置 dry_run=False 以执行)")
    else:
        print(f"\n替换完成，共修改 {count} 个文件。")

# 使用示例：把所有文件名里的空格去掉
# batch_rename_replace(r"C:\Files", " ", "", dry_run=True)