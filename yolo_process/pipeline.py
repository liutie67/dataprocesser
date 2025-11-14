from yolo_process.convert import convert
from yolo_process.checkmatches import check_and_clean_dataset
from yolo_process.split_data import split_yolo_dataset

# Step 1 分开images和labels
# path = '/home/liutie/projects/databases/fire_smoke筛选数据集_烟火分开数据集/烟'
# convert(path=path)

# Step 2 检查文件夹里image和label是否一一匹配
# path = '/home/liutie/projects/databases/fire_smoke/fire'
# check_and_clean_dataset(path)

# Step 3 分割train集和al集
path = '/home/liutie/projects/databases/fire_smoke/fire'
split_yolo_dataset(path, val_ratio=0.2, seed=42)