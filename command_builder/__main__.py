from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="启动本地 Python 命令生成器")
    parser.add_argument("--port", type=int, default=8765, help="本地服务端口")
    parser.add_argument(
        "--no-browser", action="store_true", help="启动后不自动打开浏览器"
    )
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run("command_builder.app:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
