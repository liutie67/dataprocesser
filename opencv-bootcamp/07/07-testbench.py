import cv2

image = cv2.imread("../04/building-windows.jpg")

# 中值滤波
median = cv2.medianBlur(image, 5)

# 高斯滤波
gaussian = cv2.GaussianBlur(image, (5, 5), 0)

# 双边滤波
bilateral = cv2.bilateralFilter(image, 9, 75, 75)

# 横向拼接对比
result = cv2.hconcat([
    image,
    median,
    gaussian,
    bilateral
])

cv2.imshow("Original | Median | Gaussian | Bilateral", result)
cv2.waitKey(0)
cv2.destroyAllWindows()