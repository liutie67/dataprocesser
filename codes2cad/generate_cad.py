import ezdxf


def create_signage_cad():
    # 创建一个新的 DXF 文档 (R2010版本)
    doc = ezdxf.new('R2010')

    # --- 关键修复：设置中文字体样式，防止CAD打开乱码 ---
    if 'SimHei' not in doc.styles:
        doc.styles.new('SimHei', dxfattribs={'font': 'simhei.ttf'})

    msp = doc.modelspace()

    # --- 定义尺寸 (单位: mm) ---
    # 支撑方管
    pole_w = 100
    pole_h = 1500

    # 箱体
    box_w = 1034
    box_h = 1428

    # LED显示屏
    screen_w = 960
    screen_h = 1280

    # 摄像头支撑杆
    # 标注为 200*600*600
    cam_arm_offset_x = 200
    cam_arm_h = 600
    cam_arm_w = 600

    # 避雷针
    rod_w = 12
    rod_h = 1000

    # --- 绘图坐标计算 (以地面中心为 0,0) ---

    # 1. 绘制支撑方管
    pole_p1 = (-pole_w / 2, 0)
    pole_p2 = (pole_w / 2, 0)
    pole_p3 = (pole_w / 2, pole_h)
    pole_p4 = (-pole_w / 2, pole_h)

    msp.add_lwpolyline([pole_p1, pole_p2, pole_p3, pole_p4, pole_p1], close=True)
    # 修复：使用 set_placement 替代 set_pos，并指定字体样式
    msp.add_text("支撑方管 100*100*1500 mm", dxfattribs={'height': 30, 'style': 'SimHei'}).set_placement(
        (pole_w / 2 + 50, pole_h / 2))

    # 2. 绘制箱体
    box_bottom_y = pole_h
    box_p1 = (-box_w / 2, box_bottom_y)
    box_p2 = (box_w / 2, box_bottom_y)
    box_p3 = (box_w / 2, box_bottom_y + box_h)
    box_p4 = (-box_w / 2, box_bottom_y + box_h)

    msp.add_lwpolyline([box_p1, box_p2, box_p3, box_p4, box_p1], close=True)
    msp.add_text(f"箱体 {box_w}*{box_h}*199 mm", dxfattribs={'height': 30, 'style': 'SimHei'}).set_placement(
        (box_w / 2 + 50, box_bottom_y + box_h / 2))

    # 3. 绘制 LED 显示屏
    screen_margin_x = (box_w - screen_w) / 2
    screen_margin_y = (box_h - screen_h) / 2

    screen_p1 = (-screen_w / 2, box_bottom_y + screen_margin_y)
    screen_p2 = (screen_w / 2, box_bottom_y + screen_margin_y)
    screen_p3 = (screen_w / 2, box_bottom_y + box_h - screen_margin_y)
    screen_p4 = (-screen_w / 2, box_bottom_y + box_h - screen_margin_y)

    msp.add_lwpolyline([screen_p1, screen_p2, screen_p3, screen_p4, screen_p1], close=True)
    msp.add_text(f"LED显示屏 {screen_w}*{screen_h} mm", dxfattribs={'height': 30, 'style': 'SimHei'}).set_placement(
        (-100, box_bottom_y + box_h / 2))

    # 4. 绘制爆闪灯盒子
    strobe_h = 100
    strobe_w = box_w
    strobe_y = box_bottom_y + box_h

    msp.add_line((-strobe_w / 2, strobe_y), (strobe_w / 2, strobe_y))
    msp.add_line((-strobe_w / 2, strobe_y), (-strobe_w / 2, strobe_y + strobe_h))
    msp.add_line((strobe_w / 2, strobe_y), (strobe_w / 2, strobe_y + strobe_h))
    msp.add_line((-strobe_w / 2, strobe_y + strobe_h), (strobe_w / 2, strobe_y + strobe_h))
    msp.add_text("爆闪灯盒子", dxfattribs={'height': 30, 'style': 'SimHei'}).set_placement(
        (-50, strobe_y + strobe_h + 20))

    # 5. 绘制摄像头支撑杆
    arm_connect_y = box_bottom_y + box_h - 200
    arm_start_x = -box_w / 2

    msp.add_lwpolyline([
        (arm_start_x, arm_connect_y),
        (arm_start_x - 300, arm_connect_y),
        (arm_start_x - 300, arm_connect_y + 400)
    ])
    msp.add_text("摄像头支撑杆", dxfattribs={'height': 30, 'style': 'SimHei'}).set_placement(
        (arm_start_x - 450, arm_connect_y + 200))

    # 6. 绘制避雷针
    rod_x = arm_start_x - 300
    rod_start_y = arm_connect_y + 400

    msp.add_line((rod_x, rod_start_y), (rod_x, rod_start_y + rod_h))
    msp.add_text(f"避雷针 12*{rod_h}mm", dxfattribs={'height': 30, 'style': 'SimHei'}).set_placement(
        (rod_x + 20, rod_start_y + rod_h / 2))

    # 7. 绘制地面线
    msp.add_line((-1000, 0), (1000, 0))

    # 保存文件
    filename = "traffic_signage.dxf"
    doc.saveas(filename)
    print(f"成功生成文件: {filename}，请使用 CAD 软件打开。")


import math

def create_detailed_cad():
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # --- 投影参数 (控制视角) ---
    # 这里的逻辑是将 Z 轴(深度) 投影到 X,Y 平面上
    # 角度 45度，缩放 0.5 是经典的“斜二测”画法，能很好地表现厚度
    Z_ANGLE = math.radians(45)
    Z_SCALE = 0.5

    def to_screen(x, y, z):
        """将3D坐标转换为2D图纸坐标 (轴测投影)"""
        sx = x + z * Z_SCALE * math.cos(Z_ANGLE)
        sy = y + z * Z_SCALE * math.sin(Z_ANGLE)
        return sx, sy

    def draw_line_3d(p1, p2):
        """画3D线"""
        sp1 = to_screen(*p1)
        sp2 = to_screen(*p2)
        msp.add_line(sp1, sp2)

    def draw_box_3d(x, y, z, w, h, d, detail_level='simple'):
        """
        绘制一个长方体 (基点在左下后角)
        x,y,z: 起点
        w: 宽(x轴), h: 高(y轴), d: 深(z轴)
        """
        # 定义8个顶点
        # 前面 (z + d)
        f_bl = (x, y, z + d)  # Front Bottom Left
        f_br = (x + w, y, z + d)  # Front Bottom Right
        f_tr = (x + w, y + h, z + d)  # Front Top Right
        f_tl = (x, y + h, z + d)  # Front Top Left

        # 后面 (z)
        b_bl = (x, y, z)
        b_br = (x + w, y, z)
        b_tr = (x + w, y + h, z)
        b_tl = (x, y + h, z)

        # 绘制可见线 (假设从右前方观看: 画前面、右面、顶面)

        # 1. 前面 (Front Face) - 总是完整绘制
        draw_line_3d(f_bl, f_br)
        draw_line_3d(f_br, f_tr)
        draw_line_3d(f_tr, f_tl)
        draw_line_3d(f_tl, f_bl)

        # 2. 深度连接线 (连接前后)
        # 右上角连接
        draw_line_3d(f_tr, b_tr)
        # 右下角连接
        draw_line_3d(f_br, b_br)
        # 左上角连接
        draw_line_3d(f_tl, b_tl)

        # 3. 后/侧面轮廓 (Back/Side Faces)
        draw_line_3d(b_tr, b_br)  # 后右竖线
        draw_line_3d(b_tr, b_tl)  # 后上横线

        return f_bl, f_tr, b_tr  # 返回关键点用于后续定位附着物

    # --- 尺寸定义 (mm) ---
    pole_w, pole_d, pole_h = 100, 100, 1500
    box_w, box_h, box_d = 1034, 1428, 199
    screen_w, screen_h = 960, 1280

    # --- 1. 绘制立柱 (Pole) ---
    # 立柱中心对齐 X=0
    pole_x = -pole_w / 2
    pole_y = 0
    pole_z = 0  # 立柱在中心深度

    draw_box_3d(pole_x, pole_y, pole_z, pole_w, pole_h, pole_d)

    # 1.1 绘制底座加强筋 (三角形细节)
    rib_h = 150
    rib_w = 80
    # 右侧筋
    p1 = (pole_x + pole_w, 0, pole_z + pole_d / 2)  # 柱底
    p2 = (pole_x + pole_w + rib_w, 0, pole_z + pole_d / 2)  # 地面外延
    p3 = (pole_x + pole_w, rib_h, pole_z + pole_d / 2)  # 柱身
    draw_line_3d(p1, p2)
    draw_line_3d(p2, p3)
    draw_line_3d(p3, p1)  # 斜边
    # 左侧筋
    p1_l = (pole_x, 0, pole_z + pole_d / 2)
    p2_l = (pole_x - rib_w, 0, pole_z + pole_d / 2)
    p3_l = (pole_x, rib_h, pole_z + pole_d / 2)
    draw_line_3d(p1_l, p2_l)
    draw_line_3d(p2_l, p3_l)
    draw_line_3d(p3_l, p1_l)

    # --- 2. 绘制大箱体 (Box) ---
    # 箱体安装在立柱顶部，居中
    box_x = -box_w / 2
    box_y = pole_h
    # 箱体通常比立柱厚，假设箱体中心与立柱中心对齐
    # 立柱中心 z_center = pole_d / 2
    # 箱体起始 z = z_center - box_d / 2
    box_z = (pole_d / 2) - (box_d / 2)

    draw_box_3d(box_x, box_y, box_z, box_w, box_h, box_d)

    # --- 3. 绘制 LED 屏幕 (内嵌细节) ---
    # 在箱体前表面绘制
    screen_margin_x = (box_w - screen_w) / 2
    screen_margin_y = (box_h - screen_h) / 2
    screen_z = box_z + box_d  # 前表面 Z

    # 屏幕边框 (画两圈矩形表示边框厚度)
    s_x = box_x + screen_margin_x
    s_y = box_y + screen_margin_y

    # 外圈
    p_bl = to_screen(s_x, s_y, screen_z)
    p_tr = to_screen(s_x + screen_w, s_y + screen_h, screen_z)
    p_br = to_screen(s_x + screen_w, s_y, screen_z)
    p_tl = to_screen(s_x, s_y + screen_h, screen_z)

    msp.add_lwpolyline([p_bl, p_br, p_tr, p_tl, p_bl], close=True)

    # 内圈 (稍微向内缩一点，表示屏幕区域)
    bezel = 20
    p_bl_in = to_screen(s_x + bezel, s_y + bezel, screen_z)
    p_tr_in = to_screen(s_x + screen_w - bezel, s_y + screen_h - bezel, screen_z)
    p_br_in = to_screen(s_x + screen_w - bezel, s_y + bezel, screen_z)
    p_tl_in = to_screen(s_x + bezel, s_y + screen_h - bezel, screen_z)

    msp.add_lwpolyline([p_bl_in, p_br_in, p_tr_in, p_tl_in, p_bl_in], close=True)

    # 连接内外圈 (表现边框倒角/厚度)
    msp.add_line(p_bl, p_bl_in)
    msp.add_line(p_br, p_br_in)
    msp.add_line(p_tr, p_tr_in)
    msp.add_line(p_tl, p_tl_in)

    # --- 4. 爆闪灯盒子 (顶部) ---
    strobe_h = 100
    strobe_d = box_d  # 同样深度
    strobe_w = box_w
    draw_box_3d(box_x, box_y + box_h, box_z, strobe_w, strobe_h, strobe_d)

    # 画几个圆圈代表灯珠 (在爆闪灯前表面)
    light_y = box_y + box_h + strobe_h / 2
    light_z = box_z + box_d
    for i in range(3):
        lx = box_x + (box_w / 4) * (i + 1)
        center = to_screen(lx, light_y, light_z)
        # 画椭圆模拟透视圆
        msp.add_ellipse(center, major_axis=(0, 25), ratio=0.6)  # 竖直椭圆

    # --- 5. 摄像头支架 (左侧 L型) ---
    # 从箱体左侧上方伸出
    arm_size = 50  # 方管截面
    arm_attach_y = box_y + box_h - 200
    arm_attach_x = box_x
    arm_attach_z = box_z + box_d / 2 - arm_size / 2  # 居中连接

    # 5.1 横杆 (向左伸出)
    arm_len_1 = 400
    # 为了表现L型，我们需要画两个连接的长方体
    # 横向段 (从箱体向左) -> x 从 (arm_attach_x - arm_len_1) 到 arm_attach_x
    draw_box_3d(arm_attach_x - arm_len_1, arm_attach_y, arm_attach_z, arm_len_1, arm_size, arm_size)

    # 5.2 竖杆 (向上)
    arm_len_2 = 500
    # 在横杆左端向上
    draw_box_3d(arm_attach_x - arm_len_1, arm_attach_y + arm_size, arm_attach_z, arm_size, arm_len_2, arm_size)

    # --- 6. 摄像头 (精细化) ---
    # 挂在竖杆横向延伸的小支架上，或者直接挂在弯头处。
    # 这里假设竖杆顶部还有一个小横向平台用来挂球机
    cam_base_x = arm_attach_x - arm_len_1 + arm_size / 2
    cam_base_y = arm_attach_y + arm_size + arm_len_2 - 50  # 略微靠下挂着
    cam_base_z = arm_attach_z + arm_size / 2

    # 绘制摄像头连接杆 (细圆柱)
    rod_len = 50
    p_top = to_screen(cam_base_x, cam_base_y + 50, cam_base_z)  # 连在杆上
    p_btm = to_screen(cam_base_x, cam_base_y, cam_base_z)
    msp.add_line(p_top, p_btm)

    # 绘制摄像头主体 (近似圆柱体)
    cam_r = 40
    cam_h = 60
    # 顶盖 (椭圆)
    cam_top_center = p_btm
    msp.add_ellipse(cam_top_center, major_axis=(cam_r, 0), ratio=0.5)

    # 底部 (椭圆)
    cam_btm_center = to_screen(cam_base_x, cam_base_y - cam_h, cam_base_z)
    msp.add_ellipse(cam_btm_center, major_axis=(cam_r, 0), ratio=0.5)

    # 连接线 (机身)
    l_edge_top = to_screen(cam_base_x - cam_r, cam_base_y, cam_base_z)
    l_edge_btm = to_screen(cam_base_x - cam_r, cam_base_y - cam_h, cam_base_z)
    r_edge_top = to_screen(cam_base_x + cam_r, cam_base_y, cam_base_z)
    r_edge_btm = to_screen(cam_base_x + cam_r, cam_base_y - cam_h, cam_base_z)

    msp.add_line(l_edge_top, l_edge_btm)
    msp.add_line(r_edge_top, r_edge_btm)

    # 镜头球体 (半圆弧)
    msp.add_arc(cam_btm_center, radius=cam_r, start_angle=180, end_angle=360, is_counter_clockwise=True)

    # --- 7. 避雷针 ---
    # 在竖杆顶部
    rod_h = 1000
    rod_base_x = arm_attach_x - arm_len_1 + arm_size / 2
    rod_base_y = arm_attach_y + arm_size + arm_len_2

    p_rod_base = to_screen(rod_base_x, rod_base_y, arm_attach_z + arm_size / 2)
    p_rod_top = to_screen(rod_base_x, rod_base_y + rod_h, arm_attach_z + arm_size / 2)
    msp.add_line(p_rod_base, p_rod_top)

    # 针尖装饰
    msp.add_circle(p_rod_top, radius=5)

    # --- 8. 地面示意线 ---
    g_p1 = to_screen(-1000, 0, 0)
    g_p2 = to_screen(1000, 0, 0)
    msp.add_line(g_p1, g_p2)
    # 画一点斜线表示地面纹理
    for i in range(-800, 800, 100):
        s = to_screen(i, 0, 0)
        e = to_screen(i - 50, -30, 0)
        msp.add_line(s, e)

    filename = "traffic_signage_3d_detailed.dxf"
    doc.saveas(filename)
    print(f"生成完毕: {filename}")


if __name__ == "__main__":
    create_signage_cad()
    create_detailed_cad()
