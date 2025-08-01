import cv2
import sys

# s = 0
# if len(sys.argv) > 1:
#     s = sys.argv[1]

s = '/media/liutie/备用盘/video/mdg/default-默认/2025-07-29-23-50-00BV1pC89zmEdA【睡前消息932】杭州水污染 慢一步的真相追不上谣言.mp4'
source = cv2.VideoCapture(s)

win_name = 'Camera Preview'
cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

while cv2.waitKey(1) != 27: # Escape
    has_frame, frame = source.read()
    if not has_frame:
        break
    # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame = cv2.add(frame, -50)
    cv2.imshow(win_name, frame)

source.release()
cv2.destroyWindow(win_name)