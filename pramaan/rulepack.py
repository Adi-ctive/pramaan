"""Rule-pack loading, validation and a small safe json-logic evaluator (no eval)."""
import os
from datetime import date

import yaml

PACK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rulepacks")
KINDS = {"expiry", "entity_match", "expr", "count_vs_claim", "exif_geo", "plausibility", "max_validity"}


def load_file(name):
    with open(os.path.join(PACK_DIR, name), encoding="utf-8") as f:
        return f.read()


def parse(text):
    """Parse and validate YAML. Returns (pack, errors)."""
    try:
        p = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return None, [f"YAML error: {e}"]
    errs = []
    if not isinstance(p, dict):
        return None, ["Pack must be a mapping"]
    for k in ("key", "version", "taxonomy", "categories", "rules", "severity"):
        if k not in p:
            errs.append(f"Missing top-level key '{k}'")
    if errs:
        return None, errs
    sev = p["severity"]
    for t, spec in p["taxonomy"].items():
        for f, fs in (spec.get("fields") or {}).items():
            if "anchor" not in fs:
                errs.append(f"taxonomy.{t}.fields.{f}: missing anchor")
    for c, spec in p["categories"].items():
        for s in spec.get("required_slots", []):
            if s not in p["taxonomy"]:
                errs.append(f"categories.{c}: slot {s} not in taxonomy")
    ids = set()
    for r in p["rules"] + p.get("plausibility", []):
        if r.get("id") in ids:
            errs.append(f"Duplicate rule id {r.get('id')}")
        ids.add(r.get("id"))
        if r.get("kind") not in KINDS:
            errs.append(f"Rule {r.get('id')}: unknown kind {r.get('kind')}")
        if r.get("code") and r["code"] not in sev:
            errs.append(f"Rule {r.get('id')}: code {r['code']} has no severity")
    for code, s in sev.items():
        if s not in ("HIGH", "MEDIUM", "LOW", "INFO"):
            errs.append(f"severity.{code}: bad value {s}")
    return (None if errs else p), errs


def lookup(ctx, path):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _cmp_val(v):
    if isinstance(v, str) and len(v) == 10 and v[4] == "-":
        try:
            return date.fromisoformat(v)
        except ValueError:
            return v
    return v


class Missing(Exception):
    pass


def evaluate(expr, ctx):
    """Evaluate json-logic. Raises Missing if a var it needs is absent."""
    if not isinstance(expr, dict):
        return expr
    (op, args), = expr.items()
    if op == "var":
        v = lookup(ctx, args)
        if v is None:
            raise Missing(args)
        return v
    vals = [evaluate(a, ctx) for a in (args if isinstance(args, list) else [args])]
    if op in ("==", "!=", ">", ">=", "<", "<="):
        a, b = _cmp_val(vals[0]), _cmp_val(vals[1])
        try:
            return {"==": a == b, "!=": a != b, ">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[op]
        except TypeError:
            raise Missing(f"incomparable {a!r} {b!r}")
    if op == "and":
        return all(vals)
    if op == "or":
        return any(vals)
    if op == "!":
        return not vals[0]
    raise ValueError(f"Unsupported operator {op}")
