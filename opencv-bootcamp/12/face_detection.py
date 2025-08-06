import os
import cv2
import sys
from zipfile import ZipFile
from urllib.request import urlretrieve


'''
    相关算法和技术
        SSD (Single Shot MultiBox Detector)
            一种单阶段目标检测算法，可以直接预测边界框和类别
            相比两阶段检测器(如Faster R-CNN)速度更快
            使用多尺度特征图进行检测，可以处理不同大小的对象
        OpenCV DNN模块
            支持多种深度学习框架的模型(Caffe, TensorFlow, Torch, Darknet等)
            可以在CPU上高效运行深度学习模型
            提供统一的接口加载和运行不同框架的模型
        人脸检测流程
            加载预训练模型
            对输入图像进行预处理(尺寸调整、归一化等)
            通过网络前向传播获取检测结果
            后处理检测结果(过滤低置信度检测、非极大抑制等)
'''

# ========================-Downloading Assets-========================
def download_and_unzip(url, save_path):
    print(f"Downloading and extracting assests....", end="")

    # Downloading zip file using urllib package.
    urlretrieve(url, save_path)

    try:
        # Extracting zip file using the zipfile package.
        with ZipFile(save_path) as z:
            # Extract ZIP file contents in the same directory.
            z.extractall(os.path.split(save_path)[0])

        print("Done")

    except Exception as e:
        print("\nInvalid file.", e)


URL = r"https://www.dropbox.com/s/efitgt363ada95a/opencv_bootcamp_assets_12.zip?dl=1"

asset_zip_path = os.path.join(os.getcwd(), f"opencv_bootcamp_assets_12.zip")

# Download if asset ZIP does not exist.
if not os.path.exists(asset_zip_path):
    download_and_unzip(URL, asset_zip_path)
# ====================================================================


s = 0
if len(sys.argv) > 1:
    s = sys.argv[1]

s = '/media/liutie/备用盘/video/mdg/1865003-马克思教孔夫子/2023-11-07-18-49-04BV1Nz4y1P7GH【睡前消息666】遇见马克思 孔子才懂传统文化（上）.mp4'

source = cv2.VideoCapture(s)

win_name = "Camera Preview"
cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

'''
    cv2.dnn.readNetFromCaffe(): 从Caffe模型加载网络
    第一个参数deploy.prototxt: Caffe模型的配置文件，描述网络结构
    第二个参数res10_300x300_ssd_iter_140000_fp16.caffemodel: 预训练好的模型权重文件
    这个模型是基于SSD(Single Shot MultiBox Detector)架构的人脸检测器，输入尺寸为300x300，使用FP16精度Model parameters
'''
net = cv2.dnn.readNetFromCaffe("deploy.prototxt", "res10_300x300_ssd_iter_140000_fp16.caffemodel")

in_width = 300
in_height = 300
mean = [104, 117, 123]
conf_threshold = 0.2

while cv2.waitKey(1) != 27:
    has_frame, frame = source.read()
    if not has_frame:
        break
    # frame = cv2.flip(frame, 1)
    frame_height = frame.shape[0]
    frame_width = frame.shape[1]

    '''
        cv2.dnn.blobFromImage(): 将图像转换为网络所需的输入格式(blob)
        frame: 输入图像
        1.0: 缩放因子，对图像像素值进行缩放
        (in_width, in_height): 网络期望的输入尺寸(通常为300x300)
        mean: 均值减法值，用于图像归一化(通常为(104, 117, 123))
        swapRB=False: 是否交换R和B通道(OpenCV使用BGR格式，但有些模型需要RGB)
        crop=False: 是否中心裁剪图像
    '''
    # Create a 4D blob from a frame.
    blob = cv2.dnn.blobFromImage(frame, 1.0, (in_width, in_height), mean, swapRB=False, crop=False)
    '''
        net.setInput(blob): 将预处理好的blob设置为网络的输入
        net.forward(): 执行前向传播，获取检测结果
        返回的detections是一个4维矩阵，形状通常为[1, 1, N, 7]，其中N是检测到的对象数量
        每个检测结果包含7个值: [batch_id, class_id, confidence, x_min, y_min, x_max, y_max]
    '''
    # Run a model
    net.setInput(blob)
    detections = net.forward()

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > conf_threshold:
            x_top_left = int(detections[0, 0, i, 3] * frame_width)
            y_top_left = int(detections[0, 0, i, 4] * frame_height)
            x_bottom_right  = int(detections[0, 0, i, 5] * frame_width)
            y_bottom_right  = int(detections[0, 0, i, 6] * frame_height)

            cv2.rectangle(frame, (x_top_left, y_top_left), (x_bottom_right, y_bottom_right), (0, 255, 0))
            label = "Confidence: %.4f" % confidence
            label_size, base_line = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

            cv2.rectangle(
                frame,
                (x_top_left, y_top_left - label_size[1]),
                (x_top_left + label_size[0], y_top_left + base_line),
                (255, 255, 255),
                cv2.FILLED,
            )
            cv2.putText(frame, label, (x_top_left, y_top_left), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0))

    t, _ = net.getPerfProfile()
    label = "Inference time: %.2f ms" % (t * 1000.0 / cv2.getTickFrequency())
    cv2.putText(frame, label, (0, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0))
    cv2.imshow(win_name, frame)

source.release()
cv2.destroyWindow(win_name)