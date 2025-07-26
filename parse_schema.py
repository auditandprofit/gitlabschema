import sys
from typing import Dict, List, Any, Set

try:
    import orjson as _orjson  # type: ignore
    _json = _orjson
    _HAS_ORJSON = True
except ImportError:  # fallback to builtin json
    import json as _json
    _HAS_ORJSON = False

# simple script to output a nesting of types -> [{field, type}] recursively
# usage: python parse_schema.py [schema.json]

def load_schema(path: str) -> Dict[str, Any]:
    mode = 'rb' if _HAS_ORJSON else 'r'
    with open(path, mode) as f:
        if _HAS_ORJSON:
            data = _json.loads(f.read())
        else:
            data = _json.load(f)
    schema = data.get("data", {}).get("__schema", {})
    types = schema.get("types", [])
    return {t["name"]: t for t in types if "name" in t}


def get_base_type(t: Dict[str, Any]) -> str:
    """Recursively unwrap LIST and NON_NULL wrappers to get base type name."""
    kind = t.get("kind")
    name = t.get("name")
    of_type = t.get("ofType")
    if kind in ("NON_NULL", "LIST") and of_type:
        return get_base_type(of_type)
    return name


def build_fields(type_name: str, type_map: Dict[str, Any], seen: Set[str]) -> List[Dict[str, Any]]:
    if type_name in seen:
        return []  # avoid cycles
    seen.add(type_name)
    t = type_map.get(type_name)
    fields = []
    if t and t.get("fields"):
        for f in t["fields"]:
            base = get_base_type(f["type"])
            entry = {"field": f["name"], "type": base}
            if base not in seen and type_map.get(base, {}).get("fields"):
                entry["fields"] = build_fields(base, type_map, seen)
            fields.append(entry)
    seen.remove(type_name)
    return fields


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "schema.json"
    type_map = load_schema(path)
    result = {}
    for name, t in type_map.items():
        if t.get("fields"):
            result[name] = build_fields(name, type_map, set())
    if _HAS_ORJSON:
        sys.stdout.buffer.write(_json.dumps(result, option=_orjson.OPT_INDENT_2))
    else:
        _json.dump(result, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
