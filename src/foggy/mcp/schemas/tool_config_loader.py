"""Tool Config Loader — loads MCP tool definitions from shared schema files.

Mirrors Java's ToolConfigLoader: tool descriptions come from .md files,
input schemas from .json files. Both projects read from the same source
of truth to stay in sync.

Usage:
    loader = ToolConfigLoader()
    tools = loader.get_tools()           # All tool definitions
    tool = loader.get_tool("dataset.query_model")  # Single tool
"""

import json
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

# Directory containing schema files (same structure as Java resources/schemas/)
_SCHEMA_DIR = os.path.dirname(os.path.abspath(__file__))
_DESC_DIR = os.path.join(_SCHEMA_DIR, "descriptions")


class McpToolDef(BaseModel):
    """MCP Tool definition matching MCP protocol tools/list response."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


# Registry: tool name → (description file, schema file)
# Must match Java ToolConfigLoader.getBuiltinDefaults()
BUILTIN_TOOLS: Dict[str, Dict[str, str]] = {
    "dataset.get_metadata": {
        "description_file": "get_metadata.md",
        "schema_file": "get_metadata_schema.json",
    },
    "dataset.describe_model_internal": {
        "description_file": "describe_model_internal.md",
        "schema_file": "describe_model_internal_schema.json",
    },
    "dataset.query_model": {
        "description_file": "query_model_v3.md",
        "schema_file": "query_model_v3_schema.json",
    },
    # Tools below require external services — schema files not yet copied
    # "dataset_nl.query": { ... },
    # "dataset.compose_query": { ... },
    # "chart.generate": { ... },
    # "dataset.export_with_chart": { ... },
    # "dataset.inspect_table": { ... },
    # "semantic_layer.validate": { ... },
}


class ToolConfigLoader:
    """Loads MCP tool definitions from shared schema/description files.

    Mirrors Java's ToolConfigLoader for cross-project consistency.
    """

    def __init__(self, schema_dir: Optional[str] = None):
        self._schema_dir = schema_dir or _SCHEMA_DIR
        self._desc_dir = os.path.join(self._schema_dir, "descriptions")
        self._cache: Dict[str, McpToolDef] = {}

    def _load_description(self, filename: str) -> str:
        """Load tool description from a .md file."""
        path = os.path.join(self._desc_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        logger.warning(f"Description file not found: {path}")
        return ""

    def _load_schema(self, filename: str) -> Dict[str, Any]:
        """Load tool input schema from a .json file."""
        path = os.path.join(self._schema_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                schema = json.load(f)
                # Remove $schema key (not needed in MCP tool definition)
                schema.pop("$schema", None)
                return schema
        logger.warning(f"Schema file not found: {path}")
        return {"type": "object", "properties": {}}

    def get_tool(self, name: str) -> Optional[McpToolDef]:
        """Get a single tool definition by name."""
        if name in self._cache:
            return self._cache[name]

        config = BUILTIN_TOOLS.get(name)
        if not config:
            return None

        description = self._load_description(config["description_file"])
        schema = self._load_schema(config["schema_file"])

        tool = McpToolDef(
            name=name,
            description=description,
            inputSchema=schema,
        )
        self._cache[name] = tool
        return tool

    def get_tools(self, names: Optional[List[str]] = None) -> List[McpToolDef]:
        """Get tool definitions.

        Args:
            names: Specific tool names to load. If None, loads all builtin tools.

        Returns:
            List of McpToolDef
        """
        tool_names = names or list(BUILTIN_TOOLS.keys())
        tools = []
        for name in tool_names:
            tool = self.get_tool(name)
            if tool:
                tools.append(tool)
        return tools

    def get_tools_json(self, names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get tool definitions as JSON-serializable dicts (for MCP tools/list)."""
        return [t.model_dump() for t in self.get_tools(names)]

    def reload(self) -> None:
        """Clear cache and reload all tool definitions."""
        self._cache.clear()
        logger.info("Tool config cache cleared")


# Singleton instance
_loader: Optional[ToolConfigLoader] = None


def get_tool_config_loader() -> ToolConfigLoader:
    """Get the global ToolConfigLoader instance."""
    global _loader
    if _loader is None:
        _loader = ToolConfigLoader()
    return _loader
