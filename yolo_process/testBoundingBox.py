"""
Step 6 testBoundingBox.py
"""

import os
import cv2
import numpy as np
import random
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from tqdm import tqdm
from PIL import Image
from typing import Optional


def draw(path: str = '', sample_size: int = 100, log: bool = False) -> None:
    """
    Draw bounding boxes on images from label files, with optional random sampling.

    Args:
        path: Directory containing 'images' and 'labels' folders
        sample_size: Number of images to randomly sample (<=0 means 1, >total means all)
        log: Whether to enable logging
    """
    # Validate and normalize path
    current_dir = os.path.normpath(path) if path else os.path.dirname(os.path.abspath(__file__))
    print(f"目标目录: {current_dir}")

    # Initialize logging if enabled
    if log:
        setup_logging(current_dir)

    # Define paths
    train_folder = os.path.join(current_dir, 'images')
    labels_folder = os.path.join(current_dir, 'labels')
    test_folder = os.path.join(current_dir, 'testbox')

    # Create test directory if needed
    os.makedirs(test_folder, exist_ok=True)
    if log:
        logging.info("✅ 已创建 test/ 文件夹（如已存在则跳过）")

    # Process images
    success_count = process_images(
        train_folder,
        labels_folder,
        test_folder,
        sample_size,
        log
    )

    if log:
        logging.info(f"🎉 处理完成! 成功处理 {success_count} 个文件")
    print("图像边界框绘制完成。")


def setup_logging(directory: str) -> None:
    """Configure logging system."""
    log_file = os.path.join(directory, "testBoundingBox.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8')
        ]
    )


def process_images(
        train_folder: str,
        labels_folder: str,
        test_folder: str,
        sample_size: int,
        log: bool
) -> int:
    """
    Process images with bounding boxes using multithreading.

    Returns:
        Number of successfully processed images
    """
    # Get all label files and apply sampling
    try:
        label_files = [f for f in os.listdir(labels_folder) if f.endswith(".txt")]
    except FileNotFoundError:
        if log:
            logging.error(f"❌ 标签文件夹不存在: {labels_folder}")
        return 0

    # Apply sampling
    if sample_size <= 0:
        sample_size = 1
    label_files = sample_label_files(label_files, sample_size)

    if log:
        logging.info(f"📌 共找到 {len(label_files)} 张待处理图像")

    # Process with thread pool
    with ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
        process_func = partial(
            process_single_image,
            train_folder=train_folder,
            labels_folder=labels_folder,
            test_folder=test_folder,
            log=log
        )

        futures = {
            executor.submit(process_func, label_file): label_file
            for label_file in label_files
        }

        success_count = 0
        for future in tqdm(as_completed(futures), total=len(label_files), desc="处理图像"):
            if future.result():
                success_count += 1

    return success_count


def sample_label_files(label_files: list[str], sample_size: int) -> list[str]:
    """Randomly sample label files while maintaining randomness."""
    if sample_size >= len(label_files):
        return label_files

    # Use system randomness if available
    rng = random.SystemRandom() if hasattr(random, 'SystemRandom') else random
    return rng.sample(label_files, sample_size)


# Predefined color palette for classes
CLASS_COLORS = {
    0: (0, 255, 0),  # Green - Class 0
    1: (255, 0, 0),  # Blue - Class 1
    2: (0, 0, 255),  # Red - Class 2
    3: (255, 255, 0),  # Cyan - Class 3
    4: (255, 0, 255),  # Purple - Class 4
    5: (0, 255, 255),  # Yellow - Class 5
}


def get_color_for_class(class_id: int) -> tuple[int, int, int]:
    """Get color for class ID, random if unknown."""
    return CLASS_COLORS.get(class_id, (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255)
    ))


def process_single_image(
        label_file: str,
        train_folder: str,
        labels_folder: str,
        test_folder: str,
        log: bool
) -> bool:
    """Process single image file and draw bounding boxes."""
    try:
        # Setup paths
        image_file = os.path.splitext(label_file)[0] + ".jpg"
        image_path = os.path.join(train_folder, image_file)
        label_path = os.path.join(labels_folder, label_file)
        output_path = os.path.join(test_folder, image_file)

        if log:
            logging.info(f"处理文件: {image_file}")

        # Read image
        image = read_image(image_path, log)
        if image is None:
            return False

        # Read and process labels
        height, width = image.shape[:2]
        labels = read_labels(label_path, log)
        if labels is None:
            return False

        # Draw each bounding box
        for class_id, x_center, y_center, bbox_width, bbox_height in labels:
            draw_bounding_box(
                image,
                class_id,
                x_center, y_center, bbox_width, bbox_height,
                width, height
            )

        # Save processed image
        return save_image(image, output_path, log)

    except Exception as e:
        if log:
            logging.error(f"❌ 处理文件 {label_file} 时发生未捕获的异常: {e}")
        return False


def read_image(image_path: str, log: bool) -> Optional[np.ndarray]:
    """Read image from file."""
    try:
        with open(image_path, 'rb') as f:
            img_data = np.frombuffer(f.read(), dtype=np.uint8)
        image = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        if image is None:
            if log:
                logging.warning(f"❌ 读取图像失败 (cv2.imdecode 返回 None): {image_path}")
            return None
        return image
    except Exception as e:
        if log:
            logging.error(f"❌ 读取图像时发生错误: {image_path}, 错误: {e}")
        return None


def read_labels(label_path: str, log: bool) -> Optional[list[tuple]]:
    """Read and parse label file."""
    try:
        with open(label_path, 'r') as f:
            lines = f.readlines()

        labels = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                labels.append(tuple(map(float, parts[:5])))
            except ValueError as e:
                if log:
                    logging.error(f"❌ 解析标签行失败: {line.strip()}, 错误: {e}")

        if log:
            logging.info(f"📌 找到 {len(labels)} 条有效标注信息")
        return labels

    except Exception as e:
        if log:
            logging.error(f"❌ 读取标签文件失败: {label_path}, 错误: {e}")
        return None


def draw_bounding_box(
        image: np.ndarray,
        class_id: int,
        x_center: float, y_center: float,
        bbox_width: float, bbox_height: float,
        img_width: int, img_height: int
) -> None:
    """Draw single bounding box on image."""
    # Convert normalized coordinates to pixel values
    x_min = int((x_center - bbox_width / 2) * img_width)
    y_min = int((y_center - bbox_height / 2) * img_height)
    x_max = int((x_center + bbox_width / 2) * img_width)
    y_max = int((y_center + bbox_height / 2) * img_height)

    # Get color and draw rectangle
    color = get_color_for_class(int(class_id))
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, 2)

    # Draw class label
    label_text = f"Class {int(class_id)}"
    (text_width, text_height), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(image, (x_min, y_min - text_height - 4), (x_min + text_width, y_min), color, -1)
    cv2.putText(image, label_text, (x_min, y_min - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def save_image(image: np.ndarray, output_path: str, log: bool) -> bool:
    """Save image using PIL for better path handling."""
    try:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        pil_image.save(output_path)
        if log:
            logging.info(f"✅ 已保存图像: {output_path}")
        return True
    except Exception as e:
        if log:
            logging.error(f"❌ 保存图像失败: {output_path}, 错误: {e}")
        return False


if __name__ == "__main__":
    path = './fire-smoke/combined/train'
    draw(path=path, sample_size=100)