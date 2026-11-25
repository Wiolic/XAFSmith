"""项目配置（xafsmith.json）的版本迁移：读入后在内存里升到当前版本，绝不写回文件。

xafsmith.schema 记录配置的数据标准版本（paths.SCHEMA_VERSION 是软件当前版本）。
- 旧版本：按 MIGRATIONS 逐级升；升级结果只在内存里，下次正常保存配置时才写成新版本。
- 缺 xafsmith.schema：视为 "1.0"。
- 新于软件的版本 / 无法解析的版本串：抛 ValueError（项目由更新版本的 XAFSmith 创建，请升级软件）。
schema.validate 不经过这里：校验要看文件里的真实版本。
"""
import copy
from collections.abc import Callable

from . import logs, paths

FIRST_VERSION = "1.0"             # 没有 xafsmith.schema 键的配置按它处理


def parse_version(v) -> tuple[int, ...]:
    """"1.1" → (1, 1)。按整数元组比较，不用字符串比较（"1.10" > "1.9"）。无法解析抛 ValueError。"""
    s = str(v).strip() if v is not None else ""
    try:
        parts = tuple(int(p) for p in s.split("."))
        if not parts or any(p < 0 for p in parts) or not all(p.isdigit() for p in s.split(".")):
            raise ValueError
    except ValueError:
        raise ValueError(f"无法识别的配置版本 {v!r}（应形如 \"1.1\"） / "
                         f"unrecognized config version {v!r} (expected like \"1.1\")") from None
    return parts


def _key(v: tuple[int, ...]) -> str:
    return ".".join(str(p) for p in v)


def _set_schema(cfg: dict, version: str) -> dict:
    if not isinstance(cfg.get("xafsmith"), dict):
        cfg["xafsmith"] = {}
    cfg["xafsmith"]["schema"] = version
    return cfg


def _1_0_to_1_1(cfg: dict) -> dict:
    """1.1 只新增 meta.csv 的可选列 format、group：配置本身不用改，只记新版本号。"""
    return _set_schema(cfg, "1.1")


# 键 = 从哪个版本升；值 = 返回升一级后的配置（可就地修改传入的深拷贝）
MIGRATIONS: dict[str, Callable[[dict], dict]] = {"1.0": _1_0_to_1_1}


def _stored_version(cfg: dict):
    x = cfg.get("xafsmith")
    return x.get("schema") if isinstance(x, dict) else None


def check_not_newer(v) -> None:
    """版本新于软件时抛 ValueError（双语）；无法解析的版本串同样抛。"""
    cur = parse_version(paths.SCHEMA_VERSION)
    if parse_version(v) > cur:
        raise ValueError(f"项目配置版本 {v} 比本软件支持的 {paths.SCHEMA_VERSION} 新：项目由更新版本的 XAFSmith 创建，"
                         f"请升级软件 / project config version {v} is newer than the {paths.SCHEMA_VERSION} "
                         "this XAFSmith supports: the project was created by a newer XAFSmith, please upgrade")


def upgrade(cfg: dict) -> tuple[dict, list[tuple[str, str]]]:
    """配置深拷贝后逐级升到 paths.SCHEMA_VERSION；返回 (新配置, 改动说明 [(中文, English), …])。
    已是当前版本：返回内容相同的拷贝与空说明。"""
    out = copy.deepcopy(cfg)
    raw = _stored_version(out)
    missing = raw is None
    ver = parse_version(FIRST_VERSION if missing else raw)
    check_not_newer(_key(ver))
    cur = parse_version(paths.SCHEMA_VERSION)
    notes: list[tuple[str, str]] = []
    if missing:
        notes.append(("配置缺少 xafsmith.schema，按 1.0 处理", "config has no xafsmith.schema, treated as 1.0"))
    while ver < cur:
        fn = MIGRATIONS.get(_key(ver))
        if fn is None:
            raise ValueError(f"没有从配置版本 {_key(ver)} 升级的步骤 / no migration step from config version {_key(ver)}")
        out = fn(out)
        new = parse_version(_stored_version(out))
        if new <= ver:
            raise ValueError(f"配置迁移 {_key(ver)} 没有提升版本号 / migration {_key(ver)} did not raise the version")
        notes.append((f"配置从 {_key(ver)} 升到 {_key(new)}（只在内存中；文件未改动，下次保存配置时才写成新版本）",
                      f"config upgraded from {_key(ver)} to {_key(new)} in memory only "
                      "(the file is unchanged until the config is next saved)"))
        ver = new
    return out, notes


# ------------------------------------------------------------------ 提示（日志每个文件一次；图形界面每次打开项目一次）
_LOGGED: set[str] = set()
_PENDING: dict[str, list[tuple[str, str]]] = {}


def announce(path, notes) -> None:
    """load_config 升级过配置时调用：写一条日志（同一文件只写一次），并登记给图形界面提示。"""
    if not notes:
        return
    key = str(path)
    _PENDING[key] = notes
    if key not in _LOGGED:
        _LOGGED.add(key)
        logs.log.info("%s：%s", key, "；".join(f"{zh} / {en}" for zh, en in notes))


def take_pending(path) -> list[tuple[str, str]]:
    """取走并清除某个配置文件的待提示说明（图形界面用）。"""
    return _PENDING.pop(str(path), [])
