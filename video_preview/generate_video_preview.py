import os
import cv2
import numpy as np
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor


def is_video_file(file_path):
    """检查文件是否是视频（基于扩展名）"""
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mpg', '.mpeg', '.ts'}
    file_ext = os.path.splitext(file_path)[1].lower()  # 获取小写的扩展名
    return file_ext in video_extensions


def generate_video_preview(video_path, output_path, rows=4, cols=4, preview_width=800, fit4169=True):
    """
    生成视频预览图网格

    参数:
        video_path: 视频文件路径
        output_path: 输出图片路径
        rows: 行数
        cols: 列数
        preview_width: 预览图宽度(高度按比例自动计算)
        fit4169: 是否为横屏显示优化竖屏预览的排布
    """
    if not is_video_file(video_path):
        return
    # 打开视频文件
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频文件: {video_path}")
        return

    # 获取视频信息
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = frame_count / fps

    # 计算每个截取点的时间位置
    intervals = rows * cols
    timestamps = [i * (duration / (intervals + 1)) for i in range(1, intervals + 1)]

    frames = []
    for ts in timestamps:
        # 设置到指定时间点
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)

    cap.release()

    if not frames:
        print(f"无法从视频中提取帧: {video_path}")
        return

    # 计算每个缩略图的大小
    thumb_height = frames[0].shape[0]
    thumb_width = frames[0].shape[1]

    # 调整缩略图大小，保持宽高比
    thumb_height = int((preview_width / cols) * (thumb_height / thumb_width))
    thumb_width = int(preview_width / cols)

    # 调整所有帧的大小
    resized_frames = []
    for frame in frames:
        resized = cv2.resize(frame, (thumb_width, thumb_height))
        resized_frames.append(resized)

    if (cols == rows) and (thumb_width < thumb_height) and fit4169 and (cols%2==0):
        cols = cols * 2
        rows = rows // 2

    # 创建网格图像
    grid = np.zeros((thumb_height * rows, thumb_width * cols, 3), dtype=np.uint8)

    for i, frame in enumerate(resized_frames):
        row = i // cols
        col = i % cols
        y_start = row * thumb_height
        y_end = y_start + thumb_height
        x_start = col * thumb_width
        x_end = x_start + thumb_width
        grid[y_start:y_end, x_start:x_end] = frame

    # 保存结果
    cv2.imwrite(output_path, grid)
    # print(f"预览图已保存到: {output_path}")


def generate_previews_for_directory(
        src_dir,
        dst_dir,
        rows=4,
        cols=4,
        preview_width=800,
        use_multithreading=True,
        num_threads=None
):
    """
    遍历目录并在目标目录同文件结构生成视频的预览
    :param src_dir: 源目录
    :param dst_dir: 目标目录
    :param rows: 预览图行数
    :param cols: 预览图列数
    :param preview_width: 预览图的像素宽度，高度自动调整
    :param use_multithreading: 是否使用多线程
    :param num_threads: 线程数（None=使用默认线程池线程数）
    """
    dir_map = {}

    def count_valid_tasks(src_dir):
        total_tasks = 0
        for root, dirs, files in os.walk(src_dir):
            # 关键修改：原地移除所有含@的目录，阻止os.walk进入这些目录
            dirs[:] = [d for d in dirs if '@' not in d]

            # 统计当前目录的有效内容（已过滤掉@目录）
            valid_dirs = len(dirs)  # 因为dirs已经被过滤，直接取长度即可
            valid_files = len([f for f in files if is_video_file(f)])
            total_tasks += valid_dirs + valid_files

        return total_tasks

    # 统计总任务数（排除隐藏文件）
    total_tasks = count_valid_tasks(src_dir)

    def process_file(src_file, dst_file):
        """单个文件处理函数"""
        generate_video_preview(src_file, dst_file, rows=rows, cols=cols, preview_width=preview_width)

    with tqdm(total=total_tasks, desc="Processing", unit="item") as pbar:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if '@' not in d]

            # 处理目录
            if root == src_dir:
                new_root = dst_dir
            else:
                parent_src = os.path.dirname(root)
                parent_new = dir_map[parent_src]
                dir_name = os.path.basename(root)
                new_root = os.path.join(parent_new, dir_name)

            dir_map[root] = new_root
            os.makedirs(new_root, exist_ok=True)
            pbar.update(1)

            # 过滤隐藏文件
            visible_files = [f for f in files if not f.startswith(".")]

            if use_multithreading and visible_files:
                # 线程池（可指定线程数）
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    futures = []
                    for f in visible_files:
                        if not is_video_file(f):
                            continue
                        src_file = os.path.join(root, f)
                        dst_file = os.path.join(new_root, f + '.png')
                        futures.append(
                            executor.submit(
                                process_file, src_file, dst_file
                            )
                        )
                    for future in futures:
                        future.result()
                        pbar.update(1)
            else:
                # 单线程处理
                for f in visible_files:
                    src_file = os.path.join(root, f)
                    dst_file = os.path.join(new_root, f + '.png')
                    process_file(src_file, dst_file)
                    pbar.update(1)


if __name__ == "__main__":
    # 使用示例
    input_path = "path/to/input.mp4"  # 替换为你的视频目录
    output_path = "path/to/output.png"  # 替换为输出目录
    rows = 4  # 预览图行数
    cols = 4  # 预览图列数
    preview_width = 800  # 预览图宽度(像素)
    generate_video_preview(input_path, output_path, rows, cols, preview_width)

    input_dir = "folder/to/previewer"  # 替换为你的视频目录
    output_dir = "folder/to/previewed"  # 替换为输出目录
    rows = 4  # 预览图行数
    cols = 4  # 预览图列数
    preview_width = 800  # 预览图宽度(像素)
    generate_previews_for_directory(input_dir, output_dir, rows, cols, preview_width)
