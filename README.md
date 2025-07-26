# GitLab Schema

This repository contains a GraphQL schema introspection JSON (`schema.json`).

## parse_schema.py

`parse_schema.py` reads the introspection file and prints a nested mapping of
each domain type to its fields. Edge types are resolved to their underlying
`node` type and the tree is followed recursively. Cycles are avoided by
tracking visited types along the current path. The resulting JSON is of the
form `{type: [{field, type, fields?}]}`.

Recursion depth can be expensive on large schemas. The parser therefore
defaults to following fields only three levels deep. Use the `--depth` option to
increase or decrease this limit. Passing `--stats` will print a summary instead
of the full nested mapping.

Usage:

```bash
python3 parse_schema.py [--depth N] [--stats] [--gui] [schema.json]
```

Without an argument it defaults to `schema.json` in the repository root and a
maximum depth of three. Passing `--gui` opens an interactive graph viewer that
lets you zoom the schema diagram left-to-right.
