# io 格式插件化设计（0.5.1 起实现）

> 状态：已实现（`src/xafsmith/readers/`，测试 `tests/unit/test_readers.py`）。凡标 ⚠ 的数值/物理判断点，改动前须先讨论。
>
> 实现时与设计的差异：
> 1. XDI 文件头由 reader 自己解析（`# Key.Name: value`、`Column.N`），没有用 `larch.io.read_xdi`（后者会改动列名与单位，不利于按名映射与追溯）。
> 2. 吸收边候选排序：K、L3 优先于 L2、L1，再按离导数最大值的距离排。只按距离排会把 Fe2O3 的 Fe K 边误判成能量略高的 Nd L1（公开数据 fe_athena.prj 实测出现过）。
> 3. 能量单位：列名写明 keV 则直接换算；否则中位数 < 2 报错（既不像 eV 也不像 keV），2–100 按 keV 换算并标记为猜测。
> 4. 能量“不单调”只在升降混杂（下降点 > 2%）时报错；整段降序（反向扫描）照常按升序排列。
> 5. 兼容旧调用的 `read_bsrf`、`read_columns`（按列号）、`is_bsrf` 已在 1.0 删除；按列号读会静默算错 μ，一律用 `read_scan(columns={...})` 按列名映射。

## 1. 问题

- `pipeline.py:96,161,211`、`qt/state.py:111`、`qt/pages/process.py:155,423` 写死 `read_bsrf`，
  meta.csv 中的非 BSRF 文件无法处理、校准、登记。
- `read_columns` 靠列号，同一格式不同文件列顺序不同（`cu_metal_rt.xdi` 是 i0, itrans；
  `pt_metal_rt.xdi` 是 itrans, i0），按列号读会**静默算错 μ**。
- `mode="mu"`（直接用文件 μ 列）混用了“测量模式”与“μ 的来源”，`qc.py:84` 等按 `mode == "trans"` 分支的地方会失效。

## 2. 统一结果（Group 契约，向后兼容）

保留现有属性：`energy, mu, i0, i1, ifl, mode, element, edge, e_nominal, filename, label, timestamp, source`。

改动 / 新增：

| 属性 | 含义 |
|---|---|
| `mode` | **只表示测量模式**：`trans` / `fluo` / `None`（未知）。不再出现 `"mu"` |
| `mu_from` | `"channels"`（由 I0/It/If 计算）或 `"file"`（取文件中的 μ 列） |
| `format` | reader 名称，如 `xdi` |
| `columns` | 实际使用的列映射 `{energy: "energy", i0: "i0", it: "itrans", ...}`，写入 qc/处理记录，便于追溯 |
| `meta_guessed` | 列表，记下哪些字段是猜的（如 `["edge"]`），界面与 init 据此提示核对 |

⚠ **μ 的定义规则**：文件里同时有原始通道和 μ 列时，**一律由通道计算**（透射 ln(I0/It)，荧光 If/I0），
保证全项目同一定义；只有通道不全时才用文件 μ 列，并设 `mu_from="file"`。两者都有时，计算值与文件 μ 列做一致性检查
（去掉常数偏移后相关系数 < 0.999 则在记录里警告，可能是列映射错了）。

## 3. reader 接口（`src/xafsmith/readers/`）

```python
class Reader:
    name: str                       # "xdi"、"bsrf"……，写入 meta.csv 的 format 列
    label: tuple[str, str]          # (中文, English)，界面显示
    suffixes: tuple[str, ...]       # 仅作加分，不作判定依据
    def detect(self, path, head: str) -> int: ...      # 0–100 置信度；head = 文件前 4 KB 文本
    def read(self, path, mode=None, columns=None, group=None) -> list[Group]: ...
```

- 注册表：`readers/__init__.py` 中 `REGISTRY = [BsrfReader(), XdiReader(), ...]`。
- 入口（`io.py` 保留为门面，旧函数名保留做兼容）：
  - `detect_format(path) -> (name, score)`；最高分 < 30 → 视为未知格式。
  - `read_file(path, fmt=None, **kw) -> list[Group]`（多组文件如 .prj 返回多个）。
  - `read_scan(path, fmt=None, mode=None, columns=None, group=None) -> Group`：**pipeline 与界面统一只调用它**。
- 错误：统一抛 `ReadError(zh, en)`，信息写明缺哪个通道、识别到哪些列名，界面直接显示。

## 4. 首批 reader

| name | 判定 | 读法 | 元素/边来源 |
|---|---|---|---|
| `bsrf` | 现有 `is_bsrf` 规则 | 现有 `read_bsrf` 逻辑迁入 | 文件头 Element 行 |
| `xdi` | 首行 `# XDI/` | `larch.io.read_xdi`，按 `Column.N` 名称映射 | `Element.symbol/edge`，或 `Scan.element/edge` |
| `athena_xmu` | 有 `#%` 头 | 通用列解析 + 最后一行 `#` 列名 | `#%atom`（只在是单个元素符号时采用）、`#%edge` |
| `xdac` | 首行 `XDAC` | 通用列解析，列名行不带 `#` | 头里 `E0=` → 按能量猜 |
| `prj` | 后缀 `.prj` 或 gzip 魔数 | `larch.io.read_athena` | Athena 参数 |
| `columns` | 兜底，有 ≥ 2 列数字即 10 分 | 通用列解析，按列名猜映射；猜不出则要求用户给映射 | 按能量猜 |

SSRF、ESRF、SPring-8、Diamond 等：**拿到真实样例文件后再加**，不按记忆写格式。

## 5. 列名映射（通用列解析共用）

- 列名取自：XDI `Column.N`；否则数据前最后一行非数字文本（可带或不带 `#`）。
- 按名称（不分大小写，去掉空格/下划线）匹配，先匹配到的优先：

| 角色 | 名称规则 |
|---|---|
| energy | `energy`、`e`、`ener`、`energy_ev` |
| i0 | `i0`、`io`、`imon`、`mon` |
| it | `it`、`i1`、`itrans`、`itr` |
| if | `if`、`ifl`、`ifluor`、`fluo`、`ff`；多个通道名（`ch1…chN`、`if1…`）→ 求和 |
| mu | `mu`、`xmu`、`mutrans`、`mufluor`、`ln(i0/i1)`、`if/i0` |

- ⚠ 能量单位：中位数 < 100 视为 keV，×1000，并记入 `meta_guessed`。能量不单调或像角度（< 100 且无 keV 依据）→ 报错，不猜。
- ⚠ 模式：有 it 无 if → trans；有 if 无 it → fluo；两者都有 → 以 meta.csv `mode` 为准，未给则 trans 并记入 `meta_guessed`。
- 映射不唯一或缺 energy / i0 → 抛 `ReadError`，界面弹“列映射”对话框。

## 6. 元素与吸收边

- 文件头给出的优先。否则 `guess_element_edge(energy, mu)`：取 dμ/dE 最大处能量，在 xraydb（Elam）表中
  找扫描范围内 ±25 eV 的 K/L3/L2/L1 边；**多个候选时不自动选**，返回候选列表，`init` 填第一个并在 note 写
  “吸收边按能量猜测，候选：…，请核对”。
- 处理时以 meta.csv `edge_key` 为准（现有 `load_scan` 已如此），文件头只用于登记。

## 7. 数据标准改动（schema 1.0 → 1.1，向后兼容）

- meta.csv 新增可选列：
  - `format`：reader 名或 `xafsmith.json` 中的格式模板名；空 = 自动识别。
  - `group`：多组文件（.prj）中的组名；`init` 对 .prj 每组生成一行。
- `xafsmith.json` 新增可选 `"formats"`：用户保存的列映射模板

```json
"formats": {
  "BL14W1_fluo": {"base": "columns", "energy": "Energy", "i0": "I0", "if": ["Ch1", "Ch2", "Ch3", "Ch4"], "mode": "fluo"}
}
```

- 旧项目没有这两列/这个键时行为不变（全部视作 `bsrf` 自动识别结果）。`validate` 检查 format 名是否存在。

## 8. 调用点改动

| 位置 | 改为 |
|---|---|
| `pipeline.py:96`（init 扫描） | `detect_format`；未知格式跳过并在汇总里列出文件名（不再静默） |
| `pipeline.py:161`、`:211` | `read_scan(path, fmt=row.format, mode=..., group=row.group)` |
| `qt/state.py:111`、`qt/pages/process.py:423` | `read_scan` |
| `qt/pages/process.py:150–160`（读入） | 删 BSRF/列号分支；显示识别出的格式与列映射，可改；“保存为格式模板”写入 `formats` |
| `qc.py:84–88` | 分支改看 `mode`（已不含 `"mu"`）；`mu_from == "file"` 时跳过依赖 I0 的检查并注明 |

新增 CLI：`xafsmith formats`（列出 reader 与模板）、`xafsmith inspect <文件>`（显示识别格式、列名、映射、元素/边及是否为猜测）。

## 9. 测试（`tests/unit/test_readers.py`）

- 每个公开文件：识别出的 format、元素、边、点数、能量单调。
- `cu_metal_rt.xdi`：由通道算出的 μ 与文件 `mutrans` 列一致（差 < 1e-6）。
- `cu_metal_rt.xdi` 与 `cu_rt01.xmu`（同一次测量）：μ 一致。
- `pt_metal_rt.xdi`：itrans 在 i0 前面，仍得到正确 μ（列名映射，不按列号）。
- `fe.060`：无 `#` 的列名行被识别。
- BSRF：测试内生成一个**合成的**小文件（只测解析，不作数据），覆盖透射/荧光文件头。
- 旧项目兼容：本机 IrTaOx 项目 `xafsmith process` 前后 process_summary.csv 数值不变（仅本机运行）。

## 10. 不在本次范围

死时间校正、多元素探测器逐道剔除、HDF5/NeXus、角度→能量换算、自吸收校正。
