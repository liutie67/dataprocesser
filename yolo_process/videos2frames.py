import os
import cv2
import csv
import time
from pathlib import Path


def capture_training_data_v3(video_path, save_dir="dataset",
                             extract_num=5, interval=5, mode='full',
                             class_names=None):  # <--- 新增 class_names 参数
    """
    交互式多类别视频数据采集工具 V3.3

    - v3.1 新增 class_names 参数支持自定义按键语义。
    - v3.2 新增撤回操作功能。
    - v3.3 新增进度条、时间轴标记可视化、重启程序自动加载已有标记。

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
    # === [v3.3 新增] 类别颜色映射 (BGR格式) ===
    # Z:红, X:绿, C:蓝, V:黄, B:青
    CLASS_COLORS = {
        'z': (0, 0, 255),
        'x': (0, 255, 0),
        'c': (255, 0, 0),
        'v': (0, 255, 255),
        'b': (255, 255, 0),
        'default': (200, 200, 200)
    }

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

    # === [v3.3 新增] 预读取 CSV 到内存字典，用于回显和进度条绘制 ===
    # 结构: { frame_id(int): class_label_suffix(str) }  例如: {150: 'z'}
    global_marked_frames = {}

    if file_exists:
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # 跳过表头
                for row in reader:
                    if len(row) >= 4:
                        try:
                            f_id = int(row[1])
                            c_label = row[3]  # 格式通常是 "class_z"
                            # 提取后缀 'z' 用于颜色映射，如果格式不对则保留原样
                            short_label = c_label.split('_')[-1] if '_' in c_label else c_label
                            global_marked_frames[f_id] = short_label
                        except ValueError:
                            continue
            print(f"--- [v3.3] 已加载历史标记: {len(global_marked_frames)} 条 ---")
        except Exception as e:
            print(f"警告: 读取历史CSV失败 - {e}")

    csv_file = open(csv_path, mode='a', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)
    if not file_exists:
        csv_writer.writerow(['timestamp_str', 'frame_id', 'timestamp_ms', 'class_label', 'note'])

    # --- 3. 视频载入与信息打印 ---
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    base_fps = cap.get(cv2.CAP_PROP_FPS)

    # 窗口设置 (允许调整大小以适应进度条)
    cv2.namedWindow('YOLO Multi-Class Collector', cv2.WINDOW_NORMAL)

    print(f"--- 启动采集 V3.3: {video_name} ---")
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
    msg_sub = "(Switch Input Method to ENG! & Press SPACE to Start)"

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

    # === [v3.2.1新增] 初始化消息系统 ===
    ui_message = ""  # 待显示的文字
    ui_msg_end_time = 0  # 消息显示的截止时间(时间戳)

    # === [v3.2新增] 初始化历史记录栈 ===
    # 结构: [{'files': [图片路径list], 'csv_line': [csv数据list]}]
    history_stack = []

    # 2. 等待开始逻辑
    print(">>> [就绪] 请按空格键开始播放...")
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
        # --- [修正] 获取当前帧号 ---
        # cap.read() 读完一帧后指针会自动+1，指向“下一帧”
        # 所以我们需要 -1 才能得到“当前看到的这一帧”的正确索引
        curr_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1

        # --- [修正] 重新计算时间戳 ---
        # 建议直接用帧号换算，比 get(POS_MSEC) 更精准且与帧号严格对齐
        curr_ms = (curr_pos / base_fps) * 1000.0 if base_fps > 0 else 0

        # --- UI 绘制 ---
        display_img = current_frame.copy()
        img_h, img_w = display_img.shape[:2]

        # --- 辅助函数：绘制带阴影的文字 ---
        def draw_shadow_text(img, text, pos, scale, color, thickness, offset=2):
            x, y = pos
            # 1. 绘制黑色阴影 (向右下偏移 offset 像素)
            cv2.putText(img, text, (x + offset, y + offset), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness)
            # 2. 绘制彩色正文
            cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

        # 1. 基础信息
        info_text = f"Frame: {curr_pos}/{total_frames} | Speed: x{speed_multiplier}"
        draw_shadow_text(display_img, info_text, (20, 40), 0.7, (174, 20, 255), 2)

        # 2. 菜单提示
        # 动态生成按键提示菜单
        menu_text = " ".join(display_labels)
        draw_shadow_text(display_img, menu_text, (20, 80), 0.6, (0, 140, 255), 1, offset=1)

        # === [v3.3 新增] 历史标记回显 (Ghost Marker) ===
        # 如果当前帧在已标记列表中，显示醒目的提示
        if curr_pos in global_marked_frames:
            m_label = global_marked_frames[curr_pos]
            # 获取对应的颜色，如果没有则用灰色
            m_color = CLASS_COLORS.get(m_label, CLASS_COLORS['default'])
            marker_text = f"[MARKED: CLASS_{m_label.upper()}]"

            # 在屏幕正中央显示
            text_size = cv2.getTextSize(marker_text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0]
            center_x = (img_w - text_size[0]) // 2
            center_y = (img_h // 2)

            # 画一个半透明背景框让文字更清楚
            overlay = display_img.copy()
            cv2.rectangle(overlay, (center_x - 10, center_y - 40),
                          (center_x + text_size[0] + 10, center_y + 10), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.5, display_img, 0.5, 0, display_img)

            draw_shadow_text(display_img, marker_text, (center_x, center_y), 1.5, m_color, 3)

        # 3. [v3.2.1核心修改] 全局消息显示逻辑
        # 如果当前时间还没过截止时间，或者消息是永久的(end_time=-1)，就显示
        if ui_message and (time.time() < ui_msg_end_time or ui_msg_end_time == -1):
            # 绘制显眼的黄色文字
            draw_shadow_text(display_img, ui_message, (20, 120), 1, (0, 255, 255), 2)

        # 4. 状态提示
        status_text = "PAUSED" if paused else "PLAYING"
        color = (0, 0, 255) if paused else (0, 255, 0)
        draw_shadow_text(display_img, status_text, (img_w - 150, 40), 0.7, color, 2)

        # === [v3.3 新增] 底部进度条与时间轴标记 ===
        bar_height = 20
        bar_margin = 30  # 距离底部的距离
        bar_y = img_h - bar_margin

        # (A) 绘制进度条底槽 (深灰色)
        cv2.rectangle(display_img, (0, bar_y), (img_w, bar_y + bar_height), (50, 50, 50), -1)

        # (B) 绘制当前进度 (白色半透明)
        if total_frames > 0:
            prog_width = int((curr_pos / total_frames) * img_w)
            cv2.rectangle(display_img, (0, bar_y), (prog_width, bar_y + bar_height), (200, 200, 200), -1)

        # (C) 绘制时间轴上的标记点
        for m_fid, m_lbl in global_marked_frames.items():
            if total_frames > 0:
                # 计算标记在进度条上的 x 坐标
                m_x = int((m_fid / total_frames) * img_w)
                m_c = CLASS_COLORS.get(m_lbl, CLASS_COLORS['default'])
                # 绘制一条竖线代表标记
                cv2.line(display_img, (m_x, bar_y), (m_x, bar_y + bar_height), m_c, 2)

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
        # --- [v3.2新增] 撤回功能 (Backspace: ASCII 8) ---
        elif paused and key == 8:
            if len(history_stack) > 0:
                print(" >> 正在撤回上一条记录...")
                last_record = history_stack.pop()

                # 1. 删除图片文件
                for img_path in last_record['files']:
                    try:
                        if img_path.exists():
                            os.remove(img_path)
                            print(f"    已删除: {img_path.name}")
                    except Exception as e:
                        print(f"    删除失败: {e}")

                # 2. 删除 CSV 最后一行 (需要关闭-读取-重写-重开)
                csv_file.close()  # 先关闭句柄

                try:
                    # 获取要删除的帧ID，用于更新内存中的标记字典
                    # csv_row结构: [time, frame_id, ms, label, mode]
                    frame_id_to_remove = int(last_record['csv_row'][1])
                    # === [v3.3] 从内存字典中移除，进度条上的线会立即消失 ===
                    if frame_id_to_remove in global_marked_frames:
                        del global_marked_frames[frame_id_to_remove]

                    with open(csv_path, 'r', encoding='utf-8') as f_read:
                        lines = f_read.readlines()

                    # 只有当文件有内容且不只有表头时才删除
                    if len(lines) > 1:
                        with open(csv_path, 'w', encoding='utf-8') as f_write:
                            f_write.writelines(lines[:-1])  # 写回除最后一行外的所有行
                            print("    CSV记录已回滚")
                except Exception as e:
                    print(f"    CSV回滚失败: {e}")

                # 重新以追加模式打开 CSV
                csv_file = open(csv_path, mode='a', newline='', encoding='utf-8')
                csv_writer = csv.writer(csv_file)

                # [v3.2.1修改] UI 反馈：更新全局消息
                ui_message = f"UNDO SUCCESS! Stack: {len(history_stack)}"
                ui_msg_end_time = time.time() + 3.0  # 显示3秒

                # v3.2.1
                # 注意：撤回后我们还在 paused 状态，主循环会 waitKey(0)
                # 这时因为 loop 还没重绘，我们需要continue跳过本次循环剩余部分
                # 直接强行进入下一轮循环，利用主循环头部的 draw 逻辑来刷新画面
                continue
            else:
                print(" >> 历史栈为空，无法撤回")
                ui_message = "Stack Empty! Nothing to undo."
                ui_msg_end_time = time.time() + 2.0
        elif paused and (key == ord('d') or key == ord('f')):
            # --- [修正] 微调逻辑 ---
            # d (后退): 想看上一帧，就是 current - 1
            # f (前进): 想看下一帧，就是 current + 1
            if key == ord('d'):
                target_pos = max(0, curr_pos - 1)
            else:  # key == 'f'
                target_pos = curr_pos + 1

            cap.set(cv2.CAP_PROP_POS_FRAMES, target_pos)
            ret, frame = cap.read()
            if ret: current_frame = frame
            continue

        # --- 核心功能：分类截取 (Z, X, C, V, B) ---
        elif key in KEY_MAP:
            class_label = KEY_MAP[key]
            print(f" >> [{class_label.upper()}] 类触发: 帧 {curr_pos}")

            # === [v3.3] 更新内存字典，以便进度条立即显示新标记 ===
            # KEY_MAP里的 label 可能是 "kilometer" 也可能是 "z"
            # 为了颜色映射方便，如果是自定义名字，我们需要反查出它是哪个按键对应的(z/x/c...)
            # 这里简化处理：直接存入，在绘制时如果查不到颜色就用灰色
            # 或者我们尽量存入短代码。这里为了逻辑简单，我们存入 class_label
            # 但颜色映射需要稍微适配一下：

            # 尝试找到对应的短代码(z/x/c)用于颜色
            short_code = 'default'
            for base_k, base_c in zip(BASE_KEYS, BASE_CHARS):
                if key == base_k:
                    short_code = base_c
                    break

            # 存入字典: key=帧号, value=短代码(用于颜色)
            # 注意：这里存短代码是为了画图颜色方便。如果 csv 里存的是长名字，这里只是为了UI显示
            global_marked_frames[curr_pos] = short_code

            # 准备数据
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            csv_row_data = [time_str, curr_pos, f"{curr_ms:.2f}", f"class_{class_label}", mode]

            # (A) 写入 CSV
            csv_writer.writerow(csv_row_data)
            csv_file.flush()

            # [v3.2新增] 记录本次产生的文件，用于撤回
            current_batch_files = []

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
                        full_path = class_dir / fname
                        cv2.imwrite(str(full_path), frame_temp)

                        # [v3.2新增] 将路径加入列表
                        current_batch_files.append(full_path)
                        save_count += 1

                # 4. 恢复位置
                cap.set(cv2.CAP_PROP_POS_FRAMES, backup_pos - 1)
                ret, frame = cap.read()
                if ret: current_frame = frame

            # [v3.2新增] 将本次操作压入历史栈
            history_stack.append({
                'files': current_batch_files,
                'csv_row': csv_row_data
            })

            # (C) [v3.2.1修改] UI 反馈：更新全局消息变量
            ui_message = f"Class [{class_label.upper()}] Saved! (Stack: {len(history_stack)})"
            draw_shadow_text(display_img, ui_message, (20, 120), 1, (0, 255, 255), 2)
            # 立即绘制刚刚加上的进度条竖线 (为了更好的交互体验，手动补画一笔，或者等待下一帧刷新)
            # 这里选择刷新整个画面并暂停
            # cv2.imshow('YOLO Multi-Class Collector', display_img)  # #############################################################

            # 如果是暂停状态，强制等待空格
            if paused:
                ui_msg_end_time = -1
                # 重新在当前画面画图略显复杂，简单的方法是利用下一轮循环
                # 但我们需要卡住暂停，所以这里拷贝一份 display_img 用于显示
                # 注意：由于我们已经更新了 global_marked_frames，下一帧自然会有线
                # 所以我们只需要显示文字并等待
                temp_img = display_img.copy()
                draw_shadow_text(temp_img, ui_message, (20, 120), 1, (0, 255, 255), 2)

                cv2.imshow('YOLO Multi-Class Collector', temp_img)

                while True:
                    sub_key = cv2.waitKey(0) & 0xFF
                    if sub_key == 32:  # 空格
                        ui_message = ""  # 清除消息
                        break
                    elif sub_key == 27:  # ESC
                        cap.release()
                        cv2.destroyAllWindows()
                        csv_file.close()
                        return
            else:
                # 播放时，显示 2 秒后自动消失
                ui_msg_end_time = time.time() + 2.0

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
