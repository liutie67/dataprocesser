import json
import os
from pathlib import Path


def convert_labelme_json_to_yolo(json_dir, output_dir, class_list):
    """
    将 LabelMe 的 JSON 文件批量转换为 YOLO 的 TXT 格式。

    此函数会遍历指定目录下的所有 LabelMe JSON 文件，并将其内容转换为 YOLO 格式的 TXT 文件，
    保存在指定的输出目录中。转换过程中，会使用 `class_list` 的索引作为 YOLO 格式的类别ID。

    Parameters
    ----------
    json_dir : str
        包含 LabelMe JSON 文件的目录路径。例如: 'folder/path/to/json'
    output_dir : str
        用于保存生成的 YOLO TXT 文件的目录路径。例如: 'folder/path/to/output'
    class_list : list[str]
        标签类别的列表。此列表的索引将作为 YOLO 格式中的类别索引 (0, 1, 2...)。
        例如: ['kilometer', 'hectometer']

    Raises
    ------
    FileNotFoundError
        如果 `json_dir` 或 `output_dir` 不存在。

    Examples
    --------
    >>> convert_labelme_json_to_yolo(
    ...     json_dir="folder/path/to/json",
    ...     output_dir="folder/path/to/output",
    ...     class_list=['kilometer', 'hectometer']
    ... )
    """

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 获取所有 json 文件
    json_files = list(Path(json_dir).glob('*.json'))
    print(f"找到 {len(json_files)} 个 JSON 文件，开始转换...")

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        img_w = data['imageWidth']
        img_h = data['imageHeight']
        filename = json_file.stem

        txt_content = []

        for shape in data['shapes']:
            label = shape['label']

            # 1. 检查类别是否在我们定义的列表中
            if label not in class_list:
                continue

            class_id = class_list.index(label)
            points = shape['points']

            # 2. 将 LabelMe 的点坐标转换为矩形框 (Xmin, Ymin, Xmax, Ymax)
            # 无论你在 LabelMe 里画的是矩形还是多边形，这行代码都能算出外接矩形
            x_coords = [p[0] for p in points]
            y_coords = [p[1] for p in points]

            x_min = min(x_coords)
            x_max = max(x_coords)
            y_min = min(y_coords)
            y_max = max(y_coords)

            # 3. 转换为 YOLO 格式 (x_center, y_center, w, h) 并归一化
            # 计算中心点和宽高
            dw = x_max - x_min
            dh = y_max - y_min
            x_center = x_min + dw / 2
            y_center = y_min + dh / 2

            # 归一化 (除以图像总宽高)
            x_center /= img_w
            y_center /= img_h
            w = dw / img_w
            h = dh / img_h

            # 4. 格式化并限制小数位 (防止超出 1.0 的边界溢出)
            # YOLO 格式: class_id x_center y_center w h
            line = f"{class_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"
            txt_content.append(line)

        # 5. 保存 txt 文件
        if txt_content:
            out_path = os.path.join(output_dir, f"{filename}.txt")
            with open(out_path, 'w', encoding='utf-8') as f_out:
                f_out.write('\n'.join(txt_content))

    print("转换完成！")


if __name__ == '__main__':
    # ================= 配置区域 =================
    # 1. 你的 json 文件所在文件夹
    my_json_dir = 'dataset/json_labels'

    # 2. 你希望 txt 文件输出到哪里
    my_output_dir = 'dataset/labels/train'

    # 3. 你的类别名称 (必须与 LabelMe 里填写的完全一致，顺序也很重要)
    # 比如 LabelMe 里写的是 "plate", 这里第一个就是 "plate"，对应的 ID 就是 0
    my_classes = ['plate', 'other_object']
    # ===========================================

    convert_labelme_json_to_yolo(my_json_dir, my_output_dir, my_classes)