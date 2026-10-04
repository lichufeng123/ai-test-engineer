"""Fictional task board: independent local read-only adapter example."""

import hashlib
import json
from pathlib import Path


class TaskBoardAdapter:
    adapter_id = "synthetic-taskboard"
    platform = "web"

    def __init__(self, source, state_file):
        self.source = source
        self.state_file = Path(state_file)

    def _board(self):
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def observe(self, probe):
        matches = [board for board in self._board()["boards"] if board["id"] == probe["fixture"]["id"]]
        return {"id": matches[0]["id"] if len(matches) == 1 else "ambiguous",
                "business_key": matches[0]["business_key"] if len(matches) == 1 else "ambiguous",
                "pre_state_sha256": hashlib.sha256(matches[0]["business_key"].encode()).hexdigest() if len(matches) == 1 else "",
                "match_count": len(matches)}

    def read(self, probe):
        return {"open_tasks": sum(item["status"] == "open" for item in self._board()["tasks"])}

    def readback(self, probe):
        board = self.observe(probe)
        return {"fixture_id": board["id"], "business_key": board["business_key"],
                "match_count": board["match_count"],
                "state_sha256": hashlib.sha256(self.state_file.read_bytes()).hexdigest()}

    def evaluate(self, probe, observed, oracle):
        return [{"id": probe["assertion_ids"][0],
                 "status": "passed" if observed["open_tasks"] == oracle["expected"] else "failed"}]
