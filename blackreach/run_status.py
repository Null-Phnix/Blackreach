"""One terminal vocabulary for interactive and command-line run outcomes."""
from typing import Any, Dict


def describe_run(result: Dict[str, Any]) -> Dict[str, str]:
    status = result.get("status") or (
        "success" if result.get("success") else "paused" if result.get("paused") else "stopped"
    )
    labels = {
        "success": ("Success", "green"),
        "max_steps": ("Step limit reached", "yellow"),
        "paused": ("Paused", "blue"),
        "interrupted": ("Interrupted", "yellow"),
        "error": ("Failed", "red"),
        "stopped": ("Stopped", "yellow"),
    }
    label, color = labels.get(status, ("Stopped", "yellow"))
    reasons = {
        "startup_error": "The run could not start. Check the reported configuration error.",
        "initialization_failed": "The session could not be initialized.",
        "state_load_failed": "Saved progress could not be read.",
        "log_write_failed": "The final session log could not be written.",
        "goal_complete": "The agent reported the goal complete.",
        "max_steps": "The decision limit was reached before the goal was complete.",
        "paused": "The run was paused.",
        "interrupted": "The run was interrupted.",
        "permanent_error": "The run stopped because an error could not be recovered.",
        "browser_start_failed": "The browser could not start. Run blackreach doctor.",
        "navigation_failed": "The starting page could not be opened.",
        "state_save_failed": "Progress could not be saved for resuming.",
        "cleanup_failed": "The run encountered an error while closing resources.",
    }
    reason = reasons.get(result.get("stop_reason"), result.get("stop_reason") or "")
    if not reason and not result.get("success"):
        reason = "No stop reason was recorded by this version. Check the session log."
    hint = ""
    if result.get("resumable") and result.get("session_id") is not None:
        hint = f"Resume with: blackreach run --resume {result['session_id']}"
        if status == "max_steps":
            hint += f" --steps {int(result.get('steps_taken', 0)) + 20}"
    return {"label": label, "color": color, "reason": reason,
            "error": result.get("error") or "", "hint": hint}
