# # create_val.py
#
# import os
# import random
# import shutil
# from tqdm import tqdm
# import logging
#
# # 配置日志
# logging.basicConfig(
#     filename='create_val.log',
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )
#
# # 当前目录
# current_dir = os.path.dirname(os.path.abspath(__file__))
#
# # 路径定义
# train_dir = os.path.join(current_dir, 'train')
# labels_dir = os.path.join(current_dir, 'labels')
#
# # 将 labels 移动进 train
# new_labels_dir = os.path.join(train_dir, 'labels')
# if os.path.exists(labels_dir) and not os.path.exists(new_labels_dir):
#     shutil.move(labels_dir, new_labels_dir)
#     logging.info(f"Labels moved to {new_labels_dir}")
# else:
#     logging.warning(f"{labels_dir} 不存在或 {new_labels_dir} 已存在")
#
# # 创建 images 和 val 目录
# images_dir = os.path.join(train_dir, 'images')
# val_dir = os.path.join(current_dir, 'val')
# val_images_dir = os.path.join(val_dir, 'images')
# val_labels_dir = os.path.join(val_dir, 'labels')
#
# os.makedirs(images_dir, exist_ok=True)
# os.makedirs(val_images_dir, exist_ok=True)
# os.makedirs(val_labels_dir, exist_ok=True)
#
# # 获取所有图片并随机划分训练集和验证集
# image_files = [f for f in os.listdir(train_dir) if f.endswith('.jpg')]
# total_count = len(image_files)
# val_count = int(total_count * 0.2)
# val_files = set(random.sample(image_files, val_count))
#
# # 进度条处理 + 日志输出
# with tqdm(total=total_count, desc="Moving files") as pbar:
#     for img_file in image_files:
#         src_img_path = os.path.join(train_dir, img_file)
#         label_file = os.path.splitext(img_file)[0] + '.txt'
#         src_label_path = os.path.join(new_labels_dir, label_file)
#
#         if img_file in val_files:
#             dst_img_path = os.path.join(val_images_dir, img_file)
#             dst_label_path = os.path.join(val_labels_dir, label_file)
#         else:
#             dst_img_path = os.path.join(images_dir, img_file)
#             dst_label_path = os.path.join(images_dir.replace('images', 'labels'), label_file)
#
#         # 移动图像
#         shutil.move(src_img_path, dst_img_path)
#         # 如果有对应标签，则也移动
#         if os.path.exists(src_label_path):
#             shutil.move(src_label_path, dst_label_path)
#
#         pbar.update(1)
#
# logging.info("数据划分完成")
# print("✅ 数据划分完成，详细日志请查看 create_val.log")
