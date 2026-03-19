"""Unit tests for core exceptions (RX and ExRuntimeException)."""

import pytest
from foggy.core.exceptions import (
    RX,
    RXBuilder,
    ExRuntimeException,
    ErrorLevel,
    OPER_ERROR,
    SYSTEM_ERROR,
    A_COMMON,
    B_COMMON,
    C_COMMON,
)


class TestRX:
    """Tests for RX unified response object."""

    def test_ok_with_data(self):
        """Test creating success response with data."""
        data = {"name": "test", "value": 123}
        response = RX.ok(data)

        assert response.code == RX.SUCCESS
        assert response.msg == "success"
        assert response.data == data
        assert response.ex_code is None
        assert response.is_success()
        assert not response.is_fail()

    def test_ok_with_custom_message(self):
        """Test success response with custom message."""
        response = RX.ok(data="result", msg="Custom message")

        assert response.code == 200
        assert response.msg == "Custom message"
        assert response.data == "result"

    def test_fail_with_message(self):
        """Test creating failure response."""
        response = RX.fail("Something went wrong")

        assert response.code == RX.FAIL
        assert response.msg == "Something went wrong"
        assert response.data is None
        assert response.is_fail()
        assert not response.is_success()

    def test_fail_with_data(self):
        """Test failure response with error data."""
        error_data = {"field": "email", "reason": "invalid"}
        response = RX.fail("Validation failed", data=error_data)

        assert response.code == 500
        assert response.data == error_data

    def test_fail_ex_with_defined_error(self):
        """Test failure response from ExDefined."""
        response = RX.fail_ex(OPER_ERROR)

        assert response.code == RX.FAIL
        assert response.msg == OPER_ERROR.msg
        assert response.ex_code == OPER_ERROR.ex_code
        assert response.ex_code == "A001"

    def test_fail_b_alias(self):
        """Test fail_b is alias for fail."""
        response = RX.fail_b("Error message")

        assert response.code == RX.FAIL
        assert response.msg == "Error message"

    def test_not_found_builder(self):
        """Test not_found response builder."""
        response = RX.not_found("Resource not found").build()

        assert response.code == 404
        assert response.msg == "Resource not found"

    def test_bad_request_builder(self):
        """Test bad_request response builder."""
        response = RX.bad_request("Invalid input").build()

        assert response.code == 400
        assert response.msg == "Invalid input"

    def test_unauthorized_builder(self):
        """Test unauthorized response builder."""
        response = RX.unauthorized().build()

        assert response.code == 401
        assert response.msg == "Unauthorized"

    def test_forbidden_builder(self):
        """Test forbidden response builder."""
        response = RX.forbidden().build()

        assert response.code == 403
        assert response.msg == "Forbidden"

    def test_builder_pattern(self):
        """Test full builder pattern."""
        response = (
            RX.builder()
            .code(201)
            .msg("Created")
            .data({"id": 1})
            .ex_code("A100")
            .build()
        )

        assert response.code == 201
        assert response.msg == "Created"
        assert response.data == {"id": 1}
        assert response.ex_code == "A100"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        response = RX.ok({"key": "value"})
        result = response.to_dict()

        assert result["code"] == 200
        assert result["msg"] == "success"
        assert result["data"] == {"key": "value"}
        assert result["exCode"] is None

    def test_default_success(self):
        """Test DEFAULT_SUCCESS singleton."""
        assert RX.DEFAULT_SUCCESS.code == RX.SUCCESS
        assert RX.DEFAULT_SUCCESS.msg == "success"
        assert RX.DEFAULT_SUCCESS.data is None

    def test_class_constants(self):
        """Test class constants are correct."""
        assert RX.SYSTEM_ERROR_MSG == "服务器发生异常，请联系管理员"
        assert RX.SUCCESS == 200
        assert RX.FAIL == 500
        assert RX.A_COMMON == "A"
        assert RX.B_COMMON == "B"
        assert RX.C_COMMON == "C"


class TestExRuntimeException:
    """Tests for ExRuntimeException."""

    def test_default_initialization(self):
        """Test exception with default values."""
        exc = ExRuntimeException()

        assert exc.msg == "系统异常"
        assert exc.code == 1
        assert exc.ex_code == "B001"
        assert exc.level == ErrorLevel.ERROR
        assert exc.item is None
        assert exc.user_tip is None

    def test_custom_initialization(self):
        """Test exception with custom values."""
        exc = ExRuntimeException(
            msg="Custom error",
            code=100,
            ex_code="C100",
            level=ErrorLevel.WARN,
            item={"key": "value"},
            user_tip="Please try again",
        )

        assert exc.msg == "Custom error"
        assert exc.code == 100
        assert exc.ex_code == "C100"
        assert exc.level == ErrorLevel.WARN
        assert exc.item == {"key": "value"}
        assert exc.user_tip == "Please try again"

    def test_from_defined(self):
        """Test creating exception from ExDefined."""
        exc = ExRuntimeException.from_defined(OPER_ERROR)

        assert exc.msg == OPER_ERROR.msg
        assert exc.code == OPER_ERROR.code
        assert exc.ex_code == OPER_ERROR.ex_code

    def test_from_defined_with_extra(self):
        """Test creating exception from ExDefined with extra data."""
        exc = ExRuntimeException.from_defined(
            SYSTEM_ERROR,
            item={"request_id": "123"},
            level=ErrorLevel.FATAL,
        )

        assert exc.msg == SYSTEM_ERROR.msg
        assert exc.level == ErrorLevel.FATAL
        assert exc.item == {"request_id": "123"}

    def test_message_property(self):
        """Test message property."""
        exc = ExRuntimeException(msg="Test message")
        assert exc.message == "Test message"

    def test_str_representation(self):
        """Test string representation."""
        exc = ExRuntimeException(msg="Error", ex_code="A001")
        assert str(exc) == "[A001] Error"

    def test_str_with_item(self):
        """Test string representation with item."""
        exc = ExRuntimeException(
            msg="Error",
            ex_code="A001",
            item={"field": "email"},
        )
        assert "[A001] Error" in str(exc)
        assert "field" in str(exc)

    def test_repr(self):
        """Test repr representation."""
        exc = ExRuntimeException(
            msg="Test",
            code=10,
            ex_code="B010",
            level=ErrorLevel.WARN,
        )
        repr_str = repr(exc)
        assert "ExRuntimeException" in repr_str
        assert "msg='Test'" in repr_str
        assert "code=10" in repr_str
        assert "level=WARN" in repr_str

    def test_raise_exception(self):
        """Test raising exception."""
        with pytest.raises(ExRuntimeException) as exc_info:
            raise ExRuntimeException(msg="Raised error")

        assert exc_info.value.msg == "Raised error"

    def test_cause_chain(self):
        """Test exception with cause."""
        original = ValueError("Original error")
        exc = ExRuntimeException(msg="Wrapped", cause=original)

        assert exc.cause == original


class TestErrorLevel:
    """Tests for ErrorLevel enum."""

    def test_all_levels(self):
        """Test all error levels exist."""
        levels = [ErrorLevel.DEBUG, ErrorLevel.INFO, ErrorLevel.WARN, ErrorLevel.ERROR, ErrorLevel.FATAL]
        assert len(levels) == 5

    def test_level_values(self):
        """Test error level values."""
        assert ErrorLevel.DEBUG.value == "DEBUG"
        assert ErrorLevel.INFO.value == "INFO"
        assert ErrorLevel.WARN.value == "WARN"
        assert ErrorLevel.ERROR.value == "ERROR"
        assert ErrorLevel.FATAL.value == "FATAL"