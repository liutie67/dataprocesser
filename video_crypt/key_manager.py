import os
import base64

_DEFAULT_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vcrypt.aes')


def generate_and_save_key(key_path=None, size=32):
    """生成并保存加密密钥到文件"""
    path = key_path or _DEFAULT_KEY_FILE
    if os.path.exists(path):
        raise FileExistsError("密钥文件已存在，请勿重复生成。")

    key = os.urandom(size)
    key_b64 = base64.b64encode(key)
    with open(path, 'wb') as key_file:
        key_file.write(key_b64)
    print(f"新密钥已生成并保存到 {path}。")
    return key


def load_key(key_path=None):
    """从文件加载加密密钥"""
    path = key_path or _DEFAULT_KEY_FILE
    if not os.path.exists(path):
        raise FileNotFoundError("未找到密钥文件，请先生成密钥")

    with (open(path, 'rb') as key_file):
        key_b64 = key_file.read()
        return base64.b64decode(key_b64)


if __name__ == "__main__":
    generate_and_save_key()
    key = load_key()
    print(type(key))
    print(len(key))
    print(key)
