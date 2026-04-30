"""Tests for P2.3 Optional Script API (runtime.pause)."""

from __future__ import annotations

import threading
import time

import pytest

from foggy.dataset_model.engine.compose.capability.policy import CapabilityPolicy
from foggy.dataset_model.engine.compose.runtime.script_runtime import (
    run_script,
)
from foggy.dataset_model.engine.compose.runtime.suspension import ScriptRunState
from foggy.dataset_model.engine.compose.runtime.suspension_manager import (
    SuspensionManager,
)
from tests.compose.runtime.conftest import (
    Principal,
    StubResolver,
    StubSemanticService,
)

# We need the real context because evaluate_program requires it.
from foggy.dataset_model.engine.compose.context.compose_query_context import ComposeQueryContext
from foggy.dataset_model.engine.compose.context.principal import Principal


def _create_context() -> ComposeQueryContext:
    principal = Principal(user_id="U1", tenant_id="T1")
    return ComposeQueryContext(principal=principal, authority_resolver=StubResolver(), namespace="ns1")


class TestOptionalScriptPause:

    def test_script_pause_denied_by_default(self):
        """runtime.pause is not injected by default, yielding ReferenceError."""
        ctx = _create_context()
        svc = StubSemanticService()
        
        script = 'return runtime.pause({reason: "r", timeout_ms: 1000});'
        
        with pytest.raises(RuntimeError, match="Cannot call method 'pause' on null"):
            run_script(script, ctx, semantic_service=svc)

    def test_script_pause_allowed_and_executed(self):
        """When policy allows, runtime.pause suspends the script correctly."""
        ctx = _create_context()
        svc = StubSemanticService()
        mgr = SuspensionManager()
        policy = CapabilityPolicy(allow_script_pause=True)
        
        script = 'return runtime.pause({reason: "approval", timeout_ms: 5000, summary: {msg: "need ok"}});'
        
        result_holder = {}
        def runner():
            try:
                res = run_script(
                    script, ctx, semantic_service=svc,
                    capability_policy=policy, suspension_manager=mgr
                )
                result_holder["result"] = res
            except Exception as e:
                result_holder["error"] = e

        t = threading.Thread(target=runner)
        t.start()
        
        # Wait for suspension
        run_id = None
        for _ in range(100):
            if mgr._runs:
                run_id = list(mgr._runs.keys())[0]
                if mgr._runs[run_id].state == ScriptRunState.SUSPENDED:
                    break
            time.sleep(0.01)
            
        assert run_id is not None
        run_ctx = mgr._runs[run_id]
        assert run_ctx.state == ScriptRunState.SUSPENDED
        assert run_ctx.suspension.reason == "approval"
        assert run_ctx.suspension.summary == {"msg": "need ok"}
        assert run_ctx.suspension.timeout_at is not None
        
        # Resume it
        from foggy.dataset_model.engine.compose.runtime.suspension import ResumeCommand
        mgr.resume(ResumeCommand(
            script_run_id=run_id,
            suspend_id=run_ctx.suspension.suspend_id,
            payload={"status": "approved"}
        ))
        
        t.join(timeout=2)
        
        assert "result" in result_holder
        res = result_holder["result"]
        # FSScript translates python dict to dict in the script, so returning the payload dict
        # makes script return that dict.
        assert res.value == {"status": "approved"}

    def test_script_pause_invalid_arguments(self):
        """runtime.pause raises appropriate errors when arguments are invalid."""
        ctx = _create_context()
        svc = StubSemanticService()
        policy = CapabilityPolicy(allow_script_pause=True)
        
        # Missing reason
        script1 = 'return runtime.pause({timeout_ms: 1000});'
        with pytest.raises(ValueError, match="runtime.pause requires 'reason'"):
            run_script(script1, ctx, semantic_service=svc, capability_policy=policy)
        
        # Missing timeout
        script2 = 'return runtime.pause({reason: "r"});'
        with pytest.raises(ValueError, match="runtime.pause requires 'timeout_ms'"):
            run_script(script2, ctx, semantic_service=svc, capability_policy=policy)
        
        # Not a dict
        script3 = 'return runtime.pause("r", 1000);'
        with pytest.raises(TypeError, match="runtime.pause must be called with an options object"):
            run_script(script3, ctx, semantic_service=svc, capability_policy=policy)
