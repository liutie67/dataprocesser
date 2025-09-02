def get_human_readable_size(size_bytes):
    """将字节大小转换为更易读的格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_file_suffix_category(filename):
    """
    获取文件后缀和类型

    参数:
    filename (str): 文件名或文件路径

    返回:
    tuple: (后缀, 类型) 例如: ('.mp4', 'video')
    """

    # 定义文件类型映射
    file_type_mapping = {
        'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'],
        'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'],
        'picture': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'],
        'document': ['.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                     '.csv', '.json', '.xml', '.html', '.htm', '.md']
    }

    # 获取文件后缀（转换为小写以便比较）
    if '.' in filename:
        suffix = '.' + filename.split('.')[-1].lower()
    else:
        suffix = ''

    # 判断文件类型
    file_type = 'other'

    for type_name, extensions in file_type_mapping.items():
        if suffix in extensions:
            file_type = type_name
            break

    return suffix, file_type


# 测试示例
if __name__ == "__main__":
    test_files = [
        "video.mp4",
        "song.mp3",
        "image.jpg",
        "document.pdf",
        "script.py",
        "data",
        "archive.zip"
    ]

    for file in test_files:
        suffix, file_type = get_file_info(file)
        print(f"文件名: {file:15} 后缀: {suffix:6} 类型: {file_type}")