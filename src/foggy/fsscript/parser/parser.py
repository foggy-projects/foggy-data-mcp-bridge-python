"""FSScript Parser - Parses token stream into AST."""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from foggy.fsscript.parser.tokens import Token, TokenType
from foggy.fsscript.parser.lexer import FsscriptLexer
from foggy.fsscript.parser.errors import (
    ParseError,
    UnexpectedTokenError,
    UnexpectedEndOfInputError,
    InvalidSyntaxError,
)
from foggy.fsscript.expressions.base import Expression
from foggy.fsscript.expressions.literals import (
    LiteralExpression,
    NullExpression,
    BooleanExpression,
    NumberExpression,
    StringExpression,
    ArrayExpression,
    ObjectExpression,
)
from foggy.fsscript.expressions.operators import (
    BinaryOperator,
    UnaryOperator,
    BinaryExpression,
    UnaryExpression,
    TernaryExpression,
    UpdateOperator,
    UpdateExpression,
)
from foggy.fsscript.expressions.variables import (
    VariableExpression,
    MemberAccessExpression,
    IndexAccessExpression,
    AssignmentExpression,
    DestructuringExpression,
)
from foggy.fsscript.expressions.functions import (
    FunctionCallExpression,
    MethodCallExpression,
    FunctionDefinitionExpression,
)
from foggy.fsscript.expressions.control_flow import (
    BlockExpression,
    IfExpression,
    ForExpression,
    WhileExpression,
    BreakExpression,
    ContinueExpression,
    ReturnExpression,
    BreakException,
    ContinueException,
    ReturnException,
    ExportExpression,
    ImportExpression,
    SwitchExpression,
)


# Operator precedence (higher = tighter binding)
PRECEDENCE = {
    # Lowest precedence
    TokenType.SEMICOLON: 0,
    TokenType.COMMA: 1,

    # Assignment
    TokenType.EQ: 2,

    # Arrow (lambda)
    TokenType.ARROW: 3,

    # Ternary
    TokenType.QMARK: 4,

    # Null coalescing
    TokenType.NULL_COALESCE: 4.5,

    # Logical OR
    TokenType.OR_OR: 5,
    TokenType.OR: 5,

    # Logical AND
    TokenType.AND_AND: 6,
    TokenType.AND: 6,

    # Bitwise
    TokenType.OR: 7,  # Also used for bitwise OR
    TokenType.XOR: 8,
    TokenType.AND: 9,

    # Equality
    TokenType.EQ2: 10,
    TokenType.NE: 10,

    # Comparison
    TokenType.LT: 11,
    TokenType.GT: 11,
    TokenType.LE: 11,
    TokenType.GE: 11,
    TokenType.LIKE: 11,
    TokenType.IN: 11,
    TokenType.INSTANCEOF: 11,

    # Addition/Subtraction
    TokenType.PLUS: 12,
    TokenType.MINUS: 12,

    # Multiplication/Division/Modulo
    TokenType.MULTIPLY: 13,
    TokenType.DIVIDE: 13,
    TokenType.MODULO: 13,

    # Unary operators (handled separately)
    # Postfix
    TokenType.INCREMENT: 15,
    TokenType.DECREMENT: 15,

    # Call/Member access
    TokenType.LPAREN: 16,
    TokenType.LSBRACE: 16,
    TokenType.DOT: 16,
    TokenType.QMARK_DOT: 16,
}


class FsscriptParser:
    """
    FSScript parser using recursive descent and Pratt parsing.

    Parses a stream of tokens into an Abstract Syntax Tree (AST).

    Features:
    - Recursive descent for statements
    - Pratt parsing for expressions (operator precedence)
    - Source location tracking
    - Error recovery
    """

    def __init__(self, source: str):
        """Initialize parser with source code."""
        self.source = source
        self._lexer = FsscriptLexer(source)
        self._current_token: Optional[Token] = None
        self._previous_token: Optional[Token] = None
        self._advance()

    def _save_state(self) -> dict:
        """Save parser+lexer state for lookahead."""
        return {
            "current_token": self._current_token,
            "previous_token": self._previous_token,
            "lexer_pos": self._lexer._pos,
            "lexer_line": self._lexer._line,
            "lexer_column": self._lexer._column,
            "lexer_char": self._lexer._current_char,
            "lexer_prev_type": self._lexer._previous_token_type,
            "lexer_newline": self._lexer._newline_encountered,
            "lexer_pending": self._lexer._pending_token,
        }

    def _restore_state(self, state: dict) -> None:
        """Restore parser+lexer state after lookahead."""
        self._current_token = state["current_token"]
        self._previous_token = state["previous_token"]
        self._lexer._pos = state["lexer_pos"]
        self._lexer._line = state["lexer_line"]
        self._lexer._column = state["lexer_column"]
        self._lexer._current_char = state["lexer_char"]
        self._lexer._previous_token_type = state["lexer_prev_type"]
        self._lexer._newline_encountered = state["lexer_newline"]
        self._lexer._pending_token = state["lexer_pending"]

    def _advance(self) -> Token:
        """Advance to next token, return the consumed token."""
        consumed = self._current_token
        self._previous_token = self._current_token
        self._current_token = self._lexer.next_token()
        return consumed

    def _current(self) -> Token:
        """Get current token."""
        if self._current_token is None:
            raise UnexpectedEndOfInputError("expected token")
        return self._current_token

    def _previous(self) -> Optional[Token]:
        """Get previous token."""
        return self._previous_token

    def _check(self, *types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        if self._current_token is None:
            return False
        return self._current_token.type in types

    def _match(self, *types: TokenType) -> bool:
        """If current token matches, consume it and return True."""
        if self._check(*types):
            self._advance()
            return True
        return False

    def _expect(self, token_type: TokenType, message: str = None) -> Token:
        """Expect current token to be of given type, consume and return it."""
        if not self._check(token_type):
            current = self._current()
            msg = message or f"Expected {token_type.name}"
            raise UnexpectedTokenError(
                expected=token_type.name,
                actual=current.type.name,
            )
        return self._advance()

    def _is_at_end(self) -> bool:
        """Check if at end of input."""
        return self._check(TokenType.EOF)

    def _synchronize(self) -> None:
        """Synchronize after parse error (skip to next statement)."""
        while not self._is_at_end():
            if self._previous_token and self._previous_token.type == TokenType.SEMICOLON:
                return
            if self._check(
                TokenType.VAR, TokenType.LET, TokenType.CONST,
                TokenType.FUNCTION, TokenType.IF, TokenType.FOR,
                TokenType.WHILE, TokenType.RETURN, TokenType.EXPORT,
                TokenType.IMPORT
            ):
                return
            self._advance()

    # ==================== Statement Parsing ====================

    def parse_program(self) -> BlockExpression:
        """Parse a complete program."""
        statements = []
        while not self._is_at_end():
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)
        return BlockExpression(statements=statements)

    def parse_statement(self) -> Optional[Expression]:
        """Parse a single statement."""
        # Variable declaration
        if self._check(TokenType.VAR, TokenType.LET, TokenType.CONST):
            return self._parse_variable_declaration()

        # Function declaration
        if self._check(TokenType.FUNCTION):
            return self._parse_function_declaration()

        # If statement
        if self._check(TokenType.IF):
            return self._parse_if_statement()

        # For statement
        if self._check(TokenType.FOR):
            return self._parse_for_statement()

        # While statement
        if self._check(TokenType.WHILE):
            return self._parse_while_statement()

        # Switch statement
        if self._check(TokenType.SWITCH):
            return self._parse_switch_statement()

        # Return statement
        if self._check(TokenType.RETURN):
            return self._parse_return_statement()

        # Break statement
        if self._check(TokenType.BREAK):
            return self._parse_break_statement()

        # Continue statement
        if self._check(TokenType.CONTINUE):
            return self._parse_continue_statement()

        # Throw statement
        if self._check(TokenType.THROW):
            return self._parse_throw_statement()

        # Try statement
        if self._check(TokenType.TRY):
            return self._parse_try_statement()

        # Export statement
        if self._check(TokenType.EXPORT):
            return self._parse_export_statement()

        # Import statement
        if self._check(TokenType.IMPORT):
            return self._parse_import_statement()

        # Block - but need to distinguish from object literal
        if self._check(TokenType.LBRACE):
            # Look ahead to determine if this is a block or object literal
            # Object literal: { identifier: ... } or { string: ... } etc
            # Block: { statement ... }
            # Heuristic: if next token after { is an identifier followed by :, it's an object
            # Otherwise it's a block
            return self._parse_block_or_object()

        # Empty statement
        if self._check(TokenType.SEMICOLON):
            self._advance()
            return None

        # Expression statement
        return self.parse_expression()

    def _parse_variable_declaration(self) -> Expression:
        """Parse var/let/const declaration."""
        keyword = self._advance()  # var/let/const
        is_const = keyword.type == TokenType.CONST
        is_block_scoped = keyword.type in (TokenType.LET, TokenType.CONST)

        # Check for destructuring
        if self._check(TokenType.LBRACE_DESTR, TokenType.LBRACE):
            return self._parse_destructuring_declaration(keyword.type)

        # Regular variable declaration
        name_token = self._expect(TokenType.IDENTIFIER, "Expected variable name")
        name = name_token.value

        # Optional initializer
        init = None
        if self._match(TokenType.EQ):
            init = self.parse_expression()

        # Optional semicolon
        self._match(TokenType.SEMICOLON)

        return AssignmentExpression(
            target=VariableExpression(name=name),
            value=init or NullExpression(),
            is_declaration=True,
            is_block_scoped=is_block_scoped,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_destructuring_declaration(self, keyword_type: TokenType) -> Expression:
        """Parse destructuring declaration like const {a = 1, b} = obj.

        Mirrors Java's DestructurePatternExp / DestructureItemExp.
        """
        self._expect(TokenType.LBRACE_DESTR) if self._check(TokenType.LBRACE_DESTR) else self._expect(TokenType.LBRACE)
        is_block_scoped = keyword_type in (TokenType.LET, TokenType.CONST)

        properties = []
        while not self._check(TokenType.RBRACE):
            if self._check(TokenType.IDENTIFIER):
                prop_name = self._advance().value
                default_value = None

                if self._match(TokenType.EQ):
                    default_value = self.parse_expression()

                properties.append({
                    'name': prop_name,
                    'alias': None,
                    'default': default_value,
                })
            else:
                raise InvalidSyntaxError("Expected property name in destructuring pattern")

            if not self._match(TokenType.COMMA):
                break

        self._expect(TokenType.RBRACE)
        self._expect(TokenType.EQ)

        source = self.parse_expression()
        self._match(TokenType.SEMICOLON)

        return DestructuringExpression(
            properties=properties,
            source=source,
            is_declaration=True,
            is_block_scoped=is_block_scoped,
        )

    def _parse_function_declaration(self) -> FunctionDefinitionExpression:
        """Parse function declaration."""
        keyword = self._advance()  # function

        name = None
        if self._check(TokenType.IDENTIFIER):
            name = self._advance().value

        self._expect(TokenType.LPAREN)
        param_tuples = self._parse_parameter_list()
        self._expect(TokenType.RPAREN)

        # Extract parameter names (ignore defaults for now)
        parameters = [p[0] if isinstance(p, tuple) else p for p in param_tuples]

        # Parse body
        if self._check(TokenType.LBRACE):
            body = self._parse_block()
        else:
            # Single expression body
            body = self.parse_expression()

        self._match(TokenType.SEMICOLON)

        return FunctionDefinitionExpression(
            parameters=parameters,
            body=body,
            name=name,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_parameter_list(self) -> List[Tuple[str, Optional[Expression]]]:
        """Parse function parameter list with optional default values."""
        parameters = []

        while not self._check(TokenType.RPAREN):
            if self._check(TokenType.IDENTIFIER):
                param_name = self._advance().value
                default_value = None

                if self._match(TokenType.EQ):
                    default_value = self.parse_expression()

                parameters.append((param_name, default_value))
            elif self._check(TokenType.LBRACE_DESTR, TokenType.LBRACE):
                # Destructuring parameter
                self._advance()
                # Simplified: just skip the destructuring pattern
                while not self._check(TokenType.RBRACE):
                    self._advance()
                self._expect(TokenType.RBRACE)
                parameters.append(('__destr_param__', None))
            else:
                raise InvalidSyntaxError("Expected parameter name")

            if not self._match(TokenType.COMMA):
                break

        return parameters

    def _parse_if_statement(self) -> IfExpression:
        """Parse if statement."""
        keyword = self._advance()  # if

        self._expect(TokenType.LPAREN)
        condition = self.parse_expression()
        self._expect(TokenType.RPAREN)

        then_branch = self._parse_block_or_statement()
        else_branch = None

        if self._match(TokenType.ELSE):
            if self._check(TokenType.IF):
                else_branch = self._parse_if_statement()
            else:
                else_branch = self._parse_block_or_statement()

        return IfExpression(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_for_statement(self) -> ForExpression:
        """Parse for statement (C-style, for-in, for-of)."""
        keyword = self._advance()  # for

        self._expect(TokenType.LPAREN)

        # Check for for-in or for-of
        if self._check(TokenType.VAR, TokenType.LET, TokenType.CONST):
            var_keyword = self._advance()
            var_is_block_scoped = var_keyword.type in (TokenType.LET, TokenType.CONST)
            var_name = self._expect(TokenType.IDENTIFIER).value

            if self._match(TokenType.IN):
                # for-in loop (iterates over indices/keys)
                iterable = self.parse_expression()
                self._expect(TokenType.RPAREN)
                body = self._parse_block_or_statement()

                return ForExpression(
                    variable=var_name,
                    iterable=iterable,
                    body=body,
                    is_for_in=True,
                    line=keyword.line,
                    column=keyword.column,
                )

            elif self._match(TokenType.OF):
                # for-of loop (iterates over values)
                iterable = self.parse_expression()
                self._expect(TokenType.RPAREN)
                body = self._parse_block_or_statement()

                return ForExpression(
                    variable=var_name,
                    iterable=iterable,
                    body=body,
                    is_for_in=False,
                    line=keyword.line,
                    column=keyword.column,
                )

            else:
                # C-style for with var/let/const declaration
                init = AssignmentExpression(
                    target=VariableExpression(name=var_name),
                    value=self.parse_expression() if self._match(TokenType.EQ) else NullExpression(),
                    is_declaration=True,
                    is_block_scoped=var_is_block_scoped,
                )
                return self._parse_c_style_for_rest(init, keyword)

        else:
            # C-style for or no init
            init = None
            if not self._check(TokenType.SEMICOLON):
                init = self.parse_expression()
            return self._parse_c_style_for_rest(init, keyword)

    def _parse_c_style_for_rest(self, init: Optional[Expression], keyword: Token) -> ForExpression:
        """Parse the rest of C-style for loop after init."""
        self._expect(TokenType.SEMICOLON)

        condition = None
        if not self._check(TokenType.SEMICOLON):
            condition = self.parse_expression()

        self._expect(TokenType.SEMICOLON)

        update = None
        if not self._check(TokenType.RPAREN):
            update = self.parse_expression()

        self._expect(TokenType.RPAREN)
        body = self._parse_block_or_statement()

        return ForExpression(
            init=init,
            condition=condition,
            update=update,
            body=body,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_while_statement(self) -> WhileExpression:
        """Parse while statement."""
        keyword = self._advance()  # while

        self._expect(TokenType.LPAREN)
        condition = self.parse_expression()
        self._expect(TokenType.RPAREN)

        body = self._parse_block_or_statement()

        return WhileExpression(
            condition=condition,
            body=body,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_switch_statement(self) -> Expression:
        """Parse switch statement."""
        keyword = self._advance()  # switch

        self._expect(TokenType.LPAREN)
        discriminant = self.parse_expression()
        self._expect(TokenType.RPAREN)

        self._expect(TokenType.LBRACE)

        cases = []
        default_body = None

        while not self._check(TokenType.RBRACE):
            if self._match(TokenType.CASE):
                test = self.parse_expression()
                self._expect(TokenType.COLON)
                body = []
                while not self._check(TokenType.CASE, TokenType.DEFAULT, TokenType.RBRACE):
                    stmt = self.parse_statement()
                    if stmt:
                        body.append(stmt)
                cases.append((test, BlockExpression(statements=body)))
            elif self._match(TokenType.DEFAULT):
                self._expect(TokenType.COLON)
                body = []
                while not self._check(TokenType.CASE, TokenType.DEFAULT, TokenType.RBRACE):
                    stmt = self.parse_statement()
                    if stmt:
                        body.append(stmt)
                default_body = BlockExpression(statements=body)

        self._expect(TokenType.RBRACE)

        return SwitchExpression(
            discriminant=discriminant,
            cases=cases,
            default_body=default_body,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_return_statement(self) -> ReturnExpression:
        """Parse return statement."""
        keyword = self._advance()  # return

        value = None
        if not self._check(TokenType.SEMICOLON, TokenType.RBRACE, TokenType.EOF):
            value = self.parse_expression()

        self._match(TokenType.SEMICOLON)

        return ReturnExpression(
            value=value,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_break_statement(self) -> BreakExpression:
        """Parse break statement."""
        keyword = self._advance()
        self._match(TokenType.SEMICOLON)
        return BreakExpression(line=keyword.line, column=keyword.column)

    def _parse_continue_statement(self) -> ContinueExpression:
        """Parse continue statement."""
        keyword = self._advance()
        self._match(TokenType.SEMICOLON)
        return ContinueExpression(line=keyword.line, column=keyword.column)

    def _parse_throw_statement(self) -> Expression:
        """Parse throw statement."""
        from foggy.fsscript.expressions.control_flow import ThrowExpression

        keyword = self._advance()
        value = self.parse_expression()
        self._match(TokenType.SEMICOLON)
        return ThrowExpression(
            value=value,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_try_statement(self) -> Expression:
        """Parse try-catch-finally statement."""
        from foggy.fsscript.expressions.control_flow import TryCatchExpression

        keyword = self._advance()  # try

        try_body = self._parse_block()

        catch_body = None
        catch_var = None
        if self._match(TokenType.CATCH):
            if self._match(TokenType.LPAREN):
                catch_var = self._expect(TokenType.IDENTIFIER).value
                self._expect(TokenType.RPAREN)
            catch_body = self._parse_block()

        finally_body = None
        if self._match(TokenType.FINALLY):
            finally_body = self._parse_block()

        return TryCatchExpression(
            try_body=try_body,
            catch_body=catch_body,
            catch_var=catch_var,
            finally_body=finally_body,
            line=keyword.line,
            column=keyword.column,
        )

    def _parse_export_statement(self) -> Expression:
        """Parse export statement."""
        keyword = self._advance()  # export

        # export default
        if self._match(TokenType.DEFAULT):
            value = self.parse_statement()
            return ExportExpression(
                value=value,
                is_default=True,
                line=keyword.line,
                column=keyword.column,
            )

        # export { ... }
        if self._check(TokenType.LBRACE):
            # Lookahead: is this export { name: value } (object) or export { name, name } (list)?
            saved_state = self._save_state()
            self._advance()  # consume {
            is_object_export = False
            if self._check(TokenType.IDENTIFIER):
                self._advance()  # consume first identifier
                if self._check(TokenType.COLON):
                    is_object_export = True
            self._restore_state(saved_state)  # rewind

            if is_object_export:
                # export { XX: 1231, BB: 22 } → treat as export default { ... }
                obj_expr = self._parse_object_literal()
                self._match(TokenType.SEMICOLON)
                return ExportExpression(
                    value=obj_expr,
                    is_default=True,
                    line=keyword.line,
                    column=keyword.column,
                )
            else:
                # export { name1, name2 }
                self._advance()  # consume {
                names = []
                while not self._check(TokenType.RBRACE):
                    name = self._expect(TokenType.IDENTIFIER).value
                    if self._match(TokenType.AS):
                        alias = self._expect(TokenType.IDENTIFIER).value
                        names.append(alias)
                    else:
                        names.append(name)
                    if not self._match(TokenType.COMMA):
                        break
                self._expect(TokenType.RBRACE)
                self._match(TokenType.SEMICOLON)
                return ExportExpression(
                    names=names,
                    line=keyword.line,
                    column=keyword.column,
                )

        # export var/function/class
        if self._check(TokenType.VAR, TokenType.LET, TokenType.CONST):
            # export var x = 1
            decl = self._parse_variable_declaration()
            # Extract name from the assignment
            if isinstance(decl, AssignmentExpression) and isinstance(decl.target, VariableExpression):
                return ExportExpression(
                    name=decl.target.name,
                    value=decl.value,
                    line=keyword.line,
                    column=keyword.column,
                )
            return decl

        if self._check(TokenType.FUNCTION):
            # export function name() { ... }
            func = self._parse_function_declaration()
            if func.name:
                return ExportExpression(
                    name=func.name,
                    value=func,
                    line=keyword.line,
                    column=keyword.column,
                )
            return func

        # export identifier (export an existing variable)
        if self._check(TokenType.IDENTIFIER):
            name = self._advance().value
            self._match(TokenType.SEMICOLON)
            return ExportExpression(
                name=name,
                line=keyword.line,
                column=keyword.column,
            )

        return NullExpression()

    def _parse_import_statement(self) -> Expression:
        """Parse import statement."""
        keyword = self._advance()  # import

        # import * as name from 'module'
        if self._match(TokenType.MULTIPLY):
            self._expect(TokenType.AS)
            name = self._expect(TokenType.IDENTIFIER).value
            self._expect(TokenType.FROM)
            module = self._expect(TokenType.STRING).value
            self._match(TokenType.SEMICOLON)
            return ImportExpression(
                module=module,
                namespace=name,
                line=keyword.line,
                column=keyword.column,
            )

        # import { a, b } from 'module'
        if self._check(TokenType.LBRACE):
            self._advance()
            imports = []
            while not self._check(TokenType.RBRACE):
                name = self._expect(TokenType.IDENTIFIER).value
                alias = None
                if self._match(TokenType.AS):
                    alias = self._expect(TokenType.IDENTIFIER).value
                imports.append((name, alias))
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RBRACE)
            self._expect(TokenType.FROM)
            module = self._expect(TokenType.STRING).value
            self._match(TokenType.SEMICOLON)
            return ImportExpression(
                module=module,
                names=imports,
                line=keyword.line,
                column=keyword.column,
            )

        # import defaultExport from 'module'
        if self._check(TokenType.IDENTIFIER):
            name = self._advance().value
            self._expect(TokenType.FROM)
            module = self._expect(TokenType.STRING).value
            self._match(TokenType.SEMICOLON)
            return ImportExpression(
                module=module,
                default_name=name,
                line=keyword.line,
                column=keyword.column,
            )

        return NullExpression()

    def _parse_block(self) -> BlockExpression:
        """Parse a block of statements."""
        start = self._expect(TokenType.LBRACE)

        statements = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)

        self._expect(TokenType.RBRACE)

        return BlockExpression(
            statements=statements,
            line=start.line,
            column=start.column,
        )

    def _parse_block_or_object(self) -> Expression:
        """Parse either a block or object literal, based on lookahead."""
        # Save state using lexer's save/restore
        saved_lexer_state = self._lexer.save_state()
        saved_token = self._current_token
        saved_prev_token = self._previous_token

        # Advance past the opening {
        self._advance()

        # Check if this looks like an object literal
        # Object literal patterns:
        # - Property: { key: value }
        # - Spread: { ...expr }
        # - Shorthand: { a, b }
        # Empty {} is ambiguous but in statement context we treat it as a block

        is_object = False

        if self._check(TokenType.RBRACE):
            # Empty {} - treat as block in statement context
            is_object = False
        elif self._check(TokenType.DOT_DOT_DOT):
            # Spread in object
            is_object = True
        elif self._check(TokenType.STRING):
            # String key - definitely object
            is_object = True
        elif self._check(TokenType.IDENTIFIER):
            # Check if followed by : (property) or , (shorthand) or } (shorthand)
            name_token = self._advance()
            next_token = self._current()

            if next_token and next_token.type == TokenType.COLON:
                # identifier: value - object property
                is_object = True
            elif next_token and next_token.type in (TokenType.COMMA, TokenType.RBRACE):
                # identifier, or identifier} - shorthand property
                is_object = True

        # Restore state
        self._lexer.restore_state(saved_lexer_state)
        self._current_token = saved_token
        self._previous_token = saved_prev_token

        if is_object:
            # Parse as object literal and then continue with postfix operators
            obj = self._parse_object_literal()
            # Continue parsing postfix operators (like .member, [index], etc.)
            return self._parse_postfix_loop(obj)
        else:
            return self._parse_block()

    def _parse_postfix_loop(self, left: Expression) -> Expression:
        """Continue parsing postfix operators after an expression."""
        while True:
            token = self._current()
            if token is None:
                break

            if token.type in (TokenType.LPAREN, TokenType.LSBRACE, TokenType.DOT,
                              TokenType.QMARK_DOT, TokenType.INCREMENT, TokenType.DECREMENT):
                left = self._parse_postfix(left)
            else:
                break

        return left

    def _parse_block_or_statement(self) -> Expression:
        """Parse a block or single statement."""
        if self._check(TokenType.LBRACE):
            return self._parse_block()
        return self.parse_statement()

    # ==================== Expression Parsing (Pratt) ====================

    def parse_expression(self) -> Expression:
        """Parse an expression using Pratt parsing."""
        return self._parse_expression_with_precedence(0)

    def _parse_expression_with_precedence(self, min_prec: int) -> Expression:
        """Parse expression with minimum precedence."""
        left = self._parse_prefix()

        while True:
            current = self._current()
            if current is None:
                break

            # Stop on tokens that are not expression operators
            if current.type in (TokenType.COMMA, TokenType.SEMICOLON, TokenType.RPAREN,
                                TokenType.RBRACE, TokenType.RSBRACE, TokenType.COLON,
                                TokenType.EOF):
                break

            prec = PRECEDENCE.get(current.type, -1)
            if prec <= min_prec:
                break

            if current.type == TokenType.QMARK:
                left = self._parse_ternary(left)
            elif current.type in (TokenType.INCREMENT, TokenType.DECREMENT):
                left = self._parse_postfix(left)
            elif current.type in (TokenType.LPAREN, TokenType.LSBRACE, TokenType.DOT, TokenType.QMARK_DOT):
                left = self._parse_postfix(left)
            else:
                left = self._parse_infix(left, prec)

        return left

    def _parse_prefix(self) -> Expression:
        """Parse prefix expression (unary operators, literals, etc.)."""
        token = self._current()

        if token is None:
            raise UnexpectedEndOfInputError("expected expression")

        # Literals
        if token.type == TokenType.NUMBER:
            return self._parse_number()
        if token.type == TokenType.LONG:
            return self._parse_long()
        if token.type == TokenType.STRING:
            return self._parse_string()
        if token.type == TokenType.TEMPLATE_STRING:
            return self._parse_template_string()
        if token.type == TokenType.TRUE:
            return self._parse_boolean(True)
        if token.type == TokenType.FALSE:
            return self._parse_boolean(False)
        if token.type == TokenType.NULL:
            return self._parse_null()

        # This
        if token.type == TokenType.THIS:
            return self._parse_this()

        # Identifier
        if token.type == TokenType.IDENTIFIER:
            return self._parse_identifier()

        # Parenthesized expression or arrow function
        if token.type == TokenType.LPAREN:
            return self._parse_paren_or_arrow()

        # Array literal
        if token.type == TokenType.LSBRACE:
            return self._parse_array_literal()

        # Object literal
        if token.type in (TokenType.LBRACE, TokenType.LBRACE_OBJ):
            return self._parse_object_literal()

        # Arrow function with single param: x => ...
        if token.type == TokenType.IDENTIFIER and self._peek().type == TokenType.ARROW:
            return self._parse_arrow_function_single_param()

        # Unary operators
        if token.type == TokenType.MINUS:
            return self._parse_unary(UnaryOperator.NEGATE)
        if token.type == TokenType.BANG:
            return self._parse_unary(UnaryOperator.NOT)
        if token.type == TokenType.NOT:
            return self._parse_unary(UnaryOperator.NOT)

        # Prefix increment/decrement
        if token.type == TokenType.INCREMENT:
            return self._parse_prefix_update('++')
        if token.type == TokenType.DECREMENT:
            return self._parse_prefix_update('--')

        # Delete
        if token.type == TokenType.DELETE:
            return self._parse_delete()

        # New
        if token.type == TokenType.NEW:
            return self._parse_new()

        # Typeof
        if token.type == TokenType.TYPEOF:
            return self._parse_typeof()

        # Spread (in array context)
        if token.type == TokenType.DOT_DOT_DOT:
            return self._parse_spread()

        # Function expression
        if token.type == TokenType.FUNCTION:
            return self._parse_function_declaration()

        raise InvalidSyntaxError(f"Unexpected token: {token.type.name}")

    def _peek(self) -> Token:
        """Peek at next token without consuming."""
        # This is a simplified peek - in production we'd use lexer lookahead
        # For now, we just check current token
        return self._current()

    def _parse_infix(self, left: Expression, prec: int) -> Expression:
        """Parse infix expression (binary operators)."""
        token = self._advance()

        # Assignment
        if token.type == TokenType.EQ:
            right = self.parse_expression()
            return AssignmentExpression(
                target=left,
                value=right,
                line=token.line,
                column=token.column,
            )

        # Binary operators
        op_map = {
            TokenType.PLUS: BinaryOperator.ADD,
            TokenType.MINUS: BinaryOperator.SUBTRACT,
            TokenType.MULTIPLY: BinaryOperator.MULTIPLY,
            TokenType.DIVIDE: BinaryOperator.DIVIDE,
            TokenType.MODULO: BinaryOperator.MODULO,
            TokenType.EQ2: BinaryOperator.EQUAL,
            TokenType.NE: BinaryOperator.NOT_EQUAL,
            TokenType.LT: BinaryOperator.LESS,
            TokenType.GT: BinaryOperator.GREATER,
            TokenType.LE: BinaryOperator.LESS_EQUAL,
            TokenType.GE: BinaryOperator.GREATER_EQUAL,
            TokenType.AND_AND: BinaryOperator.AND,
            TokenType.OR_OR: BinaryOperator.OR,
            TokenType.INSTANCEOF: BinaryOperator.INSTANCEOF,
        }

        if token.type in op_map:
            right = self._parse_expression_with_precedence(prec)
            return BinaryExpression(
                left=left,
                operator=op_map[token.type],
                right=right,
                line=token.line,
                column=token.column,
            )

        # Logical operators (keywords)
        if token.type == TokenType.AND:
            right = self._parse_expression_with_precedence(prec)
            return BinaryExpression(
                left=left,
                operator=BinaryOperator.AND,
                right=right,
                line=token.line,
                column=token.column,
            )

        if token.type == TokenType.OR:
            right = self._parse_expression_with_precedence(prec)
            return BinaryExpression(
                left=left,
                operator=BinaryOperator.OR,
                right=right,
                line=token.line,
                column=token.column,
            )

        # Null coalescing
        if token.type == TokenType.NULL_COALESCE:
            right = self._parse_expression_with_precedence(prec)
            return BinaryExpression(
                left=left,
                operator=BinaryOperator.NULL_COALESCE,
                right=right,
                line=token.line,
                column=token.column,
            )

        raise InvalidSyntaxError(f"Unknown infix operator: {token.type.name}")

    def _parse_postfix(self, left: Expression) -> Expression:
        """Parse postfix expression (call, member access, etc.)."""
        token = self._current()

        if token.type == TokenType.LPAREN:
            return self._parse_function_call(left)

        if token.type == TokenType.LSBRACE:
            return self._parse_index_access(left)

        if token.type == TokenType.DOT:
            return self._parse_member_access(left)

        if token.type == TokenType.QMARK_DOT:
            return self._parse_optional_member_access(left)

        if token.type == TokenType.INCREMENT:
            self._advance()
            # Postfix increment - returns old value, then increments
            return UpdateExpression(
                operator=UpdateOperator.INCREMENT,
                operand=left,
                prefix=False,
            )

        if token.type == TokenType.DECREMENT:
            self._advance()
            # Postfix decrement - returns old value, then decrements
            return UpdateExpression(
                operator=UpdateOperator.DECREMENT,
                operand=left,
                prefix=False,
            )

        return left

    def _parse_ternary(self, condition: Expression) -> TernaryExpression:
        """Parse ternary expression."""
        token = self._advance()  # consume ?

        then_expr = self.parse_expression()
        self._expect(TokenType.COLON)
        else_expr = self.parse_expression()

        return TernaryExpression(
            condition=condition,
            then_expr=then_expr,
            else_expr=else_expr,
            line=token.line,
            column=token.column,
        )

    # ==================== Literal Parsing ====================

    def _parse_number(self) -> NumberExpression:
        """Parse number literal."""
        token = self._advance()
        return NumberExpression(value=token.value, line=token.line, column=token.column)

    def _parse_long(self) -> NumberExpression:
        """Parse long literal (treated as int in Python)."""
        token = self._advance()
        return NumberExpression(value=token.value, line=token.line, column=token.column)

    def _parse_string(self) -> StringExpression:
        """Parse string literal."""
        token = self._advance()
        return StringExpression(value=token.value, line=token.line, column=token.column)

    def _parse_template_string(self) -> Expression:
        """Parse template string literal with interpolation."""
        from foggy.fsscript.expressions.literals import TemplateLiteralExpression

        token = self._advance()
        parts = token.value

        if not parts:
            return StringExpression(value='', line=token.line, column=token.column)

        # Check if it's a simple string (no interpolation)
        if all(p[0] == 'str' for p in parts):
            value = ''.join(p[1] for p in parts)
            return StringExpression(value=value, line=token.line, column=token.column)

        # Has interpolation - parse expressions
        result_parts = []
        for p in parts:
            if p[0] == 'str':
                result_parts.append(StringExpression(value=p[1]))
            elif p[0] == 'expr':
                # Parse the expression string
                expr_str = p[1]
                expr_parser = FsscriptParser(expr_str)
                try:
                    expr = expr_parser.parse_expression()
                    result_parts.append(expr)
                except Exception:
                    # If parsing fails, treat as string
                    result_parts.append(StringExpression(value=expr_str))

        return TemplateLiteralExpression(
            parts=result_parts,
            line=token.line,
            column=token.column,
        )

    def _parse_boolean(self, value: bool) -> BooleanExpression:
        """Parse boolean literal."""
        token = self._advance()
        return BooleanExpression(value=value, line=token.line, column=token.column)

    def _parse_null(self) -> NullExpression:
        """Parse null literal."""
        token = self._advance()
        return NullExpression(line=token.line, column=token.column)

    def _parse_this(self) -> VariableExpression:
        """Parse this keyword."""
        token = self._advance()
        return VariableExpression(name='this', line=token.line, column=token.column)

    def _parse_identifier(self) -> Expression:
        """Parse identifier or arrow function with single param."""
        token = self._advance()

        # Check if this is a single-param arrow function: x => expr
        if self._check(TokenType.ARROW):
            self._advance()  # consume =>
            return self._parse_arrow_function_body([token.value])

        return VariableExpression(name=token.value, line=token.line, column=token.column)

    def _parse_paren_or_arrow(self) -> Expression:
        """Parse parenthesized expression or arrow function parameters."""
        start = self._advance()  # consume (

        # Empty parens => arrow function
        if self._check(TokenType.RPAREN):
            self._advance()
            if self._check(TokenType.ARROW):
                self._advance()
                return self._parse_arrow_function_body([])
            # Empty parens without arrow - return null
            return NullExpression()

        # Check if this looks like arrow function params (identifiers only)
        # We need to peek to determine if it's arrow function or expression
        could_be_arrow_params = True
        params = []

        # Save state for potential backtrack
        saved_lexer_state = self._lexer.save_state()
        saved_token = self._current_token
        saved_prev_token = self._previous_token

        # Try to parse as parameter list
        while not self._check(TokenType.RPAREN, TokenType.EOF):
            if self._check(TokenType.IDENTIFIER):
                params.append(self._current_token.value)
                self._advance()
                if self._check(TokenType.COMMA):
                    self._advance()
                elif not self._check(TokenType.RPAREN):
                    could_be_arrow_params = False
                    break
            else:
                could_be_arrow_params = False
                break

        # If we got identifiers and now see ) followed by =>
        if could_be_arrow_params and self._check(TokenType.RPAREN):
            self._advance()
            if self._check(TokenType.ARROW):
                self._advance()
                return self._parse_arrow_function_body(params)
            else:
                # Just parenthesized identifier(s)
                if len(params) == 1:
                    return VariableExpression(name=params[0], line=start.line, column=start.column)

        # Backtrack and parse as expression
        self._lexer.restore_state(saved_lexer_state)
        self._current_token = saved_token
        self._previous_token = saved_prev_token

        # Parse inner expression
        inner = self.parse_expression()
        self._expect(TokenType.RPAREN)
        return inner

    def _parse_arrow_function_body(self, params: List[str]) -> FunctionDefinitionExpression:
        """Parse arrow function body."""
        if self._check(TokenType.LBRACE):
            body = self._parse_block()
        else:
            # Expression body
            body = self.parse_expression()

        return FunctionDefinitionExpression(
            parameters=params,  # params is already List[str]
            body=body,
        )

    def _parse_arrow_function_single_param(self) -> FunctionDefinitionExpression:
        """Parse arrow function with single parameter."""
        name_token = self._advance()
        self._expect(TokenType.ARROW)

        if self._check(TokenType.LBRACE):
            body = self._parse_block()
        else:
            body = self.parse_expression()

        return FunctionDefinitionExpression(
            parameters=[name_token.value],  # Just the string name
            body=body,
        )

    def _parse_array_literal(self) -> ArrayExpression:
        """Parse array literal."""
        from foggy.fsscript.expressions.literals import SpreadExpression

        start = self._advance()  # consume [

        elements = []
        while not self._check(TokenType.RSBRACE):
            # Spread operator
            if self._check(TokenType.DOT_DOT_DOT):
                self._advance()
                elem = self.parse_expression()
                elements.append(SpreadExpression(expression=elem))
            else:
                elements.append(self.parse_expression())

            if not self._match(TokenType.COMMA):
                break

        self._expect(TokenType.RSBRACE)

        return ArrayExpression(
            elements=elements,
            line=start.line,
            column=start.column,
        )

    def _parse_object_literal(self) -> ObjectExpression:
        """Parse object literal."""
        start = self._advance()  # consume {

        properties = {}
        while not self._check(TokenType.RBRACE):
            # Spread operator
            if self._check(TokenType.DOT_DOT_DOT):
                self._advance()
                # Simplified: skip spread in object
                self.parse_expression()
                if not self._match(TokenType.COMMA):
                    break
                continue

            # Property name
            if self._check(TokenType.IDENTIFIER):
                key = self._advance().value

                # Shorthand property: { a }
                if not self._check(TokenType.COLON):
                    properties[key] = VariableExpression(name=key)
                    if not self._match(TokenType.COMMA):
                        break
                    continue

                self._expect(TokenType.COLON)
                value = self.parse_expression()
                properties[key] = value
            elif self._check(TokenType.STRING):
                key = self._advance().value
                self._expect(TokenType.COLON)
                value = self.parse_expression()
                properties[key] = value
            else:
                raise InvalidSyntaxError("Expected property name")

            if not self._match(TokenType.COMMA):
                break

        self._expect(TokenType.RBRACE)

        return ObjectExpression(
            properties=properties,
            line=start.line,
            column=start.column,
        )

    # ==================== Operator Parsing ====================

    def _parse_unary(self, operator: UnaryOperator) -> UnaryExpression:
        """Parse unary expression."""
        token = self._advance()
        operand = self._parse_expression_with_precedence(PRECEDENCE.get(token.type, 14))
        return UnaryExpression(
            operator=operator,
            operand=operand,
            line=token.line,
            column=token.column,
        )

    def _parse_prefix_update(self, op: str) -> Expression:
        """Parse prefix ++/--."""
        token = self._advance()
        operand = self.parse_expression()
        return UpdateExpression(
            operator=UpdateOperator.INCREMENT if op == '++' else UpdateOperator.DECREMENT,
            operand=operand,
            prefix=True,
            line=token.line,
            column=token.column,
        )

    def _parse_delete(self) -> Expression:
        """Parse delete expression."""
        token = self._advance()
        target = self.parse_expression()
        # In Python, delete is typically just returning the target as None
        return NullExpression(line=token.line, column=token.column)

    def _parse_new(self) -> Expression:
        """Parse new expression."""
        token = self._advance()

        if self._check(TokenType.IDENTIFIER):
            class_name = self._advance().value
        else:
            class_name = 'Object'

        args = []
        if self._match(TokenType.LPAREN):
            args = self._parse_argument_list()
            self._expect(TokenType.RPAREN)

        # Simplified: create empty object
        return ObjectExpression(
            properties={},
            line=token.line,
            column=token.column,
        )

    def _parse_typeof(self) -> Expression:
        """Parse ``typeof expr`` — returns a UnaryExpression with TYPEOF."""
        token = self._advance()  # consume 'typeof'
        operand = self._parse_expression_with_precedence(14)  # just below unary
        return UnaryExpression(
            operator=UnaryOperator.TYPEOF,
            operand=operand,
            line=token.line,
            column=token.column,
        )

    def _parse_spread(self) -> Expression:
        """Parse spread expression."""
        token = self._advance()
        argument = self.parse_expression()
        # Simplified: just return the argument
        return argument

    def _parse_function_call(self, callee: Expression) -> FunctionCallExpression:
        """Parse function call."""
        token = self._advance()  # consume (

        arguments = self._parse_argument_list()
        self._expect(TokenType.RPAREN)

        return FunctionCallExpression(
            function=callee,
            arguments=arguments,
            line=token.line,
            column=token.column,
        )

    def _parse_argument_list(self) -> List[Expression]:
        """Parse function argument list."""
        args = []
        while not self._check(TokenType.RPAREN):
            args.append(self.parse_expression())
            if not self._match(TokenType.COMMA):
                break
        return args

    def _parse_index_access(self, obj: Expression) -> IndexAccessExpression:
        """Parse index access expression."""
        token = self._advance()  # consume [

        index = self.parse_expression()
        self._expect(TokenType.RSBRACE)

        return IndexAccessExpression(
            obj=obj,
            index=index,
            line=token.line,
            column=token.column,
        )

    def _parse_member_access(self, obj: Expression) -> MemberAccessExpression:
        """Parse member access expression."""
        token = self._advance()  # consume .

        # Allow keywords as property names (e.g., obj.default, obj.delete)
        member_token = self._expect_identifier_or_keyword()
        member = member_token.value

        return MemberAccessExpression(
            obj=obj,
            member=member,
            line=token.line,
            column=token.column,
        )

    def _parse_optional_member_access(self, obj: Expression) -> MemberAccessExpression:
        """Parse optional member access expression (?.)."""
        token = self._advance()  # consume ?.

        # Allow keywords as property names
        member_token = self._expect_identifier_or_keyword()
        member = member_token.value

        return MemberAccessExpression(
            obj=obj,
            member=member,
            line=token.line,
            column=token.column,
        )

    def _expect_identifier_or_keyword(self) -> Token:
        """Expect an identifier or keyword token (for property names).

        In JavaScript, keywords like ``default``, ``delete``, ``new`` etc.
        are valid property names after ``.``.
        """
        current = self._current()
        if current.type == TokenType.IDENTIFIER:
            return self._advance()
        # Accept reserved words as property names
        _keyword_types = {
            TokenType.DEFAULT, TokenType.DELETE, TokenType.NEW,
            TokenType.RETURN, TokenType.IF, TokenType.ELSE,
            TokenType.FOR, TokenType.WHILE, TokenType.SWITCH,
            TokenType.CASE, TokenType.BREAK, TokenType.CONTINUE,
            TokenType.AND, TokenType.OR,
            TokenType.FUNCTION, TokenType.VAR, TokenType.LET,
            TokenType.CONST, TokenType.EXPORT, TokenType.IMPORT,
            TokenType.FROM, TokenType.AS, TokenType.IN, TokenType.OF,
            TokenType.NULL, TokenType.TRUE, TokenType.FALSE,
            TokenType.TRY, TokenType.CATCH, TokenType.FINALLY,
            TokenType.THROW, TokenType.TYPEOF, TokenType.INSTANCEOF,
        }
        if current.type in _keyword_types:
            return self._advance()
        # Fallback: expect identifier (will raise UnexpectedTokenError)
        return self._expect(TokenType.IDENTIFIER)


__all__ = [
    "FsscriptParser",
    "PRECEDENCE",
]
