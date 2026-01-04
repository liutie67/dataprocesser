import os
import shutil
import fnmatch
import logging

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)


def load_patterns_from_file(file_path):
    """
    读取单个文件的规则。
    备注：忽略空行和 # 注释。
    """
    patterns = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        except Exception as e:
            logging.warning(f"读取规则文件出错 {file_path}: {e}")
    return patterns


def is_match(filename, patterns):
    """
    检查文件名是否匹配当前累积的任意规则。
    """
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def copy_selected_files(src_root, dst_root, rule_filename='.gitattributes', tolerance=True):
    """
    核心函数：支持规则继承的复制工具。

    逻辑：
    1. 使用 rule_cache 字典存储 { '目录绝对路径': [该目录及其父级的所有规则] }
    2. os.walk 默认从顶层向下遍历，确保我们处理子目录时，父目录的规则已存在缓存中。
    """

    stats = {'copied': 0, 'skipped': 0, 'errors': 0}

    # 获取绝对路径，防止路径拼接出错
    src_root = os.path.abspath(src_root)
    dst_root = os.path.abspath(dst_root)

    if not os.path.exists(src_root):
        logging.error(f"错误：源目录不存在 -> {src_root}")
        return

    # ---【核心修改点】开始 ---
    # 获取源文件夹的名称 (例如 "dataprocesser")
    # src_folder_name = os.path.basename(src_root)

    # 将其拼接到目标路径之后
    # 变更前: dst_root = .../transparent_encryption
    # 变更后: dst_root = .../transparent_encryption/dataprocesser
    # dst_root = os.path.join(dst_root, src_folder_name)
    # ---【核心修改点】结束 ---

    logging.info(f"源目录名称: [{dst_root}]")
    logging.info(f"最终导出目标: [{dst_root}]")
    logging.info(f"规则策略: 父级规则自动继承")

    # 规则缓存字典：Key=目录路径, Value=规则列表
    rule_cache = {}

    # 遍历目录树 (topdown=True 是默认值，这对继承逻辑至关重要)
    for current_root, dirs, files in os.walk(src_root):
        current_root_abs = os.path.abspath(current_root)

        # --- 1. 计算当前目录的有效规则 (继承 + 本地) ---

        # A. 获取父级规则
        parent_patterns = []
        if current_root_abs != src_root:
            # 如果不是根目录，则查找父目录的规则
            parent_dir = os.path.dirname(current_root_abs)
            # 从缓存中获取父级规则（因为是 topdown 遍历，父级一定已经被处理过）
            parent_patterns = rule_cache.get(parent_dir, [])

        # B. 获取本地规则
        local_rule_file = os.path.join(current_root, rule_filename)
        local_patterns = load_patterns_from_file(local_rule_file)

        # C. 合并规则 (父级规则 + 本地规则)
        # 这里简单的列表相加即可，子级规则追加在后
        effective_patterns = parent_patterns + local_patterns

        # D. 存入缓存，供更深层的子目录使用
        rule_cache[current_root_abs] = effective_patterns

        # --- 2. 处理文件复制 ---

        # 计算相对路径，用于在目标目录重建结构
        rel_path = os.path.relpath(current_root, src_root)

        # 如果当前目录（包含继承的）没有任何规则，且也不包含在默认策略里，则跳过该目录下所有文件
        if not effective_patterns:
            stats['skipped'] += len(files)
            continue

        for filename in files:
            # 跳过规则文件本身（可选）
            if filename == rule_filename:
                continue

            # 检查匹配 (使用合并后的 effective_patterns)
            if is_match(filename, effective_patterns):
                src_file = os.path.join(current_root, filename)

                # 构建目标路径
                if rel_path == '.':
                    dst_file_dir = dst_root
                else:
                    dst_file_dir = os.path.join(dst_root, rel_path)

                dst_file = os.path.join(dst_file_dir, filename)

                try:
                    os.makedirs(dst_file_dir, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    # 只有在详细模式下才打印每个文件，避免日志过多
                    # logging.info(f"复制: {filename}")
                    stats['copied'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    msg = f"复制出错: {src_file} -> {e}"
                    if tolerance:
                        logging.warning(msg + " (已容忍跳过)")
                    else:
                        logging.error(msg)
                        raise e
            else:
                stats['skipped'] += 1

    logging.info("-" * 30)
    logging.info(f"任务结束。统计结果：")
    logging.info(f"  [√] 成功复制: {stats['copied']} 个文件")
    logging.info(f"  [-] 跳过文件: {stats['skipped']} 个文件")
    logging.info(f"  [!] 发生错误: {stats['errors']} 个文件")


# --- 执行入口 ---
if __name__ == '__main__':
    # 设置输入输出目录
    input_dir = r'./Data_Source_A'
    output_dir = r'./Data_Backup_B'

    # 启动复制
    # tolerance=True: 遇到文件占用或无权限时不崩溃
    copy_selected_files(input_dir, output_dir, tolerance=True)