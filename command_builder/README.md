# Python 命令生成器

一个只在本机运行的 FastAPI 网页工具，用于解析和编辑 Python 命令、保存配置、生成不同终端格式的命令，并记录生成历史。工具不会执行所粘贴或生成的命令。

## 主要功能

- 粘贴 `python`、`py` 或 `uv run python` 命令，自动拆分脚本/模块和参数。
- 支持脚本调用与 `python -m package` 模块调用。
- 支持 PowerShell、cmd、Bash 的解析、引用和输出。
- 参数可编辑、启停、拖拽排序，并实时预览重建后的命令。
- 点击“复制命令”会自动写入历史；新配置名称不冲突时同时自动保存。
- 已保存配置的名称作为固定身份：编辑名称后再复制，会按新名称另存为新配置，原配置保持不变。
- 主动保存时，普通字段和值的修改直接更新；参数数量、模式或类型变化时，可选择覆盖原配置、自动添加数字后缀另存或取消。
- 新名称与已有配置冲突时不会静默覆盖；主动保存可选择覆盖同名配置、自动添加数字后缀另存或取消。
- 左右侧栏可折叠；桌面端可拖动历史栏左边缘调整宽度，中央编辑区会同步伸缩。
- 侧栏折叠状态和历史栏宽度均保存在浏览器本地。
- 保存配置、生成历史以及 JSON/TXT 备份迁移。

## 启动

在仓库根目录执行：

```powershell
uv sync --group dev
uv run python -m command_builder
```

默认自动打开 `http://127.0.0.1:8765`。可选启动参数：

```powershell
uv run python -m command_builder --port 9000 --no-browser
```

## 数据与迁移

- 本地数据保存在 `command_builder/data/command_builder.sqlite3`。
- JSON 导出包含全部配置与历史，可在另一台电脑选择“合并”或“全部替换”导入。
- schema v2 增加脚本/模块调用模式；旧版 schema v1 备份和数据库会自动迁移为脚本模式。
- TXT 导出是按生成时间排列的命令清单，仅用于查看和分享。
- `command_builder/data/` 已加入 `.gitignore`，不会意外提交个人命令和路径。

## 测试

```powershell
uv run --group dev pytest command_builder/tests
```
