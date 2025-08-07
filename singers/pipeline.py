import os

from video_process import canny_video, convert_to_x264, combine_video_audio
from getmp3 import extract_audio


def pipeline(video_name, video_path='videos'):
    os.makedirs(video_path, exist_ok=True)
    os.makedirs(os.path.join(video_path, 'processed'), exist_ok=True)
    if os.path.exists(os.path.join(video_path, video_name)):
        audio_out = extract_audio(video_name)
        canny_out = canny_video(video_name)
        convert_out = convert_to_x264(canny_out)
        combine_video_audio(convert_out, audio_out)
    else:
        print('No such video:', os.path.join(video_path, video_name))
        return 'Wrong video path!'


pipeline('单依纯《天空》.mp4')
