# MCP Tool Description Sync Policy

This directory contains the Python runtime copy of MCP tool descriptions.

`query_model_v3*.md` is not independently owned here. The source of truth is the Java MCP resource directory:

`foggy-data-mcp-bridge/foggy-dataset-mcp/src/main/resources/schemas/descriptions/`

When changing `query_model_v3*.md`:

1. Update the Java canonical file first.
2. Update the Java `query_model_v3_CHANGELOG.md` entry explaining why the prompt changed, what problem it solves, and how it was validated.
3. Run `python scripts/sync_mcp_schemas.py --java-root ..\foggy-data-mcp-bridge` from `foggy-data-mcp-bridge-python`.
4. Keep this Python copy as a synced runtime artifact unless a Python-only exception is explicitly documented.

