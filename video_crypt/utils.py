import hashlib


def string_to_hash(text: str, length: int = 32) -> str:
    """
    将任意字符串转换为固定长度的十六进制哈希值
    :param text: 输入字符串
    :param length: 输出长度(字符数)，最大64(SHA-256产生64字符十六进制)
    :return: 固定长度的哈希字符串
    """
    if length > 64:
        raise ValueError("最大支持64字符(SHA-256)")

    # 创建SHA-256哈希对象
    sha256 = hashlib.sha256()
    # 更新哈希对象(自动处理编码)
    sha256.update(text.encode('utf-8'))
    # 获取十六进制摘要并截断
    return sha256.hexdigest()[:length]
