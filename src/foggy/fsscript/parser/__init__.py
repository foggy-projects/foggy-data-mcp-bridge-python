"""FSScript Parser Module.

Provides lexical analysis and parsing for FSScript expressions.
"""

from foggy.fsscript.parser.tokens import TokenType, Token, SourceLocation, KEYWORDS
from foggy.fsscript.parser.lexer import FsscriptLexer, LexerConfig, LexerState
from foggy.fsscript.parser.parser import FsscriptParser, PRECEDENCE
from foggy.fsscript.parser.dialect import (
    FsscriptDialect,
    DEFAULT_DIALECT,
    SQL_EXPRESSION_DIALECT,
    COMPOSE_QUERY_DIALECT,
)
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
    # Dialect
    "FsscriptDialect",
    "DEFAULT_DIALECT",
    "SQL_EXPRESSION_DIALECT",
    "COMPOSE_QUERY_DIALECT",
    # Errors
    "FsscriptError",
    "LexerError",
    "ParseError",
    "UnexpectedTokenError",
    "UnexpectedEndOfInputError",
    "InvalidSyntaxError",
    "UnsupportedFeatureError",
]
