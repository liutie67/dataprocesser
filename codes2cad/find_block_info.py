import ezdxf
from ezdxf import bbox
import sys
import os


def find_block_info(dxf_path, target_block_name):
    # 1. 加载文件
    if not os.path.exists(dxf_path):
        print(f"错误: 文件 {dxf_path} 不存在")
        return

    try:
        doc = ezdxf.readfile(dxf_path)
    except IOError:
        print("错误: 无法读取文件")
        return
    except ezdxf.DXFStructureError:
        print("错误: 文件结构损坏")
        return

    msp = doc.modelspace()

    # 2. 检查块定义是否存在
    if target_block_name not in doc.blocks:
        print(f"⚠️  警告: 图纸中没有定义名为 '{target_block_name}' 的块。")
        # 我们可以列出所有可用的块名供参考
        print(f"可用块名示例: {[b.name for b in doc.blocks if not b.name.startswith('*')][:5]}...")
        return

    # 3. 使用 query 快速查找所有该名字的块参照 (INSERT)
    # query 语法类似于 SQL: 查找类型为 INSERT 且 name 等于 target_block_name 的实体
    block_refs = msp.query(f'INSERT[name=="{target_block_name}"]')

    if len(block_refs) == 0:
        print(f"ℹ️  图纸中定义了块 '{target_block_name}'，但在模型空间中没有被使用（没有参照）。")
        return

    print(f"\n======== 查找结果: '{target_block_name}' (共 {len(block_refs)} 个) ========\n")

    for i, insert in enumerate(block_refs):
        print(f"--- [实例 #{i + 1}] 句柄: {insert.dxf.handle} ---")

        # A. 获取基础属性 (坐标、缩放、旋转)
        # insert.dxf.insert 是插入点 (Insertion Point)，通常是块的 (0,0,0)点在图纸上的位置
        pos = insert.dxf.insert
        scale = (insert.dxf.xscale, insert.dxf.yscale, insert.dxf.zscale)
        rotation = insert.dxf.rotation  # 角度

        print(f"  1. 插入点坐标 (XYZ): ({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})")
        print(f"  2. 缩放比例: X={scale[0]:.2f}, Y={scale[1]:.2f}, Z={scale[2]:.2f}")
        print(f"  3. 旋转角度: {rotation:.2f} 度")

        # B. 计算实际物理边界 (Bounding Box)
        try:
            # bbox.extents 直接返回一个 BoundingBox 对象
            bound_box = bbox.extents([insert])

            # 必须检查 has_data，因为有些块可能是空的
            if bound_box.has_data:
                min_p = bound_box.extmin
                max_p = bound_box.extmax

                # 计算长宽 (世界坐标系下的绝对尺寸)
                width = max_p.x - min_p.x
                height = max_p.y - min_p.y

                print(f"  4. 实际边界 (Bounding Box):")
                print(f"     左下角: ({min_p.x:.2f}, {min_p.y:.2f})")
                print(f"     右上角: ({max_p.x:.2f}, {max_p.y:.2f})")
                print(f"     物理尺寸: 宽 {width:.2f} x 高 {height:.2f}")
            else:
                print(f"  4. 实际边界: 无数据 (可能是空块)")

        except Exception as e:
            print(f"  4. 边界计算失败: {e}")

        print("")


if __name__ == "__main__":
    # 使用示例
    # 假设你之前生成的图纸里没有定义块，你可以先手动在CAD里把那些线条建成一个块，或者找一个现成的图纸

    dxf_file = "YourFile.dxf"  # 替换成你的文件名
    block_name = "BlockName"  # 替换成你要查找的块名

    # 简单的命令行参数处理
    if len(sys.argv) >= 3:
        dxf_file = sys.argv[1]
        block_name = sys.argv[2]

    find_block_info(dxf_file, block_name)