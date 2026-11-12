"""控制台版入口（xafsmith-cli.exe；Windows 文件名不区分大小写，不能与 XAFSmith.exe 同名）：命令行 / AI 助手使用，行为与 pip 安装的 `xafsmith` 相同。"""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from xafsmith import cli
    cli.main()
