"""modelcheck —— 模型 JSON 的结构性检查（E11）。纯函数，无 larch / Qt 依赖；schema（validate 报告）与
fit_exafs.normalize_model（抛 ValueError）共用同一份检查，样板同 sigma2.model_issues + raise_on_errors。

只收结构性检查：必填字段、datasets 为非空数组、顶层不得有 sample/paths、datasets[i] 是对象、sample/paths 存在且非空、
id 非空且不重复、范围键缺失、params 是对象。依赖数据、k 上限、N_idp、警告的检查（范围合理性、路径文件、变量数、重复样品、
fitspace）留在 schema。

两处原有规则并不一致，用 strict 参数各自保持原结果（不统一：统一会让某些模型从“能拟合”变“报错”或反之）：
  strict=True（schema.validate）                       strict=False（normalize_model）
  必填 name / params / datasets、旧格式必填 9 个字段     只要求 kmin kmax rmin rmax kweight（kweight 缺省 2，不算缺）
  params 必须是对象                                      不检查 params 类型
  datasets[i] 缺 sample/paths：键不存在                  键不存在、为空、为 0 都算缺
  id：键存在时 .strip() 后须非空；缺省 id = sample        id 必须是非空字符串（不 strip）；缺省 id = sample，非字符串即报错
  范围键缺失：数据集与顶层都没有这个键                   值为 None（键不存在，或值是 null）
  顶层检查先后：必填 → sample/paths → params → datasets   datasets → sample/paths
  消息：where + 简短中文（报告用）                        完整双语消息（与 v1.4.1 之前逐字相同）

返回项为 (级别 'error'|'warn', 位置, 中文, English)。strict=True 时 位置 相对模型文件（空串 = 模型本身），中文是不含位置的短消息；
strict=False 时 中文 / English 已是 normalize_model 一直抛出的完整消息，位置只作参考。
"""
from __future__ import annotations

RANGE_KEYS = ("kmin", "kmax", "rmin", "rmax", "kweight")
MODEL_REQUIRED = ["name", "sample", "kmin", "kmax", "rmin", "rmax", "kweight", "params", "paths"]
MODEL_REQUIRED_MULTI = ["name", "params", "datasets"]


def _err(where, zh, en):
    return ("error", where, zh, en)


def has_datasets(m) -> bool:
    """datasets 是非空数组（否则后面的数据集检查无从谈起）。"""
    return isinstance(m.get("datasets"), list) and bool(m["datasets"])


def legacy_params_issues(m, strict=True):
    """params 必须是对象（只在 strict 下检查；normalize_model 不查）。"""
    if strict and "params" in m and not isinstance(m["params"], dict):
        yield _err("params", "应是对象 {名称: 初值或 {value, vary, min, max, expr}}",
                   "must be an object {name: value or {value, vary, min, max, expr}}")


def legacy_issues(m, strict):
    """旧格式（没有 datasets 键）：必填字段。"""
    if strict:
        for k in MODEL_REQUIRED:
            if k not in m:
                yield _err("", f"缺少字段 {k}", f"missing field {k}")
        return
    miss = [k for k in RANGE_KEYS if m.get(k, 2 if k == "kweight" else None) is None]   # kweight 缺省 2（v1.1）
    if miss:
        yield _err("", f"模型缺少 {', '.join(miss)}", f"model is missing {', '.join(miss)}")


def top_issues(m, strict):
    """多数据集模型（有 datasets 键）的顶层检查。"""
    if strict:
        for k in MODEL_REQUIRED_MULTI:
            if k not in m:
                yield _err("", f"缺少字段 {k}", f"missing field {k}")
        for k in ("sample", "paths"):
            if k in m:
                yield _err(k, f"多数据集模型不得有顶层 {k}（写进 datasets[i]），否则旧代码会误读",
                           f"a multi-dataset model must not have a top-level '{k}' (put it in datasets[i]), "
                           "or older code will misread it")
        yield from legacy_params_issues(m, True)
        if not has_datasets(m):
            yield _err("datasets", "应是非空数组", "must be a non-empty array")
        return
    if not has_datasets(m):
        yield _err("datasets", "datasets 必须是非空数组", "datasets must be a non-empty array")
    for k in ("sample", "paths"):
        if k in m:
            yield _err(k, f"多数据集模型不得有顶层 {k}（写进 datasets[i]）",
                       f"a multi-dataset model must not have a top-level '{k}' (put it in datasets[i])")


def dataset_head_issues(m, i, d, seen, strict):
    """datasets[i]：是对象；sample/paths 存在（strict）/ 非空（normalize）；id 非空且不重复。seen 是已用 id 的集合（本函数更新它）。"""
    if not isinstance(d, dict):
        yield _err(f"datasets[{i}]", "应是对象 { sample, paths, … }" if strict else f"datasets[{i}] 不是对象",
                   f"datasets[{i}] is not an object")
        return
    if strict:
        did = d.get("id", d.get("sample"))
        where = f"datasets[{i}]({did})"
        for k in ("sample", "paths"):
            if k not in d:
                yield _err(where, f"缺少字段 {k}", f"missing field {k}")
        if "id" in d and (not isinstance(d["id"], str) or not d["id"].strip()):
            yield _err(f"{where} id", "不能为空", "must not be empty")
        elif did is not None:
            if did in seen:
                yield _err(f"{where} id", f"id {did} 重复（缺省 id = sample）", f"duplicate id {did} (default id = sample)")
            seen.add(did)
        return
    for k in ("sample", "paths"):
        if not d.get(k):
            yield _err(f"datasets[{i}].{k}", f"datasets[{i}].{k} 缺失或为空", f"datasets[{i}].{k} is missing or empty")
    did = d.get("id", d.get("sample"))
    if not isinstance(did, str) or not did:
        yield _err(f"datasets[{i}].id", f"datasets[{i}].id 为空", f"datasets[{i}].id is empty")
    elif did in seen:
        yield _err(f"datasets[{i}].id", f"datasets[{i}].id 重复：{did}", f"duplicate datasets[{i}].id: {did}")
    else:
        seen.add(did)


def dataset_range_issues(m, i, d, strict):
    """datasets[i] 的范围键（kmin kmax rmin rmax kweight）数据集与顶层都没有。"""
    if strict:
        miss = [k for k in RANGE_KEYS if k not in d and k not in m]
        if miss:
            did = d.get("id", d.get("sample"))
            yield _err(f"datasets[{i}]({did})", f"缺少 {', '.join(miss)}（数据集与顶层都没有）",
                       f"missing {', '.join(miss)} (neither in the dataset nor at top level)")
        return
    miss = [k for k in RANGE_KEYS if (d[k] if k in d else m.get(k)) is None]
    if miss:
        j = "/".join(miss)
        yield _err(f"datasets[{i}].{j}", f"datasets[{i}].{j} 缺失（数据集与顶层都没有）",
                   f"datasets[{i}].{j} missing (neither in the dataset nor at top level)")


def _iter(m, strict):
    if not isinstance(m, dict):
        return
    if "datasets" not in m:
        yield from legacy_issues(m, strict)
        yield from legacy_params_issues(m, strict)
        return
    yield from top_issues(m, strict)
    if not has_datasets(m):
        return
    seen = set()
    for i, d in enumerate(m["datasets"]):
        yield from dataset_head_issues(m, i, d, seen, strict)
        if isinstance(d, dict):
            yield from dataset_range_issues(m, i, d, strict)


def structure_issues(m, strict=True) -> list:
    """模型 JSON（未规范化）→ [(级别, 位置, 中文, English)]，只含结构性检查；输出顺序即各规则的检查顺序。"""
    return list(_iter(m, strict))


def raise_on_errors(m, strict=False):
    """normalize_model 用：第一条 error → ValueError("中文 / English")。惰性求值：与逐条检查时一样，在第一个错误处停下。"""
    for level, _where, zh, en in _iter(m, strict):
        if level == "error":
            raise ValueError(f"{zh} / {en}")
