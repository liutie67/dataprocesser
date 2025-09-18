from pathlib import Path
import os
from datetime import datetime


def create_1gb_files(nums: int=1, folder='', scale=1000):
    if nums <= 0:
        print('No num to create !')
        return
    folder = Path(folder)
    os.makedirs(folder, exist_ok=True)

    size_gb = 1
    size_bytes = size_gb * scale * scale * scale
    chunk_size = 16 * scale * scale

    timestamp = datetime.now().strftime("%Y%m%d-%H-%M-%S")

    for num in range(nums):
        filename = f"{timestamp}_{num}_1gb_file.bin"
        with open(os.path.join(folder, filename), 'wb') as f:
            for _ in range(size_bytes // chunk_size):
                f.write(b'\0' * chunk_size)
                # 写入剩余部分
            remaining = size_bytes % chunk_size
            if remaining:
                f.write(b'\0' * remaining)
        print(num, f"<{filename}>", "Generated. ")