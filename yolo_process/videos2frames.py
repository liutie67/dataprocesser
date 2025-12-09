import cv2
import os
import csv
import time
from pathlib import Path


def capture_training_data_v2(video_path, save_dir="dataset/raw_images",
                             extract_num=3, interval=5, mode='full'):
    """
    交互式视频数据采集工具 (YOLO数据集构建辅助)。

    支持倍速播放、逐帧进退、自动记录时间点到CSV，并可选择自动截取前后帧。

    Parameters
    ----------
    video_path : str
        视频文件的路径。
    save_dir : str, optional
        图片保存的根目录，默认为 "dataset/raw_images"。
    extract_num : int, optional
        截取范围参数。默认为 3，表示截取 [当前帧-3 ... 当前帧 ... 当前帧+3]。
    interval : int, optional
        截取间隔。默认为 5，表示每隔 5 帧保存一张，防止数据重复。
    mode : {'full', 'mark_only'}, optional
        工作模式:
        - 'full': 打点记录 CSV 并立即执行截图保存 (默认)。
        - 'mark_only': 仅在 CSV 中记录帧号，不进行截图操作 (适合性能较差的机器或快速初筛)。

    Returns
    -------
    None
        函数运行过程中会生成图片文件和 .csv 记录文件。

    # Examples
    # --------
    # >>> # 完整模式：每按一次S，保存前后共7张图(3+1+3)，并记录CSV
    # >>> capture_training_data_v2('traffic.mp4', mode='full')
    # >>> # 快速打点模式：只记CSV，不截图
    # >>> capture_training_data_v2('traffic.mp4', mode='mark_only')
    """

    # --- 1. 初始化路径与文件 ---
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"Error: 视频文件不存在 - {video_path}")
        return

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    # CSV 初始化：与视频同名，保存在视频同级目录下
    csv_path = video_path.with_suffix('.csv')
    file_exists = csv_path.exists()

    csv_file = open(csv_path, mode='a', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)
    if not file_exists:
        csv_writer.writerow(['timestamp_str', 'frame_id', 'timestamp_ms', 'note'])

    # --- 2. 视频载入 ---
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    base_fps = cap.get(cv2.CAP_PROP_FPS)
    video_name = video_path.stem

    print(f"--- 启动采集: {video_name} ---")
    print(f"模式: {mode} | 总帧数: {total_frames} | FPS: {base_fps}")
    print("---------------------------------------------------------")
    print("【播放控制】 空格: 暂停/继续 | 1/2/3: 切换倍速")
    print("【暂停微调】 d: 后退一帧 | f: 前进一帧")
    print("【数据采集】 s: 记录并保存(根据模式)")
    print("【退出程序】 ESC")
    print("---------------------------------------------------------")

    # --- 3. 状态变量 ---
    paused = False
    speed_multiplier = 1.0  # 1倍速
    current_frame = None  # 缓存当前帧用于暂停时重绘

    ret, frame = cap.read()  # 预读第一帧
    if not ret: return
    current_frame = frame

    while True:
        # 获取当前播放位置信息
        curr_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        curr_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

        # --- UI 绘制 (在副本上绘制，不污染原图) ---
        display_img = current_frame.copy()

        # 左上角：基础信息
        info_text = f"Frame: {curr_pos}/{total_frames} | Speed: {speed_multiplier}x"
        cv2.putText(display_img, info_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # 右上角：状态提示
        status_text = "PAUSED" if paused else "PLAYING"
        color = (0, 0, 255) if paused else (0, 255, 0)
        cv2.putText(display_img, status_text, (display_img.shape[1] - 150, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        cv2.imshow('YOLO Data Collector', display_img)

        # --- 键盘事件监听 ---
        # 如果暂停，无限等待按键(wait 0)；如果播放，根据倍速计算延迟
        if paused:
            delay = 0
        else:
            delay = int(1000 / (base_fps * speed_multiplier))
            if delay < 1: delay = 1  # 防止延迟过低

        key = cv2.waitKey(delay) & 0xFF

        # --- 逻辑处理 ---

        # 1. 退出
        if key == 27:  # ESC
            break

        # 2. 暂停/播放
        elif key == 32:  # Space
            paused = not paused

        # 3. 倍速控制 (1, 2, 3)
        elif key == ord('1'):
            speed_multiplier = 1.0
        elif key == ord('2'):
            speed_multiplier = 2.0
        elif key == ord('3'):
            speed_multiplier = 3.0

        # 4. 逐帧微调 (仅在暂停时有效)
        elif paused and (key == ord('d') or key == ord('f')):
            target_pos = curr_pos
            if key == ord('d'):  # 后退 (Previous)
                target_pos = max(0, curr_pos - 2)  # -2 是因为read()会自动+1，所以要回退两步再读才是上一帧
            elif key == ord('f'):  # 前进 (Next)
                target_pos = curr_pos  # 当前已经是下一帧的准备位置了

            cap.set(cv2.CAP_PROP_POS_FRAMES, target_pos)
            ret, frame = cap.read()
            if ret:
                current_frame = frame
            # 微调后保持暂停状态，直接进入下一次循环刷新画面
            continue

        # 5. 核心功能：截取/打点 (S键)
        elif key == ord('s'):
            print(f" >> [S] 触发: 帧 {curr_pos}")

            # (A) 写入 CSV
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            csv_writer.writerow([time_str, curr_pos, f"{curr_ms:.2f}", mode])
            csv_file.flush()  # 立即写入硬盘

            # (B) 截图逻辑
            save_count = 0
            if mode == 'full':
                # 记录原始位置以便跳回
                backup_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

                # 计算目标帧列表
                target_frames = []
                for i in range(-extract_num, extract_num + 1):
                    f_idx = curr_pos + (i * interval)
                    if 0 <= f_idx < total_frames:
                        target_frames.append(f_idx)

                # 跳转并保存
                for f_idx in target_frames:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)  # 注意：set使用的是0-based index
                    ret_temp, frame_temp = cap.read()
                    if ret_temp:
                        fname = f"{video_name}_f{f_idx:06d}.jpg"
                        cv2.imwrite(str(save_path / fname), frame_temp)
                        save_count += 1

                # 恢复位置
                cap.set(cv2.CAP_PROP_POS_FRAMES, backup_pos - 1)  # -1 抵消由于read造成的位移
                # 重新读取当前帧以确保画面同步
                ret, frame = cap.read()
                if ret: current_frame = frame

            # (C) UI 反馈：显示“保存成功”并保持暂停
            # 在当前画面上额外绘制一行字
            feedback_text = f"SAVED! CSV Updated. Imgs: {save_count}" if mode == 'full' else "MARKED! CSV Updated."
            cv2.putText(display_img, feedback_text, (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.imshow('YOLO Data Collector', display_img)

            # 关键修改：如果是暂停状态，按S后必须等待空格才继续，否则如果是播放状态，按S后继续播放
            if paused:
                # 进入死循环等待，直到按下空格(32)继续，或者按下d/f微调，或者ESC退出
                while True:
                    sub_key = cv2.waitKey(0) & 0xFF
                    if sub_key == 32:  # 空格：继续播放
                        break  # 跳出等待循环，回到主循环
                    elif sub_key == 27:  # ESC
                        cap.release()
                        cv2.destroyAllWindows()
                        csv_file.close()
                        return
                    # 这里也可以允许在保存后的等待期继续按d/f微调，这里暂略以保持逻辑简单

            # 如果原本是播放状态，代码流会自然进入下一次循环继续播放

        # --- 正常播放逻辑 ---
        if not paused:
            ret, frame = cap.read()
            if not ret:
                print("视频播放结束")
                # 循环播放逻辑：
                # cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                # ret, frame = cap.read()
                break
            current_frame = frame

    # 清理资源
    cap.release()
    cv2.destroyAllWindows()
    csv_file.close()
    print(f"采集结束。CSV记录已保存至: {csv_path}")


# --- 使用示例 ---
if __name__ == "__main__":
    # 请修改这里的视频路径
    # 模式: 'full' (截图+记录) 或 'mark_only' (仅记录)
    capture_training_data_v2(r"C:\Users\vides.mp4", mode='full')
    pass