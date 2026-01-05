# parser/dsl_models.py
from dataclasses import dataclass
from typing import List

@dataclass
class Step:
    text: str
    is_physical: bool = False

@dataclass
class TestCase:
    name: str
    depends_on: List[str]
    pre: List[Step]
    run: List[Step]
    finally_: List[Step]
    # New timing parameters (in minutes)
    max_wait: int = 120
    poll_interval: int = 2
