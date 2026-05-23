# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指导。

## 项目概述

个人数据处理工具集 — 包含多个独立的 Python 模块，涵盖媒体文件管理、加密、YOLO 数据集准备、重复文件检测和 CAD 图纸生成。Python 3.12+，使用 uv 管理环境与依赖。

## 构建与运行

```bash
# 安装依赖
uv sync

# 运行某个模块（各模块独立运行）
uv run python <module>/pipeline.py
uv run python <module>/local_launchpad.py

# 运行占位主入口
uv run python main.py
```

无测试套件。各模块自包含，独立运行。

## 架构

仓库是独立模块（顶层目录）的平铺集合，每个模块解决特定的数据处理任务。模块之间没有共享框架，仅共享设计模式。

### 常见文件约定（跨模块重复出现）

- **`pipeline.py`** — 主编排入口，将多个处理步骤串联为工作流。见于：`yolo_process`、`video_crypt`、`duplicate_detection`、`singers`。
- **`local_launchpad.py`** — 模块级配置与启动脚本，包含硬编码路径、参数及对 pipeline 函数的调用。这些文件已被 gitignore，作为本地运行配置。见于：`video_crypt`、`folders_files`、`folder_partition`、`occupation`、`transparent_encryption`。
- **`utiles.py`** — 模块内工具函数（注：拼写为故意为之）。见于：`duplicate_detection`、`folders_files`、`occupation`。

### 模块概览

| 模块 | 用途 |
|---|---|
| `yolo_process/` | YOLO 数据集工具：分离图像/标签、划分训练/验证集、边界框可视化、合并类别、重写标签、视频抽帧 |
| `video_crypt/` | AES-256-CBC 视频加密/解密，支持文件名匿名化和密钥管理 |
| `video_preview/` | 视频网格缩略图生成，支持批量处理 |
| `duplicate_detection/` | 基于 SHA256 的重复文件检测，SQLite 数据库跟踪（快速哈希 vs 完整哈希） |
| `singers/` | 音频提取（ffmpeg）和 Canny 边缘检测视频处理 |
| `folders_files/` | 文件管理：按大小分区、批量重命名、文件夹比较、文件筛选/移动 |
| `folder_partition/` | 大规模文件夹分区，结合文件抽取与加密 |
| `transparent_encryption/` | 基于规则（.gitattributes 风格）的文件选择和结构化复制 |
| `codes2cad/` | 交通标志 CAD 图纸生成（通过 ezdxf 输出 DXF），支持 2D/3D 渲染和中文字体 |
| `occupation/` | 磁盘空间测试 — 生成大体积占位文件 |
| `dp_conversations_convert/` | DeepSeek 对话导出格式转换器（markdown/text） |
| `personal_library/` | 基于 Tkinter 的媒体文件查看器 GUI |

### 关键技术细节

- **加密**：`video_crypt` 通过 pycryptodome 使用 AES-256-CBC。密钥存储在 `.aes` 文件中（已 gitignore）。`key_manager.py` 负责密钥生成与读取。
- **YOLO 数据集**：`yolo_process` 操作标准 YOLO 格式（图像 + `.txt` 标签文件）。`pipeline.py` 串联流程：分离 → 验证 → 划分。
- **重复检测**：两阶段哈希 — 先快速检查（文件大小 + 头尾哈希），再用完整 SHA256 确认。SQLite 数据库跟踪已扫描文件。
- **多线程**：多个模块使用 `ThreadPoolExecutor` 进行批量 I/O 操作（图像复制、哈希计算、预览生成）。
- **CAD 生成**：`codes2cad` 使用 ezdxf 编程生成包含交通标志详细组件的 DXF 图纸。

## 依赖

核心：numpy、opencv-python、pillow、pycryptodome、tqdm、ezdxf。外部工具：ffmpeg（`singers/` 模块用于音频提取）。
