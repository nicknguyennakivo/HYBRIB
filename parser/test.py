from enum import Enum
from dataclasses import dataclass
from typing import List, Dict

class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class TestCase:
    name: str
    depends_on: List[str]
    pre: list
    run: list
    finally_: list
