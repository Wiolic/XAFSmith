"""会话快照：关闭时保存、打开时恢复，并支持命名“拟合草稿”（做到一半的拟合可以随时接着做）。

保存位置（项目内，不含原始数据）：
  output/gui/session.json        上次关闭时的状态（自动）
  output/gui/drafts/<名称>.json  用户手动保存的拟合草稿

快照内容：当前页面、归一化/背景/FT 参数、已载入的谱（只记名字，恢复时重新载入）、各页面的设置
（拟合页的路径表、参数表、拟合范围、所选 FEFF 目录等）。**不保存拟合结果本身**（含 lmfit 对象）：
已完成并想保留的拟合请用“保存结果”，它们进 models/ 与 output/。

纯函数（encode / decode / snapshot / apply）不依赖界面线程，便于单元测试。
"""
from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from xafsmith import logs, paths

VERSION = 1
PAGE_KEYS_SKIP = {"split"}          # 不需要保存的页面状态键（窗口分栏位置之类随界面变化）


def enabled() -> bool:
    """自动测试 / 截图时设置 XAFSMITH_NO_SESSION（或 XAFSMITH_NO_RECENT）即不读写会话文件。"""
    if os.environ.get("XAFSMITH_NO_SESSION") or os.environ.get("XAFSMITH_NO_RECENT"):
        return False
    from xafsmith import update as xup
    return bool(xup.load_settings().get("restore_session", True))


def session_file() -> Path:
    return paths.GUI / "session.json"


def drafts_dir() -> Path:
    return paths.GUI / "drafts"


# ----------------------------------------------------------------------------- 编码
def encode(v):
    """把页面状态里的值转成可存 JSON 的形式（DataFrame / Path / numpy 加标记，无法表示的抛 TypeError）。"""
    if isinstance(v, pd.DataFrame):
        return {"__df__": json.loads(v.to_json(orient="split", date_format="iso", default_handler=str))}
    if isinstance(v, Path):
        return {"__path__": str(v)}
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (tuple, set)):
        return [encode(x) for x in v]
    if isinstance(v, dict):
        return {str(k): encode(x) for k, x in v.items()}
    if isinstance(v, list):
        return [encode(x) for x in v]
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    raise TypeError(f"无法保存 {type(v).__name__}")


def decode(v):
    if isinstance(v, dict):
        if "__df__" in v:
            d = v["__df__"]
            return pd.DataFrame(d["data"], columns=d["columns"], index=d["index"])
        if "__path__" in v:
            return Path(v["__path__"])
        return {k: decode(x) for k, x in v.items()}
    if isinstance(v, list):
        return [decode(x) for x in v]
    return v


def encode_state(state: dict) -> dict:
    """逐键编码，某个键不能保存就跳过并写日志（不让一个键拖垮整份快照）。"""
    out = {}
    for k, v in state.items():
        if k in PAGE_KEYS_SKIP:
            continue
        try:
            out[str(k)] = encode(v)
        except Exception:                                  # noqa: BLE001
            logs.log.debug("session：页面状态键 %s 无法保存，已跳过", k, exc_info=True)
    return out


# ----------------------------------------------------------------------------- 快照
def snapshot(S, pages: dict, only: tuple[str, ...] | None = None) -> dict:
    """S：qt.state.State；pages：{键: 页面对象}（页面有 .state 字典）。only：只取这些页面（草稿用）。"""
    pg = {}
    for key, p in pages.items():
        st = getattr(p, "state", None)
        if not isinstance(st, dict) or not st or (only is not None and key not in only):
            continue
        enc = encode_state(st)
        if enc:
            pg[key] = enc
    return dict(
        version=VERSION,
        saved=datetime.datetime.now().isoformat(timespec="seconds"),
        page=S.extra.get("page", "data"),
        norm=encode(dict(S.norm_par)), bkg=encode(dict(S.bkg_par)), ft=encode(dict(S.ft_par)),
        groups=list(S.groups),
        pages=pg,
    )


def apply_params(S, snap: dict):
    """把快照里的处理参数写回 S（只更新已有键，忽略未知键）。"""
    for name, target in (("norm", S.norm_par), ("bkg", S.bkg_par), ("ft", S.ft_par)):
        for k, v in (snap.get(name) or {}).items():
            if k in target:
                target[k] = v


def apply_pages(snap: dict, pages: dict, only: tuple[str, ...] | None = None):
    for key, st in (snap.get("pages") or {}).items():
        p = pages.get(key)
        if p is None or not isinstance(getattr(p, "state", None), dict) or (only is not None and key not in only):
            continue
        for k, v in st.items():
            try:
                p.state[k] = decode(v)
            except Exception:                              # noqa: BLE001
                logs.log.debug("session：恢复页面 %s 的键 %s 失败", key, k, exc_info=True)


# ----------------------------------------------------------------------------- 文件
def _write(path: Path, snap: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)                                   # 原子替换：写到一半崩溃不会留下坏文件


def _read(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) and d.get("version") == VERSION else None
    except FileNotFoundError:
        return None
    except Exception:                                       # noqa: BLE001
        logs.log.warning("session：读取 %s 失败（已忽略）", path, exc_info=True)
        return None


def save_session(S, pages: dict) -> bool:
    if not enabled() or not paths.is_project(paths.ROOT):
        return False
    try:
        _write(session_file(), snapshot(S, pages))
        return True
    except Exception:                                       # noqa: BLE001
        logs.log.warning("session：保存会话失败", exc_info=True)
        return False


def load_session() -> dict | None:
    return _read(session_file())


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(name).strip()).strip("._") or "draft"


def save_draft(name: str, S, pages: dict, only: tuple[str, ...] = ("fit",)) -> Path:
    """保存命名草稿（默认只含拟合页设置 + 处理参数 + 所需的谱名）。"""
    snap = snapshot(S, pages, only=only)
    snap["name"] = name
    snap["only"] = list(only)
    p = drafts_dir() / (safe_name(name) + ".json")
    _write(p, snap)
    return p


def list_drafts() -> list[dict]:
    """[{name, file, saved}]，最近保存的在前。"""
    out = []
    d = drafts_dir()
    if d.exists():
        for f in d.glob("*.json"):
            s = _read(f)
            if s:
                out.append(dict(name=s.get("name", f.stem), file=f, saved=s.get("saved", "")))
    return sorted(out, key=lambda x: x["saved"], reverse=True)


def load_draft(file) -> dict | None:
    return _read(Path(file))


def delete_draft(file) -> None:
    f = Path(file)
    if f.parent == drafts_dir() and f.suffix == ".json":    # 只删草稿目录里的 .json
        f.unlink(missing_ok=True)
