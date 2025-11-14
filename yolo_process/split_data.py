"""
Step 3

YOLO数据集分割模块

功能：将YOLO格式的数据集分割为训练集和验证集
支持多线程文件操作，提高大数据集处理效率

作者：LIU Tie
版本：1.0
日期：2025-11-14
"""

import os
import shutil
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


def split_yolo_dataset(path, val_ratio=0.2, seed=42, max_workers=8):
    """
    分割YOLO格式的数据集为训练集和验证集

    该函数会：
    1. 读取指定路径下的images和labels文件夹
    2. 按比例随机分割数据集为训练集和验证集
    3. 创建train和val文件夹结构
    4. 使用多线程移动对应的图片和标签文件
    5. 清理原始的images和labels空文件夹

    Args:
        path (str): 数据集根目录路径，包含images和labels文件夹
        val_ratio (float): 验证集比例，范围0-1，默认0.2（20%）
        seed (int): 随机种子，用于保证可重复性，默认42
        max_workers (int): 最大线程数，用于并行文件操作，默认8

    Returns:
        tuple: 返回两个列表 (train_names, val_names)
               - train_names: 训练集文件名列表（不含扩展名）
               - val_names: 验证集文件名列表（不含扩展名）

    Raises:
        FileNotFoundError: 当指定的路径或images/labels文件夹不存在时
        ValueError: 当没有找到图像文件或val_ratio超出范围时

    Example:
        >>> # 基本用法：使用默认参数
        >>> train_files, val_files = split_yolo_dataset('./dataset')
        >>>
        >>> # 自定义验证集比例和随机种子
        >>> split_yolo_dataset('./dataset', val_ratio=0.3, seed=123)
        >>>
        >>> # 使用更多线程加速处理
        >>> split_yolo_dataset('./dataset', max_workers=16)
        >>>
        >>> # 处理特定数据集
        >>> split_yolo_dataset('./fire-smoke/combined-15000')
    """
    # 参数验证
    if not 0 < val_ratio < 1:
        raise ValueError(f"val_ratio必须在0和1之间，当前值: {val_ratio}")

    if max_workers < 1:
        raise ValueError(f"max_workers必须大于0，当前值: {max_workers}")

    # 设置随机种子保证可重复性
    random.seed(seed)

    # 定义路径
    images_dir = os.path.join(path, 'images')
    labels_dir = os.path.join(path, 'labels')
    train_dir = os.path.join(path, 'train')
    val_dir = os.path.join(path, 'val')

    # 验证源文件夹存在
    if not os.path.exists(images_dir):
        raise FileNotFoundError(f"图片目录不存在: {images_dir}")
    if not os.path.exists(labels_dir):
        raise FileNotFoundError(f"标签目录不存在: {labels_dir}")

    print(f"🔍 开始处理数据集: {path}")
    print(f"📁 源图片目录: {images_dir}")
    print(f"📁 源标签目录: {labels_dir}")

    # 获取所有图像文件名
    image_files = [f for f in os.listdir(images_dir)
                   if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    if not image_files:
        raise ValueError(f"在图片目录中未找到任何图像文件: {images_dir}")

    # 获取基本文件名和扩展名
    base_names = [os.path.splitext(f)[0] for f in image_files]
    image_ext = os.path.splitext(image_files[0])[1]  # 假设所有图片扩展名相同

    print(f"📊 找到 {len(base_names)} 个图像文件")

    # 随机打乱并分割数据集
    random.shuffle(base_names)
    split_idx = int(len(base_names) * (1 - val_ratio))
    train_names = base_names[:split_idx]
    val_names = base_names[split_idx:]

    print(f"📋 数据集分割:")
    print(f"   - 训练集: {len(train_names)} 个样本 ({len(train_names) / len(base_names) * 100:.1f}%)")
    print(f"   - 验证集: {len(val_names)} 个样本 ({len(val_names) / len(base_names) * 100:.1f}%)")

    # 创建目标文件夹结构
    train_images_dir = os.path.join(train_dir, 'images')
    train_labels_dir = os.path.join(train_dir, 'labels')
    val_images_dir = os.path.join(val_dir, 'images')
    val_labels_dir = os.path.join(val_dir, 'labels')

    for dir_path in [train_images_dir, train_labels_dir, val_images_dir, val_labels_dir]:
        os.makedirs(dir_path, exist_ok=True)

    print("📁 创建目标目录结构完成")

    def process_files(names, dest_dir, dataset_type):
        """
        处理文件移动的多线程函数

        Args:
            names: 文件名列表（不含扩展名）
            dest_dir: 目标目录
            dataset_type: 数据集类型（'train' 或 'val'）
        """
        file_pairs = []
        missing_labels = 0

        for name in names:
            # 图像文件路径
            src_img = os.path.join(images_dir, f"{name}{image_ext}")
            dst_img = os.path.join(dest_dir, 'images', f"{name}{image_ext}")
            file_pairs.append((src_img, dst_img))

            # 标签文件路径
            src_label = os.path.join(labels_dir, f"{name}.txt")
            if os.path.exists(src_label):
                dst_label = os.path.join(dest_dir, 'labels', f"{name}.txt")
                file_pairs.append((src_label, dst_label))
            else:
                missing_labels += 1

        if missing_labels > 0:
            print(f"⚠️  警告: {dataset_type}集中有 {missing_labels} 个图像没有对应的标签文件")

        # 多线程移动文件
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(shutil.move, src, dst) for src, dst in file_pairs]

            # 使用进度条显示移动进度
            for future in tqdm(as_completed(futures), total=len(futures),
                               desc=f"🚚 移动 {dataset_type} 集文件"):
                try:
                    future.result()  # 获取结果，如有异常会抛出
                except Exception as e:
                    print(f"❌ 文件移动失败: {e}")

        return len(file_pairs)

    # 处理训练集和验证集
    print("\n" + "=" * 50)
    print("开始移动文件...")
    print("=" * 50)

    train_files_moved = process_files(train_names, train_dir, "训练")
    val_files_moved = process_files(val_names, val_dir, "验证")

    # 尝试删除原始的空文件夹
    print("\n🧹 清理原始目录...")
    for dir_to_remove in [images_dir, labels_dir]:
        try:
            if os.path.exists(dir_to_remove) and not os.listdir(dir_to_remove):
                os.rmdir(dir_to_remove)
                print(f"✅ 已删除空目录: {dir_to_remove}")
            elif os.path.exists(dir_to_remove):
                print(f"⚠️  目录非空，保留: {dir_to_remove}")
        except OSError as e:
            print(f"❌ 删除目录失败 {dir_to_remove}: {e}")

    # 打印最终结果
    print("\n" + "=" * 50)
    print("🎉 数据集分割完成！")
    print("=" * 50)
    print(f"📊 最终统计:")
    print(f"   - 训练集: {len(train_names)} 图像")
    print(f"   - 验证集: {len(val_names)} 图像")
    print(f"   - 验证集比例: {val_ratio:.2f} ({len(val_names) / len(base_names) * 100:.1f}%)")
    print(f"   - 随机种子: {seed}")
    print(f"   - 总移动文件数: {train_files_moved + val_files_moved}")
    print(f"📁 输出目录:")
    print(f"   - 训练集: {train_dir}")
    print(f"   - 验证集: {val_dir}")

    return train_names, val_names


def main():
    """
    命令行入口函数
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='分割YOLO格式的数据集为训练集和验证集',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  python split_data.py ./dataset                    # 使用默认参数
  python split_data.py ./dataset --val_ratio 0.3   # 自定义验证集比例
  python split_data.py ./dataset --seed 123        # 设置随机种子
  python split_data.py ./dataset --max_workers 16  # 使用更多线程
        '''
    )
    parser.add_argument('path', help='数据集根目录路径，包含images和labels文件夹')
    parser.add_argument('--val_ratio', type=float, default=0.2,
                        help='验证集比例，默认0.2')
    parser.add_argument('--seed', type=int, default=42,
                        help='随机种子，默认42')
    parser.add_argument('--max_workers', type=int, default=8,
                        help='最大线程数，默认8')

    args = parser.parse_args()

    try:
        split_yolo_dataset(
            path=args.path,
            val_ratio=args.val_ratio,
            seed=args.seed,
            max_workers=args.max_workers
        )
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # 示例用法
    dataset_path = "./fire-smoke/combined-15000"  # 替换为你的数据集路径

    # 参数配置
    val_ratio = 0.2  # 验证集比例
    random_seed = 42  # 随机种子
    max_workers = 8  # 最大线程数

    try:
        train_files, val_files = split_yolo_dataset(
            path=dataset_path,
            val_ratio=val_ratio,
            seed=random_seed,
            max_workers=max_workers
        )

        print(f"\n✅ 分割完成!")
        print(f"训练集样本: {len(train_files)} 个")
        print(f"验证集样本: {len(val_files)} 个")

    except Exception as e:
        print(f"❌ 数据集分割失败: {e}")