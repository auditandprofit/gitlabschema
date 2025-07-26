# GitLab Schema

This repository contains a GraphQL schema introspection JSON (`schema.json`).

## parse_schema.py

`parse_schema.py` reads the introspection file and prints a simplified
mapping of each type to its immediate fields. Each field is represented by
its name and the base type name. The output is a JSON object of the form
`{type: [{field, type}]}` which is significantly smaller and faster to
generate than the previous recursive version.

Usage:

```bash
python3 parse_schema.py [schema.json]
```

Without an argument it defaults to `schema.json` in the repository root.
