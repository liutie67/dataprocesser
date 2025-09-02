import hashlib


def hash_file_complet(file_path, algorithm='sha256'):
    """计算整个文件的哈希值（包含元数据）"""
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        # 分块读取以避免大文件内存问题
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


if __name__ == '__main__':
    # 检查算法是否可用
    # print(hashlib.algorithms_available)  # 所有可用算法
    print(hashlib.algorithms_guaranteed) # 标准保证可用的算法

    # 示例
    file_hash = hash_file_complet('path/to/file')
    print(f"SHA-256 (整个文件): {file_hash}")
    print(f"len of hash: {len(file_hash)}")
    print(f"type of file_hash: {type(file_hash)}")