import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from video_preview.generate_video_preview import generate_video_preview, is_video_file

from video_crypt.crypt import (
    decrypt_file_with_name,
    decrypt_folder_name,
    encrypt_file_with_name,
    encrypt_folder_name,
    sanitize_path_component,
)
from video_crypt.key_manager import load_key
from video_crypt.utils import string_to_hash


def mediatranscryption(
        src_dir,
        dst_dir,
        encrypt=True,
        delete_source=False,
        mapping_pictures=False,
        use_multithreading=True,
        num_threads=None,
        save_mapping=False,
        save_preview=False,
        logging=False,
        rows=4,
        cols=4,
        preview_width=1980,
        previewOnly=False,
        detached_prevew=None,
        key_path=None,
        allow_legacy_unpadded=False,
):
    """
    遍历目录并加密/解密文件，支持删除源文件、多线程、保存文件名映射。
    :param src_dir: 源目录
    :param dst_dir: 目标目录
    :param encrypt: True=加密，False=解密
    :param delete_source: 是否删除源文件
    :param mapping_pictures: 是否只删除视频类大文件
    :param use_multithreading: 是否使用多线程
    :param num_threads: 线程数（None=使用默认线程池线程数）
    :param save_mapping: 是否在平行结构中保存映射（目录名+映射的log文件）
    :param save_preview: 是否在平行结构中保存预览图
    :param rows: 预览图行数
    :param cols: 预览图列数
    :param preview_width: 预览图的像素宽度，高度自动调整
    :param previewOnly: 只输出preview@文件夹,不输出加密文件
    :param detached_prevew: 将预览图/映射输出到独立目录
    :param key_path: 密钥文件路径，None 则使用默认路径
    :param allow_legacy_unpadded: 允许旧版无 padding 文件兼容导出；开启时解密源文件会保留
    """
    key = load_key(key_path)
    dir_map = {}
    mapping_dir_map = {}

    # 如果需要保存映射，生成映射目录路径
    mapping_root = dst_dir
    keep_all_failed = False
    failures = []
    effective_delete_source = delete_source
    if allow_legacy_unpadded and not encrypt and delete_source:
        effective_delete_source = False
        print("已开启旧版无 padding 兼容模式；源加密文件将被保留。")

    def count_valid_tasks(src_root):
        total_tasks = 0
        for _root, dirs, files in os.walk(src_root):
            # 关键修改：原地移除所有含@的目录，阻止os.walk进入这些目录
            if not encrypt:
                dirs[:] = [d for d in dirs if "@" not in d]

            # 统计当前目录和有效文件（排除隐藏文件）；目录自身也会更新进度条
            total_tasks += 1
            total_tasks += len([f for f in files if not f.startswith(".")])
        return total_tasks

    def get_map_dir(root):
        if detached_prevew:
            os.makedirs(detached_prevew, exist_ok=True)
            return detached_prevew if save_mapping else None
        return mapping_dir_map.get(root) if save_mapping else None

    def record_failure(src_file, error):
        failures.append((src_file, error))
        print(f"\n处理失败，源文件已保留: {src_file}")
        print(f"  {type(error).__name__}: {error}")

    def safe_component(name, label):
        safe_name = sanitize_path_component(name)
        if safe_name != name:
            print(f"{label}包含当前系统不支持的字符，已改名: {name} -> {safe_name}")
        return safe_name

    def process_file(src_file, dst_file, map_dir, orig_name, enc_name):
        """单个文件处理函数"""
        if encrypt:
            if not previewOnly:
                encrypt_file_with_name(src_file, dst_file, key)
        else:
            decrypt_file_with_name(
                src_file,
                os.path.dirname(dst_file),
                key,
                allow_legacy_unpadded=allow_legacy_unpadded,
            )

        if save_mapping and map_dir:
            # 如果 mapping_pictures 为真，则mapping图像源文件
            if mapping_pictures:
                if is_video_file(src_file):
                    log_path = os.path.join(map_dir, f"{orig_name}.log")
                    if logging:
                        with open(log_path, "w", encoding="utf-8") as log_f:
                            log_f.write(enc_name)
                else:
                    # 否则保存原始文件
                    file_path = os.path.join(map_dir, f"{enc_name}-{orig_name}")
                    shutil.copyfile(src_file, file_path)
            else:
                log_path = os.path.join(map_dir, f"{orig_name}.log")
                if logging:
                    with open(log_path, "w", encoding="utf-8") as log_f:
                        log_f.write(enc_name)

        if save_preview and encrypt and map_dir:
            preview_path = os.path.join(map_dir, f"{enc_name}-{orig_name}.png")
            generate_video_preview(
                src_file,
                preview_path,
                rows=rows,
                cols=cols,
                preview_width=preview_width,
            )

        if effective_delete_source:
            try:
                os.remove(src_file)
            except OSError as exc:
                print(f"处理成功但删除源文件失败: {src_file} - {exc}")

    # 统计总任务数（排除隐藏文件）
    total_tasks = count_valid_tasks(src_dir)

    with tqdm(total=total_tasks, desc="Processing", unit="item") as pbar:
        for root, dirs, files in os.walk(src_dir):
            if not encrypt:
                dirs[:] = [d for d in dirs if "@" not in d]

            if root == src_dir:
                new_root = dst_dir
                map_root = mapping_root if save_mapping else None
            else:
                parent_src = os.path.dirname(root)
                if parent_src not in dir_map:
                    # 父目录已被跳过，跳过此目录及所有子目录
                    dirs[:] = []
                    pbar.update(1)
                    continue

                parent_new = dir_map[parent_src]
                dir_name = os.path.basename(root)
                if encrypt:
                    output_dir_name = encrypt_folder_name(dir_name, key)
                else:
                    skip_this = False
                    try:
                        output_dir_name = decrypt_folder_name(dir_name, key)
                    except Exception:
                        if keep_all_failed:
                            print(f"\n无法解密文件夹名，保持原名: {dir_name}")
                            output_dir_name = dir_name
                        else:
                            print(f"\n无法解密文件夹名: {dir_name}")
                            while True:
                                choice = input(
                                    "选择操作 [y=保持原名 / n=跳过 / end=停止解密 / all=全部保持]: "
                                ).strip().lower()
                                if choice in ("n", "no"):
                                    skip_this = True
                                    break
                                if choice == "end":
                                    print("用户终止解密")
                                    return failures
                                if choice in ("y", "yes"):
                                    output_dir_name = dir_name
                                    break
                                if choice == "all":
                                    keep_all_failed = True
                                    output_dir_name = dir_name
                                    print(f"无法解密文件夹名，保持原名: {dir_name}")
                                    break
                                print("无效选项，请输入 y/n/end/all")

                    if skip_this:
                        dirs[:] = []
                        pbar.update(1)
                        continue

                output_dir_name = safe_component(output_dir_name, "文件夹名")
                new_root = os.path.join(parent_new, output_dir_name)

                if save_mapping:
                    parent_map_new = mapping_dir_map[parent_src]
                    map_dir_name = safe_component(f"{dir_name}@{output_dir_name}", "映射文件夹名")
                    map_root = os.path.join(parent_map_new, map_dir_name)
                else:
                    map_root = None

            dir_map[root] = new_root
            os.makedirs(new_root, exist_ok=True)
            if save_mapping:
                mapping_dir_map[root] = map_root
                os.makedirs(map_root, exist_ok=True)
            pbar.update(1)

            # 过滤隐藏文件
            visible_files = [f for f in files if not f.startswith(".")]
            if not visible_files:
                continue

            if use_multithreading:
                # 线程池（可指定线程数）
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    future_to_src = {}
                    for filename in visible_files:
                        enc_name = string_to_hash(filename)
                        src_file = os.path.join(root, filename)
                        dst_file = os.path.join(new_root, enc_name)
                        future = executor.submit(
                            process_file,
                            src_file,
                            dst_file,
                            get_map_dir(root),
                            filename,
                            enc_name,
                        )
                        future_to_src[future] = src_file

                    for future in as_completed(future_to_src):
                        src_file = future_to_src[future]
                        try:
                            future.result()
                        except Exception as exc:
                            record_failure(src_file, exc)
                        finally:
                            pbar.update(1)
            else:
                # 单线程处理
                for filename in visible_files:
                    enc_name = string_to_hash(filename)
                    src_file = os.path.join(root, filename)
                    dst_file = os.path.join(new_root, enc_name)
                    try:
                        process_file(src_file, dst_file, get_map_dir(root), filename, enc_name)
                    except Exception as exc:
                        record_failure(src_file, exc)
                    finally:
                        pbar.update(1)

    if failures:
        print(f"\n处理完成，其中 {len(failures)} 个文件失败；失败源文件均已保留。")
    else:
        print("\n处理完成，没有文件失败。")

    return failures


if __name__ == "__main__":
    # 设置源目录和目标目录
    source_directory = "/some/path/2encrypt"
    target_directory = "encrypted"
    mediatranscryption(
        source_directory,
        target_directory,
        encrypt=True,
        delete_source=True,
        mapping_pictures=True,
    )

    # 设置源目录和目标目录
    source_directory = "encrypted/some/path"
    target_directory = "decrypted"
    mediatranscryption(
        source_directory,
        target_directory,
        encrypt=False,
        delete_source=True,
    )

    print("处理完成!")
