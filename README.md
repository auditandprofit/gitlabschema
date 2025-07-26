# GitLab Schema

This repository contains a GraphQL schema introspection JSON (`schema.json`).

## parse_schema.py

`parse_schema.py` reads the introspection file and prints a nested mapping of
each domain type to its fields. Edge types are resolved to their underlying
`node` type and the tree is followed recursively. Cycles are avoided by
tracking visited types along the current path. The resulting JSON is of the
form `{type: [{field, type, fields?}]}`.

Usage:

```bash
python3 parse_schema.py [schema.json]
```

Without an argument it defaults to `schema.json` in the repository root.
