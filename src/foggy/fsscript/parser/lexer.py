"""FSScript Lexer - Tokenizes FSScript source code."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Generator, Optional

from foggy.fsscript.parser.tokens import KEYWORDS, SourceLocation, Token, TokenType
from foggy.fsscript.parser.errors import LexerError

if TYPE_CHECKING:
    # Type-only import to avoid circular dependency at runtime.
    # `dialect.py` itself only depends on `tokens.py`; this guard makes it
    # explicit that lexer.py never needs FsscriptDialect at runtime — it only
    # consumes the materialized keyword dict via `dialect.effective_keywords()`,
    # which the parser passes in.
    from foggy.fsscript.parser.dialect import FsscriptDialect


class LexerState(Enum):
    """State for number parsing."""
    LEFT_OF_POINT = auto()
    RIGHT_OF_POINT = auto()
    IN_EXPONENT = auto()


@dataclass
class LexerConfig:
    """Configuration for lexer behavior."""
    enable_asi: bool = True  # Automatic Semicolon Insertion
    track_comments: bool = False
    template_string_mode: bool = False


class FsscriptLexer:
    """
    FSScript lexical analyzer.

    Converts source code string into a stream of tokens.

    Features:
    - Number parsing (integers, floats, hex, scientific notation)
    - String parsing (single/double quotes)
    - Template string parsing with ${} interpolation
    - Operator recognition (multi-character operators)
    - Keyword recognition
    - ASI (Automatic Semicolon Insertion)
    - Comment handling (// and /* */)
    - Source location tracking
    """

    def __init__(
        self,
        source: str,
        config: Optional[LexerConfig] = None,
        dialect: Optional["FsscriptDialect"] = None,
    ):
        self.source = source
        self.config = config or LexerConfig()

        # Dialect: per-instance keyword override.
        # `None` keeps the historical fast path of pointing directly at the
        # module-level KEYWORDS constant (zero copy, no merge cost). A non-None
        # dialect materializes its merged dict once at __init__.
        if dialect is None:
            self._keywords: dict[str, TokenType] = KEYWORDS
        else:
            self._keywords = dialect.effective_keywords()

        # Position tracking
        self._pos = 0
        self._line = 1
        self._column = 1
        self._token_start_line = 1
        self._token_start_column = 1

        # Current character
        self._current_char: Optional[str] = None
        self._advance()

        # Previous token (for ASI)
        self._previous_token_type: Optional[TokenType] = None
        self._newline_encountered = False

        # Pending token (for ASI insertion)
        self._pending_token: Optional[Token] = None

        # Context tracking
        self._brace_depth = 0
        self._function_arg_list_depth = 0
        self._expect_function_id = False
        self._expect_function_lparen = False
        self._paren_stack: list[int] = []

    def _advance(self) -> Optional[str]:
        """Advance to the next character."""
        if self._pos >= len(self.source):
            self._current_char = None
            return None

        self._current_char = self.source[self._pos]
        self._pos += 1

        # Update line/column
        if self._current_char == '\n':
            self._line += 1
            self._column = 1
            self._newline_encountered = True
        else:
            self._column += 1

        return self._current_char

    def _peek(self, offset: int = 1) -> Optional[str]:
        """Peek at character without advancing."""
        pos = self._pos + offset - 1
        if pos >= len(self.source):
            return None
        return self.source[pos]

    def save_state(self) -> dict:
        """Save current lexer state for backtracking."""
        return {
            '_pos': self._pos,
            '_line': self._line,
            '_column': self._column,
            '_token_start_line': self._token_start_line,
            '_token_start_column': self._token_start_column,
            '_current_char': self._current_char,
            '_previous_token_type': self._previous_token_type,
            '_newline_encountered': self._newline_encountered,
            '_pending_token': self._pending_token,
            '_brace_depth': self._brace_depth,
            '_function_arg_list_depth': self._function_arg_list_depth,
            '_expect_function_id': self._expect_function_id,
            '_expect_function_lparen': self._expect_function_lparen,
            '_paren_stack': self._paren_stack.copy(),
        }

    def restore_state(self, state: dict) -> None:
        """Restore lexer state from saved state."""
        for key, value in state.items():
            setattr(self, key, value)

    def _skip_whitespace(self) -> None:
        """Skip whitespace characters (but track newlines)."""
        while self._current_char is not None and self._current_char in ' \t\r':
            self._advance()

    def _skip_line_comment(self) -> None:
        """Skip // comment until end of line."""
        while self._current_char is not None and self._current_char != '\n':
            self._advance()

    def _skip_block_comment(self) -> None:
        """Skip /* */ block comment."""
        self._advance()  # Skip *
        while self._current_char is not None:
            if self._current_char == '*' and self._peek() == '/':
                self._advance()
                self._advance()
                return
            self._advance()

    def _make_token(
        self,
        token_type: TokenType,
        value: Any = None
    ) -> Token:
        """Create a token with source location."""
        token = Token(
            type=token_type,
            value=value,
            line=self._token_start_line,
            column=self._token_start_column
        )
        self._token_start_line = self._line
        self._token_start_column = self._column
        return token

    def _read_string(self, quote: str) -> Token:
        """Read a string literal."""
        result = []
        start_line = self._token_start_line
        start_column = self._token_start_column

        while self._current_char is not None and self._current_char != quote:
            if self._current_char == '\\':
                self._advance()
                if self._current_char is None:
                    raise LexerError(
                        "Unterminated string escape",
                        line=self._line,
                        column=self._column
                    )
                # Handle escape sequences
                escape_map = {
                    'n': '\n', 'r': '\r', 't': '\t',
                    '\\': '\\', "'": "'", '"': '"',
                    '`': '`', '$': '$'
                }
                result.append(escape_map.get(self._current_char, self._current_char))
                self._advance()
            else:
                result.append(self._current_char)
                self._advance()

        if self._current_char is None:
            raise LexerError(
                f"Unterminated string starting at line {start_line}, column {start_column}",
                line=start_line,
                column=start_column
            )

        self._advance()  # Skip closing quote
        return self._make_token(TokenType.STRING, ''.join(result))

    def _read_template_string(self) -> Token:
        """Read a template string literal with potential interpolation."""
        parts = []
        start_line = self._token_start_line
        start_column = self._token_start_column

        while self._current_char is not None and self._current_char != '`':
            if self._current_char == '\\':
                self._advance()
                if self._current_char is None:
                    raise LexerError(
                        "Unterminated template string escape",
                        line=self._line,
                        column=self._column
                    )
                escape_map = {
                    'n': '\n', 'r': '\r', 't': '\t',
                    '\\': '\\', '`': '`', '$': '$'
                }
                parts.append(('str', escape_map.get(self._current_char, self._current_char)))
                self._advance()
            elif self._current_char == '$' and self._peek() == '{':
                # Start of interpolation - extract the expression
                self._advance()  # Skip $
                self._advance()  # Skip {

                # Read the expression until matching }
                brace_count = 1
                expr_chars = []

                while self._current_char is not None and brace_count > 0:
                    if self._current_char == '{':
                        brace_count += 1
                        expr_chars.append(self._current_char)
                    elif self._current_char == '}':
                        brace_count -= 1
                        if brace_count > 0:
                            expr_chars.append(self._current_char)
                    elif self._current_char == '\\' and self._peek() is not None:
                        # Handle escape sequences in expression
                        expr_chars.append(self._current_char)
                        self._advance()
                        if self._current_char is not None:
                            expr_chars.append(self._current_char)
                    else:
                        expr_chars.append(self._current_char)
                    self._advance()

                # Store the expression (excluding the final })
                expr_str = ''.join(expr_chars).strip()
                parts.append(('expr', expr_str))
            else:
                parts.append(('str', self._current_char))
                self._advance()

        if self._current_char is None:
            raise LexerError(
                f"Unterminated template string starting at line {start_line}, column {start_column}",
                line=start_line,
                column=start_column
            )

        self._advance()  # Skip closing backtick
        return self._make_token(TokenType.TEMPLATE_STRING, parts)

    def _read_number(self) -> Token:
        """Read a number literal (integer, float, hex, scientific notation)."""
        start_line = self._token_start_line
        start_column = self._token_start_column
        result = []
        has_dot = False
        has_exponent = False

        # Handle hex numbers
        if self._current_char == '0' and self._peek() in ('x', 'X'):
            result.append(self._current_char)
            self._advance()
            result.append(self._current_char)
            self._advance()

            while self._current_char is not None and self._current_char in '0123456789abcdefABCDEF':
                result.append(self._current_char)
                self._advance()

            value = int(''.join(result), 16)
            return self._make_token(TokenType.NUMBER, value)

        # Parse number with optional decimal and exponent
        while self._current_char is not None:
            if self._current_char.isdigit():
                result.append(self._current_char)
                self._advance()
            elif self._current_char == '.' and not has_dot and not has_exponent:
                if self._peek() and self._peek().isdigit():
                    has_dot = True
                    result.append(self._current_char)
                    self._advance()
                else:
                    # It's a method call like 5.toString()
                    break
            elif self._current_char in ('e', 'E') and not has_exponent:
                has_exponent = True
                result.append(self._current_char)
                self._advance()
                if self._current_char in ('+', '-'):
                    result.append(self._current_char)
                    self._advance()
            elif self._current_char == 'L':
                # Long literal (treat as int in Python)
                self._advance()
                value = int(''.join(result))
                return self._make_token(TokenType.LONG, value)
            else:
                break

        num_str = ''.join(result)
        if has_dot or has_exponent:
            value = float(num_str)
        else:
            value = int(num_str)

        return self._make_token(TokenType.NUMBER, value)

    def _read_identifier(self) -> Token:
        """Read an identifier or keyword."""
        result = []

        while self._current_char is not None and self._is_identifier_char(self._current_char):
            result.append(self._current_char)
            self._advance()

        name = ''.join(result)

        # Check if it's a keyword (per-dialect; falls back to KEYWORDS when
        # no dialect was supplied — see __init__).
        token_type = self._keywords.get(name.lower())
        if token_type:
            return self._make_token(token_type, name)

        return self._make_token(TokenType.IDENTIFIER, name)

    def _is_identifier_char(self, char: str) -> bool:
        """Check if character can be part of identifier."""
        return char.isalnum() or char == '_' or char == '$'

    def _read_operator(self) -> Token:
        """Read an operator token."""
        char = self._current_char

        # Multi-character operators
        two_char = char + (self._peek() or '')
        three_char = two_char + (self._peek(2) or '')

        # Check three-character operators first
        if three_char == '===':
            self._advance()
            self._advance()
            self._advance()
            return self._make_token(TokenType.EQ2, '===')
        if three_char == '!==':
            self._advance()
            self._advance()
            self._advance()
            return self._make_token(TokenType.NE, '!==')

        # Check two-character operators
        if two_char == '==':
            self._advance()
            self._advance()
            return self._make_token(TokenType.EQ2, '==')
        if two_char == '!=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.NE, '!=')
        if two_char == '<>':
            self._advance()
            self._advance()
            return self._make_token(TokenType.NE, '<>')
        if two_char == '<=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.LE, '<=')
        if two_char == '>=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.GE, '>=')
        if two_char == '&&':
            self._advance()
            self._advance()
            return self._make_token(TokenType.AND_AND, '&&')
        if two_char == '||':
            self._advance()
            self._advance()
            return self._make_token(TokenType.OR_OR, '||')
        if two_char == '??':
            self._advance()
            self._advance()
            return self._make_token(TokenType.NULL_COALESCE, '??')
        if two_char == '=>':
            self._advance()
            self._advance()
            return self._make_token(TokenType.ARROW, '=>')
        if two_char == '++':
            self._advance()
            self._advance()
            return self._make_token(TokenType.INCREMENT, '++')
        if two_char == '--':
            self._advance()
            self._advance()
            return self._make_token(TokenType.DECREMENT, '--')
        if two_char == '?.':
            self._advance()
            self._advance()
            return self._make_token(TokenType.QMARK_DOT, '?.')
        if two_char == '+=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.PLUS, '+=')  # Use PLUS with compound value
        if two_char == '-=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.MINUS, '-=')
        if two_char == '*=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.MULTIPLY, '*=')
        if two_char == '/=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.DIVIDE, '/=')
        if two_char == '%=':
            self._advance()
            self._advance()
            return self._make_token(TokenType.MODULO, '%=')

        # Three-character spread operator
        if three_char == '...':
            self._advance()
            self._advance()
            self._advance()
            return self._make_token(TokenType.DOT_DOT_DOT, '...')

        # Single character operators
        single_char_ops = {
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.MULTIPLY,
            '/': TokenType.DIVIDE,
            '%': TokenType.MODULO,
            '=': TokenType.EQ,
            '<': TokenType.LT,
            '>': TokenType.GT,
            '!': TokenType.BANG,
            '?': TokenType.QMARK,
            ':': TokenType.COLON,
            ',': TokenType.COMMA,
            ';': TokenType.SEMICOLON,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '[': TokenType.LSBRACE,
            ']': TokenType.RSBRACE,
            '.': TokenType.DOT,
            '@': TokenType.AT,
            '#': TokenType.HASH,
            '^': TokenType.XOR,
            '&': TokenType.AND,
            '|': TokenType.OR,
        }

        if char in single_char_ops:
            self._advance()
            return self._make_token(single_char_ops[char], char)

        # Unknown character
        raise LexerError(
            f"Unexpected character: {char}",
            line=self._line,
            column=self._column
        )

    def _can_end_statement(self, token_type: TokenType) -> bool:
        """Check if token can end a statement (for ASI)."""
        return token_type in (
            TokenType.IDENTIFIER,
            TokenType.NUMBER,
            TokenType.LONG,
            TokenType.STRING,
            TokenType.TEMPLATE_STRING,
            TokenType.RPAREN,
            TokenType.RSBRACE,
            TokenType.RBRACE,
            TokenType.TRUE,
            TokenType.FALSE,
            TokenType.NULL,
            TokenType.THIS,
            TokenType.BREAK,
            TokenType.CONTINUE,
        )

    def _can_continue_statement(self, token_type: TokenType) -> bool:
        """Check if token can continue a statement (for ASI)."""
        return token_type in (
            TokenType.DOT,
            TokenType.QMARK_DOT,
            TokenType.COMMA,
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.MULTIPLY,
            TokenType.DIVIDE,
            TokenType.MODULO,
            TokenType.EQ,
            TokenType.EQ2,
            TokenType.NE,
            TokenType.LT,
            TokenType.GT,
            TokenType.LE,
            TokenType.GE,
            TokenType.AND,
            TokenType.OR,
            TokenType.XOR,
            TokenType.AND_AND,
            TokenType.OR_OR,
            TokenType.QMARK,
            TokenType.COLON,
            TokenType.ARROW,
            TokenType.LPAREN,
            TokenType.IN,
            TokenType.LIKE,
            TokenType.IS,       # SQL: x IS NULL
            TokenType.BETWEEN,  # SQL: x BETWEEN a AND b
        )

    def _cannot_continue_statement(self, token_type: TokenType) -> bool:
        """Check if token cannot continue a statement (for ASI)."""
        return token_type in (
            TokenType.IDENTIFIER,
            TokenType.NUMBER,
            TokenType.LONG,
            TokenType.STRING,
            TokenType.TEMPLATE_STRING,
            TokenType.FUNCTION,
            TokenType.IF,
            TokenType.FOR,
            TokenType.WHILE,
            TokenType.SWITCH,
            TokenType.RETURN,
            TokenType.VAR,
            TokenType.LET,
            TokenType.CONST,
            TokenType.EXPORT,
            TokenType.IMPORT,
            TokenType.TRY,
            TokenType.THROW,
            TokenType.BREAK,
            TokenType.CONTINUE,
            TokenType.DELETE,
            TokenType.TRUE,
            TokenType.FALSE,
            TokenType.NULL,
            TokenType.THIS,
            TokenType.LBRACE,
            TokenType.LSBRACE,
            TokenType.AT,
            TokenType.HASH,
        )

    def _handle_lbrace(self) -> Token:
        """Handle left brace with context awareness."""
        self._advance()

        # Check if this is an object literal in function parameter default value
        if self._function_arg_list_depth > 0 and self._previous_token_type == TokenType.EQ:
            return self._make_token(TokenType.LBRACE_OBJ, '{')

        # Check if this is destructuring after const/let/var
        if self._previous_token_type in (TokenType.CONST, TokenType.LET, TokenType.VAR):
            return self._make_token(TokenType.LBRACE_DESTR, '{')

        self._brace_depth += 1
        return self._make_token(TokenType.LBRACE, '{')

    def _handle_rbrace(self) -> Token:
        """Handle right brace."""
        self._advance()
        if self._brace_depth > 0:
            self._brace_depth -= 1
        return self._make_token(TokenType.RBRACE, '}')

    def _next_token_raw(self) -> Token:
        """Get next token without ASI processing."""
        while self._current_char is not None:
            # Skip whitespace (but not newlines - they're tracked for ASI)
            if self._current_char in ' \t\r':
                self._skip_whitespace()
                continue

            # Skip comments
            if self._current_char == '/' and self._peek() == '/':
                self._skip_line_comment()
                continue
            if self._current_char == '/' and self._peek() == '*':
                self._skip_block_comment()
                continue

            # Newline (for ASI tracking)
            if self._current_char == '\n':
                self._newline_encountered = True
                self._advance()
                continue

            # String literals
            if self._current_char in ('"', "'"):
                quote = self._current_char
                self._advance()
                return self._read_string(quote)

            # Template string
            if self._current_char == '`':
                self._advance()
                return self._read_template_string()

            # Numbers
            if self._current_char.isdigit():
                return self._read_number()

            # Dot followed by number (e.g., .5)
            if self._current_char == '.' and self._peek() and self._peek().isdigit():
                return self._read_number()

            # Identifiers and keywords
            if self._current_char.isalpha() or self._current_char in '_$':
                token = self._read_identifier()
                # Update function context tracking
                self._update_function_context(token.type)
                return token

            # Left brace with context
            if self._current_char == '{':
                return self._handle_lbrace()

            # Right brace
            if self._current_char == '}':
                return self._handle_rbrace()

            # Operators and delimiters
            if self._current_char in '+-*/%=<>&|!?:;,()[]{}.@#^':
                return self._read_operator()

            # Unknown character
            raise LexerError(
                f"Unexpected character: {self._current_char}",
                line=self._line,
                column=self._column
            )

        return self._make_token(TokenType.EOF)

    def _update_function_context(self, token_type: TokenType) -> None:
        """Update function argument list context tracking."""
        if token_type == TokenType.FUNCTION:
            self._expect_function_id = True
            self._expect_function_lparen = False
        elif token_type == TokenType.IDENTIFIER and self._expect_function_id:
            self._expect_function_id = False
            self._expect_function_lparen = True
        elif token_type == TokenType.LPAREN and self._expect_function_lparen:
            self._expect_function_lparen = False
            self._function_arg_list_depth += 1
            self._paren_stack.append(1)
        elif self._function_arg_list_depth > 0:
            if token_type == TokenType.LPAREN:
                depth = self._paren_stack.pop()
                self._paren_stack.append(depth + 1)
            elif token_type == TokenType.RPAREN:
                depth = self._paren_stack.pop()
                if depth == 1:
                    self._function_arg_list_depth -= 1
                else:
                    self._paren_stack.append(depth - 1)
            self._expect_function_id = False
            self._expect_function_lparen = False
        else:
            self._expect_function_id = False
            self._expect_function_lparen = False

    def next_token(self) -> Token:
        """Get next token with ASI processing."""
        # Return pending token if any
        if self._pending_token is not None:
            token = self._pending_token
            self._pending_token = None
            return token

        previous_type = self._previous_token_type
        token = self._next_token_raw()

        # ASI processing
        if self.config.enable_asi and self._newline_encountered:
            self._newline_encountered = False

            # Don't insert ASI before { (e.g., function foo() { ... })
            # The { starts a block, not a new statement
            if token.type == TokenType.LBRACE:
                self._previous_token_type = token.type
                return token

            if (self._can_end_statement(previous_type) and
                not self._can_continue_statement(token.type) and
                token.type != TokenType.EOF and
                self._cannot_continue_statement(token.type)):
                # Insert semicolon
                self._pending_token = token
                self._previous_token_type = TokenType.SEMICOLON
                return self._make_token(TokenType.SEMICOLON, 'ASI;')

        self._previous_token_type = token.type
        return token

    def tokenize(self) -> Generator[Token, None, None]:
        """Generate all tokens from source."""
        while True:
            token = self.next_token()
            yield token
            if token.type == TokenType.EOF:
                break

    def get_all_tokens(self) -> list[Token]:
        """Get all tokens as a list."""
        return list(self.tokenize())


__all__ = [
    "FsscriptLexer",
    "LexerConfig",
    "LexerState",
]