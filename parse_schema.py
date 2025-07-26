import sys
from typing import Dict, List, Any

try:
    import orjson as _orjson  # type: ignore
    _json = _orjson
    _HAS_ORJSON = True
except ImportError:  # pragma: no cover - optional dependency
    import json as _json
    _HAS_ORJSON = False


def load_schema(path: str) -> Dict[str, Any]:
    """Load introspection schema and return a mapping of type name to type data."""
    mode = "rb" if _HAS_ORJSON else "r"
    with open(path, mode) as f:
        data = _json.loads(f.read()) if _HAS_ORJSON else _json.load(f)
    schema = data.get("data", {}).get("__schema", {})
    types = schema.get("types", [])
    return {t["name"]: t for t in types if "name" in t}


def get_base_type(t: Dict[str, Any]) -> str:
    """Recursively unwrap LIST/NON_NULL wrappers to get the underlying type name."""
    kind = t.get("kind")
    name = t.get("name")
    of_type = t.get("ofType")
    if kind in ("NON_NULL", "LIST") and of_type:
        return get_base_type(of_type)
    return name or ""


def extract_fields(type_map: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Return simplified mapping of type -> [{field, type}] (non-recursive)."""
    result: Dict[str, List[Dict[str, str]]] = {}
    for name, t in type_map.items():
        fields = t.get("fields")
        if not fields:
            continue
        entries = []
        for f in fields:
            base = get_base_type(f.get("type", {}))
            entries.append({"field": f.get("name", ""), "type": base})
        result[name] = entries
    return result


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "schema.json"
    type_map = load_schema(path)
    result = extract_fields(type_map)
    if _HAS_ORJSON:
        sys.stdout.buffer.write(_json.dumps(result, option=_orjson.OPT_INDENT_2))
    else:
        _json.dump(result, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
