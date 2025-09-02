import hashlib
import os


def hash_file_complet(file_path, algorithm='sha256'):
    """计算整个文件的哈希值（包含元数据）"""
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        # 分块读取以避免大文件内存问题
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def hash_file_fast(file_path, algorithm='sha256', chunk_size=8192):
    """
    快速计算文件的哈希值，基于文件大小和头🀄️尾各8KB数据块
    参数:
        file_path: 文件路径
        algorithm: 哈希算法，默认为'sha256'
        chunk_size: 数据块大小，默认为8KB
    返回:
        文件的快速哈希值
    """
    hash_func = hashlib.new(algorithm)

    # 首先添加文件大小信息
    file_size = os.path.getsize(file_path)
    hash_func.update(str(file_size).encode('utf-8'))

    with open(file_path, 'rb') as f:
        # 1. 读取文件开头8KB
        start_chunk = f.read(chunk_size)
        hash_func.update(start_chunk)

        # 2. 如果文件足够大，读取文件中间部分（可选，增强准确性）
        if file_size > 3 * chunk_size:
            # 跳转到文件中间位置（前后各留8KB空间）
            mid_position = max(chunk_size, (file_size - chunk_size) // 2)
            # 确保不会读取超出文件范围
            mid_position = min(mid_position, file_size - chunk_size)

            f.seek(mid_position)
            mid_chunk = f.read(chunk_size)
            hash_func.update(mid_chunk)

        # 3. 读取文件末尾8KB
        if file_size > chunk_size:
            f.seek(-chunk_size, 2)  # 从文件末尾向前移动8KB
        else:
            f.seek(0)  # 小文件直接回到开头

        end_chunk = f.read(chunk_size)
        hash_func.update(end_chunk)

    return hash_func.hexdigest()


if __name__ == '__main__':
    # 检查算法是否可用
    print(hashlib.algorithms_available)  # 所有可用算法
    print(hashlib.algorithms_guaranteed) # 标准保证可用的算法

    # # 示例
    # file_hash = hash_file_complet('path/to/file')
    # print(f"SHA-256 (整个文件): {file_hash}")
    # print(f"len of hash: {len(file_hash)}")
    # print(f"type of file_hash: {type(file_hash)}")