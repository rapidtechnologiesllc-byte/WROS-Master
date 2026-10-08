"""Every queue message type the code enqueues must have a registered handler; the
production worker marks unhandled types FAILED and retries them for nothing."""
import ast
import pathlib

from app.services.message_handler_registry import MessageHandlerRegistry

APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"

# Producers that can never actually enqueue (dead path or invalid enqueue() kwargs)
UNREACHABLE = {
    "candidate_sourcing_complete": "producer source_candidates_for_job is never enqueued",
    "create_thunder_outreach": "job_created_orchestrator is never imported",
    "ops_alert_thunder_critical": "cascade_failure_signal_handler is never registered",
    "process_candidate": "enqueue() called with unsupported kwargs (TypeError before queueing)",
    "send_email": "enqueue() called with unsupported channel_type kwarg (TypeError before queueing)",
}


def _enqueued_task_names():
    names = {}
    for path in APP_DIR.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = getattr(node.func, "attr", getattr(node.func, "id", None))
            if func_name != "enqueue":
                continue
            literals = [kw.value for kw in node.keywords if kw.arg == "task_name"]
            if node.args:
                literals.append(node.args[0])
            for value in literals:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    names.setdefault(value.value, f"{path.relative_to(APP_DIR.parent)}:{node.lineno}")
    return names


def test_every_enqueued_message_type_has_a_handler():
    registered = set(MessageHandlerRegistry.get_all_handlers())
    missing = {name: where for name, where in _enqueued_task_names().items()
               if name not in registered and name not in UNREACHABLE}
    assert not missing, f"Enqueued with no registered handler: {missing}"


def test_unreachable_allowlist_stays_honest():
    enqueued = _enqueued_task_names()
    registered = set(MessageHandlerRegistry.get_all_handlers())
    stale = [name for name in UNREACHABLE if name not in enqueued or name in registered]
    assert not stale, f"Remove from UNREACHABLE (no longer enqueued or now handled): {stale}"
