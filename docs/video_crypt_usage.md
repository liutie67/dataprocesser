# 安装与使用指南

## 本地安装

在任意 Python 环境中，通过本地路径以可编辑模式安装：

```bash
pip install -e /path/to/dataprocesser
```

或使用 uv：

```bash
uv pip install -e /path/to/dataprocesser
```

`-e`（editable）模式下，源码的修改会立即生效，无需重新安装。

安装后即可在任意项目中导入使用。

---

## video_crypt — 媒体文件加密/解密

### 快速开始

```python
from video_crypt import generate_and_save_key, mediatranscryption

# 1. 生成密钥（只需执行一次）
generate_and_save_key("/path/to/mykey.aes")

# 2. 加密
mediatranscryption(
    src_dir="/path/to/originals",
    dst_dir="/path/to/encrypted",
    key_path="/path/to/mykey.aes",
)

# 3. 解密
mediatranscryption(
    src_dir="/path/to/encrypted",
    dst_dir="/path/to/decrypted",
    encrypt=False,
    key_path="/path/to/mykey.aes",
)
```

### mediatranscryption 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `src_dir` | str | 必填 | 源目录路径 |
| `dst_dir` | str | 必填 | 目标目录路径 |
| `encrypt` | bool | `True` | `True`=加密，`False`=解密 |
| `delete_source` | bool | `False` | 处理完成后是否删除源文件 |
| `mapping_pictures` | bool | `False` | 为 `True` 时，仅对视频文件生成映射 log，图片文件会复制到映射目录 |
| `use_multithreading` | bool | `True` | 是否使用多线程处理 |
| `num_threads` | int | `None` | 线程数，`None` 使用系统默认 |
| `save_mapping` | bool | `False` | 是否在目标目录旁保存文件名映射 |
| `save_preview` | bool | `False` | 是否为视频文件生成缩略图网格 |
| `logging` | bool | `False` | 是否将映射写入 log 文件 |
| `rows` | int | 4 | 预览图网格行数 |
| `cols` | int | 4 | 预览图网格列数 |
| `preview_width` | int | 1980 | 预览图像素宽度，高度自动计算 |
| `previewOnly` | bool | `False` | 仅输出预览图，不输出加密文件 |
| `detached_prevew` | str | `None` | 将预览图输出到独立目录 |
| `key_path` | str | `None` | 密钥文件路径，`None` 使用默认位置（包目录下的 `vcrypt.aes`） |

### 密钥管理

```python
from video_crypt import generate_and_save_key, load_key

# 生成新密钥（文件已存在时会报错）
generate_and_save_key("/path/to/mykey.aes")
# 生成 64 字节密钥
generate_and_save_key("/path/to/mykey.aes", size=64)

# 加载密钥（返回 bytes）
key = load_key("/path/to/mykey.aes")
```

不传 `key_path` 时，默认读取 `video_crypt/vcrypt.aes`。

### 单文件加密/解密

```python
from video_crypt import load_key, encrypt_file_with_name, decrypt_file_with_name

key = load_key("/path/to/mykey.aes")

# 加密单个文件
encrypt_file_with_name("/path/to/file.mp4", "/path/to/encrypted.bin", key)

# 解密单个文件（自动恢复原始文件名）
decrypt_file_with_name("/path/to/encrypted.bin", "/path/to/output_dir", key)
```

### 文件夹名加密/解密

```python
from video_crypt import load_key, encrypt_folder_name, decrypt_folder_name

key = load_key("/path/to/mykey.aes")

# 加密文件夹名（返回 URL 安全的 Base64 字符串）
enc_name = encrypt_folder_name("我的文件夹", key)
# 例如 → "7HX9v2Jk4PZRmnBcKtEySQABcdEfghIj"

# 解密
original = decrypt_folder_name(enc_name, key)
```

### 文件名哈希

```python
from video_crypt import string_to_hash

# 将任意文件名转为固定长度的十六进制哈希
hash_str = string_to_hash("视频文件.mp4")       # 32 字符（默认）
hash_str = string_to_hash("视频文件.mp4", 16)   # 16 字符
# 最大支持 64 字符
```

---

## video_preview — 视频预览图生成

```python
from video_preview import generate_video_preview, generate_previews_for_directory, is_video_file

# 为单个视频生成缩略图网格
generate_video_preview(
    video_path="/path/to/video.mp4",
    output_path="/path/to/preview.png",
    rows=4,
    cols=4,
    preview_width=1980,
)

# 批量生成整个目录的视频预览
generate_previews_for_directory(
    src_dir="/path/to/videos",
    dst_dir="/path/to/previews",
    rows=4,
    cols=4,
    preview_width=1980,
)

# 判断文件是否为视频
is_video_file("clip.mp4")   # True
is_video_file("photo.jpg")  # False
```

---

## 在其他项目的 pyproject.toml 中引用

如果其他项目也使用 uv/pip 管理依赖，可以在 `pyproject.toml` 中声明：

```toml
[project]
dependencies = [
    "dataprocesser @ file:///Users/liutie/projects/dataprocesser",
]
```

或通过相对路径（项目需在同一文件系统上）：

```toml
[project]
dependencies = [
    "dataprocesser @ file://../dataprocesser",
]
```
