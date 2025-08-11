import os
import base64


KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vcrypt.aes')


def generate_and_save_key(size=32):
    """生成并保存加密密钥到文件"""
    if os.path.exists(KEY_FILE):
        raise FileExistsError("密钥文件已存在，请勿重复生成。")

    key = os.urandom(size)
    key_b64 = base64.b64encode(key)
    with open(KEY_FILE, 'wb') as key_file:
        key_file.write(key_b64)
    print(f"新密钥已生成并保存到 {KEY_FILE}。")
    return key


def load_key():
    """从文件加载加密密钥"""
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError("未找到密钥文件，请先生成密钥")

    with (open(KEY_FILE, 'rb') as key_file):
        key_b64 = key_file.read()
        return base64.b64decode(key_b64)


if __name__ == "__main__":
    generate_and_save_key()
    key = load_key()
    print(type(key))
    print(len(key))
    print(key)
