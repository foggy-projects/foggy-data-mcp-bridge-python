"""FSScript Parser Module.

Provides lexical analysis and parsing for FSScript expressions.
"""

from foggy.fsscript.parser.tokens import TokenType, Token, SourceLocation, KEYWORDS
from foggy.fsscript.parser.lexer import FsscriptLexer, LexerConfig, LexerState
from foggy.fsscript.parser.parser import FsscriptParser, PRECEDENCE
from foggy.fsscript.parser.errors import (
    FsscriptError,
    LexerError,
    ParseError,
    UnexpectedTokenError,
    UnexpectedEndOfInputError,
    InvalidSyntaxError,
    UnsupportedFeatureError,
)

__all__ = [
    # Tokens
    "TokenType",
    "Token",
    "SourceLocation",
    "KEYWORDS",
    # Lexer
    "FsscriptLexer",
    "LexerConfig",
    "LexerState",
    # Parser
    "FsscriptParser",
    "PRECEDENCE",
    # Errors
    "FsscriptError",
    "LexerError",
    "ParseError",
    "UnexpectedTokenError",
    "UnexpectedEndOfInputError",
    "InvalidSyntaxError",
    "UnsupportedFeatureError",
]