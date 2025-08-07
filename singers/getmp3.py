import os
import subprocess


def extract_audio(video_name, video_path='videos'):
    current_dir = os.path.dirname(os.path.realpath(__file__))
    in_video_path = os.path.join(current_dir, video_path, video_name)
    output_audio_path = os.path.join(current_dir, 'audios', video_name.split('.')[0] + '.aac')
    command = [
        'ffmpeg',
        '-i', in_video_path,          # 输入视频文件
        '-vn',                      # 禁用视频流
        '-acodec', 'copy',         # 直接复制音频流（无转码，保持原质量）
        output_audio_path,               # 输出文件（如 .aac, .mp3, .wav）
        '-hide_banner',  # 隐藏FFmpeg欢迎信息
        '-loglevel', 'error'  # 只显示错误日志
    ]
    subprocess.run(command)

    return output_audio_path

