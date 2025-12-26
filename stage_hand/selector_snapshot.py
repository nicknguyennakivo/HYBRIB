from dataclasses import dataclass
from typing import Optional, List, Dict
import json


@dataclass
class SelectorSnapshot:
    step: str                     # original NL step
    selector: str
    method: str                   # click | fill | press | select
    arguments: List[str]          # method args
    description: str              # from observe
    coordinates: Optional[Dict[str, int]] = None  # {"x": 491, "y": 136} for coordinate clicks


    def load_snapshots(path: str) -> Dict[str, "SelectorSnapshot"]:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        return {
            step: SelectorSnapshot(**data)
            for step, data in raw.items()
        }
    @staticmethod
    def load_selector_snapshots(path: str) -> dict[str, "SelectorSnapshot"]:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        print(f"Raw data loaded from {path}: {raw}")

        snapshots = {}
        for step, data in raw.items():
            snapshots[step] = SelectorSnapshot(
                step=data["step"],
                selector=data["selector"],
                method=data["method"],
                arguments=data.get("arguments", []),
                description=data.get("description", "")
            )

        return snapshots

    