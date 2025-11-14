"""
文件整理模块

功能：将指定目录中的图片文件和文本标签文件分别移动到images和labels文件夹中
适用于YOLO等深度学习项目的数据集整理

作者：LIU Tie
版本：1.0
日期：2024-01-01
"""

import os
import shutil
from tqdm import tqdm
import logging


def convert(path='', log=False):
    """
    整理数据集文件，适用于图片和标签放在一个文件夹时，将图片和标签文件分开到两个文件夹。

    该函数会：
    1. 在输入的指定路径下创建images和labels文件夹
    2. 将图片文件(.jpg, .jpeg, .png, .bmp, .gif)移动到images文件夹
    3. 将标签文件(.txt)移动到labels文件夹
    4. 可选生成详细的操作日志

    Args:
        path (str): 要处理的目录路径，默认为当前目录
        log (bool): 是否生成日志文件，默认为False

    Returns:
        None

    Raises:
        OSError: 当目录创建或文件移动失败时可能抛出

    Example:
        >>> # 基本用法
        >>> convert('./dataset')
        >>>
        >>> # 启用日志记录
        >>> convert('./dataset', log=True)
        >>>
        >>> # 处理当前目录
        >>> convert()
    """
    # 配置日志
    if log:
        logging.basicConfig(
            filename='convert.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.info(f"📄 开始处理目录: {path}")

    # 获取要处理的目录路径
    current_dir = path
    if log:
        logging.info(f"📁 当前处理目录: {current_dir}")

    # 定义目标文件夹路径
    images_dir = os.path.join(current_dir, 'images')
    labels_dir = os.path.join(current_dir, 'labels')

    # 创建 images 和 labels 文件夹（如果不存在）
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    if log:
        logging.info("✅ 已创建 images/ 和 labels/ 目录（如已存在则跳过）")

    # 支持的图片扩展名
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']

    # 获取当前目录下的所有文件（仅文件，排除自身）
    all_files = [
        f for f in os.listdir(current_dir)
        if os.path.isfile(os.path.join(current_dir, f)) and
        f != os.path.basename(__file__)  # 排除本脚本文件
    ]

    # 统计移动的文件数量
    moved_images = 0
    moved_labels = 0

    # 使用进度条显示处理进度
    with tqdm(total=len(all_files), desc="📦 文件整理进度") as pbar:
        for filename in all_files:
            file_path = os.path.join(current_dir, filename)
            name, ext = os.path.splitext(filename)

            try:
                # 处理图片文件
                if ext.lower() in image_extensions:
                    dst = os.path.join(images_dir, filename)
                    shutil.move(file_path, dst)
                    moved_images += 1
                    if log:
                        logging.info(f"🖼️ 移动图片: {filename} -> images/")

                # 处理标签文件
                elif ext.lower() == '.txt':
                    dst = os.path.join(labels_dir, filename)
                    shutil.move(file_path, dst)
                    moved_labels += 1
                    if log:
                        logging.info(f"🏷️ 移动标签: {filename} -> labels/")

            except Exception as e:
                error_msg = f"⚠️ 移动 {filename} 出错: {e}"
                if log:
                    logging.error(error_msg)
                else:
                    print(error_msg)
            finally:
                pbar.update(1)

    # 输出处理结果统计
    result_msg = f"""
✨ 文件整理完成！
📊 处理统计:
   - 移动图片文件: {moved_images} 个
   - 移动标签文件: {moved_labels} 个
   - 总处理文件: {len(all_files)} 个
"""
    print(result_msg)

    if log:
        logging.info(f"✅ 所有文件处理完成，共移动{moved_images}张图片和{moved_labels}个标签")
        logging.info("=" * 50)
        print("📝 详细日志已保存到 convert.log")


if __name__ == "__main__":
    # 示例用法
    path = './fire-smoke/smoke'
    convert(path, log=False)

    # 其他使用示例：
    # convert()                    # 处理当前目录
    # convert('./dataset')         # 处理指定目录
    # convert('./data', log=True)  # 处理目录并生成日志