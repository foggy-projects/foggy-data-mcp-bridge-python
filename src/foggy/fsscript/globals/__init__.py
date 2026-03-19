"""Built-in globals package for FSScript."""

from foggy.fsscript.globals.array import ArrayGlobal
from foggy.fsscript.globals.console import ConsoleGlobal
from foggy.fsscript.globals.json_global import JsonGlobal

__all__ = [
    "ArrayGlobal",
    "ConsoleGlobal",
    "JsonGlobal",
]