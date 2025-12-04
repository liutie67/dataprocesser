import cv2
import os
import argparse
import json
import numpy as np
import concurrent.futures
from pathlib import Path
from tqdm import tqdm
import time

from video_crypt.utils import string_to_hash


def save_image_safe(path, img, quality=95):
    """
    [Windows兼容性核心] 安全保存图片，支持中文路径。
    使用 numpy 先将图片编码为二进制流，再写入文件。

    Args:
        path (Path | str): 保存路径
        img (numpy.ndarray): 图像数据 (BGR)
        quality (int): JPEG/PNG 压缩质量 (0-100)

    Returns:
        bool: 是否保存成功
    """
    path = str(path)
    # 获取文件扩展名以决定编码格式
    ext = os.path.splitext(path)[1].lower()

    # 设置编码参数
    if ext in ['.jpg', '.jpeg']:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    elif ext == '.png':
        # PNG 压缩级别 0-9，将 quality (0-100) 映射一下，通常默认即可
        params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
    else:
        params = []

    try:
        # imencode 返回 (success, encoded_img)
        success, encoded_img = cv2.imencode(ext, img, params)
        if success:
            encoded_img.tofile(path)
            return True
        return False
    except Exception as e:
        print(f"保存图片失败: {e}")
        return False


def extract_frames_from_video(
        video_path,
        output_dir,
        frame_interval=10,
        target_size=None,
        quality=95,
        prefix="frame",
        start_frame=0,
        end_frame=None,
        min_object_size=0,
        save_original_size=False,
        progress_position=None,
        quiet=False
):
    """
    从单个视频中提取帧。

    Args:
        video_path (str | Path): 视频路径。
        output_dir (str | Path): 结果输出目录。
        frame_interval (int): 采样间隔（每隔几帧取一张）。
        target_size (tuple | None): 目标尺寸 (width, height)，None 表示不缩放。
        quality (int): 图片保存质量。
        prefix (str): 输出文件名前缀。
        start_frame (int): 起始帧索引。
        end_frame (int | None): 结束帧索引。
        min_object_size (float): 基于 Canny 边缘检测的过滤阈值 (0.0-1.0)。
        save_original_size (bool): 是否同时保存原图。
        progress_position (int | None): tqdm 进度条在终端的行位置（用于多层进度条）。
        quiet (bool): 是否静默模式（不显示进度条，用于多进程时防止混乱）。

    Returns:
        dict: 包含处理统计信息的字典。
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 将视频名称信息注入 prefix
    prefix = prefix + '_' +  string_to_hash(str(video_path), 8)

    # 1. 打开视频
    # 注意：cv2.VideoCapture 在某些 Windows 环境下对中文路径支持不佳
    # 尝试传递字符串，如果失败可能需要改用临时文件或其他库，但在大多数现代 OpenCV 版本已修复
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        return {'error': f"无法打开视频: {video_path}", 'video': video_path.name}

    # 2. 获取元数据
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    orig_area = orig_w * orig_h

    # 修正 end_frame
    real_end = total_frames if (end_frame is None or end_frame > total_frames) else end_frame

    # 计算待处理帧
    frames_indices = range(start_frame, real_end, frame_interval)
    total_tasks = len(frames_indices)

    if total_tasks == 0:
        cap.release()
        return {'saved': 0, 'skipped': 0, 'video': video_path.name}

    # 3. 初始化统计
    stats = {
        'video': video_path.name,
        'saved': 0,
        'skipped': 0,
        'details': []
    }

    # 4. 进度条配置
    # 如果 quiet=True，disable=True；否则显示
    pbar = tqdm(
        total=total_tasks,
        desc=f"处理 {video_path.name[:15]}...",
        unit="img",
        position=progress_position,
        leave=False,  # 处理完后清除该行，保持界面整洁
        disable=quiet
    )

    # 5. 循环处理
    for idx in frames_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()

        if not ret:
            stats['skipped'] += 1
            pbar.update(1)
            continue

        # --- 过滤逻辑 ---
        save_this_frame = True
        if min_object_size > 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_ratio = cv2.countNonZero(edges) / orig_area
            if edge_ratio < min_object_size:
                save_this_frame = False

        # --- 保存逻辑 ---
        if save_this_frame:
            timestamp = idx / fps if fps > 0 else 0
            fname = f"{prefix}_{idx:06d}_t{timestamp:.2f}.jpg".replace('.', '_', 1)  # 只有第一个点替换，保留后缀

            # 这里统一存为 jpg 以减小体积，也可以根据参数改
            out_name = output_dir / fname

            # Resize
            process_img = frame
            if target_size:
                process_img = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

            # 使用安全保存函数 (解决中文路径问题)
            save_image_safe(out_name, process_img, quality)

            # 保存原图
            if save_original_size and target_size:
                orig_name = output_dir / f"orig_{fname}"
                save_image_safe(orig_name, frame, quality)

            stats['saved'] += 1
            stats['details'].append({'file': fname, 'time': timestamp})
        else:
            stats['skipped'] += 1

        pbar.update(1)

    pbar.close()
    cap.release()
    return stats


def batch_extract_from_directory(
        input_dir,
        output_base,
        num_workers=4,
        **kwargs
):
    """
    批量多进程处理视频目录。

    Args:
        input_dir (str): 输入目录。
        output_base (str): 输出基准目录。
        num_workers (int): 进程池大小（并发数）。
        **kwargs: 传递给 extract_frames_from_video 的参数。

    Examples:
        >>> batch_extract_from_directory(
        >>>     input_dir="folder/to/videos",
        >>>     output_base="folder/to/save/frames",
        >>>     frame_interval=10,
        >>>     prefix='f',
        >>> )
    """
    input_path = Path(input_dir)
    output_path = Path(output_base)

    # 1. 扫描文件
    valid_exts = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
    # 递归查找所有文件并过滤扩展名 (不区分大小写)
    video_files = [
        f for f in input_path.rglob("*")
        if f.suffix.lower() in valid_exts and f.is_file()
    ]

    if not video_files:
        print(f"❌ 在 {input_dir} 未找到视频文件。")
        return

    print(f"📂 扫描到 {len(video_files)} 个视频文件")
    print(f"🚀 启动 {num_workers} 个进程进行并行处理...")
    print(f"💾 输出目录: {output_base}\n")

    # 2. 准备任务参数
    tasks = []
    for vid in video_files:
        # 保持原有目录结构 或 仅以文件名建文件夹？这里选择以文件名建文件夹
        # 例如: input/A/video.mp4 -> output/video/
        vid_output_dir = output_path / vid.stem

        # 封装参数
        task_kwargs = kwargs.copy()
        task_kwargs.update({
            'video_path': vid,
            'output_dir': vid_output_dir,
            # 多进程模式下，关闭子进度条，防止终端混乱
            'quiet': True if num_workers > 1 else False,
            # 如果是单进程，子进度条显示在第1行 (第0行给总进度)
            'progress_position': 1 if num_workers == 1 else None
        })
        tasks.append(task_kwargs)

    # 3. 执行处理
    total_saved = 0
    total_skipped = 0

    start_time = time.time()

    # 主进度条
    main_pbar = tqdm(total=len(tasks), desc="Total Progress", unit="video", position=0)

    # 选择执行模式
    if num_workers > 1:
        # 并行模式
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            # 提交所有任务
            futures = [executor.submit(extract_frames_from_video, **k) for k in tasks]

            # as_completed 会在某个任务完成时 yield
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if 'error' in res:
                        tqdm.write(f"⚠️  错误 [{res['video']}]: {res['error']}")
                    else:
                        total_saved += res['saved']
                        total_skipped += res['skipped']
                        # 可以在这里打印完成信息，用 tqdm.write 避免打断进度条
                        # tqdm.write(f"✅ 完成: {res['video']} (存: {res['saved']})")
                except Exception as e:
                    tqdm.write(f"💥 进程异常: {e}")
                finally:
                    main_pbar.update(1)
    else:
        # 串行模式 (用于调试或单线程需求)
        for task in tasks:
            try:
                # 动态显示当前正在处理的视频名
                main_pbar.set_description(f"Processing {task['video_path'].name[:15]}")
                res = extract_frames_from_video(**task)
                if 'error' not in res:
                    total_saved += res['saved']
                    total_skipped += res['skipped']
            except Exception as e:
                print(f"错误: {e}")
            main_pbar.update(1)

    main_pbar.close()

    duration = time.time() - start_time
    print(f"\n🎉 全部完成!")
    print(f"⏱️  耗时: {duration:.2f}秒")
    print(f"📸 总共保存: {total_saved} 张")
    print(f"🗑️  总共跳过: {total_skipped} 张")


def parse_args():
    parser = argparse.ArgumentParser(description="多进程视频抽帧工具 (YOLO数据集准备)")

    parser.add_argument('--input', '-i', type=str, required=True, help='输入视频路径 或 文件夹路径')
    parser.add_argument('--output', '-o', type=str, required=True, help='输出目录')

    # 核心参数
    parser.add_argument('--interval', type=int, default=10, help='每隔多少帧保存一张 (默认: 10)')
    parser.add_argument('--width', type=int, default=640, help='Resize 宽度 (默认: 640, 0表示原图)')
    parser.add_argument('--height', type=int, default=640, help='Resize 高度 (默认: 640, 0表示原图)')
    parser.add_argument('--workers', type=int, default=4, help='并发进程数 (默认: 4, 设为1则显示详细单视频进度)')

    # 过滤与高级
    parser.add_argument('--min-obj', type=float, default=0.0, help='Canny边缘过滤阈值 0.0-1.0 (默认: 0.0 不过滤)')
    parser.add_argument('--quality', type=int, default=95, help='图片质量 (默认: 95)')

    return parser.parse_args()


if __name__ == "__main__":
    # 解决 Windows 下多进程必须在 if __name__ == "__main__" 下运行的问题
    # 同时也解决 Windows 下 multiprocessing 的 freeze_support 问题
    import multiprocessing

    multiprocessing.freeze_support()

    args = parse_args()

    input_p = Path(args.input)
    target_size = (args.width, args.height) if (args.width > 0 and args.height > 0) else None

    # 提取参数字典
    process_kwargs = {
        'frame_interval': args.interval,
        'target_size': target_size,
        'min_object_size': args.min_obj,
        'quality': args.quality
    }

    if input_p.is_file():
        # 单文件模式：强制单进程以显示详细进度条
        print("检测到单个文件输入，进入单文件模式...")
        extract_frames_from_video(
            video_path=input_p,
            output_dir=Path(args.output) / input_p.stem,
            progress_position=0,
            quiet=False,
            **process_kwargs
        )
    elif input_p.is_dir():
        # 文件夹模式
        batch_extract_from_directory(
            input_dir=input_p,
            output_base=args.output,
            num_workers=args.workers,
            **process_kwargs
        )
    else:
        print(f"❌ 路径不存在: {input_p}")


# import cv2
# import os
# import argparse
# import json
# from pathlib import Path
# from tqdm import tqdm
#
#
# def extract_frames_for_yolo(
#         video_path,
#         output_dir,
#         frame_interval=10,
#         target_size=None,
#         quality=95,
#         prefix="frame",
#         start_frame=0,
#         end_frame=None,
#         min_object_size=0.02,
#         save_original_size=False,
#         verbose=True
# ):
#     """
#     从视频中提取帧用于YOLO目标识别模型训练。
#     支持尺寸调整、帧间隔提取和基于简单边缘检测的无目标过滤。
#
#     参数:
#     ----------
#     video_path : str | Path
#         输入视频文件路径
#     output_dir : str | Path
#         输出图片保存目录
#     frame_interval : int, default=10
#         帧间隔，每隔多少帧提取一张
#     target_size : tuple, optional
#         目标尺寸 (width, height)，默认保持原尺寸
#     quality : int, default=95
#         保存图片的JPEG质量（1-100）
#     prefix : str, default="frame"
#         输出图片文件名前缀
#     start_frame : int, default=0
#         开始提取的帧序号 (包含)
#     end_frame : int, optional
#         结束提取的帧序号 (不包含)，None表示到视频结束
#     min_object_size : float, default=0.02
#         最小对象尺寸（相对于画面总像素的比例）。用于过滤画面过于单一的帧（基于Canny边缘检测）。
#         设为 0 或使用 --no-filter 禁用此功能。
#     save_original_size : bool, default=False
#         如果 target_size 已设置，是否同时保存原始尺寸的图片副本
#     verbose : bool, default=True
#         是否显示进度信息和详细日志
#
#     返回:
#     ----------
#     dict : 包含提取信息的字典（保存数量、跳过数量、信息文件路径等）
#
#     Examples:
#         >>> # 单个视频处理
#         >>> result = extract_frames_for_yolo(
#         >>>     video_path="path/to/video.mp4",
#         >>>     output_dir="folder/to/save/frames",
#         >>>     frame_interval=5,
#         >>>     target_size=(640, 480)
#         >>> )
#     """
#
#     # 转换为 Path 对象，统一处理路径
#     video_path = Path(video_path)
#     output_dir = Path(output_dir)
#
#     # 创建输出目录
#     output_dir.mkdir(parents=True, exist_ok=True)
#
#     # 打开视频文件
#     cap = cv2.VideoCapture(str(video_path))
#     if not cap.isOpened():
#         raise ValueError(f"无法打开视频文件: {video_path}")
#
#     # 获取视频信息
#     total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#     fps = cap.get(cv2.CAP_PROP_FPS)
#     original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     original_area = original_width * original_height
#     duration = total_frames / fps if fps > 0 else 0
#
#     if verbose:
#         print(f"🎬 视频信息:")
#         print(f"  文件名: {video_path.name}")
#         print(f"  总帧数: {total_frames}")
#         print(f"  FPS: {fps:.2f}")
#         print(f"  分辨率: {original_width}x{original_height}")
#         print(f"  时长: {duration:.2f}秒")
#         print(f"  输出目录: {output_dir}")
#
#     # 设置结束帧 (确保不超过视频总帧数)
#     if end_frame is None or end_frame > total_frames:
#         end_frame = total_frames
#
#     # 检查参数有效性
#     if start_frame >= end_frame:
#         raise ValueError(f"开始帧({start_frame})必须小于结束帧({end_frame})")
#
#     if frame_interval < 1:
#         raise ValueError(f"帧间隔({frame_interval})必须大于等于1")
#
#     # 检查目标尺寸是否有效
#     if target_size is not None and (target_size[0] <= 0 or target_size[1] <= 0):
#         target_size = None  # 忽略无效尺寸
#
#     # 计算需要处理的帧范围
#     frames_to_process = range(start_frame, end_frame, frame_interval)
#     num_frames_to_save = len(frames_to_process)
#
#     if verbose:
#         print(f"\n⚙️ 提取设置:")
#         print(f"  帧间隔: {frame_interval}")
#         print(f"  提取范围: 帧 {start_frame} 到 {end_frame} (不含)")
#         print(f"  目标尺寸: {target_size if target_size else '原尺寸'}")
#         print(f"  过滤阈值 (min_object_size): {min_object_size * 100:.2f}%")
#         print(f"  预计提取: {num_frames_to_save} 张图片")
#
#     # 如果无需处理
#     if num_frames_to_save == 0:
#         cap.release()
#         return {'saved_count': 0, 'skipped_count': 0, 'frame_info': []}
#
#     # 初始化统计信息
#     saved_count = 0
#     skipped_count = 0
#     frame_info = []
#
#     # 创建进度条
#     pbar = tqdm(total=num_frames_to_save, desc="提取帧", unit="帧", disable=not verbose)
#
#     # 逐帧处理
#     for frame_idx in frames_to_process:
#         # 设置当前帧位置
#         cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
#
#         # 读取帧
#         ret, frame = cap.read()
#         if not ret:
#             # 读取失败，可能是视频损坏或到达文件末尾
#             skipped_count += 1
#             pbar.update(1)
#             continue
#
#         # 计算时间戳
#         timestamp = frame_idx / fps if fps > 0 else 0
#
#         # --- 目标存在性过滤 ---
#         has_potential_object = True
#         if min_object_size > 0:
#             # 转换为灰度图 (用于减少计算量)
#             gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#             # 边缘检测 (Canny 是一种高效的边缘检测算法)
#             edges = cv2.Canny(gray, 50, 150)  # Canny 阈值可根据需要调整
#             # 计算边缘区域占比 (非零像素点 / 总像素点)
#             edge_ratio = cv2.countNonZero(edges) / original_area
#
#             # 如果边缘区域太小，认为画面过于简单，可能没有明显目标
#             if edge_ratio < min_object_size:
#                 has_potential_object = False
#
#         # --- 保存图片 ---
#         if has_potential_object:
#             # 生成文件名
#             # 使用帧序号确保唯一性，添加时间戳增加可读性
#             timestamp_str = f"{timestamp:.2f}".replace('.', '_')
#             filename = f"{prefix}_{frame_idx:06d}_t{timestamp_str}.png"
#             output_path = output_dir / filename
#
#             save_frame = frame.copy()
#
#             # 调整尺寸（如果需要）
#             if target_size is not None:
#                 # 使用 INTER_AREA 插值法进行缩小时效果最好
#                 save_frame = cv2.resize(save_frame, target_size, interpolation=cv2.INTER_AREA)
#
#             # 保存调整后的图片
#             # cv2.IMWRITE_JPEG_QUALITY 用于设置 JPEG 压缩质量
#
#             ret_write = cv2.imwrite(str(output_path), save_frame)
#
#             if not ret_write:
#                 raise ValueError("cv2.imwrite() 写入错误！")
#
#             # 如果需要，保存原始尺寸的副本
#             if save_original_size and target_size is not None:
#                 original_filename = f"original_{prefix}_{frame_idx:06d}.png"
#                 original_path = output_dir / original_filename
#                 cv2.imwrite(str(original_path), frame)
#
#             # 记录帧信息
#             info = {
#                 'frame_idx': frame_idx,
#                 'timestamp': timestamp,
#                 'filename': filename,
#                 'original_size': (original_width, original_height),
#                 # shape[:2][::-1] 将 (height, width) 转换为 (width, height)
#                 'saved_size': save_frame.shape[:2][::-1],
#                 'has_potential_object': has_potential_object
#             }
#             frame_info.append(info)
#
#             saved_count += 1
#         else:
#             skipped_count += 1
#
#         pbar.update(1)
#
#     # 关闭视频和进度条
#     cap.release()
#     pbar.close()
#
#     # 打印统计信息
#     if verbose and num_frames_to_save > 0:
#         print(f"\n✅ 提取完成!")
#         print(f"  总处理帧数: {num_frames_to_save}")
#         print(f"  成功保存: {saved_count} 张")
#         print(f"  跳过: {skipped_count} 张 (含读取失败/过滤)")
#         print(f"  保存比例: {saved_count / num_frames_to_save * 100:.1f}%")
#
#     # --- 保存提取元数据 ---
#
#     # 保存提取信息到JSON文件
#     info_file = output_dir / "extraction_info.json"
#     with open(info_file, 'w') as f:
#         json.dump({
#             'video_path': str(video_path),
#             'total_frames': total_frames,
#             'fps': fps,
#             'original_resolution': [original_width, original_height],
#             'extraction_settings': {
#                 'frame_interval': frame_interval,
#                 'start_frame': start_frame,
#                 'end_frame': end_frame,
#                 'target_size': target_size,
#                 'min_object_size': min_object_size,
#                 'quality': quality
#             },
#             'extraction_stats': {
#                 'frames_processed': num_frames_to_save,
#                 'frames_saved': saved_count,
#                 'frames_skipped': skipped_count
#             },
#             # 仅记录关键信息，完整的 frame_list 可能过大
#             'frame_list_count': len(frame_info)
#         }, f, indent=2)
#
#     # 保存文件列表（便于后续标注或数据管理）
#     list_file = output_dir / "file_list.txt"
#     with open(list_file, 'w') as f:
#         for info in frame_info:
#             f.write(f"{info['filename']}\n")
#
#     return {
#         'saved_count': saved_count,
#         'skipped_count': skipped_count,
#         'frame_info_count': len(frame_info),
#         'info_file': str(info_file),
#         'list_file': str(list_file)
#     }
#
#
# def process_video_directory(
#         input_dir,
#         output_base_dir,
#         frame_interval=10,
#         video_extensions=['.mp4', '.avi', '.mov', '.mkv'],
#         **kwargs
# ):
#     """
#     批量处理目录中的所有视频文件。保存目录中不可包含汉字(windows)。
#
#     参数:
#     ----------
#     input_dir : str
#         包含视频文件的输入目录
#     output_base_dir : str
#         输出基目录。每个视频会在该目录下创建以视频名命名的子目录。
#     frame_interval : int, default=10
#         帧间隔
#     video_extensions : list, default=['.mp4', '.avi', '.mov', '.mkv']
#         视频文件扩展名列表
#     **kwargs :
#         传递给 extract_frames_for_yolo 的其他参数 (target_size, quality, etc.)
#
#     返回:
#     ----------
#     dict : 每个视频的处理结果
#     """
#
#     input_dir = Path(input_dir)
#     output_base_dir = Path(output_base_dir)
#
#     if not input_dir.exists():
#         raise ValueError(f"输入目录不存在: {input_dir}")
#
#     # 查找所有视频文件 (使用集合自动去重)
#     video_files = set()
#     for ext in video_extensions:
#         # 查找所有大小写扩展名的文件 (glob在某些系统上不区分大小写，但同时查找更安全)
#         video_files.update(input_dir.glob(f"*{ext.lower()}"))
#         video_files.update(input_dir.glob(f"*{ext.upper()}"))
#
#     # 转换为列表并按名称排序，以便有序处理
#     video_files = sorted(list(video_files))
#
#     if not video_files:
#         raise ValueError(f"在目录 {input_dir} 中未找到符合扩展名 {video_extensions} 的视频文件")
#
#     print(f"\n--- 批量处理开始 ---")
#     print(f"找到 {len(video_files)} 个视频文件")
#
#     results = {}
#
#     # 使用 tqdm 包装外层循环，显示总进度
#     for video_path in tqdm(video_files, desc="总进度", unit="视频"):
#         print(f"\n--- 🎥 正在处理: {video_path.name} ---")
#
#         # 为每个视频创建输出子目录 (使用视频的文件名，不含扩展名)
#         video_name = video_path.stem
#         output_dir = output_base_dir / video_name
#         output_dir.mkdir(parents=True, exist_ok=True)
#
#         try:
#             # 调用单个视频处理函数
#             result = extract_frames_for_yolo(
#                 video_path,
#                 output_dir,
#                 frame_interval=frame_interval,
#                 verbose=True,  # 批量处理时，关闭内部的详细打印，只保留进度条
#                 **kwargs
#             )
#             results[str(video_path)] = result
#         except Exception as e:
#             print(f"❗ 处理 {video_path.name} 时出错: {e}")
#             results[str(video_path)] = {'error': str(e)}
#
#     print(f"\n--- 批量处理完成 ---")
#     return results
#
#
# def parse_arguments():
#     """解析命令行参数"""
#     parser = argparse.ArgumentParser(
#         description='从视频中提取帧用于YOLO训练',
#         formatter_class=argparse.RawTextHelpFormatter  # 保持帮助信息格式
#     )
#
#     # 输入输出参数
#     parser.add_argument('--input', type=str, required=True,
#                         help='输入视频文件路径 (非批量) 或 目录路径 (批量)')
#     parser.add_argument('--output', type=str, required=True,
#                         help='输出图片保存目录')
#
#     # 提取参数
#     parser.add_argument('--interval', type=int, default=10,
#                         help='帧间隔，每隔 n 帧提取一张（默认: 10）')
#     parser.add_argument('--start', type=int, default=0,
#                         help='开始提取的帧序号（默认: 0）')
#     parser.add_argument('--end', type=int, default=None,
#                         help='结束提取的帧序号（默认: 视频结束）')
#
#     # 图像处理参数
#     parser.add_argument('--width', type=int, default=None,
#                         help='输出图片宽度。需同时设置 --height')
#     parser.add_argument('--height', type=int, default=None,
#                         help='输出图片高度。需同时设置 --width')
#     parser.add_argument('--quality', type=int, default=95,
#                         help='JPEG质量 (1-100, 默认: 95)')
#
#     # 过滤参数
#     parser.add_argument('--min-object-size', type=float, default=0.02,
#                         help='最小对象尺寸比例（0.0-1.0）。低于此边缘占比的帧将被跳过 (默认: 0.02)')
#     parser.add_argument('--no-filter', action='store_true',
#                         help='禁用目标检测过滤 (相当于 min-object-size=0)')
#
#     # 批量处理参数
#     parser.add_argument('--batch', action='store_true',
#                         help='启用批量处理模式。此时 --input 必须是包含视频文件的目录。')
#
#     return parser.parse_args()
#
#
# if __name__ == "__main__":
#
#     try:
#         args = parse_arguments()
#
#         # 组合目标尺寸
#         target_size = None
#         if args.width and args.height:
#             target_size = (args.width, args.height)
#         elif args.width or args.height:
#             # 提醒用户需要同时设置宽度和高度
#             print("警告: 必须同时设置 --width 和 --height 才能调整尺寸。将使用原尺寸。")
#
#         # 设置过滤阈值
#         min_object_size = 0 if args.no_filter else args.min_object_size
#
#         # 检查输入是文件还是目录，并根据 --batch 参数决定处理模式
#         input_path = Path(args.input)
#
#         if args.batch:
#             # 批量处理目录
#             if not input_path.is_dir():
#                 raise ValueError(f"启用 --batch 时，输入路径必须是一个目录: {input_path}")
#
#             process_video_directory(
#                 input_dir=input_path,
#                 output_base_dir=args.output,
#                 frame_interval=args.interval,
#                 target_size=target_size,
#                 quality=args.quality,
#                 start_frame=args.start,
#                 end_frame=args.end,
#                 min_object_size=min_object_size,
#                 # verbose 在批量处理内部控制
#             )
#
#         else:
#             # 处理单个视频
#             if not input_path.is_file():
#                 # 如果不是文件，但用户没开批量模式，提示
#                 raise ValueError(f"未启用 --batch 时，输入路径必须是一个视频文件: {input_path}")
#
#             # 输出目录直接使用用户指定的
#             extract_frames_for_yolo(
#                 video_path=input_path,
#                 output_dir=args.output,
#                 frame_interval=args.interval,
#                 target_size=target_size,
#                 quality=args.quality,
#                 start_frame=args.start,
#                 end_frame=args.end,
#                 min_object_size=min_object_size,
#                 verbose=True
#             )
#
#     except ValueError as ve:
#         print(f"\n错误: {ve}")
#     except Exception as e:
#         print(f"\n发生未预期的错误: {e}")
#
#     print("程序结束。")