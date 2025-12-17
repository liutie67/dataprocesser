import ezdxf
from ezdxf import bbox
from ezdxf.math import Vec2, is_point_in_polygon_2d
import sys
import os


def find_boxed_text(dxf_path, target_text_content):
    # 1. 加载文件
    if not os.path.exists(dxf_path):
        print(f"❌ 错误: 文件 {dxf_path} 不存在")
        return

    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return

    print(f"正在搜索内容为 '{target_text_content}' 且被框住的文字...")

    # 2. 获取所有候选多段线 (作为框框)
    # 我们假设框框是 LWPOLYLINE (最常见的2D多段线) 且必须是闭合的
    polylines = msp.query('LWPOLYLINE')
    candidate_boxes = []

    for poly in polylines:
        if poly.is_closed:
            # 获取多段线的所有顶点 (2D坐标)
            # poly.get_points() 返回的是 (x, y, start_width, end_width, bulge)
            # 我们只需要 x, y
            points = [Vec2(p[0], p[1]) for p in poly.get_points()]
            candidate_boxes.append({'entity': poly, 'points': points})

    print(f"  - 找到 {len(candidate_boxes)} 个闭合多段线框。")

    # 3. 获取所有目标文字
    # 同时搜索 TEXT (单行) 和 MTEXT (多行)
    # 注意：MTEXT 内容可能包含格式代码，这里做简单的精确匹配
    target_texts = []

    # 检查 TEXT
    for t in msp.query('TEXT'):
        if t.dxf.text == target_text_content:
            target_texts.append(t)

    # 检查 MTEXT (需要去格式化，这里简化处理，直接查 plain_text)
    for t in msp.query('MTEXT'):
        # MTEXT 获取纯文本比较复杂，简单匹配 text 属性
        # 实际项目中可能需要 t.plain_text() 但这需要较新版 ezdxf 支持且消耗性能
        if target_text_content in t.text:
            target_texts.append(t)

    print(f"  - 找到 {len(target_texts)} 个内容匹配的文字对象。")
    print("\n======== 开始几何匹配 (Point-in-Polygon) ========\n")

    matched_count = 0

    # 4. 双重循环进行空间匹配
    for text_obj in target_texts:
        # 获取文字的位置 (插入点)
        # 忽略 Z 轴，只看 2D 平面
        t_pos = Vec2(text_obj.dxf.insert.x, text_obj.dxf.insert.y)

        found_box = None

        # 遍历所有框框，看文字在哪个里面
        for box in candidate_boxes:
            # 核心算法：判断点是否在多边形内
            # 这是一个射线法算法，非常高效
            if is_point_in_polygon_2d(t_pos, box['points']):
                found_box = box['entity']
                break  # 找到框就不找了（假设文字只在一个框里）

        if found_box:
            matched_count += 1
            poly_entity = found_box

            print(f"--- [匹配组 #{matched_count}] ---")
            print(f"  文字句柄: {text_obj.dxf.handle} | 框框句柄: {poly_entity.dxf.handle}")

            # 5. 计算框框的几何信息 (作为整体信息)
            try:
                # 计算多段线的边界
                bound = bbox.extents([poly_entity])
                if bound.has_data:
                    min_p = bound.extmin
                    max_p = bound.extmax
                    width = max_p.x - min_p.x
                    height = max_p.y - min_p.y

                    center_x = min_p.x + width / 2
                    center_y = min_p.y + height / 2

                    print(f"  1. 整体中心坐标: ({center_x:.2f}, {center_y:.2f})")
                    print(f"  2. 整体边界范围 (Box):")
                    print(f"     左下: ({min_p.x:.2f}, {min_p.y:.2f})")
                    print(f"     右上: ({max_p.x:.2f}, {max_p.y:.2f})")
                    print(f"  3. 整体尺寸: 宽 {width:.2f} x 高 {height:.2f}")
            except Exception as e:
                print(f"  计算边界失败: {e}")
            print("")
        else:
            # 文字找到了，但没在任何框里
            # print(f"  文字 ({t_pos}) 未找到对应的包围框。")
            pass

    if matched_count == 0:
        print("未找到任何被框住的目标文字。")


if __name__ == "__main__":
    # 示例配置
    target_file = "Your File.dxf"  # 你的文件名
    search_text = "文字"  # 你要找的文字内容

    # 简单的命令行支持
    if len(sys.argv) >= 3:
        target_file = sys.argv[1]
        search_text = sys.argv[2]

    find_boxed_text(target_file, search_text)