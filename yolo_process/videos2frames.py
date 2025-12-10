import cv2
import csv
import time
from pathlib import Path


def capture_training_data_v3(video_path, save_dir="dataset",
                             extract_num=3, interval=5, mode='full',
                             class_names=[]):  # <--- 新增 class_names 参数
    """
    交互式多类别视频数据采集工具 V3.1
    (新增 class_names 参数支持自定义按键语义。)

    支持多键分类(z/x/c/v/b)，仅向前回溯截取，并自动分文件夹存储。

    Parameters
    ----------
    video_path : str
        视频文件的路径。
    save_dir : str, optional
        数据保存根目录。最终结构为: save_dir / 视频名 / class_x / 图片.jpg
    extract_num : int, optional
        向前回溯截取的数量。
        例如 extract_num=3, interval=5, 当前帧100:
        截取帧为 [85, 90, 95, 100]。
    interval : int, optional
        截取间隔帧数。
    mode : {'full', 'mark_only'}, optional
        'full': 记录 CSV 并保存图片。
        'mark_only': 仅记录 CSV。
    class_names : list, optional
        待分类型的名称，最多支持5种。按输入顺序映射到z, x, c, v, b

    Returns
    -------
    None
    """

    # --- 1. 初始化路径 ---
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"Error: 视频文件不存在 - {video_path}")
        return

    video_name = video_path.stem
    output_root = Path(save_dir) / video_name
    output_root.mkdir(parents=True, exist_ok=True)

    # --- 2. 构建按键映射 (KEY_MAP) ---
    # 定义基础按键列表 (顺序对应 z, x, c, v, b)
    BASE_KEYS = [ord('z'), ord('x'), ord('c'), ord('v'), ord('b')]
    BASE_CHARS = ['z', 'x', 'c', 'v', 'b']

    KEY_MAP = {}
    display_labels = []  # 用于UI显示

    # 截断多余的输入 (最多5个)
    safe_class_names = class_names[:5] if class_names else []

    for i, key_code in enumerate(BASE_KEYS):
        # 如果用户提供了对应的名字，使用用户定义的名字
        if i < len(safe_class_names):
            label = safe_class_names[i]
            # UI 显示格式: [Z]kilometer
            display_labels.append(f"[{BASE_CHARS[i].upper()}]{label}")
        else:
            # 否则使用默认字符作为名字
            label = BASE_CHARS[i]
            # UI 显示格式: [C] (未命名时简化显示)
            display_labels.append(f"[{BASE_CHARS[i].upper()}]")

        KEY_MAP[key_code] = label

    # CSV 初始化
    csv_path = output_root / f"{video_name}_labels.csv"
    file_exists = csv_path.exists()

    csv_file = open(csv_path, mode='a', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)
    if not file_exists:
        csv_writer.writerow(['timestamp_str', 'frame_id', 'timestamp_ms', 'class_label', 'note'])

    # --- 3. 视频载入与信息打印 ---
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    base_fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"--- 启动采集 V3.1: {video_name} ---")
    print(f"保存路径: {output_root}")
    print("---------------------------------------------------------")
    print("【当前按键映射】")
    for i, key_code in enumerate(BASE_KEYS):
        label = KEY_MAP[key_code]
        print(f"  按键 '{BASE_CHARS[i]}' -> 类别: {label}")
    print("---------------------------------------------------------")
    print("【播放控制】 空格: 暂停/继续 | 1/2/3: 切换倍速")
    print("【退出程序】 ESC")
    print("---------------------------------------------------------")

    # --- 状态变量 ---
    paused = False
    speed_multiplier = 1.0
    current_frame = None

    ret, frame = cap.read()
    if not ret: return
    current_frame = frame

    # === 修改开始: 开场暂停并显示提示 ===

    # 1. 制作开场引导画面
    intro_frame = current_frame.copy()
    h, w = intro_frame.shape[:2]

    # 提示语 (OpenCV默认不支持中文，使用英文替代)
    # "Hit Z/X/C/V/B at the LAST frame!"
    # "(Press SPACE to Start)"
    msg_title = "Hit Z/X/C/V/B at the LAST frame you can see object!"
    msg_sub = "(Press SPACE to Start)"

    font = cv2.FONT_HERSHEY_SIMPLEX

    # 计算文字大小以居中
    (w_title, h_title), _ = cv2.getTextSize(msg_title, font, 1.8, 3)
    (w_sub, h_sub), _ = cv2.getTextSize(msg_sub, font, 1.0, 2)

    x_title = (w - w_title) // 2
    x_sub = (w - w_sub) // 2
    y_center = h // 2

    # 绘制文字: 阴影(黑色) + 本体(亮色) 实现高对比度
    # 标题 (亮黄色)
    cv2.putText(intro_frame, msg_title, (x_title + 2, y_center - 10 + 2), font, 1.8, (0, 0, 0), 3)  # 阴影
    cv2.putText(intro_frame, msg_title, (x_title, y_center - 10), font, 1.8, (0, 255, 255), 3)  # 本体

    # 副标题 (亮绿色)
    cv2.putText(intro_frame, msg_sub, (x_sub + 2, y_center + 50 + 2), font, 1.0, (0, 0, 0), 2)  # 阴影
    cv2.putText(intro_frame, msg_sub, (x_sub, y_center + 50), font, 1.0, (0, 255, 0), 2)  # 本体

    cv2.imshow('YOLO Multi-Class Collector', intro_frame)
    print(">>> [就绪] 请按空格键开始播放...")

    # 2. 强制等待循环
    while True:
        start_key = cv2.waitKey(0) & 0xFF
        if start_key == 32:  # Space
            break
        elif start_key == 27:  # ESC
            cap.release()
            cv2.destroyAllWindows()
            csv_file.close()
            return

    # === 修改结束 ===

    # --- 状态变量 ---
    paused = False  # 按空格后，默认状态为自动播放
    # speed_multiplier = 1.0 ... (后续代码保持不变)

    while True:
        curr_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        curr_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

        # --- UI 绘制 ---
        display_img = current_frame.copy()

        info_text = f"Frame: {curr_pos}/{total_frames} | Speed: {speed_multiplier}x"
        cv2.putText(display_img, info_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (174, 20, 255), 2)

        # 动态生成按键提示菜单 (使用初始化时生成的 display_labels)
        # 使用 join 拼接，如果名字太长可能需要你手动调整字体大小或位置
        menu_text = " ".join(display_labels)
        cv2.putText(display_img, menu_text, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (5, 255, 5), 1)

        status_text = "PAUSED" if paused else "PLAYING"
        color = (0, 0, 255) if paused else (0, 255, 0)
        cv2.putText(display_img, status_text, (display_img.shape[1] - 150, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        cv2.imshow('YOLO Multi-Class Collector', display_img)

        # --- 键盘事件监听 ---
        if paused:
            delay = 0
        else:
            delay = int(1000 / (base_fps * speed_multiplier))
            if delay < 1: delay = 1

        key = cv2.waitKey(delay) & 0xFF

        # --- 逻辑处理 ---
        if key == 27:  # ESC
            break
        elif key == 32:  # Space
            paused = not paused
        elif key == ord('1'):
            speed_multiplier = 1.0
        elif key == ord('2'):
            speed_multiplier = 2.0
        elif key == ord('3'):
            speed_multiplier = 3.0
        elif key == ord('5'):
            speed_multiplier = 0.5
        elif paused and (key == ord('d') or key == ord('f')):
            # 微调逻辑
            target_pos = max(0, curr_pos - 2) if key == ord('d') else curr_pos
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_pos)
            ret, frame = cap.read()
            if ret: current_frame = frame
            continue

        # --- 核心功能：分类截取 (Z, X, C, V, B) ---
        elif key in KEY_MAP:
            class_label = KEY_MAP[key]
            print(f" >> [{class_label.upper()}] 类触发: 帧 {curr_pos}")

            # (A) 写入 CSV
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            # 记录类别
            csv_writer.writerow([time_str, curr_pos, f"{curr_ms:.2f}", f"class_{class_label}", mode])
            csv_file.flush()

            save_count = 0
            if mode == 'full':
                backup_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

                # 1. 准备分类子文件夹
                class_dir = output_root / f"class_{class_label}"
                class_dir.mkdir(exist_ok=True)

                # 2. 计算回溯帧列表 (只取当前及以前)
                # range(-extract_num, 1) 生成: -3, -2, -1, 0
                target_frames = []
                for i in range(-extract_num, 1):
                    f_idx = curr_pos + (i * interval)
                    if 0 <= f_idx < total_frames:
                        target_frames.append(f_idx)

                # 3. 跳转并保存
                for f_idx in target_frames:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                    ret_temp, frame_temp = cap.read()
                    if ret_temp:
                        # 文件名: 视频名_类别_帧号.jpg
                        fname = f"{video_name}_{class_label}_{f_idx:06d}.jpg"
                        cv2.imwrite(str(class_dir / fname), frame_temp)
                        save_count += 1

                # 4. 恢复位置
                cap.set(cv2.CAP_PROP_POS_FRAMES, backup_pos - 1)
                ret, frame = cap.read()
                if ret: current_frame = frame

            # (C) UI 反馈与暂停锁定
            feedback_text = f"Class [{class_label.upper()}] Saved! Count: {save_count}"
            cv2.putText(display_img, feedback_text, (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.imshow('YOLO Multi-Class Collector', display_img)

            # 如果是暂停状态，强制等待空格
            if paused:
                while True:
                    sub_key = cv2.waitKey(0) & 0xFF
                    if sub_key == 32:
                        break
                    elif sub_key == 27:
                        cap.release()
                        cv2.destroyAllWindows()
                        csv_file.close()
                        return

        # --- 正常播放 ---
        if not paused:
            ret, frame = cap.read()
            if not ret: break
            current_frame = frame

    cap.release()
    cv2.destroyAllWindows()
    csv_file.close()
    print(f"采集结束。数据保存在: {output_root}")


# --- 使用示例 ---
if __name__ == "__main__":
    # 示例：回溯截取前3帧+当前帧，间隔5帧
    # 按 'z' 会保存到 class_z 文件夹，按 'x' 保存到 class_x 文件夹
    capture_training_data_v3(r"C:\Users\video.MOV",
                             save_dir="dataset",
                             extract_num=5,
                             class_names=['a', 'b', 'c'])
    pass
