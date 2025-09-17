import tkinter as tk
from tkinter import ttk, filedialog
import os
from PIL import Image, ImageTk
import threading
import cv2
import time


class MediaPreviewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("媒体文件预览器 - macOS")
        self.root.geometry("1200x800")

        # 设置macOS特定的样式
        self.style = ttk.Style()
        self.style.theme_use('aqua')  # macOS原生样式

        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # 创建顶部控制栏
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        self.select_btn = ttk.Button(self.control_frame, text="选择文件夹", command=self.select_folder)
        self.select_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.folder_path = tk.StringVar()
        self.path_entry = ttk.Entry(self.control_frame, textvariable=self.folder_path, width=50)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # 创建文件列表和预览区域
        self.list_frame = ttk.Frame(self.main_frame)
        self.list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))

        self.preview_frame = ttk.Frame(self.main_frame)
        self.preview_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置网格权重
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        self.list_frame.rowconfigure(0, weight=1)
        self.list_frame.columnconfigure(0, weight=1)
        self.preview_frame.rowconfigure(0, weight=1)
        self.preview_frame.columnconfigure(0, weight=1)

        # 文件列表
        self.file_listbox = tk.Listbox(self.list_frame, selectmode=tk.SINGLE)
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)

        # 添加滚动条
        self.list_scrollbar = ttk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.list_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=self.list_scrollbar.set)

        # 预览区域
        self.preview_label = ttk.Label(self.preview_frame, text="选择文件夹以预览媒体文件", anchor=tk.CENTER)
        self.preview_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # 存储媒体文件路径和当前预览状态
        self.media_files = []
        self.current_media_index = -1
        self.is_playing_video = False
        self.video_capture = None

    def select_folder(self):
        folder_path = filedialog.askdirectory(title="选择包含媒体文件的文件夹")
        if folder_path:
            self.folder_path.set(folder_path)
            self.load_media_files(folder_path)

    def load_media_files(self, folder_path):
        self.media_files = []
        self.file_listbox.delete(0, tk.END)

        # 支持的图片和视频格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv'}

        try:
            for filename in os.listdir(folder_path):
                filepath = os.path.join(folder_path, filename)
                if os.path.isfile(filepath):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in image_extensions or ext in video_extensions:
                        self.media_files.append(filepath)
                        self.file_listbox.insert(tk.END, filename)

            self.status_var.set(f"找到 {len(self.media_files)} 个媒体文件")

            if self.media_files:
                self.file_listbox.selection_set(0)
                self.on_file_select(None)

        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")

    def on_file_select(self, event):
        if not self.media_files:
            return

        selection = self.file_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        if index == self.current_media_index:
            return

        # 停止当前视频播放
        self.stop_video_playback()

        self.current_media_index = index
        filepath = self.media_files[index]
        ext = os.path.splitext(filepath)[1].lower()

        # 根据文件类型处理预览
        if ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}:
            self.preview_image(filepath)
        else:
            self.preview_video(filepath)

    def preview_image(self, image_path):
        try:
            # 使用PIL打开图片并调整大小以适应预览区域
            image = Image.open(image_path)

            # 获取预览区域尺寸
            width = self.preview_frame.winfo_width()
            height = self.preview_frame.winfo_height()

            if width > 1 and height > 1:  # 确保有有效的尺寸
                # 调整图片大小，保持纵横比
                image.thumbnail((width, height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo  # 保持引用

            self.status_var.set(f"预览图片: {os.path.basename(image_path)}")

        except Exception as e:
            self.preview_label.configure(image=None, text=f"无法加载图片: {str(e)}")
            self.status_var.set(f"错误: {str(e)}")

    def preview_video(self, video_path):
        # 设置视频捕获
        self.video_capture = cv2.VideoCapture(video_path)
        if not self.video_capture.isOpened():
            self.preview_label.configure(image=None, text="无法打开视频文件")
            return

        self.is_playing_video = True
        self.status_var.set(f"预览视频: {os.path.basename(video_path)}")

        # 在新线程中播放视频
        thread = threading.Thread(target=self._play_video)
        thread.daemon = True
        thread.start()

    def _play_video(self):
        while self.is_playing_video and self.video_capture.isOpened():
            ret, frame = self.video_capture.read()
            if not ret:
                break

            # 将OpenCV BGR格式转换为RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)

            # 调整大小以适应预览区域
            width = self.preview_frame.winfo_width()
            height = self.preview_frame.winfo_height()

            if width > 1 and height > 1:
                image.thumbnail((width, height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(image)

            # 在主线程中更新GUI
            self.root.after(0, self._update_video_frame, photo)

            # 控制帧率
            time.sleep(1 / 30)  # 约30fps

        self.video_capture.release()

    def _update_video_frame(self, photo):
        if self.is_playing_video:
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo  # 保持引用

    def stop_video_playback(self):
        self.is_playing_video = False
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None


if __name__ == "__main__":
    root = tk.Tk()
    app = MediaPreviewApp(root)
    root.mainloop()