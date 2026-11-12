"""窗口版入口（XAFSmith.exe，无控制台）：总是打开图形界面；带参数时按命令行处理。"""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from xafsmith import cli
    if len(sys.argv) == 1:
        sys.argv.append("gui")
    cli.main()
