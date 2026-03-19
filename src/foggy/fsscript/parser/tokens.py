"""Token types and Token class for FSScript lexer."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class TokenType(Enum):
    """Token types for FSScript lexer."""

    # End of file
    EOF = auto()

    # Literals
    NUMBER = auto()      # 42, 3.14, 0xFF, 1e10
    STRING = auto()      # 'hello', "world"
    TEMPLATE_STRING = auto()  # `template ${expr}`
    LONG = auto()        # 123L

    # Keywords
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    THIS = auto()

    # Declarations
    VAR = auto()
    LET = auto()
    CONST = auto()
    FUNCTION = auto()

    # Control flow
    IF = auto()
    ELSE = auto()
    FOR = auto()
    WHILE = auto()
    SWITCH = auto()
    CASE = auto()
    DEFAULT = auto()
    DEFAULT_COLON = auto()  # default: in switch

    # Jump statements
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    THROW = auto()

    # Exception handling
    TRY = auto()
    CATCH = auto()
    FINALLY = auto()

    # Modules
    IMPORT = auto()
    CIMPORT = auto()     # Class import
    EXPORT = auto()
    FROM = auto()
    AS = auto()

    # Operators - Arithmetic
    PLUS = auto()        # +
    MINUS = auto()       # -
    MULTIPLY = auto()    # *
    DIVIDE = auto()      # /
    MODULO = auto()      # %

    # Operators - Comparison
    EQ = auto()          # =
    EQ2 = auto()         # ==
    NE = auto()          # != or <>
    LT = auto()          # <
    LE = auto()          # <=
    GT = auto()          # >
    GE = auto()          # >=

    # Operators - Logical
    AND = auto()         # and keyword
    OR = auto()          # or keyword
    AND_AND = auto()     # &&
    OR_OR = auto()       # ||
    NOT = auto()         # not keyword
    XOR = auto()         # ^

    # Operators - Special
    ARROW = auto()       # =>
    NULL_COALESCE = auto()  # ??

    # Operators - Unary
    BANG = auto()        # !
    NEW = auto()
    DELETE = auto()
    LIKE = auto()

    # Operators - Update
    INCREMENT = auto()   # ++
    DECREMENT = auto()   # --

    # Delimiters
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    LBRACE = auto()      # {
    LBRACE_OBJ = auto()  # { (object literal context)
    LBRACE_DESTR = auto()  # { (destructuring context)
    RBRACE = auto()      # }
    LSBRACE = auto()     # [
    RSBRACE = auto()     # ]
    COMMA = auto()       # ,
    COLON = auto()       # :
    SEMICOLON = auto()   # ;

    # Special tokens
    DOT = auto()         # .
    DOT_DOT_DOT = auto()  # ...
    QMARK = auto()       # ?
    QMARK_DOT = auto()   # ?.
    AT = auto()          # @ (Spring Bean)
    HASH = auto()        # # (request property)
    DOLLAR = auto()      # $ (variable)
    DOLLAR_LBRACE = auto()  # ${
    SQM = auto()         # Single quote mark context
    BACKQUOTE = auto()   # `

    # Keywords - Other
    IN = auto()
    OF = auto()
    REQUEST = auto()

    # Identifier
    IDENTIFIER = auto()

    # Special
    CONCAT = auto()      # String concatenation marker
    ERROR = auto()


# Keywords mapping (lowercase -> TokenType)
KEYWORDS: dict[str, TokenType] = {
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
    "this": TokenType.THIS,
    "var": TokenType.VAR,
    "let": TokenType.LET,
    "const": TokenType.CONST,
    "function": TokenType.FUNCTION,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "for": TokenType.FOR,
    "while": TokenType.WHILE,
    "switch": TokenType.SWITCH,
    "case": TokenType.CASE,
    "default": TokenType.DEFAULT,
    "return": TokenType.RETURN,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "throw": TokenType.THROW,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "finally": TokenType.FINALLY,
    "import": TokenType.IMPORT,
    "export": TokenType.EXPORT,
    "from": TokenType.FROM,
    "as": TokenType.AS,
    "in": TokenType.IN,
    "of": TokenType.OF,
    "new": TokenType.NEW,
    "delete": TokenType.DELETE,
    "like": TokenType.LIKE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "request": TokenType.REQUEST,
}


@dataclass
class Token:
    """Represents a lexical token with source location."""

    type: TokenType
    value: Any
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def __post_init__(self):
        if self.end_line is None:
            self.end_line = self.line
        if self.end_column is None:
            self.end_column = self.column + len(str(self.value)) if self.value is not None else self.column + 1

    def __repr__(self) -> str:
        if self.value is not None and self.type not in (TokenType.EOF, TokenType.SEMICOLON):
            return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"
        return f"Token({self.type.name}, {self.line}:{self.column})"

    @property
    def location(self) -> str:
        """Return location string for error messages."""
        return f"line {self.line}, column {self.column}"


@dataclass
class SourceLocation:
    """Source location for error reporting."""

    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    source: Optional[str] = None  # Source file name or identifier

    def __str__(self) -> str:
        if self.source:
            return f"{self.source}:{self.line}:{self.column}"
        return f"line {self.line}, column {self.column}"


__all__ = [
    "TokenType",
    "Token",
    "SourceLocation",
    "KEYWORDS",
]