import os
import cv2
import numpy as np
import random
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from tqdm import tqdm
from PIL import Image
from typing import Optional, List, Tuple, Dict, Union

# ================= 配置区域 =================

# 预定义一组鲜艳易区分的颜色 (BGR格式)
# 顺序: 鲜绿, 鲜蓝, 鲜红, 青色, 洋红, 黄色, 橙色, 紫色, 柠檬绿, 深天蓝
BRIGHT_COLORS = [
    (0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255),
    (0, 255, 255), (0, 165, 255), (128, 0, 128), (50, 205, 50), (235, 206, 135)
]

# 支持的图片扩展名
VALID_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}


# ===========================================

def draw_dataset_visualization(
        source_dir: str = '',
        class_names: Optional[List[str]] = None,
        sample_nums: int = 100,
        log_enabled: bool = False
) -> None:
    """
    读取数据集的标签和图片，绘制边界框并保存到 testbox 文件夹，用于预览数据质量.

    Parameters
    ----------
    source_dir : str, optional
        数据集的根目录路径。该目录下应包含 'images' 和 'labels' 子文件夹。
        默认为空字符串，表示当前脚本所在目录。
    class_names : List[str], optional
        类别名称列表。列表的索引将作为类别ID。
        例如输入 ['Smoke', 'Fire']，则 0='Smoke', 1='Fire'。
        如果不提供，将直接显示 "Class ID"。
    sample_nums : int, optional
        随机采样的图片数量。如果小于等于0，则处理1张；如果大于总数，则处理所有图片。
        默认值为 100。
    log_enabled : bool, optional
        是否开启日志记录功能。
        默认值为 False。

    Returns
    -------
    None
    """
    # 路径标准化
    current_dir = os.path.normpath(source_dir) if source_dir else os.getcwd()
    print(f"📂 目标工作目录: {current_dir}")

    # 构建 ID -> 名称 的映射字典
    class_mapping: Dict[int, str] = {}
    if class_names:
        class_mapping = {i: name for i, name in enumerate(class_names)}
        print(f"🏷️  类别映射已加载: {class_mapping}")
    else:
        print("⚠️ 未提供 class_names，将直接显示类别 ID。")

    # 初始化日志
    if log_enabled:
        setup_logging(current_dir)

    # 定义子目录
    train_folder = os.path.join(current_dir, 'images')
    labels_folder = os.path.join(current_dir, 'labels')
    output_folder = os.path.join(current_dir, 'testbox')

    # 检查基本目录结构
    if not os.path.exists(train_folder) or not os.path.exists(labels_folder):
        msg = f"❌ 目录结构错误: 未在 '{current_dir}' 下找到 'images' 或 'labels' 文件夹。"
        print(msg)
        if log_enabled: logging.error(msg)
        return

    # 创建输出目录
    os.makedirs(output_folder, exist_ok=True)

    # 执行处理
    success_count = process_image_batch(
        train_folder,
        labels_folder,
        output_folder,
        class_mapping,  # 传递映射字典
        sample_nums,
        log_enabled
    )

    print(f"\n✨ 处理完成! 成功生成 {success_count} 张可视化样本，保存在 '{output_folder}'。")


def setup_logging(directory: str) -> None:
    """
    配置日志系统.

    Parameters
    ----------
    directory : str
        日志文件保存的目录路径。
    """
    log_file = os.path.join(directory, "visualization.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file, mode='w', encoding='utf-8')]
    )


def process_image_batch(
        images_dir: str,
        labels_dir: str,
        output_dir: str,
        class_mapping: Dict[int, str],
        sample_size: int,
        log_enabled: bool
) -> int:
    """
    使用多线程批量处理图片和标签.

    Parameters
    ----------
    images_dir : str
        图片文件夹路径。
    labels_dir : str
        标签文件夹路径。
    output_dir : str
        输出文件夹路径。
    class_mapping : Dict[int, str]
        类别 ID 到名称的映射字典。
    sample_size : int
        采样数量。
    log_enabled : bool
        是否记录日志。

    Returns
    -------
    int
        成功处理的图片数量。
    """
    # 获取所有标签文件
    all_label_files = [f for f in os.listdir(labels_dir) if f.endswith(".txt")]

    if not all_label_files:
        if log_enabled: logging.warning(f"⚠️ 在 {labels_dir} 中未找到 .txt 标签文件")
        return 0

    # 随机采样
    target_files = sample_label_files(all_label_files, sample_size)

    if log_enabled:
        logging.info(f"📌 计划处理 {len(target_files)} 张图片 (总标签数: {len(all_label_files)})")

    # 多线程处理
    max_workers = min(32, (os.cpu_count() or 1) * 2)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        process_func = partial(
            process_single_pair,
            images_dir=images_dir,
            labels_dir=labels_dir,
            output_dir=output_dir,
            class_mapping=class_mapping,
            log_enabled=log_enabled
        )

        futures = {executor.submit(process_func, f): f for f in target_files}

        success_count = 0
        for future in tqdm(as_completed(futures), total=len(target_files), desc="绘制进度"):
            if future.result():
                success_count += 1

    return success_count


def sample_label_files(file_list: List[str], sample_size: int) -> List[str]:
    """
    从文件列表中随机采样.

    Parameters
    ----------
    file_list : List[str]
        原始文件列表。
    sample_size : int
        需要的样本数量。

    Returns
    -------
    List[str]
        采样后的文件列表。
    """
    if sample_size <= 0:
        sample_size = 1

    if sample_size >= len(file_list):
        return file_list

    rng = random.SystemRandom() if hasattr(random, 'SystemRandom') else random
    return rng.sample(file_list, sample_size)


def get_color(class_id: int) -> Tuple[int, int, int]:
    """
    根据类别ID获取对应的颜色.

    Parameters
    ----------
    class_id : int
        类别ID。

    Returns
    -------
    Tuple[int, int, int]
        (B, G, R) 颜色元组。
    """
    if 0 <= class_id < len(BRIGHT_COLORS):
        return BRIGHT_COLORS[class_id]

    random.seed(class_id)
    return (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))


def find_image_file(base_name: str, images_dir: str) -> Optional[str]:
    """
    根据文件名（不含扩展名）查找对应的图片文件.

    Parameters
    ----------
    base_name : str
        不含扩展名的文件名。
    images_dir : str
        图片目录。

    Returns
    -------
    Optional[str]
        找到的完整图片文件名，未找到则返回 None。
    """
    for ext in VALID_IMAGE_EXTENSIONS:
        filename = base_name + ext
        if os.path.exists(os.path.join(images_dir, filename)):
            return filename
    return None


def process_single_pair(
        label_filename: str,
        images_dir: str,
        labels_dir: str,
        output_dir: str,
        class_mapping: Dict[int, str],
        log_enabled: bool
) -> bool:
    """
    处理单对图片和标签文件：读取、绘制、保存.

    Parameters
    ----------
    label_filename : str
        标签文件名。
    images_dir : str
        图片目录。
    labels_dir : str
        标签目录。
    output_dir : str
        输出目录。
    class_mapping : Dict[int, str]
        类别映射字典。
    log_enabled : bool
        是否记录日志。

    Returns
    -------
    bool
        处理是否成功。
    """
    try:
        base_name = os.path.splitext(label_filename)[0]

        # 1. 寻找对应的图片文件
        image_filename = find_image_file(base_name, images_dir)
        if not image_filename:
            return False

        image_path = os.path.join(images_dir, image_filename)
        label_path = os.path.join(labels_dir, label_filename)
        output_path = os.path.join(output_dir, image_filename)

        # 2. 读取图片
        img_array = np.fromfile(image_path, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if image is None:
            return False

        height, width = image.shape[:2]

        # 3. 读取标签
        with open(label_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 4. 绘制所有框
        has_valid_box = False
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue

            try:
                class_id = int(parts[0])
                cx, cy, w, h = map(float, parts[1:5])

                # 传入 class_mapping
                draw_box_on_image(image, class_id, cx, cy, w, h, width, height, class_mapping)
                has_valid_box = True
            except ValueError:
                continue

        # 5. 保存结果
        if has_valid_box:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            Image.fromarray(img_rgb).save(output_path)
            return True
        else:
            return True  # 空标签也被视为处理完成

    except Exception as e:
        if log_enabled: logging.error(f"❌ 处理异常 {label_filename}: {str(e)}")
        return False


def draw_box_on_image(
        image: np.ndarray,
        class_id: int,
        cx: float, cy: float, w: float, h: float,
        img_width: int, img_height: int,
        class_mapping: Dict[int, str]
) -> None:
    """
    在图像上绘制单个边界框和类别标签.

    Parameters
    ----------
    image : np.ndarray
        OpenCV 图像对象 (原地修改)。
    class_id : int
        类别 ID。
    cx, cy, w, h : float
        归一化的 YOLO 坐标。
    img_width, img_height : int
        图像的像素宽高。
    class_mapping : Dict[int, str]
        类别 ID 到名称的映射字典。
    """
    # 坐标转换
    x_min = int((cx - w / 2) * img_width)
    y_min = int((cy - h / 2) * img_height)
    x_max = int((cx + w / 2) * img_width)
    y_max = int((cy + h / 2) * img_height)

    x_min, y_min = max(0, x_min), max(0, y_min)
    x_max, y_max = min(img_width, x_max), min(img_height, y_max)

    color = get_color(class_id)

    # 1. 绘制矩形框
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, 2)

    # 2. 获取标签文字 (优先使用映射表中的名字)
    class_name = class_mapping.get(class_id, f"Class {class_id}")
    label_text = f"{class_name} {class_id}"

    # 3. 绘制文字背景和文字
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 1
    (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

    if y_min - text_h - 5 < 0:
        text_origin_y = y_min + text_h + 5
        rect_y1 = y_min
        rect_y2 = y_min + text_h + 5
    else:
        text_origin_y = y_min - 5
        rect_y1 = y_min - text_h - 5
        rect_y2 = y_min

    cv2.rectangle(image, (x_min, rect_y1), (x_min + text_w, rect_y2), color, -1)
    cv2.putText(image, label_text, (x_min, text_origin_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)


if __name__ == "__main__":
    # 使用示例
    target_path = './fire-smoke/combined/train'

    # 在这里定义你的类别名称，顺序对应ID 0, 1, 2...
    my_classes = ['Smoke', 'Fire']

    draw_dataset_visualization(
        source_dir=target_path,
        class_names=my_classes,
        sample_nums=50
    )