# Python 命令生成器

一个只在本机运行的 FastAPI 网页工具，用于保存 Python 命令配置、生成不同终端格式的命令，并记录生成历史。工具不会执行所生成的命令。

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
- TXT 导出是按生成时间排列的命令清单，仅用于查看和分享。
- `command_builder/data/` 已加入 `.gitignore`，不会意外提交个人命令和路径。

## 测试

```powershell
uv run --group dev pytest command_builder/tests
```
