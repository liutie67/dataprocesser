import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import os

from video_crypt.key_manager import load_key
from video_crypt.utils import string_to_hash


def encrypt_file_with_name(input_path, output_path, key, chunk_size=1024):
    """
    加密文件（包含文件名加密）
    :param chunk_size:
    :param input_path: 输入文件路径
    :param output_path: 输出加密文件路径（固定后缀为.bin）
    :param key: 加密密钥（32字节用于AES-256）
    """
    # 获取原始文件名并加密
    original_name = os.path.basename(input_path)
    name_cipher = AES.new(key, AES.MODE_CBC, iv=os.urandom(16))
    encrypted_name = name_cipher.encrypt(pad(original_name.encode('utf-8'), AES.block_size))

    # 文件内容加密
    content_cipher = AES.new(key, AES.MODE_CBC)
    iv = content_cipher.iv

    # abs_dir_path = os.path.dirname(os.path.abspath(__file__))
    # output_path = os.path.join(abs_dir_path, 'encrypted-videos')
    # os.makedirs(output_path, exist_ok=True)
    # output_path = os.path.join(output_path, '.bin')

    with open(input_path, 'rb') as fin, open(output_path, 'wb') as fout:
        # 写入文件头结构：[IV(16B)]*2[加密文件名长度(2B)][加密文件名][加密内容]
        fout.write(iv)
        fout.write(name_cipher.iv)  # 文件名加密的IV
        fout.write(len(encrypted_name).to_bytes(2, 'big'))
        fout.write(encrypted_name)

        # 加密并写入文件内容
        while chunk := fin.read(chunk_size * chunk_size):  # 1MB分块
            if len(chunk) % AES.block_size != 0:
                chunk = pad(chunk, AES.block_size)
            fout.write(content_cipher.encrypt(chunk))


def decrypt_file_with_name(input_path, output_dir, key, chunk_size=1024):
    """
    解密文件（包含文件名解密）
    :param chunk_size:
    :param input_path: 加密文件路径
    :param output_dir: 解密文件输出目录
    :param key: 加密密钥
    """
    with open(input_path, 'rb') as fin:
        # 读取文件头
        content_iv = fin.read(16)
        name_iv = fin.read(16)
        name_len = int.from_bytes(fin.read(2), 'big')
        encrypted_name = fin.read(name_len)

        # 解密文件名
        name_cipher = AES.new(key, AES.MODE_CBC, iv=name_iv)
        original_name = unpad(name_cipher.decrypt(encrypted_name), AES.block_size).decode('utf-8')

        # 解密内容
        content_cipher = AES.new(key, AES.MODE_CBC, iv=content_iv)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, original_name)

        with open(output_path, 'wb') as fout:
            while chunk := fin.read(chunk_size * chunk_size):
                decrypted = content_cipher.decrypt(chunk)
                fout.write(decrypted)

            # 移除最后一个块的填充
            fout.seek(-decrypted[-1], 2)
            fout.truncate()


def encrypt_folder_name(folder_name, key):
    """
    加密文件夹名称（使用随机IV）
    :param key: 32字节AES密钥
    :param folder_name: 要加密的文件夹名
    :return: 固定长度的安全Base64字符串（无等号，特殊字符已替换）
    """
    # 生成随机IV
    iv = os.urandom(AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC, iv)

    # 加密并添加填充
    if len(folder_name) > 30:
        folder_name = folder_name[:30]
    encrypted = cipher.encrypt(pad(folder_name.encode('utf-8'), AES.block_size))

    # 组合IV和密文
    combined = iv + encrypted

    # Base64编码并做安全替换
    b64_str = base64.b64encode(combined).decode('utf-8')
    safe_str = b64_str.replace('+', '-').replace('/', '_').rstrip('=')

    return safe_str  # 示例: "7HX9v2Jk4PZRmnBcKtEySQABcdEfghIj"


def decrypt_folder_name(encrypted_str, key):
    """
    解密文件夹名称
    :param key: 32字节AES密钥
    :param encrypted_str: encrypt_folder_name()返回的字符串
    :return: 原始文件夹名
    """
    # 还原Base64特殊字符和填充
    restored = encrypted_str.replace('-', '+').replace('_', '/')
    # 计算需要补足的等号数量（Base64长度需为4的倍数）
    padding = '=' * (4 - len(restored) % 4)
    combined = base64.b64decode(restored + padding)

    # 分离IV和密文
    iv = combined[:AES.block_size]
    encrypted = combined[AES.block_size:]

    # 解密
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)

    return decrypted.decode('utf-8')


if __name__ == '__main__':
    import time

    # 使用示例
    key = load_key()
    print(f"使用的秘钥：\n{key}")
    print(type(key))
    print(len(key))
    print(base64.b64encode(key))
    # input_path = '../yolo_process/database/test-d38bc61df8084f119a21bcbbb55d1423.png'
    input_path = '/media/liutie/备用盘/video/mdg/default-默认/2022-07-30-20-48-54BV1Pt4y1V7Wd【海豹故事会】727直播回放，顺着网线来找你.mp4'

    filename = input_path.split('/')[-1].split('.')[0]
    enc_name = string_to_hash(filename, 16)
    start_time = time.time()
    encrypt_file_with_name(input_path, f'encrypted/encrypted-{enc_name}', key)
    encrypt_time = time.time() - start_time

    decrypt_file_with_name(f'encrypted/encrypted-{enc_name}', 'decrypted', key)
    decrypt_time = time.time() - start_time

    file_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"加密过程，用时:{encrypt_time:.1f}，速度:{file_size/encrypt_time:.2f} MB/s")
    print(f"解密过程，用时:{decrypt_time:.1f}，速度:{file_size/decrypt_time:.2f} MB/s")