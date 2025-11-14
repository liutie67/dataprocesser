"""
Step 3 rewritelabel.py

将指定labels文件夹内所有txt文件内的标签从0变成1或者从1变成0的代码，每个txt文件内包含1行或多行，
每行第一个字符是0，后面用空格隔开有四个表示框坐标的浮点数。
将fire和smoke一起进行yolo检测训练，使类别标签不同
"""

import os
from collections import defaultdict


def swap_labels_in_files(folder_path, swap=False):
    """
    统计标签类别并根据参数决定是否交换标签

    参数:
        folder_path: labels文件夹路径
        swap: 是否执行标签交换 (默认False)
    """
    label_counts = defaultdict(int)

    # 遍历labels文件夹中的所有文件
    for filename in os.listdir(folder_path):
        if filename.endswith('.txt'):
            filepath = os.path.join(folder_path, filename)

            # 读取文件内容
            with open(filepath, 'r') as f:
                lines = f.readlines()

            # 处理每一行
            new_lines = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 1:  # 确保至少有一个元素（标签）
                    # 统计标签类别
                    label = parts[0]
                    label_counts[label] += 1

                    # 如果需要交换标签
                    if swap:
                        if parts[0] == '0':
                            parts[0] = '1'
                        elif parts[0] == '1':
                            parts[0] = '0'

                    # 重新组合行
                    new_line = ' '.join(parts) + '\n'
                    new_lines.append(new_line)

            # 如果需要交换标签，则写回文件
            if swap:
                with open(filepath, 'w') as f:
                    f.writelines(new_lines)

    # 输出统计结果
    print("\n标签统计结果:")
    for label, count in sorted(label_counts.items(), key=lambda x: int(x[0])):
        print(f"类别 {label}: {count} 个")

    print(f"\n共发现 {len(label_counts)} 种标签类别")

    if swap:
        print("\n标签交换已完成！")
    else:
        print("\n当前为只读模式，未修改文件 (如需交换请设置 swap=True)")


if __name__ == '__main__':
    # import argparse
    # # 设置命令行参数
    # parser = argparse.ArgumentParser(description='统计和交换YOLO标签文件中的类别标签')
    # parser.add_argument('folder', help='labels文件夹路径')
    # parser.add_argument('--swap', action='store_true', help='是否执行标签交换 (默认只统计)')
    # args = parser.parse_args()
    # # 执行函数
    # swap_labels_in_files(args.folder, args.swap)
    path = './fire-smoke/combined/labels'
    swap_labels_in_files(path, swap=False)