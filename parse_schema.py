import argparse
import sys
import tempfile
import os
from typing import Dict, List, Any, Set, Optional, Tuple

from PIL import Image, ImageTk
from tkinter import Tk, Canvas, BOTH, Button
from graphviz import Digraph

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
    """Return simplified mapping of type -> [{field, type}] for domain types."""

    def is_domain_type(name: str) -> bool:
        """Return True if ``name`` refers to a GitLab-defined domain type."""
        if name.startswith("__"):
            return False
        if name.endswith("Connection") or name.endswith("Edge") or name.endswith("Payload"):
            return False
        return True

    result: Dict[str, List[Dict[str, str]]] = {}
    for name, t in type_map.items():
        if not is_domain_type(name):
            continue
        if t.get("kind") not in ("OBJECT", "INTERFACE"):
            continue

        fields = t.get("fields")
        if not fields:
            continue

        entries = []
        for f in fields:
            base = get_base_type(f.get("type", {}))
            entries.append({"field": f.get("name", ""), "type": base})

        result[name] = entries

    return result


def build_edge_node_map(type_map: Dict[str, Any]) -> Dict[str, str]:
    """Return mapping of Edge type name -> underlying node type name."""
    edge_map: Dict[str, str] = {}
    for name, t in type_map.items():
        if not name.endswith("Edge"):
            continue
        fields = t.get("fields")
        if not fields:
            continue
        for f in fields:
            if f.get("name") == "node":
                edge_map[name] = get_base_type(f.get("type", {}))
                break
    return edge_map


def build_nested_fields(
    type_name: str,
    type_map: Dict[str, Any],
    edge_map: Dict[str, str],
    seen: Set[str],
    *,
    depth: int = 0,
    max_depth: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Recursively build nested fields following edges, avoiding cycles."""
    if max_depth is not None and depth >= max_depth:
        return []
    if type_name in seen:
        return []
    seen.add(type_name)

    t = type_map.get(type_name)
    fields = []
    if t and t.get("fields"):
        for f in t["fields"]:
            base = get_base_type(f.get("type", {}))
            target = edge_map.get(base, base)
            entry: Dict[str, Any] = {"field": f.get("name", ""), "type": target}
            if (
                target not in seen
                and type_map.get(target, {}).get("fields")
            ):
                entry["fields"] = build_nested_fields(
                    target,
                    type_map,
                    edge_map,
                    seen,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            fields.append(entry)

    seen.remove(type_name)
    return fields


def extract_nested(
    type_map: Dict[str, Any], *, max_depth: Optional[int] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Return recursive mapping of domain types following edges."""

    def is_domain_type(name: str) -> bool:
        if name.startswith("__"):
            return False
        if name.endswith("Connection") or name.endswith("Edge") or name.endswith("Payload"):
            return False
        return True

    edge_map = build_edge_node_map(type_map)
    result: Dict[str, List[Dict[str, Any]]] = {}
    for name, t in type_map.items():
        if not is_domain_type(name):
            continue
        if t.get("kind") not in ("OBJECT", "INTERFACE"):
            continue
        result[name] = build_nested_fields(
            name, type_map, edge_map, set(), depth=0, max_depth=max_depth
        )

    return result


def calculate_stats(nested: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
    """Return statistics about the nested mapping."""

    unique_paths: Set[Tuple[str, ...]] = set()
    unique_types: Set[str] = set()

    def walk(current_type: str, fields: List[Dict[str, Any]], path: Tuple[str, ...]):
        unique_types.add(current_type)
        for entry in fields:
            field_name = entry.get("field", "")
            target = entry.get("type", "")
            new_path = path + (field_name,)
            unique_paths.add(new_path)
            unique_types.add(target)
            if entry.get("fields"):
                walk(target, entry["fields"], new_path)

    for root, root_fields in nested.items():
        walk(root, root_fields, (root,))

    return {"unique_paths": len(unique_paths), "unique_types": len(unique_types)}


def _build_graph(nested: Dict[str, List[Dict[str, Any]]]) -> Digraph:
    """Return Graphviz digraph for ``nested`` mapping."""
    dot = Digraph()
    dot.attr(rankdir="LR")
    seen_nodes: Set[str] = set()

    def walk(source: str, fields: List[Dict[str, Any]]):
        if source not in seen_nodes:
            dot.node(source)
            seen_nodes.add(source)
        for entry in fields:
            target = entry.get("type", "")
            label = entry.get("field", "")
            if target not in seen_nodes:
                dot.node(target)
                seen_nodes.add(target)
            dot.edge(source, target, label=label)
            if entry.get("fields"):
                walk(target, entry["fields"])

    for root, root_fields in nested.items():
        walk(root, root_fields)

    return dot


def _show_image(path: str) -> None:
    """Display PNG ``path`` in a simple Tkinter viewer with zoom controls."""

    original = Image.open(path)

    root = Tk()
    root.title("Schema Graph")

    canvas = Canvas(root, highlightthickness=0)
    canvas.pack(fill=BOTH, expand=True)

    zoom = 1.0

    def redraw() -> None:
        nonlocal zoom
        width = int(original.width * zoom)
        height = int(original.height * zoom)
        resized = original.resize((width, height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        canvas.delete("all")
        canvas.config(scrollregion=(0, 0, width, height), width=width, height=height)
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas.image = photo  # keep reference

    def zoom_in(event=None) -> None:  # type: ignore[override]
        nonlocal zoom
        zoom *= 1.2
        redraw()

    def zoom_out(event=None) -> None:  # type: ignore[override]
        nonlocal zoom
        zoom /= 1.2
        redraw()

    Button(root, text="Zoom In", command=zoom_in).pack(side="left")
    Button(root, text="Zoom Out", command=zoom_out).pack(side="left")

    root.bind("+", zoom_in)
    root.bind("-", zoom_out)

    redraw()
    root.mainloop()


def visualize(nested: Dict[str, List[Dict[str, Any]]]) -> None:
    """Render ``nested`` mapping and open GUI viewer."""
    dot = _build_graph(nested)
    with tempfile.TemporaryDirectory() as tmp:
        outfile = os.path.join(tmp, "graph")
        dot.render(outfile, format="png", cleanup=True)
        _show_image(outfile + ".png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse GraphQL schema")
    parser.add_argument("schema", nargs="?", default="schema.json")
    parser.add_argument(
        "--depth",
        type=int,
        default=3,
        help="limit recursion depth when building nested fields",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="print statistics about unique paths and types",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="visualize nested fields in an interactive graph",
    )
    args = parser.parse_args()

    type_map = load_schema(args.schema)
    result = extract_nested(type_map, max_depth=args.depth)
    if args.gui:
        visualize(result)
        return
    elif args.stats:
        output = calculate_stats(result)
    else:
        output = result

    if _HAS_ORJSON:
        sys.stdout.buffer.write(_json.dumps(output, option=_orjson.OPT_INDENT_2))
    else:
        _json.dump(output, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
