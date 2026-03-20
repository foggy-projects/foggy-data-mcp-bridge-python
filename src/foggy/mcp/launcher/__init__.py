"""Launcher module for MCP server."""

from foggy.mcp.launcher.app import create_app, main

__all__ = [
    "create_app",
    "main",
]