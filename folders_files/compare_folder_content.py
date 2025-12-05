import os
import shutil
from pathlib import Path


def compare_and_clean_directories(source_dir, dest_dir):
    """
    对比两个目录的文件名。
    1. 打印对比情况。
    2. 如果 dest_dir 有多余文件，询问用户如何处理 (删除/移动/忽略)。
    """

    print(f"\n正在对比目录...")
    print(f"源目录:\t {source_dir}")
    print(f"目标目录:\t {dest_dir}")
    print("-" * 30)

    # --- 1. 获取源目录所有文件名 (递归，集合) ---
    source_filenames = set()
    for root, dirs, files in os.walk(source_dir):
        # 排除隐藏文件夹
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            # 排除隐藏文件
            if not f.startswith('.'):
                source_filenames.add(f)

    # --- 2. 获取目标目录所有文件名及路径 (单层，字典映射) ---
    # 格式: {'filename.txt': '/path/to/dest/filename.txt'}
    dest_files_map = {}
    if os.path.exists(dest_dir):
        for f in os.listdir(dest_dir):
            full_path = os.path.join(dest_dir, f)
            # 排除隐藏文件和文件夹
            if not f.startswith('.') and os.path.isfile(full_path):
                dest_files_map[f] = full_path
    else:
        print(f"错误: 目标目录不存在 {dest_dir}")
        return

    dest_filenames = set(dest_files_map.keys())

    # --- 3. 集合运算 ---
    common_files = source_filenames & dest_filenames
    missing_in_dest = source_filenames - dest_filenames  # 源里有，目标里没有
    extra_in_dest = dest_filenames - source_filenames  # 目标里有，源里没有 (多余的)

    # --- 4. 打印结果 ---
    print(f"对比结果:")
    print(f"  - 共同文件:\t {len(common_files)} 个")
    print(f"  - 源目录独有 (目标缺失):\t {len(missing_in_dest)} 个")
    print(f"  - 目标目录多余 (Extra):\t {len(extra_in_dest)} 个")

    # --- 5. 处理多余文件 ---
    if len(extra_in_dest) > 0:
        print(f"\n发现 {len(extra_in_dest)} 个多余文件 (仅存在于目标目录):")
        # 打印前5个示例，避免刷屏
        for i, name in enumerate(list(extra_in_dest)[:5]):
            print(f"  * {name}")
        if len(extra_in_dest) > 5:
            print(f"  ... 等 (共 {len(extra_in_dest)} 个)")

        while True:
            choice = input("\n请选择操作: [d]删除 / [y]移入extra文件夹 / [n]不做处理: ").lower().strip()

            if choice == 'n':
                print("操作取消，未做任何更改。")
                break

            elif choice == 'd':
                confirm = input(f"警告: 确定要永久删除这 {len(extra_in_dest)} 个文件吗? (y/n): ")
                if confirm.lower() == 'y':
                    count = 0
                    for name in extra_in_dest:
                        path_to_remove = dest_files_map[name]
                        try:
                            os.remove(path_to_remove)
                            count += 1
                        except Exception as e:
                            print(f"删除失败 {name}: {e}")
                    print(f"已删除 {count} 个文件。")
                else:
                    print("取消删除。")
                break

            elif choice == 'y':
                extra_dir = os.path.join(dest_dir, "extra")
                Path(extra_dir).mkdir(parents=True, exist_ok=True)

                count = 0
                for name in extra_in_dest:
                    src_path = dest_files_map[name]
                    target_path = os.path.join(extra_dir, name)

                    # 处理重名 (如果extra里已经有了)
                    if os.path.exists(target_path):
                        base, ext = os.path.splitext(name)
                        c = 1
                        while os.path.exists(os.path.join(extra_dir, f"{base}_{c}{ext}")):
                            c += 1
                        target_path = os.path.join(extra_dir, f"{base}_{c}{ext}")

                    try:
                        shutil.move(src_path, target_path)
                        count += 1
                    except Exception as e:
                        print(f"移动失败 {name}: {e}")

                print(f"已将 {count} 个文件移动到: {extra_dir}")
                break
            else:
                print("输入无效，请输入 d, y 或 n")
    else:
        print("\n目标目录非常干净，没有多余文件。")

# 使用示例
# compare_and_clean_directories("./source_files", "./dest_files")