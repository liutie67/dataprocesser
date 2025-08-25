import os

from video_process import canny_video, convert_to_x264, combine_video_audio
from getmp3 import extract_audio


def pipeline(video_path, video_save2_path='videos'):
    os.makedirs(video_save2_path, exist_ok=True)
    os.makedirs(os.path.join(video_save2_path, 'processed'), exist_ok=True)
    if os.path.exists(video_path):
        video_name = os.path.split(video_path)[-1]
        video_dir = os.path.dirname(video_path)
        audio_out = extract_audio(video_path)
        canny_out = canny_video(video_name, video_dir)
        convert_out = convert_to_x264(canny_out)
        combine_video_audio(convert_out, audio_out)
        return None
    else:
        print('No such video:', video_path)
        return 'Wrong video path!'


if __name__ == '__main__':
    pipeline('单依纯《天空》.mp4')
