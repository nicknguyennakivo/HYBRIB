import json
from dataclasses import asdict
from pathlib import Path
from stage_hand.selector_snapshot import SelectorSnapshot


class SnapshotStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def get(self, step: str) -> SelectorSnapshot | None:
        raw = self.data.get(step)
        return SelectorSnapshot(**raw) if raw else None

    def put(self, snapshot: SelectorSnapshot):
        self.data[snapshot.step] = asdict(snapshot)
        self.path.write_text(json.dumps(self.data, indent=2))
