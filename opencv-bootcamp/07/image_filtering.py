import cv2
import sys
import numpy
import time

PREVIEW  = 0  # Preview Mode
BLUR     = 1  # Blurring Filter
FEATURES = 2  # Corner Feature Detector
CANNY    = 3  # Canny Edge Detector

feature_params = dict(maxCorners=500, qualityLevel=0.2, minDistance=15, blockSize=9)
print(feature_params)
s = 0
if len(sys.argv) > 1:
    s = sys.argv[1]
s = '/media/liutie/备用盘/video/mdg/default-默认/2025-07-29-23-50-00BV1pC89zmEdA【睡前消息932】杭州水污染 慢一步的真相追不上谣言.mp4'
image_filter = PREVIEW
alive = True

win_name = "Camera Filters"
cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
result = None

source = cv2.VideoCapture(s)
fps = source.get(cv2.CAP_PROP_FPS)  # 获取视频的原始帧率（可选）
target_fps = fps+3  # 目标帧率（按需调整）
frame_delay = 1.0 / target_fps  # 每帧的理想间隔时间（秒）

while alive:
    start_time = time.time()  # 记录开始时间
    has_frame, frame = source.read()
    if not has_frame:
        break

    # frame = cv2.flip(frame, 1)

    if image_filter == PREVIEW:
        result = frame
    elif image_filter == CANNY:
        result = cv2.Canny(frame, 80, 150)
    elif image_filter == BLUR:
        result = cv2.blur(frame, (13, 13))
    elif image_filter == FEATURES:
        result = frame
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners = cv2.goodFeaturesToTrack(frame_gray, **feature_params)
        if corners is not None:
            for x, y in numpy.float32(corners).reshape(-1, 2):
                cv2.circle(result, (int(x), int(y)), 10, (0, 255, 0), 1)

    cv2.imshow(win_name, result)
    # 控制帧率
    elapsed = time.time() - start_time
    if elapsed < frame_delay:
        time.sleep(frame_delay - elapsed)

    key = cv2.waitKey(1)
    if key == ord("Q") or key == ord("q") or key == 27:
        alive = False
    elif key == ord("C") or key == ord("c"):
        image_filter = CANNY
    elif key == ord("B") or key == ord("b"):
        image_filter = BLUR
    elif key == ord("F") or key == ord("f"):
        image_filter = FEATURES
    elif key == ord("P") or key == ord("p"):
        image_filter = PREVIEW

source.release()
cv2.destroyWindow(win_name)