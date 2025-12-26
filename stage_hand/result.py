from dataclasses import dataclass
from typing import Any, Optional, List

@dataclass
class StepResult:
    step: int
    instruction: str
    status: str
    error: Optional[str] = None
    used_agent: bool = False

@dataclass
class TestResult:
    passed: bool
    failed_step: Optional[int] = None
    reason: Optional[str] = None
    steps: List[StepResult] = None


@dataclass
class EngineActResult:
    success: bool
    used_agent: bool = False
    error: Optional[str] = None
    raw: Optional[Any] = None   # stagehand / agent result