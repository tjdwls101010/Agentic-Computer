"""Report whether the pinned engine and macOS permissions are ready, and install the engine when asked."""
from computer import agent_desktop

_SETTINGS = "System Settings > Privacy & Security > {pane}: enable the app that launches Claude Code"
_EXIT_OK = 0
_EXIT_PROBLEM = 1
_EXIT_NOT_INSTALLED = 3


def report():
    """Return (payload, exit_code) describing the install and permissions."""
    state = agent_desktop.status()
    problems = _problems(state)
    state["ok"] = not problems
    if problems:
        state["fix"] = "; ".join(problems)
    if not (state["binary_present"] and state["helper_present"]):
        return state, _EXIT_NOT_INSTALLED
    return state, _EXIT_OK if not problems else _EXIT_PROBLEM


def fix():
    """Install the pinned release, then report. Returns (payload, exit_code)."""
    try:
        installed = agent_desktop.install()
    except (agent_desktop.InstallError, OSError) as error:
        return {"ok": False, "error": str(error), "fix": "run doctor --fix again; if it keeps failing, check the network and the release assets"}, _EXIT_PROBLEM
    payload, code = report()
    payload["installed"] = installed
    return payload, code


def _problems(state):
    problems = []
    if not (state["binary_present"] and state["helper_present"] and state["hashes_match"]):
        return ["engine is missing or does not match the pinned hashes: run doctor --fix"]
    if state.get("version") != state["expected_version"]:
        problems.append(f"engine reports version {state.get('version')}, expected {state['expected_version']}: run doctor --fix")
    if state.get("accessibility") != "granted":
        problems.append(_SETTINGS.format(pane="Accessibility"))
    if state.get("screen_recording") != "granted":
        problems.append(_SETTINGS.format(pane="Screen Recording") + " (only screenshots need this)")
    return problems
