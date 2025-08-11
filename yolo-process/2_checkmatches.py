"""
检查并清理指定相对目录path中images和labels文件夹不匹配的图像和标签文件
"""


import os
import argparse


def check_and_clean_dataset(folder_name, delete=False, mode='sep'):
    """
    检查并清理不匹配的图像和标签文件

    参数:
        folder_name: 包含图片标签或者包含images和labels文件夹的父目录
        delete: 是否直接删除不匹配的文件 (默认False，只显示)
        mode: .jpg和.txt是否在一起（默认'sep'不在一起，'tog'在一起）
    """
    # 定义路径
    images_dir = os.path.join(folder_name, 'images')
    labels_dir = os.path.join(folder_name, 'labels')

    # 确保文件夹存在
    if not os.path.exists(images_dir):
        print(f"错误: images文件夹不存在于 {folder_name}")
        return
    if not os.path.exists(labels_dir):
        print(f"错误: labels文件夹不存在于 {folder_name}")
        return

    # 获取所有文件（不带扩展名）
    image_files = {os.path.splitext(f)[0] for f in os.listdir(images_dir) if f.endswith('.jpg')}
    label_files = {os.path.splitext(f)[0] for f in os.listdir(labels_dir) if f.endswith('.txt')}

    # 找出不匹配的文件
    images_without_labels = image_files - label_files
    labels_without_images = label_files - image_files

    # 处理结果
    print("\n检查结果:")
    print(f"1. 有图片但无标签的文件 ({len(images_without_labels)}个):")
    for file in sorted(images_without_labels):
        print(f"  - {file}.jpg")

    print(f"\n2. 有标签但无图片的文件 ({len(labels_without_images)}个):")
    for file in sorted(labels_without_images):
        print(f"  - {file}.txt")

    # 如果需要删除文件
    if delete:
        print("\n开始删除不匹配的文件...")
        deleted_count = 0

        # 删除无标签的图片
        for file in images_without_labels:
            img_path = os.path.join(images_dir, f"{file}.jpg")
            os.remove(img_path)
            print(f"已删除: {img_path}")
            deleted_count += 1

        # 删除无图片的标签
        for file in labels_without_images:
            label_path = os.path.join(labels_dir, f"{file}.txt")
            os.remove(label_path)
            print(f"已删除: {label_path}")
            deleted_count += 1

        print(f"\n总共删除了 {deleted_count} 个文件")
    else:
        print("\n提示: 本次只显示不匹配的文件，如需删除请设置 delete=True")


if __name__ == "__main__":
    # # 设置命令行参数
    # parser = argparse.ArgumentParser(description='检查并清理不匹配的图像和标签文件')
    # parser.add_argument('folder', help='包含images和labels文件夹的目录')
    # parser.add_argument('--delete', action='store_true', help='是否直接删除不匹配的文件')
    #
    # args = parser.parse_args()

    # 执行检查
    # check_and_clean_dataset(args.folder, args.delete)

    path = './fire-smoke/combined'
    check_and_clean_dataset(path, delete=False)
