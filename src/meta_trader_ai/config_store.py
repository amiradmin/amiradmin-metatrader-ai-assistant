from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from .models import StrategyConfig


class StrategyConfigStore:
    def __init__(self, path: str | Path | None = None) -> None:
        default = os.getenv("MTAI_STRATEGY_CONFIG", "strategy_config.json")
        self.path = Path(path or default)
        self._lock = RLock()

    def load(self) -> StrategyConfig:
        with self._lock:
            if not self.path.exists():
                config = StrategyConfig()
                self.save(config)
                return config
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return StrategyConfig.model_validate(data)

    def save(self, config: StrategyConfig) -> StrategyConfig:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp.replace(self.path)
            return config
