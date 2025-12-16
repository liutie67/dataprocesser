import ezdxf
import os
import sys

# --- 兼容性设置：处理不同 ezdxf 版本的常量位置 ---
try:
    # 新版 ezdxf (v1.x+)
    from ezdxf.const import BLK_XREF, BLK_XREF_OVERLAY
except ImportError:
    try:
        # 旧版 ezdxf
        from ezdxf.lldxf.const import BLK_XREF, BLK_XREF_OVERLAY
    except ImportError:
        # 如果都找不到，使用 DXF 标准数值硬编码作为后备
        # Bit 2 (4): This is an xref
        # Bit 3 (8): This is an xref overlay
        BLK_XREF = 4
        BLK_XREF_OVERLAY = 8


def inspect_dxf_content(dxf_filepath):
    """
    读取并检查 DXF 文件的内容
    """

    # 1. 检查文件是否存在
    if not os.path.exists(dxf_filepath):
        print(f"❌ 错误: 文件未找到: {dxf_filepath}")
        return

    print(f"\n======== 正在检查文件: {os.path.basename(dxf_filepath)} ========")

    # 2. 尝试加载文件
    try:
        doc = ezdxf.readfile(dxf_filepath)
        print("✅ DXF 文件加载成功!")
    except IOError:
        print("❌ 错误: 无法读取文件（可能被其他程序占用或不是DXF文件）。")
        return
    except ezdxf.DXFStructureError as e:
        print(f"❌ 错误: DXF 文件结构损坏: {e}")
        return

    # 3. 文件头信息
    print("\n--- [1] 文件头变量 (Header) ---")
    header = doc.header
    version = header.get('$ACADVER', '未知')
    units = header.get('$INSUNITS', '未指定')
    # 单位代码映射表
    unit_map = {0: 'Unitless', 1: 'Inches', 4: 'Millimeters', 6: 'Meters'}
    unit_str = unit_map.get(units, str(units))

    print(f"  DXF 版本: {version}")
    print(f"  图形单位: {unit_str}")

    # 4. 图层信息
    print("\n--- [2] 图层 (Layers) ---")
    layers = list(doc.layers)
    if layers:
        print(f"  共发现 {len(layers)} 个图层:")
        for i, layer in enumerate(layers[:10]):  # 只显示前10个
            state = []
            if layer.is_locked(): state.append("锁定")
            if layer.is_off(): state.append("关闭")
            if layer.is_frozen(): state.append("冻结")
            state_str = f"[{', '.join(state)}]" if state else "[正常]"
            print(f"    - {layer.dxf.name:<15} 颜色:{layer.dxf.color:<3} {state_str}")
        if len(layers) > 10:
            print(f"    ... (还有 {len(layers) - 10} 个图层未显示)")
    else:
        print("  没有发现用户定义的图层。")

    # 5. 块定义 (Block Definitions)
    print("\n--- [3] 块定义 (Blocks) ---")
    user_blocks = []

    for block in doc.blocks:
        # 过滤逻辑：排除布局(Layout)、模型空间(ModelSpace)和外部参照(XREF)
        is_layout = block.is_layout_block if hasattr(block, 'is_layout_block') else (
            block.dxf.name.lower().startswith('*'))

        # 检查 XREF 标志位
        flags = getattr(block.dxf, 'flags', 0)
        is_xref = bool(flags & BLK_XREF) or bool(flags & BLK_XREF_OVERLAY)

        if not is_layout and not is_xref:
            user_blocks.append(block)

    if user_blocks:
        print(f"  共发现 {len(user_blocks)} 个用户块定义:")
        for blk in user_blocks:
            print(f"    - 块名: {blk.dxf.name:<15} 图元数: {len(blk)}")
    else:
        print("  没有发现用户定义的块 (全是系统块或无块)。")

    # 6. 模型空间统计
    print("\n--- [4] 模型空间 (ModelSpace) ---")
    msp = doc.modelspace()
    entity_counts = {}
    total_entities = 0

    for e in msp:
        etype = e.dxftype()
        entity_counts[etype] = entity_counts.get(etype, 0) + 1
        total_entities += 1

    if total_entities > 0:
        print(f"  模型空间共有 {total_entities} 个图元。统计如下:")
        for etype, count in entity_counts.items():
            print(f"    - {etype}: {count}")
    else:
        print("  模型空间是空的 (一张白纸)。")

    print("\n======== 检查结束 ========\n")


# --- 主程序入口 ---
if __name__ == "__main__":
    # 这里设置你要检查的文件名
    # 如果你之前运行过生成的脚本，应该有这个文件
    target_file = 'test.dxf'

    # 为了方便，如果找不到默认文件，尝试让用户输入
    if not os.path.exists(target_file):
        if len(sys.argv) > 1:
            target_file = sys.argv[1]
        else:
            print(f"当前目录下未找到默认文件 '{target_file}'。")
            target_file = input("请输入你要检查的 DXF 文件路径: ").strip().strip('"')  # 去除引号

    inspect_dxf_content(target_file)
