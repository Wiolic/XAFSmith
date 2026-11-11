# 示例数据来源（tests/data/demo_project/data/raw/public/）

全部为公开数据，取自 xraylarch 仓库 `examples/xafsdata/`
(https://github.com/xraypy/xraylarch/tree/master/examples/xafsdata)，下载日期 2026-11-11。
仓库许可：MIT（Copyright 2010-2026 Matthew Newville, Mauro Rovezzi, Bruce Ravel 等）。
注意：MIT 许可覆盖该仓库的分发；数据最初的测量者见各文件头。许可或来源不明确的文件不收录。

| 文件 | 内容 | 文件头中的来源信息 |
|---|---|---|
| cu_metal_rt.xdi | Cu 箔 K 边，透射，XDI | APS 13ID，2001-06-26 |
| cu_rt01.xmu | 同一条 Cu 箔谱，Athena .xmu 格式 | APS 13ID，2001-06-26 |
| feo_rt1.xdi | FeO 粉末 K 边，透射，XDI | APS 20BM，NXS school 2001 |
| fe2o3_rt1.xmu | Fe2O3 粉末 K 边，.xmu | APS 20BM，NXS school 2001 |
| fe3c_rt.xdi | Fe3C 粉末 K 边，XDI | APS 13-BM-D，2002-03-16 |
| ni_metal_rt.xdi | Ni 箔 K 边，XDI | 见文件头 |
| pt_metal_rt.xdi | Pt 箔 L3 边，XDI | 见文件头 |
| fe_athena.prj | Fe 的 Athena 工程 | 见 xraylarch 仓库 |
| fe.060 | Fe 箔 K 边，XDAC 格式 | NSLS X-11A，2002-10-03 |

用途：测试 XDI、.xmu、.prj、XDAC 读入路径；Cu 箔第一壳层基准拟合；Fe K 边价态与 LCF 测试。
基准数值（S0²、ΔE0、σ²）的来源另行写在 tests/benchmark/ 中，不得凭记忆填写。

## 基准测试用文件（tests/data/benchmark/）

| 文件 | 内容 | 来源 |
|---|---|---|
| feffcu01.dat | Cu 金属 fcc 第一壳层 FEFF 路径（FEFF 6.10，reff = 2.5478 Å，N = 12） | xraylarch 仓库 examples/feffit/feffcu01.dat（MIT），下载于 2026-11-11 |

Cu 基准的参考数值取自 xraylarch 回归测试 tests/test_larchexamples_xafs.py::test13_feffit1
（amp 0.93、del_e0 4.364 eV、del_r −0.006 Å、sig2 0.0087 Å²），详见 tests/benchmark/test_cu_feffit.py。
