"""The build state machine: Idea -> Shape -> Draft -> Test -> Use.

Pure and authoritative. The model proposes a stage/`done` in each turn; the
server calls into here to decide whether a transition is legal. Deterministic
code disposes — the model can never force an illegal jump.
"""
ORDER = ["idea", "shape", "draft", "test", "use"]

# Allowed target stages from each stage. Test can return to Draft ("Something's off").
_ALLOWED = {
    "idea": {"shape"},
    "shape": {"draft"},
    "draft": {"test"},
    "test": {"draft", "use"},
    "use": set(),
}


class FlowError(Exception):
    pass


def next_stage(current: str) -> str:
    if current not in ORDER:
        raise FlowError(f"unknown stage {current!r}")
    i = ORDER.index(current)
    if i + 1 >= len(ORDER):
        raise FlowError(f"{current} is the final stage")
    return ORDER[i + 1]


def can_transition(current: str, target: str) -> bool:
    return target in _ALLOWED.get(current, set())


def validate_transition(current: str, target: str) -> None:
    if current not in ORDER:
        raise FlowError(f"unknown stage {current!r}")
    if not can_transition(current, target):
        raise FlowError(f"cannot move from {current} to {target}")
