"""readers.formats —— 各格式的 reader。新增格式：写一个 Reader 子类，在 readers/__init__.py 的 REGISTRY 中登记。

不凭记忆写格式：只加入有真实样例文件可测的格式（见 tests/data/demo_project/SOURCES.md）。
"""
from xafsmith import logs
import re
from pathlib import Path

import numpy as np

from .base import (ReadError, Reader, header_names, make_group, nearest_edge, read_text,
                   split_table, table_to_group)

_BSRF_ELEM = re.compile(r"Element:\s*([A-Z][a-z]?)\s*,\s*([\d.]+)\s*eV\s*,\s*(.*)$")


def _valid_symbol(s):
    import xraydb
    try:
        return bool(s) and xraydb.atomic_number(s) is not None
    except Exception:                          # noqa: BLE001
        logs.log.debug("readers.formats._valid_symbol 出错（已忽略或已提示）", exc_info=True)
        return False


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ BSRF
class BsrfReader(Reader):
    name = "bsrf"
    label = ("BSRF（北京同步辐射 1W1B 等）", "BSRF (Beijing SR, 1W1B etc.)")

    def detect(self, path, head):
        first = "".join(head.splitlines(True)[:5])
        return 90 if ("BSRF" in first or "Element:" in first) else 0

    def read(self, path, mode=None, columns=None, group=None):
        path = Path(path)
        header, rows = [], []
        for line in read_text(path).splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                header.append(s.lstrip("#").strip())
                continue
            try:
                rows.append([float(x) for x in s.split()])
            except ValueError:
                continue
        if not rows:
            raise ReadError(f"{path.name}：没有数值数据", f"{path.name}: no numeric data")
        data = np.array([r for r in rows if len(r) == len(rows[0])])
        if data.shape[1] < 4:
            raise ReadError(f"{path.name}：BSRF 格式应至少有 4 列（Energy I0 I1 If）",
                            f"{path.name}: BSRF files need at least 4 columns (Energy I0 I1 If)")
        element, e_nom, mode_hdr, timestamp = None, None, None, ""
        for h in header:
            m = _BSRF_ELEM.search(h)
            if m:
                element, e_nom = m.group(1), float(m.group(2))
                txt = m.group(3).lower()
                mode_hdr = "fluo" if "fluor" in txt else ("trans" if "trans" in txt else None)
            elif re.match(r"\d{4}/\d+/\d+", h):
                timestamp = h
        mode = mode if mode in ("trans", "fluo") else (mode_hdr or "trans")
        g = make_group(data[:, 0], i0=data[:, 1], i1=data[:, 2], ifl=data[:, 3], mode=mode,
                       element=element, e_nominal=e_nom, filename=path, timestamp=timestamp,
                       source="BSRF", fmt=self.name,
                       columns={"energy": ["Energy"], "i0": ["I0"], "it": ["I1"], "if": ["If"]},
                       guessed=[] if mode_hdr else ["mode"])
        g.header = header
        return [g]


# ------------------------------------------------------------------ XDI
class XdiReader(Reader):
    name = "xdi"
    label = ("XDI（X 射线吸收数据交换格式）", "XDI (X-ray Absorption Data Interchange)")
    suffixes = (".xdi",)

    def detect(self, path, head):
        return 100 if head.lstrip().startswith("# XDI/") or head.lstrip().startswith("#XDI/") else 0

    @staticmethod
    def parse_header(text):
        meta, cols, in_meta = {}, {}, True
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if not s.startswith("#"):
                break
            body = s.lstrip("#").strip()
            if body.startswith("///"):
                in_meta = False
                continue
            if not in_meta:
                continue
            m = re.match(r"^([A-Za-z]\w*\.[\w.]+)\s*:\s*(.*)$", body)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            mc = re.match(r"^Column\.(\d+)$", key, re.I)
            if mc:
                toks = val.split()
                cols[int(mc.group(1))] = (toks[0] if toks else "", " ".join(toks[1:]))
            else:
                meta[key] = val
        xdi_cols = [cols[i] for i in sorted(cols)] if cols else None
        return meta, xdi_cols

    def read(self, path, mode=None, columns=None, group=None):
        path = Path(path)
        text = read_text(path)
        meta, xdi_cols = self.parse_header(text)
        pre, data = split_table(text)
        names, units = header_names(pre, data.shape[1], xdi_cols)
        el = meta.get("Element.symbol") or meta.get("Scan.element")
        ed = meta.get("Element.edge") or meta.get("Scan.edge")
        el = el if _valid_symbol(el) else None
        desc = "; ".join(x for x in (meta.get("Sample.name"), meta.get("Sample.prep"),
                                     meta.get("Sample.notes")) if x)
        g = table_to_group(path, self.name, pre, data, names, units, columns=columns, mode=mode,
                           element=el, edge=ed if el else None,
                           e_nominal=_f(meta.get("Scan.edge_energy")),
                           timestamp=meta.get("Scan.start_time", ""), description=desc)
        g.xdi_meta = meta
        return [g]


# ------------------------------------------------------------------ Athena .xmu
class AthenaXmuReader(Reader):
    name = "athena_xmu"
    label = ("Athena 文本（.xmu，#% 文件头）", "Athena text (.xmu, #% header)")
    suffixes = (".xmu",)

    def detect(self, path, head):
        return 95 if any(l.startswith("#%") for l in head.splitlines()[:15]) else 0

    @staticmethod
    def _element(atom, edge, emin, emax):
        """#%atom 可能是元素符号，也可能是化学式（如 Fe2O3）：用吸收边能量落在扫描范围内的元素。"""
        import xraydb
        syms = [s for s in dict.fromkeys(re.findall(r"[A-Z][a-z]?", atom or "")) if _valid_symbol(s)]
        if len(syms) == 1:
            return syms[0]
        if edge:
            hit = []
            for s in syms:
                try:
                    if emin <= float(xraydb.xray_edge(s, edge).energy) <= emax:
                        hit.append(s)
                except Exception:              # noqa: BLE001
                    logs.log.debug("readers.formats._element 出错（已忽略或已提示）", exc_info=True)
                    pass
            if len(hit) == 1:
                return hit[0]
        return None

    def read(self, path, mode=None, columns=None, group=None):
        path = Path(path)
        text = read_text(path)
        pre, data = split_table(text)
        hdr = {}
        for l in pre:
            m = re.match(r"^#%(\w+):\s*(.*)$", l)
            if m:
                hdr[m.group(1)] = m.group(2).strip()
        names, units = header_names(pre, data.shape[1])
        edge = hdr.get("edge") or None
        el = self._element(hdr.get("atom"), edge, float(data[:, 0].min()), float(data[:, 0].max()))
        desc = "; ".join(x for x in (hdr.get("name"), hdr.get("prep")) if x)
        g = table_to_group(path, self.name, pre, data, names, units, columns=columns, mode=mode,
                           element=el, edge=edge if el else None, timestamp=hdr.get("date", ""),
                           description=desc)
        g.athena_header = hdr
        return [g]


# ------------------------------------------------------------------ XDAC（NSLS 等）
class XdacReader(Reader):
    name = "xdac"
    label = ("XDAC 数据文件", "XDAC datafile")

    def detect(self, path, head):
        return 100 if head.startswith("XDAC") else 0

    def read(self, path, mode=None, columns=None, group=None):
        path = Path(path)
        text = read_text(path)
        pre, data = split_table(text)
        names, units = header_names(pre, data.shape[1])
        e0 = None
        stamp = ""
        desc = []
        for l in pre:
            m = re.match(r"^E0\s*=\s*([\d.]+)", l)
            if m:
                e0 = float(m.group(1))
                continue
            m = re.search(r'created on (\S+) at (.+?) on ', l)
            if m:
                stamp = f"{m.group(1)} {m.group(2)}"
                continue
            if "=" in l or l.startswith(('XDAC', '"', '-')) or (names and l.split() == names):
                continue
            desc.append(l)
        el = ed = None
        guessed = []
        if e0:
            ne = nearest_edge(e0, 15.0)
            if ne:
                el, ed = ne[0], ne[1]
                guessed = ["element", "edge"]
        g = table_to_group(path, self.name, pre, data, names, units, columns=columns, mode=mode,
                           element=el, edge=ed, e_nominal=e0, timestamp=stamp, guessed=guessed,
                           description="; ".join(desc))
        return [g]


# ------------------------------------------------------------------ Athena 工程 .prj
class PrjReader(Reader):
    name = "prj"
    label = ("Athena 工程（.prj）", "Athena project (.prj)")
    suffixes = (".prj",)

    def detect(self, path, head):
        if str(path).lower().endswith(".prj"):
            return 100
        try:
            with open(path, "rb") as f:
                return 60 if f.read(2) == b"\x1f\x8b" else 0
        except OSError:
            return 0

    def read(self, path, mode=None, columns=None, group=None):
        from larch.io import read_athena

        from .base import guess_element_edge
        path = Path(path)
        prj = read_athena(str(path), do_preedge=False, do_bkg=False, do_fft=False)
        items = prj.groups.items() if hasattr(prj, "groups") else prj._athena_groups.items()
        out = []
        for name, grp in items:
            if group is not None and name != group:
                continue
            guessed, warns = [], []
            el, ed, cands = guess_element_edge(grp.energy, grp.mu)
            if el:
                guessed = ["element", "edge"]
                if len(cands) > 1:
                    warns.append("吸收边按能量猜测，候选：" + "、".join(f"{a} {b}" for a, b, _ in cands))
            g = make_group(grp.energy, mu=grp.mu, mode=mode if mode in ("trans", "fluo") else None,
                           element=el, edge=ed, e_nominal=cands[0][2] if cands else None,
                           filename=path, label=name, source="athena_prj", fmt=self.name,
                           mu_from="file", columns={"mu": [name]}, guessed=guessed, warnings=warns)
            g.athena_params = getattr(grp, "athena_params", None)
            g.group_name = name
            out.append(g)
        if group is not None and not out:
            raise ReadError(f"工程中没有组“{group}”", f"No group '{group}' in the project")
        return out


# ------------------------------------------------------------------ 通用列文本（兜底）
class ColumnsReader(Reader):
    name = "columns"
    label = ("通用列文本（按列名映射）", "Generic column text (mapped by column name)")
    suffixes = (".dat", ".txt", ".csv", ".chi")

    def detect(self, path, head):
        n = 0
        for line in head.splitlines():
            try:
                if len([float(x) for x in re.split(r"[\s,]+", line.strip())]) >= 2:
                    n += 1
            except ValueError:
                pass
        return 10 if n >= 3 else 0

    def read(self, path, mode=None, columns=None, group=None):
        path = Path(path)
        pre, data = split_table(read_text(path))
        names, units = header_names(pre, data.shape[1])
        return [table_to_group(path, self.name, pre, data, names, units, columns=columns, mode=mode)]
