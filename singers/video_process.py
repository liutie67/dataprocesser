import os
import subprocess

import cv2

def canny_video(video_name, video_path='videos'):
    source = os.path.join(video_path, video_name)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print("Error opening video stream or file.")

    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    print('Processed video Resolution:', frame_width, 'x', frame_height)
    fps = cap.get(cv2.CAP_PROP_FPS)
    video_name_out = os.path.join(video_path, 'processed', 'canny-' + video_name.split('.')[0] + '.mp4')
    out_mp4 = cv2.VideoWriter(video_name_out, cv2.VideoWriter_fourcc(*"XVID"), fps, (frame_width, frame_height))

    # Read until video is completed
    while cap.isOpened():
        # Capture frame-by-frame
        ret, frame = cap.read()
        if ret:
            # Write the frame to the output files
            frame = cv2.Canny(frame, 80, 150)
            frame[70:160, 80:210] = 0
            frame[30:80, 1650:1870] = 0
            frame[700:1000, 1580:1870] = 0
            frame = cv2.bitwise_not(frame)
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            out_mp4.write(frame)
        # Break the loop
        else:
            break

    cap.release()
    out_mp4.release()
    print('Processed video saved as', video_name_out, '.')

    return video_name_out


def convert_to_x264(input_from_canny_video):
    """
    subprocess.run('ffmpeg -y -i "output.mp4" -c:v libx264 "output.mp4"  -hide_banner -loglevel error')

    将视频转换为H.264编码（兼容性更好）
    参数:
        input_video (str): 输入视频路径（如 "output.mp4"）
        output_video (str): 输出视频路径（如 "output_x264.mp4"）
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    input_video = os.path.join(current_dir, input_from_canny_video)
    output_video = input_video.split('.')[0] + '-x264.mp4'
    command = [
        'ffmpeg',
        '-y',  # 覆盖输出文件无需确认
        '-i', input_video,  # 输入文件
        '-c:v', 'libx264',  # 视频编码器
        output_video,  # 输出文件
        '-hide_banner',  # 隐藏FFmpeg欢迎信息
        '-loglevel', 'error'  # 只显示错误日志
    ]

    # 执行命令
    result = subprocess.run(command, capture_output=True, text=True)

    # 检查错误
    if result.returncode != 0:
        print(f"错误：转换失败！FFmpeg输出：\n{result.stderr}")
    else:
        print(f"x 264 Processed: {input_from_canny_video.split('.')[0]}-x264.mp4")

    return output_video


def combine_video_audio(input_from_convert2x264, input_from_extract_audio, output_path='videos'):
    video_path = input_from_convert2x264
    audio_path = input_from_extract_audio
    current_dir = os.path.dirname(os.path.realpath(__file__))
    output_video = os.path.join(current_dir, output_path, input_from_extract_audio.split(os.sep)[-1] + '-final.mp4')
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_video,  # 输出文件
        '-hide_banner',  # 隐藏FFmpeg欢迎信息
        '-loglevel', 'error'  # 只显示错误日志
    ]

    subprocess.run(cmd, check=True)
    print('Finished.')
