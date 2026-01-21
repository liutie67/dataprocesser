import cv2
import os
from pathlib import Path
from tqdm import tqdm
import concurrent.futures


def process_single_image(file_path, source_root, output_root):
    """
    处理单张图片的函数（用于多线程调用）
    """
    try:
        # 1. 计算相对路径，以保持目录结构
        # 例如: source/train/a.jpg -> train/a.jpg
        rel_path = file_path.relative_to(source_root)

        # 2. 构建输出路径，并将后缀强制改为 .png
        # 例如: output/train/a.png
        dest_path = output_root / rel_path.with_suffix('.png')

        # 3. 如果目标文件夹不存在，自动创建
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # 4. 读取图片
        img = cv2.imread(str(file_path))
        if img is None:
            return False, f"无法读取: {file_path.name}"

        # 5. 核心转换逻辑：伪灰度 (Fake Grayscale)
        # 步骤A: 转为单通道灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 步骤B: 转回3通道BGR (三个通道数值相同)
        # 这样既去除了色彩信息，又保留了 [H, W, 3] 的形状，适配 YOLO 预训练权重
        fake_gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # 6. 保存为 PNG
        # PNG 是无损压缩，虽然体积比 JPG 大，但没有压缩噪点，适合作为最终训练数据
        cv2.imwrite(str(dest_path), fake_gray)

        return True, None

    except Exception as e:
        return False, str(e)


def convert_dataset_to_fake_grayscale(source_dir, output_dir, workers=4):
    """
    主函数：遍历、多线程分发

    Args:
        source_dir (str): 原始数据集根目录
        output_dir (str): 转换后保存的根目录
        workers (int): 线程数，建议设置为 CPU 核心数或稍大
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)

    # 1. 检查输入
    if not source_path.exists():
        print(f"❌ 错误：源目录不存在 {source_path}")
        return

    # 2. 扫描所有图片文件
    print("🔍 正在扫描文件结构...")
    img_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
    # rglob('*') 递归查找所有文件
    all_files = [p for p in source_path.rglob('*')
                 if p.is_file() and p.suffix.lower() in img_extensions]

    total_files = len(all_files)
    print(f"✅ 找到 {total_files} 张图片，准备处理...")
    print(f"🚀 启用 {workers} 线程并行处理")
    print(f"📂 输出目录: {output_path} (格式将统一为 .png)")

    # 3. 多线程处理
    success_count = 0
    fail_count = 0

    # 使用 tqdm 显示进度条
    with tqdm(total=total_files, unit="img") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有任务
            # 使用 list comprehension 构建任务参数
            futures = [
                executor.submit(process_single_image, f, source_path, output_path)
                for f in all_files
            ]

            # 获取结果
            for future in concurrent.futures.as_completed(futures):
                is_success, msg = future.result()
                if is_success:
                    success_count += 1
                else:
                    fail_count += 1
                    # 只有出错时才打印详细信息，防止刷屏
                    pbar.write(f"⚠️ 处理失败: {msg}")

                pbar.update(1)

    print("\n" + "=" * 50)
    print("🎉 处理完成！")
    print(f"✅ 成功转换: {success_count}")
    print(f"❌ 失败数量: {fail_count}")
    print(f"📂 结果保存在: {output_path}")
    print("=" * 50)


# ==========================================
# 使用示例
# ==========================================
if __name__ == "__main__":
    # 配置区
    SOURCE_DIR = r"datasets/kilohecto_data"  # 你的原始彩色数据集路径
    OUTPUT_DIR = r"datasets/kilohecto_gray_png"  # 你想保存的新路径

    # 这里的 workers 可以根据你电脑 CPU 核心数调整，默认 8 线程通常很快
    convert_dataset_to_fake_grayscale(SOURCE_DIR, OUTPUT_DIR, workers=8)