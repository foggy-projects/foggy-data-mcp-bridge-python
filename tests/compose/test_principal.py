"""M1 Principal invariants — cross-repo parity test."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.context import Principal


class TestPrincipalInvariants:
    def test_user_id_required_non_empty(self):
        """userId must be non-empty. Cross-repo with Java PrincipalTest."""
        with pytest.raises(ValueError):
            Principal(user_id="")
        with pytest.raises(ValueError):
            Principal(user_id=None)  # type: ignore[arg-type]

    def test_minimal_constructor_defaults(self):
        """Only user_id is required; every other field defaults to None/empty."""
        p = Principal(user_id="u001")
        assert p.user_id == "u001"
        assert p.tenant_id is None
        assert p.roles == ()
        assert p.dept_id is None
        assert p.authorization_hint is None
        assert p.policy_snapshot_id is None

    def test_roles_default_is_empty_tuple_not_none(self):
        """Roles is never None — always iterable."""
        p = Principal(user_id="u001")
        assert isinstance(p.roles, tuple)
        assert len(p.roles) == 0

    def test_roles_accepts_iterable_normalises_to_tuple(self):
        """Construction accepts any iterable; stored as tuple for hashability."""
        p_list = Principal(user_id="u001", roles=["admin", "editor"])
        assert p_list.roles == ("admin", "editor")
        assert isinstance(p_list.roles, tuple)

        p_gen = Principal(user_id="u001", roles=(r for r in ["a", "b"]))
        assert p_gen.roles == ("a", "b")

    def test_roles_rejects_non_string_entries(self):
        with pytest.raises(TypeError):
            Principal(user_id="u001", roles=["ok", 123])  # type: ignore[list-item]


class TestPrincipalImmutability:
    def test_frozen_dataclass_rejects_attribute_mutation(self):
        """Principal is a frozen dataclass; setattr raises."""
        p = Principal(user_id="u001", roles=["admin"])
        with pytest.raises(Exception):  # FrozenInstanceError
            p.user_id = "u002"  # type: ignore[misc]

    def test_instances_are_value_equal(self):
        """Two Principals with identical field values are equal."""
        a = Principal(user_id="u001", roles=["admin"], dept_id="d1")
        b = Principal(user_id="u001", roles=["admin"], dept_id="d1")
        assert a == b

    def test_instances_are_hashable(self):
        """Frozen + tuple roles ⇒ hashable ⇒ usable in cache-key sets."""
        a = Principal(user_id="u001", roles=["admin"])
        b = Principal(user_id="u001", roles=["admin"])
        # Same value, hashes equal
        assert hash(a) == hash(b)
        assert {a, b} == {a}


class TestPrincipalConvenience:
    def test_roles_list_returns_fresh_mutable_list(self):
        p = Principal(user_id="u001", roles=["a", "b"])
        l1 = p.roles_list()
        l1.append("c")  # mutate caller's copy
        assert p.roles == ("a", "b")  # original unaffected
        assert l1 == ["a", "b", "c"]
