import os


def sync_directories(img_dir, label_dir, pre_num=32):
    """
    对比两个文件夹中的文件，基于图片文件名的前pre_num个字符进行匹配。

    找出在其中一个文件夹中存在而在另一个中缺失的文件（基于特定的匹配规则），
    并提供交互式的删除选项。

    Parameters
    ----------
    img_dir : str
        包含 .png 图片文件的目录路径。
        匹配时将取文件主名（去除后缀）的前 pre_num 个字符。
    label_dir : str
        包含无后缀文件的目录路径。
        匹配时使用完整文件名。
    pre_num : int
        匹配文件的前pre_num个字符

    Returns
    -------
    None
        此函数直接将结果输出到标准输出（终端），并根据用户输入执行文件删除操作。
        不返回任何值。

    Notes
    -----
    匹配逻辑假设：
    img_filename[:pre_num] == label_filename
    """

    # 1. 检查路径是否存在
    if not os.path.exists(img_dir) or not os.path.exists(label_dir):
        print("错误：输入的文件夹路径不存在。")
        return

    # 2. 获取文件列表并构建映射
    # img_map: 键是文件名截取前pre_num位, 值是完整文件名(含.png)
    img_map = {}
    for f in os.listdir(img_dir):
        if f.lower().endswith('.png'):
            # 去除后缀
            name_no_ext = os.path.splitext(f)[0]
            # 核心修改：只取前pre_num个字符作为对比用的 Key
            key = name_no_ext[:pre_num]
            img_map[key] = f

    # label_map: 键是文件名, 值是文件名 (无后缀)
    label_map = {
        f: f
        for f in os.listdir(label_dir)
        if not f.startswith('.') and '.' not in f
    }

    img_set = set(img_map.keys())
    label_set = set(label_map.keys())

    # 3. 计算差异
    # 在图片文件夹里有(截取后)，但标签文件夹里没有
    extra_in_imgs = img_set - label_set
    # 在标签文件夹里有，但图片文件夹里没有(截取后)
    extra_in_labels = label_set - img_set

    # 4. 输出结果到终端
    if not extra_in_imgs and not extra_in_labels:
        print(f"完美匹配！图片名(前{pre_num}位)与标签名一一对应，无需操作。")
        return

    print("-" * 30)
    print(f"对比结果 (图片名仅对比前{pre_num}位):")

    if extra_in_imgs:
        print(f"\n[图片文件夹] 多余的文件 ({len(extra_in_imgs)} 个):")
        for key in extra_in_imgs:
            # 打印完整的原始文件名
            print(f"  - {img_map[key]}")

    if extra_in_labels:
        print(f"\n[无后缀文件夹] 多余的文件 ({len(extra_in_labels)} 个):")
        for key in extra_in_labels:
            print(f"  - {label_map[key]}")

    print("-" * 30)

    # 5. 交互操作
    user_input = input("输入 'd' 删除以上多余文件，输入 'n' 不操作退出: ").strip().lower()

    if user_input == 'd':
        print("\n开始删除...")
        count = 0

        # 删除多余的图片
        for key in extra_in_imgs:
            file_path = os.path.join(img_dir, img_map[key])
            try:
                os.remove(file_path)
                print(f"已删除: {file_path}")
                count += 1
            except OSError as e:
                print(f"删除失败 {file_path}: {e}")

        # 删除多余的无后缀文件
        for key in extra_in_labels:
            file_path = os.path.join(label_dir, label_map[key])
            try:
                os.remove(file_path)
                print(f"已删除: {file_path}")
                count += 1
            except OSError as e:
                print(f"删除失败 {file_path}: {e}")

        print(f"\n操作完成，共删除了 {count} 个文件。")

    elif user_input == 'n':
        print("操作已取消。")
    else:
        print("无效输入，程序退出。")

# --- 使用示例 ---
# path_img = r"C:\Dataset\images"
# path_lbl = r"C:\Dataset\labels"
# sync_directories(path_img, path_lbl)