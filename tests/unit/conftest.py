"""pytest 配置：保证测试不碰用户的项目文件夹与界面设置。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XAFSMITH_NO_RECENT"] = "1"
