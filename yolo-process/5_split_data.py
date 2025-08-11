import os
import shutil
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


def split_yolo_dataset(path, val_ratio=0.2, seed=42, max_workers=8):
    """
    分割YOLO格式的数据集为train和val集

    参数:
        path (str): 数据集根目录路径，包含images和labels文件夹
        val_ratio (float): 验证集比例，默认0.2
        seed (int): 随机种子，默认42
        max_workers (int): 最大线程数，默认8
    """
    # 设置随机种子
    random.seed(seed)

    # 定义路径
    images_dir = os.path.join(path, 'images')
    labels_dir = os.path.join(path, 'labels')
    train_dir = os.path.join(path, 'train')
    val_dir = os.path.join(path, 'val')

    # 验证源文件夹存在
    if not os.path.exists(images_dir):
        raise FileNotFoundError(f"Images directory not found: {images_dir}")
    if not os.path.exists(labels_dir):
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")

    # 获取所有图像文件名（不带扩展名）
    image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not image_files:
        raise ValueError("No image files found in the images directory")

    # 获取基本文件名和扩展名
    base_names = [os.path.splitext(f)[0] for f in image_files]
    image_ext = os.path.splitext(image_files[0])[1]

    # 纯Python实现数据集分割
    random.shuffle(base_names)
    split_idx = int(len(base_names) * (1 - val_ratio))
    train_names = base_names[:split_idx]
    val_names = base_names[split_idx:]

    # 创建目标文件夹结构
    os.makedirs(os.path.join(train_dir, 'images'), exist_ok=True)
    os.makedirs(os.path.join(train_dir, 'labels'), exist_ok=True)
    os.makedirs(os.path.join(val_dir, 'images'), exist_ok=True)
    os.makedirs(os.path.join(val_dir, 'labels'), exist_ok=True)

    def process_files(names, dest_dir):
        """处理文件移动的多线程函数"""
        file_pairs = []

        for name in names:
            # 图像文件
            src_img = os.path.join(images_dir, f"{name}{image_ext}")
            dst_img = os.path.join(dest_dir, 'images', f"{name}{image_ext}")
            file_pairs.append((src_img, dst_img))

            # 标签文件
            src_label = os.path.join(labels_dir, f"{name}.txt")
            if os.path.exists(src_label):
                dst_label = os.path.join(dest_dir, 'labels', f"{name}.txt")
                file_pairs.append((src_label, dst_label))

        # 多线程移动文件
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(shutil.move, src, dst) for src, dst in file_pairs]
            for _ in tqdm(as_completed(futures), total=len(futures), desc=f"移动 {dest_dir} 文件"):
                pass

    # 处理训练集和验证集
    process_files(train_names, train_dir)
    process_files(val_names, val_dir)

    # 尝试删除空文件夹
    for dir_to_remove in [images_dir, labels_dir]:
        try:
            os.rmdir(dir_to_remove)
        except OSError:
            pass

    # 打印结果
    print("\n数据集分割完成！")
    print(f"训练集数量: {len(train_names)} 图像")
    print(f"验证集数量: {len(val_names)} 图像")
    print(f"验证集比例: {val_ratio:.2f}")
    print(f"随机种子: {seed}")


# 使用示例
if __name__ == "__main__":
    dataset_path = "./fire-smoke/combined-15000"  # 替换为你的数据集路径

    val_ratio = 0.2  # 验证集比例
    random_seed = 42  # 随机种子
    max_workers = 8

    split_yolo_dataset(dataset_path, val_ratio, random_seed, max_workers=max_workers)