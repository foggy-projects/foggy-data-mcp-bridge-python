"""Tests for Semantic Layer Validation Service."""

import pytest
from datetime import date

from foggy.mcp.validation.service import (
    SemanticLayerValidationService,
    ValidationRequest,
    ValidationResult,
    ValidationError,
    ValidationWarning,
    ValidationSeverity,
)


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_empty_result_is_valid(self):
        """Empty result should be valid."""
        result = ValidationResult()
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_add_error_marks_invalid(self):
        """Adding error should mark result as invalid."""
        result = ValidationResult()
        result.add_error("TEST_ERROR", "Test error message")
        assert result.valid is False
        assert len(result.errors) == 1

    def test_add_warning_keeps_valid(self):
        """Adding warning should not affect validity."""
        result = ValidationResult()
        result.add_warning("TEST_WARNING", "Test warning")
        assert result.valid is True
        assert len(result.warnings) == 1

    def test_merge_results(self):
        """Merging should combine errors and warnings."""
        result1 = ValidationResult()
        result1.add_warning("W1", "Warning 1")

        result2 = ValidationResult()
        result2.add_error("E1", "Error 1")

        result1.merge(result2)
        assert result1.valid is False
        assert len(result1.warnings) == 1
        assert len(result1.errors) == 1

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ValidationResult()
        result.add_error("E1", "Error", path="field")
        result.add_warning("W1", "Warning")

        d = result.to_dict()
        assert d["valid"] is False
        assert len(d["errors"]) == 1
        assert len(d["warnings"]) == 1
        assert d["errors"][0]["code"] == "E1"


class TestValidationError:
    """Tests for ValidationError."""

    def test_error_creation(self):
        """Test creating an error."""
        error = ValidationError(
            code="TEST_ERROR",
            message="Test message",
            path="field.name",
        )
        assert error.code == "TEST_ERROR"
        assert error.message == "Test message"
        assert error.path == "field.name"
        assert error.severity == ValidationSeverity.ERROR

    def test_error_to_dict(self):
        """Test error to dictionary conversion."""
        error = ValidationError(
            code="TEST",
            message="Msg",
            path="path",
            severity=ValidationSeverity.WARNING,
        )
        d = error.to_dict()
        assert d["code"] == "TEST"
        assert d["message"] == "Msg"
        assert d["path"] == "path"
        assert d["severity"] == "warning"


class TestValidationWarning:
    """Tests for ValidationWarning."""

    def test_warning_creation(self):
        """Test creating a warning."""
        warning = ValidationWarning(
            code="TEST_WARNING",
            message="Test warning",
            path="field",
            suggestion="Fix this",
        )
        assert warning.code == "TEST_WARNING"
        assert warning.suggestion == "Fix this"

    def test_warning_to_dict(self):
        """Test warning to dictionary conversion."""
        warning = ValidationWarning(
            code="W1",
            message="Warning",
            suggestion="Suggestion",
        )
        d = warning.to_dict()
        assert d["suggestion"] == "Suggestion"


class TestValidationRequest:
    """Tests for ValidationRequest."""

    def test_empty_request(self):
        """Test empty request."""
        request = ValidationRequest()
        assert request.model_name is None
        assert request.query_model is None

    def test_model_request(self):
        """Test model validation request."""
        request = ValidationRequest(
            model_name="test_model",
            model_type="tm",
            model_content={"name": "test", "table": "test_table"},
        )
        assert request.model_name == "test_model"
        assert request.model_type == "tm"


class TestSemanticLayerValidationService:
    """Tests for SemanticLayerValidationService."""

    @pytest.fixture
    def service(self):
        """Create validation service."""
        return SemanticLayerValidationService()

    def test_validate_empty_model(self, service):
        """Test validating empty model."""
        result = service.validate_model_definition({})
        assert result.valid is False
        assert any(e.code == "MISSING_NAME" for e in result.errors)

    def test_validate_valid_table_model(self, service):
        """Test validating valid table model."""
        model = {
            "name": "sales",
            "table": "sales_table",
            "columns": [
                {"name": "id", "type": "INTEGER"},
                {"name": "amount", "type": "DECIMAL"},
            ],
        }
        result = service.validate_model_definition(model, model_type="tm")
        assert result.valid is True

    def test_validate_model_missing_table(self, service):
        """Test validating model without table."""
        model = {"name": "test_model"}
        result = service.validate_model_definition(model, model_type="tm")
        assert result.valid is False
        assert any(e.code == "MISSING_TABLE" for e in result.errors)

    def test_validate_model_reserved_name(self, service):
        """Test validating model with reserved name."""
        model = {"name": "limit", "table": "test"}
        result = service.validate_model_definition(model)
        assert any(w.code == "RESERVED_NAME" for w in result.warnings)

    def test_validate_model_duplicate_columns(self, service):
        """Test validating model with duplicate columns."""
        model = {
            "name": "test",
            "table": "test_table",
            "columns": [
                {"name": "id", "type": "INTEGER"},
                {"name": "id", "type": "STRING"},  # Duplicate
            ],
        }
        result = service.validate_model_definition(model)
        assert result.valid is False
        assert any(e.code == "DUPLICATE_COLUMN" for e in result.errors)

    def test_validate_measure(self, service):
        """Test validating measures."""
        model = {
            "name": "test",
            "table": "test",
            "measures": [
                {"name": "total", "aggregation": "SUM", "column": "amount"},
                {"name": "count", "aggregation": "COUNT"},
            ],
        }
        result = service.validate_model_definition(model)
        assert result.valid is True

    def test_validate_measure_unknown_aggregation(self, service):
        """Test validating measure with unknown aggregation."""
        model = {
            "name": "test",
            "table": "test",
            "measures": [
                {"name": "custom", "aggregation": "CUSTOM_AGG"},
            ],
        }
        result = service.validate_model_definition(model)
        assert any(w.code == "UNKNOWN_AGGREGATION" for w in result.warnings)

    def test_validate_query_missing_model(self, service):
        """Test validating query without model."""
        query = {"select": ["col1", "col2"]}
        result = service.validate_query(query)
        assert result.valid is False
        assert any(e.code == "MISSING_MODEL" for e in result.errors)

    def test_validate_query_valid(self, service):
        """Test validating valid query."""
        query = {
            "query_model": "test_model",
            "select": ["col1", "col2"],
            "limit": 100,
        }
        result = service.validate_query(query)
        assert result.valid is True

    def test_validate_query_invalid_limit(self, service):
        """Test validating query with invalid limit."""
        query = {
            "query_model": "test",
            "limit": -1,
        }
        result = service.validate_query(query)
        assert result.valid is False
        assert any(e.code == "INVALID_LIMIT" for e in result.errors)

    def test_validate_query_large_limit(self, service):
        """Test validating query with large limit."""
        query = {
            "query_model": "test",
            "limit": 200000,
        }
        result = service.validate_query(query)
        assert any(w.code == "LARGE_LIMIT" for w in result.warnings)

    def test_validate_filter_missing_column(self, service):
        """Test validating filter without column."""
        query = {
            "query_model": "test",
            "filters": [{"operator": "eq", "value": "test"}],
        }
        result = service.validate_query(query)
        assert result.valid is False
        assert any(e.code == "MISSING_FILTER_COLUMN" for e in result.errors)

    def test_validate_filter_missing_operator(self, service):
        """Test validating filter without operator."""
        query = {
            "query_model": "test",
            "filters": [{"column": "name", "value": "test"}],
        }
        result = service.validate_query(query)
        assert result.valid is False
        assert any(e.code == "MISSING_OPERATOR" for e in result.errors)

    def test_validate_datasource_missing_type(self, service):
        """Test validating datasource without type."""
        config = {"name": "my_db"}
        result = service.validate_datasource_connection(config)
        assert result.valid is False
        assert any(e.code == "MISSING_TYPE" for e in result.errors)

    def test_validate_datasource_missing_host(self, service):
        """Test validating datasource without host."""
        config = {"name": "my_db", "type": "mysql"}
        result = service.validate_datasource_connection(config)
        assert result.valid is False
        assert any(e.code == "MISSING_CONNECTION_PARAMS" for e in result.errors)

    def test_validate_datasource_sqlite(self, service):
        """Test validating SQLite datasource."""
        config = {"name": "local", "type": "sqlite", "path": ":memory:"}
        result = service.validate_datasource_connection(config)
        assert result.valid is True

    def test_validate_all_models(self, service):
        """Test validating all registered models."""
        service.register_model("model1", {"name": "model1", "table": "table1"})
        service.register_model("model2", {"name": "model2", "table": "table2"})

        result = service.validate_all_models()
        assert result.valid is True

    def test_validate_reference_checking(self):
        """Test reference validation in query models."""
        service = SemanticLayerValidationService(validate_references=True)

        # Register a table model
        service.register_model("sales_tm", {"name": "sales_tm", "table": "sales"})

        # Validate QM referencing unregistered TM
        qm = {
            "name": "sales_qm",
            "base_model": "nonexistent_tm",
        }
        result = service._validate_query_model(qm)
        assert any(w.code == "UNRESOLVED_REFERENCE" for w in result.warnings)


class TestValidationIntegration:
    """Integration tests for validation."""

    @pytest.fixture
    def service(self):
        """Create validation service with models."""
        service = SemanticLayerValidationService()

        # Register sample table models
        service.register_model("sales", {
            "name": "sales",
            "table": "sales",
            "columns": [
                {"name": "id", "type": "INTEGER"},
                {"name": "amount", "type": "DECIMAL"},
                {"name": "date", "type": "DATE"},
            ],
        })

        return service

    def test_validate_full_workflow(self, service):
        """Test full validation workflow."""
        request = ValidationRequest(
            model_name="sales",
            model_type="tm",
            model_content={
                "name": "sales",
                "table": "sales",
                "columns": [{"name": "id", "type": "INTEGER"}],
            },
        )
        result = service.validate(request)
        assert result.valid is True

    def test_validate_query_with_references(self, service):
        """Test validating query with model references."""
        request = ValidationRequest(
            query_model="sales",
            query_content={
                "query_model": "sales",
                "select": ["id", "amount"],
                "filters": [{"column": "amount", "operator": "gt", "value": 100}],
            },
        )
        result = service.validate(request)
        assert result.valid is True