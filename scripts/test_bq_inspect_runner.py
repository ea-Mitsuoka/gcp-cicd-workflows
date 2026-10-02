#!/usr/bin/env python3
"""Pin how bq-inspect runs the caller's canonical targets during the make-to-task move.

A caller with a root Taskfile.yml runs its targets with go-task, installed by the caller's
own pinned scripts/actions/setup-task (ai-dev-foundation ADR-0026); a caller without one
keeps make. No step may call either runner directly.
"""

from pathlib import Path
from typing import Any

import yaml


WORKFLOW = Path(__file__).parents[1] / ".github/workflows/bq-inspect.yml"
CANONICAL_TARGETS = ("setup", "inspect", "remediation-draft")


def fail(message: str) -> None:
    raise AssertionError(message)


document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
job = document.get("jobs", {}).get("inspect")
if not isinstance(job, dict):
    fail("bq-inspect must keep its inspect job")
steps: list[dict[str, Any]] = job.get("steps", [])

selectors = [step for step in steps if step.get("id") == "runner"]
if len(selectors) != 1:
    fail("exactly one step with id 'runner' must select the canonical runner")
selector_script = selectors[0].get("run", "")
for fragment in ("Taskfile.yml", "name=task", "name=make", "$GITHUB_OUTPUT"):
    if fragment not in selector_script:
        fail(f"runner selection must contain {fragment!r}")

installs = [step for step in steps if step.get("uses") == "./scripts/actions/setup-task"]
if len(installs) != 1:
    fail("go-task must be installed by the caller's own scripts/actions/setup-task")
if installs[0].get("if") != "steps.runner.outputs.name == 'task'":
    fail("go-task must be installed only when the caller has a Taskfile.yml")
if steps.index(installs[0]) < steps.index(selectors[0]):
    fail("go-task must be installed after the runner is selected")

for target in CANONICAL_TARGETS:
    calls = [
        step
        for step in steps
        if f'"$RUNNER" {target}' in step.get("run", "")
    ]
    if len(calls) != 1:
        fail(f"exactly one step must run the {target} target through $RUNNER")
    if calls[0].get("env", {}).get("RUNNER") != "${{ steps.runner.outputs.name }}":
        fail(f"the {target} step must take RUNNER from the runner selection")
    if steps.index(calls[0]) < steps.index(installs[0]):
        fail(f"the {target} step must run after go-task is installed")

for step in steps:
    script = step.get("run", "")
    for line in script.splitlines():
        command = line.strip()
        if command.startswith(("make ", "task ")):
            fail(f"steps must call the selected runner, not a fixed one: {command!r}")

print("bq-inspect runner selection: OK")
