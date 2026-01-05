# HYBRIB

Lightweight test orchestration prototype for running DSL-defined UI test cases with dependency handling.

## Project layout
- `main_orchestrator.py` — entry point.
- `parser/` — DSL data models and parser.
- `runner/` — orchestrator and executor.
- `testcase/` — test case files (`.txt`) written in the DSL.
- `stagehand/` or `stage_hand/` — experimental UI-driving engine pieces (optional/in-progress).

## Prerequisites
- Python 3.10+ (tested with 3.13 on Windows)
- Windows PowerShell (examples below use PowerShell)

## Set up (Windows PowerShell)
1. Open a terminal at the repo root (folder containing `main_orchestrator.py`).
2. Create and activate a virtual environment:
   - Create: `py -3 -m venv .venv`
   - Activate: `.\.venv\Scripts\Activate`
3. Install dependencies:
   - `pip install -r requirements.txt`
   - `python -m playwright install`

## Running
From the project root:

- `python .\main_orchestrator.py --testcase=backup_vm_incremental`

This loads the test case `create_backup_job_365_incremental.txt`, automatically runs its dependencies (e.g. the full backup), executes, and exits with code 0 on pass or 1 on failure.

## Testcase DSL
Each file in `testcase/` follows this structure:

- Directives:
  - `@testcase <name>`
  - `@depends_on <name1> <name2> ...` (optional)
  - `@max_wait <minutes>` (optional, default 60 unless overridden in code)
  - `@poll_interval <minutes>` (optional, default 3 unless overridden in code)
- Sections:
  - `@pre`     — steps that run before the main flow
  - `@run`     — main steps
  - `@finally` — always-run cleanup/verification
- Steps:
  - One human-readable instruction per line
  - Prefix with `[physical]` for steps performed outside the UI automation engine

Example:

```
@testcase backup_m365_full
@max_wait 30
@poll_interval 2

@run
Type "admin" on the username input.
Click the "Log In" button.
Expect "Data Protection" to be visible.

@finally
[physical] Verify backup exists in repository.
```

Notes:
- Dependency names are the testcase names (not file names) unless your loader maps them differently. In this project, `.txt` is appended automatically by the loader, and names should match the file base name.

## Adding a new testcase
1. Create a new file in `testcase/`, e.g. `my_flow.txt`.
2. Fill it with the DSL directives/sections/steps.
3. Make sure any `@depends_on` entries match other testcase names.
4. Run the orchestrator.

## Troubleshooting
- `ModuleNotFoundError` when running:
  - Make sure you run `python` from the repo root so relative imports like `parser.*` and `runner.*` resolve.
  - Ensure `stagehand/` or `stage_hand/` is not overshadowing a pip package unexpectedly; keep `__init__.py` present if using it as a package.
- `FileNotFoundError: Testcase not found`:
  - The loader looks in the `testcase/` folder. Ensure the filename exists and the `@depends_on` names map to existing files.
- Stagehand-related imports missing:
  - The provided `stagehand` pieces are stubs/examples. Replace placeholder classes and imports with your real UI automation stack, or keep the executor in "print only" mode.

## Extending execution
- The `runner/TestCaseExecutor` currently prints steps. To integrate a real UI engine:
  - Implement the logic in `stagehand/` (or your own module) to interpret and perform steps.
  - Call that logic from `TestCaseExecutor.run_stagehand`.
  - Use `max_wait` and `poll_interval` from `TestCase` to tune waiting/retry behavior.

## Exit codes
- 0 — all tests passed
- 1 — any test failed (or an exception occurred)
