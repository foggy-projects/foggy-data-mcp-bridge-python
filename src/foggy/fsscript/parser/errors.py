"""Error handling for FSScript parser."""

from typing import Optional

from foggy.fsscript.parser.tokens import SourceLocation


class FsscriptError(Exception):
    """Base error for FSScript parsing and evaluation."""

    def __init__(
        self,
        message: str,
        location: Optional[SourceLocation] = None,
        source_code: Optional[str] = None
    ):
        self.message = message
        self.location = location
        self.source_code = source_code
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.location:
            return f"{self.location}: {self.message}"
        return self.message

    def __str__(self) -> str:
        return self._format_message()


class LexerError(FsscriptError):
    """Error during lexical analysis."""

    def __init__(
        self,
        message: str,
        line: int = 1,
        column: int = 1,
        source_code: Optional[str] = None
    ):
        location = SourceLocation(line=line, column=column)
        super().__init__(message, location, source_code)


class ParseError(FsscriptError):
    """Error during parsing."""

    def __init__(
        self,
        message: str,
        location: Optional[SourceLocation] = None,
        source_code: Optional[str] = None
    ):
        super().__init__(message, location, source_code)


class UnexpectedTokenError(ParseError):
    """Unexpected token encountered during parsing."""

    def __init__(
        self,
        expected: str,
        actual: str,
        location: Optional[SourceLocation] = None,
        source_code: Optional[str] = None
    ):
        self.expected = expected
        self.actual = actual
        message = f"Expected {expected}, but got {actual}"
        super().__init__(message, location, source_code)


class UnexpectedEndOfInputError(ParseError):
    """Unexpected end of input during parsing."""

    def __init__(
        self,
        expected: str,
        location: Optional[SourceLocation] = None,
        source_code: Optional[str] = None
    ):
        self.expected = expected
        message = f"Unexpected end of input, expected {expected}"
        super().__init__(message, location, source_code)


class InvalidSyntaxError(ParseError):
    """Invalid syntax encountered."""

    def __init__(
        self,
        message: str,
        location: Optional[SourceLocation] = None,
        source_code: Optional[str] = None
    ):
        super().__init__(f"Invalid syntax: {message}", location, source_code)


class UnsupportedFeatureError(ParseError):
    """Unsupported language feature."""

    def __init__(
        self,
        feature: str,
        location: Optional[SourceLocation] = None,
        source_code: Optional[str] = None
    ):
        self.feature = feature
        message = f"Unsupported feature: {feature}"
        super().__init__(message, location, source_code)


__all__ = [
    "FsscriptError",
    "LexerError",
    "ParseError",
    "UnexpectedTokenError",
    "UnexpectedEndOfInputError",
    "InvalidSyntaxError",
    "UnsupportedFeatureError",
]