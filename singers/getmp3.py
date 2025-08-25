import os
import subprocess


def extract_audio(in_video_path, audio_save2_path='audios'):
    current_dir = os.path.dirname(os.path.realpath(__file__))
    video_name = os.path.split(in_video_path)[-1]
    os.makedirs(os.path.join(current_dir, audio_save2_path), exist_ok=True)
    output_audio_path = os.path.join(current_dir, audio_save2_path, video_name.split('.')[0] + '.aac')
    if os.path.exists(output_audio_path):
        print(output_audio_path, ' already exists !')
        return output_audio_path
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

