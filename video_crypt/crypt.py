import base64
import hashlib
import hmac
import os
import uuid

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from video_crypt.key_manager import load_key
from video_crypt.utils import string_to_hash


_FORMAT_MAGIC = b"VCF2"
_MAC_SIZE = 32
_ORIGINAL_SIZE_BYTES = 8

_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_path_component(name, replacement="_", max_length=240):
    """清理单段路径名称，避免当前系统不支持的文件名字符。"""
    if os.name != "nt":
        return name or "unnamed"

    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join(
        replacement if char in invalid_chars or ord(char) < 32 else char
        for char in name
    )
    sanitized = sanitized.rstrip(" .")
    if not sanitized:
        sanitized = "unnamed"

    stem, ext = os.path.splitext(sanitized)
    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        sanitized = f"_{sanitized}"

    if len(sanitized) > max_length:
        stem, ext = os.path.splitext(sanitized)
        keep = max(1, max_length - len(ext))
        sanitized = f"{stem[:keep]}{ext}"

    return sanitized


def _unique_path(path):
    """目标路径已存在时，自动追加序号，避免覆盖已有文件。"""
    if not os.path.exists(path):
        return path

    folder = os.path.dirname(path)
    stem, ext = os.path.splitext(os.path.basename(path))
    counter = 1
    while True:
        candidate = os.path.join(folder, f"{stem} ({counter}){ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def _temp_path_for(output_path):
    """为目标文件生成同目录临时文件路径，便于成功后原子替换。"""
    folder = os.path.dirname(output_path) or "."
    filename = os.path.basename(output_path)
    return os.path.join(folder, f".{filename}.{os.getpid()}.{uuid.uuid4().hex}.tmp")


def _chunk_bytes(chunk_size):
    """将分块大小对齐到 AES block，保证中间块可直接加解密。"""
    size = max(AES.block_size, chunk_size * chunk_size)
    return size - (size % AES.block_size)


def _new_file_hmac(key):
    mac_key = hashlib.sha256(b"video_crypt:v2:hmac:" + key).digest()
    return hmac.new(mac_key, digestmod=hashlib.sha256)


def _output_path_for_name(output_dir, original_name):
    os.makedirs(output_dir, exist_ok=True)
    safe_name = sanitize_path_component(original_name)
    output_path = _unique_path(os.path.join(output_dir, safe_name))
    return output_path, safe_name


def encrypt_file_with_name(input_path, output_path, key, chunk_size=1024):
    """
    加密文件（包含文件名加密）
    新版 VCF2 结构：[魔数][内容IV][文件名IV][文件名长度][原始大小][加密文件名][加密内容][HMAC]
    :param chunk_size:
    :param input_path: 输入文件路径
    :param output_path: 输出加密文件路径
    :param key: 加密密钥（32字节用于AES-256）
    """
    original_name = os.path.basename(input_path)
    name_cipher = AES.new(key, AES.MODE_CBC, iv=os.urandom(AES.block_size))
    encrypted_name = name_cipher.encrypt(pad(original_name.encode("utf-8"), AES.block_size))

    content_cipher = AES.new(key, AES.MODE_CBC)
    content_iv = content_cipher.iv
    original_size = os.path.getsize(input_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    temp_path = _temp_path_for(output_path)
    chunk_bytes = _chunk_bytes(chunk_size)

    try:
        with open(input_path, "rb") as fin, open(temp_path, "wb") as fout:
            header = b"".join(
                [
                    _FORMAT_MAGIC,
                    content_iv,
                    name_cipher.iv,
                    len(encrypted_name).to_bytes(2, "big"),
                    original_size.to_bytes(_ORIGINAL_SIZE_BYTES, "big"),
                    encrypted_name,
                ]
            )
            file_mac = _new_file_hmac(key)
            file_mac.update(header)
            fout.write(header)

            previous = fin.read(chunk_bytes)
            while True:
                current = fin.read(chunk_bytes)
                if not current:
                    encrypted_chunk = content_cipher.encrypt(pad(previous, AES.block_size))
                    file_mac.update(encrypted_chunk)
                    fout.write(encrypted_chunk)
                    break

                encrypted_chunk = content_cipher.encrypt(previous)
                file_mac.update(encrypted_chunk)
                fout.write(encrypted_chunk)
                previous = current

            fout.write(file_mac.digest())

        os.replace(temp_path, output_path)
        return output_path
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def _decrypt_v2_file(fin, input_path, output_dir, key, chunk_size):
    content_iv = fin.read(AES.block_size)
    name_iv = fin.read(AES.block_size)
    name_len_bytes = fin.read(2)
    original_size_bytes = fin.read(_ORIGINAL_SIZE_BYTES)
    if (
        len(content_iv) != AES.block_size
        or len(name_iv) != AES.block_size
        or len(name_len_bytes) != 2
        or len(original_size_bytes) != _ORIGINAL_SIZE_BYTES
    ):
        raise ValueError("加密文件头不完整")

    name_len = int.from_bytes(name_len_bytes, "big")
    encrypted_name = fin.read(name_len)
    if len(encrypted_name) != name_len:
        raise ValueError("加密文件头不完整")

    header = b"".join(
        [
            _FORMAT_MAGIC,
            content_iv,
            name_iv,
            name_len_bytes,
            original_size_bytes,
            encrypted_name,
        ]
    )
    file_mac = _new_file_hmac(key)
    file_mac.update(header)

    name_cipher = AES.new(key, AES.MODE_CBC, iv=name_iv)
    original_name = unpad(name_cipher.decrypt(encrypted_name), AES.block_size).decode("utf-8")
    output_path, safe_name = _output_path_for_name(output_dir, original_name)
    temp_path = _temp_path_for(output_path)

    ciphertext_start = fin.tell()
    ciphertext_len = os.path.getsize(input_path) - ciphertext_start - _MAC_SIZE
    if ciphertext_len < AES.block_size or ciphertext_len % AES.block_size != 0:
        raise ValueError("加密文件内容不完整")

    content_cipher = AES.new(key, AES.MODE_CBC, iv=content_iv)
    chunk_bytes = _chunk_bytes(chunk_size)
    original_size = int.from_bytes(original_size_bytes, "big")

    try:
        with open(temp_path, "wb") as fout:
            previous = None
            remaining = ciphertext_len
            plain_size = 0

            while remaining:
                to_read = min(chunk_bytes, remaining)
                chunk = fin.read(to_read)
                if len(chunk) != to_read:
                    raise ValueError("加密文件内容不完整")
                file_mac.update(chunk)

                if previous is not None:
                    decrypted = content_cipher.decrypt(previous)
                    fout.write(decrypted)
                    plain_size += len(decrypted)
                previous = chunk
                remaining -= len(chunk)

            expected_mac = fin.read(_MAC_SIZE)
            if len(expected_mac) != _MAC_SIZE:
                raise ValueError("加密文件缺少 HMAC 校验")
            if not hmac.compare_digest(file_mac.digest(), expected_mac):
                raise ValueError("加密文件 HMAC 校验失败，文件可能已损坏")

            final = unpad(content_cipher.decrypt(previous), AES.block_size)
            fout.write(final)
            plain_size += len(final)
            if plain_size != original_size:
                raise ValueError("加密文件大小校验失败，文件可能已损坏")

        os.replace(temp_path, output_path)
        if safe_name != original_name:
            print(f"文件名包含当前系统不支持的字符，已改名: {original_name} -> {safe_name}")
        return output_path
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def _decrypt_legacy_file(fin, output_dir, key, chunk_size, allow_legacy_unpadded):
    content_iv = fin.read(AES.block_size)
    name_iv = fin.read(AES.block_size)
    name_len_bytes = fin.read(2)
    name_len = int.from_bytes(name_len_bytes, "big")
    encrypted_name = fin.read(name_len)

    if (
        len(content_iv) != AES.block_size
        or len(name_iv) != AES.block_size
        or len(name_len_bytes) != 2
        or len(encrypted_name) != name_len
    ):
        raise ValueError("加密文件头不完整")

    name_cipher = AES.new(key, AES.MODE_CBC, iv=name_iv)
    original_name = unpad(name_cipher.decrypt(encrypted_name), AES.block_size).decode("utf-8")

    content_cipher = AES.new(key, AES.MODE_CBC, iv=content_iv)
    output_path, safe_name = _output_path_for_name(output_dir, original_name)
    temp_path = _temp_path_for(output_path)
    chunk_bytes = _chunk_bytes(chunk_size)

    try:
        with open(temp_path, "wb") as fout:
            previous = fin.read(chunk_bytes)
            if not previous:
                raise ValueError("加密文件内容为空")

            while True:
                current = fin.read(chunk_bytes)
                if not current:
                    decrypted = content_cipher.decrypt(previous)
                    try:
                        final = unpad(decrypted, AES.block_size)
                    except ValueError as exc:
                        if not allow_legacy_unpadded:
                            raise ValueError(
                                "旧版文件 padding 校验失败，文件可能已损坏；"
                                "仅在确认这是旧版无 padding 文件时开启 allow_legacy_unpadded。"
                            ) from exc
                        final = decrypted
                        print("已使用旧版无 padding 兼容模式；输出文件未经过完整性校验。")
                    fout.write(final)
                    break

                fout.write(content_cipher.decrypt(previous))
                previous = current

        os.replace(temp_path, output_path)
        if safe_name != original_name:
            print(f"文件名包含当前系统不支持的字符，已改名: {original_name} -> {safe_name}")
        return output_path
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def decrypt_file_with_name(input_path, output_dir, key, chunk_size=1024, allow_legacy_unpadded=False):
    """解密文件；有 VCF2 魔数时按新版校验格式解密，否则按旧版格式兼容解密。"""
    with open(input_path, "rb") as fin:
        magic = fin.read(len(_FORMAT_MAGIC))
        if magic == _FORMAT_MAGIC:
            return _decrypt_v2_file(fin, input_path, output_dir, key, chunk_size)

        fin.seek(0)
        return _decrypt_legacy_file(fin, output_dir, key, chunk_size, allow_legacy_unpadded)


def encrypt_folder_name(folder_name, key):
    """
    加密文件夹名称（使用随机IV）
    :param key: 32字节AES密钥
    :param folder_name: 要加密的文件夹名
    :return: 固定长度的安全Base64字符串（无等号，特殊字符已替换）
    """
    iv = os.urandom(AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC, iv)

    if len(folder_name) > 30:
        folder_name = folder_name[:30]
    encrypted = cipher.encrypt(pad(folder_name.encode("utf-8"), AES.block_size))

    combined = iv + encrypted
    b64_str = base64.b64encode(combined).decode("utf-8")
    safe_str = b64_str.replace("+", "-").replace("/", "_").rstrip("=")

    return safe_str


def decrypt_folder_name(encrypted_str, key):
    """
    解密文件夹名称
    :param key: 32字节AES密钥
    :param encrypted_str: encrypt_folder_name()返回的字符串
    :return: 原始文件夹名
    """
    restored = encrypted_str.replace("-", "+").replace("_", "/")
    padding = "=" * ((4 - len(restored) % 4) % 4)
    combined = base64.b64decode(restored + padding)

    iv = combined[:AES.block_size]
    encrypted = combined[AES.block_size:]

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)

    return decrypted.decode("utf-8")


if __name__ == "__main__":
    import time

    key = load_key()
    print(f"使用的秘钥：\n{key}")
    print(type(key))
    print(len(key))
    print(base64.b64encode(key))

    input_path = "/path/to/video.mp4"
    filename = input_path.split("/")[-1].split(".")[0]
    enc_name = string_to_hash(filename, 16)
    start_time = time.time()
    encrypt_file_with_name(input_path, f"encrypted/encrypted-{enc_name}", key)
    encrypt_time = time.time() - start_time

    decrypt_file_with_name(f"encrypted/encrypted-{enc_name}", "decrypted", key)
    decrypt_time = time.time() - start_time

    file_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"加密过程，用时:{encrypt_time:.1f}，速度:{file_size / encrypt_time:.2f} MB/s")
    print(f"解密过程，用时:{decrypt_time:.1f}，速度:{file_size / decrypt_time:.2f} MB/s")
