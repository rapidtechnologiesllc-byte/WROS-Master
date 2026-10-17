"""Fake Flash brains for tests: no network, scripted answers, every request kept."""
from typing import List, Optional

from app.services.flash_brain.llm import BrainUnavailable, ToolLoopResult


class FakeSmall:
    """SmallBrain stand-in: returns `responses` in order (an Exception is raised instead)."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: List[dict] = []

    def extract_json(self, *, purpose, system, user, schema, tenant_id):
        self.requests.append({"purpose": purpose, "system": system, "user": user, "schema": schema})
        if not self.responses:
            raise BrainUnavailable("FakeSmall has no scripted response left")
        step = self.responses.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeLarge:
    """LargeBrain stand-in. extract_json answers like FakeSmall. run_tools replays `script`, one turn
    per call: rounds (each a list of (tool name, args) calls) up to the turn's final text (a str), or
    an Exception, which is raised. A call with no script left is an unfinished turn (refused)."""

    def __init__(self, *script, extract: Optional[list] = None):
        self.script = list(script)
        self.extract = list(extract or [])
        self.requests: List[dict] = []

    def extract_json(self, *, purpose, system, user, schema, tenant_id):
        self.requests.append({"purpose": purpose, "user": user})
        step = self.extract.pop(0) if self.extract else BrainUnavailable("no scripted extraction")
        if isinstance(step, Exception):
            raise step
        return step

    def run_tools(self, *, system, history, user_message, tools, execute, tenant_id, purpose="agent"):
        self.requests.append({"history": list(history), "user": user_message, "tools": [t.name for t in tools],
                              "purpose": purpose})
        result = ToolLoopResult()
        while self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            if isinstance(step, str):
                result.text = step
                return result
            result.rounds += 1
            for name, args in step:
                outcome = execute(name, args)
                result.trace.append({"name": name, "args": args, "result": outcome})
        result.refused = True
        return result
