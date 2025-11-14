"""
Step 1 convert.py

将指定相对目录path的.jpg和.txt分别放在path新建的images和lables文件夹中
"""


import os
import shutil
from tqdm import tqdm
import logging


def convert(path='', log=False):
    # 配置日志
    if log:
        logging.basicConfig(
            filename='convert.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    # 当前目录
    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # current_dir = os.path.join(current_dir, path)
    current_dir = path
    if log:
        logging.info(f"📄 当前处理目录: {current_dir}")

    # 定义目标文件夹路径
    images_dir = os.path.join(current_dir, 'images')
    labels_dir = os.path.join(current_dir, 'labels')

    # 创建 train 和 labels 文件夹（如果不存在）
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    if log:
        logging.info("✅ 已创建 train/ 和 labels/ 目录（如已存在则跳过）")

    # 支持的图片扩展名
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']

    # 获取当前目录下的所有文件（仅文件，排除自身）
    all_files = [
        f for f in os.listdir(current_dir)
        if os.path.isfile(os.path.join(current_dir, f)) and
        f != os.path.basename(__file__)
    ]

    # 进度条
    with tqdm(total=len(all_files), desc="处理进度") as pbar:
        for filename in all_files:
            file_path = os.path.join(current_dir, filename)
            name, ext = os.path.splitext(filename)

            try:
                if ext.lower() in image_extensions:
                    dst = os.path.join(images_dir, filename)
                    shutil.move(file_path, dst)
                    if log:
                        logging.info(f"🖼️ 移动图片: {filename} -> train/")
                elif ext.lower() == '.txt':
                    dst = os.path.join(labels_dir, filename)
                    shutil.move(file_path, dst)
                    if log:
                        logging.info(f"🏷️ 移动标签: {filename} -> labels/")
            except Exception as e:
                if log:
                    logging.error(f"⚠️ 移动 {filename} 出错: {e}")
            finally:
                pbar.update(1)

    if log:
        logging.info("✅ 所有文件处理完成")
        print("✨ 文件整理已完成，详细日志请查看 convert.log")
    else:
        print("处理完成，log=False。")


if __name__ == "__main__":
    path = './fire-smoke/smoke'
    convert(path, log=False)
