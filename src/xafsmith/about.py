"""软件信息：作者、免责声明、引用方式（界面、汇总报告、安装向导、命令行共用同一套文字）。"""
from . import __version__

REPO = "https://github.com/Wiolic/XAFSmith"
CREDIT = "Developed by Eggy & Claude Opus 5.5 (Anthropic)"
LICENSE = "PolyForm Noncommercial License 1.0.0"
LICENSE_CN = ("许可：PolyForm Noncommercial 1.0.0——允许非商业用途（个人、学术研究、教学）的使用、修改和分发；"
              "禁止任何商业用途（包括出售或收费分发本软件及其修改版）。分发时须附上许可条款与引用说明。")
LICENSE_EN = ("License: PolyForm Noncommercial 1.0.0 — noncommercial use (personal, academic, teaching), modification "
              "and distribution are allowed; any commercial use, including selling or paid distribution of the software "
              "or a modified version, is not. Distributions must include the license terms and the citation notice.")

DISCLAIMER_CN = ("免责声明：本软件按“现状”提供，不附带任何形式的保证；作者不对使用本软件得到的任何结果负责。"
                 "请使用者自行核验结果，建议将关键结果与 Athena / Artemis（Demeter）的处理和拟合结果对比。")
DISCLAIMER_EN = ("Disclaimer: XAFSmith is provided \"as is\", without warranty of any kind. The authors accept no "
                 "responsibility for results obtained with it. Please validate your results; we recommend "
                 "cross-checking key results against Athena / Artemis (Demeter).")

CITATION_TEXT = f"Eggy & Claude. XAFSmith: XAFS processing and fitting software, version {__version__}. {REPO}"
CITE_CN = f"如果在论文中使用了本软件，请引用本仓库，并同时引用其所依赖的 Larch 与 FEFF：{CITATION_TEXT}"
CITE_EN = ("If you use XAFSmith in a publication, please cite this repository "
           f"(and Larch and FEFF, on which it is built): {CITATION_TEXT}")
UPSTREAM = [
    "M. Newville, \"Larch: An Analysis Package for XAFS and Related Spectroscopies\", "
    "J. Phys.: Conf. Ser. 430, 012007 (2013).",
    "S. I. Zabinsky, J. J. Rehr, A. Ankudinov, R. C. Albers, M. J. Eller, \"Multiple-scattering calculations "
    "of x-ray-absorption spectra\", Phys. Rev. B 52, 2995 (1995).  (FEFF6)",
    "A. L. Ankudinov, B. Ravel, J. J. Rehr, S. D. Conradson, \"Real-space multiple-scattering calculation and "
    "interpretation of x-ray-absorption near-edge structure\", Phys. Rev. B 58, 7565 (1998).  (FEFF8; cite when FEFF8L is used)",
]


def text_block():
    return "\n".join([f"XAFSmith {__version__} — {CREDIT}", f"{REPO}  ({LICENSE})", "", DISCLAIMER_CN, DISCLAIMER_EN, "",
                      CITE_CN, CITE_EN, "", *UPSTREAM])
