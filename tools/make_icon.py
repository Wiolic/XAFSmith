"""生成 XAFSmith 图标（扁平简笔画）：蓝底 + 煎蛋 + XAFS 吸收谱。

构思：蓝色圆角方形边框内是圆角方形的蛋白；一条 μ(E) 曲线横穿蛋白——边前平台、陡升的吸收边，蛋黄是白线峰
顶上的一个点，右侧是逐渐衰减的 EXAFS 振荡。灵感来自作者头像（蓝底煎蛋）。
输出：src/xafsmith/assets/xafsmith.png（512×512）与 xafsmith.ico（16–256 多尺寸）。

用法：python tools/make_icon.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "src" / "xafsmith" / "assets"
N = 1024                                 # 绘制尺寸（单位坐标 0–1 乘 N），4 倍超采样
SS = 4
BLUE = (38, 110, 196, 255)
WHITE = (255, 247, 226, 255)
YOLK = (255, 168, 20, 255)
YOLK_HI = (255, 222, 140, 255)
LINE = (16, 44, 100, 255)

BORDER = 0.07                            # 蛋白（圆角方形）四周留出的蓝色边框
YC = (0.40, None, 0.046)                 # 白线峰 x 位置、（自动）、蛋黄半径


def mu(x):
    """μ(E) 曲线 y 坐标：边前平台 → 吸收边 → 白线峰（顶上是蛋黄）→ 衰减的 EXAFS 振荡"""
    xe = YC[0] - 0.035
    step = 1 / (1 + math.exp(-(x - xe) / 0.014))
    wl = math.exp(-((x - YC[0]) / 0.04) ** 2)
    dx = max(0.0, x - (YC[0] + 0.03))
    osc = -math.sin(dx / 0.08 * math.pi) * math.exp(-dx / 0.32) * (1 - math.exp(-dx / 0.015))
    return 0.62 - 0.20 * step - 0.13 * wl - 0.11 * osc * step


def make():
    S = N * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(0.22 * S), fill=BLUE)
    # 蛋白：规则圆角方形，四周留蓝色边框
    m = BORDER * S                                    # 蓝色边框宽度
    d.rounded_rectangle((m, m, S - 1 - m, S - 1 - m), radius=int(0.22 * S - m), fill=WHITE)
    # 谱线：横穿蛋白
    w = 0.042 * S
    xs = [0.16 + 0.70 * i / 800 for i in range(801)]
    line = [(x * S, mu(x) * S) for x in xs]
    for (xa, ya), (xb, yb) in zip(line, line[1:]):
        d.line((xa, ya, xb, yb), fill=LINE, width=int(w))
    for x, y in line[::2] + [line[-1]]:
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=LINE)
    # 蛋黄
    xpk = min(xs, key=mu)                             # 白线峰顶
    xc, yc, r = xpk * S, (mu(xpk) - 0.035) * S, YC[2] * S   # 坐在峰顶上方，不遮住峰形
    d.ellipse((xc - r, yc - r, xc + r, yc + r), fill=YOLK)
    hr = r * 0.3
    hx, hy = xc - r * 0.4, yc - r * 0.4
    d.ellipse((hx - hr, hy - hr * 0.75, hx + hr, hy + hr * 0.75), fill=YOLK_HI)

    # 文字
    font = None
    for name in ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"):
        try:
            font = ImageFont.truetype(name, int(0.15 * S))
            break
        except OSError:
            pass
    font = font or ImageFont.load_default()
    box = d.textbbox((0, 0), "XAFSmith", font=font)
    scale = 0.70 * S / (box[2] - box[0])            # 宽度占图标 70%
    font = font.font_variant(size=int(font.size * scale)) if hasattr(font, "font_variant") else font
    d.text((0.5 * S, 0.80 * S), "XAFSmith", font=font, fill=LINE, anchor="mm")

    OUT.mkdir(parents=True, exist_ok=True)
    img.resize((512, 512), Image.LANCZOS).save(OUT / "xafsmith.png")
    img.resize((256, 256), Image.LANCZOS).save(
        OUT / "xafsmith.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ok", OUT)


if __name__ == "__main__":
    make()
