# GitLab Schema

This repository contains a GraphQL schema introspection JSON (`schema.json`).

## parse_schema.py

`parse_schema.py` reads the introspection file and prints a simplified tree
representation in the form `type -> [{field, type}]` recursively. Repeated
references are truncated to avoid cycles.

Usage:

```bash
python3 parse_schema.py [schema.json]
```

Without an argument it defaults to `schema.json` in the repository root.
