import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ghost_ai.domain.models import Action, ActionType, Conditions, Rule  # noqa: E402
from ghost_ai.engine.service import AutomationService  # noqa: E402
from ghost_ai.storage.db import Store  # noqa: E402


@pytest.fixture
def sandbox(tmp_path):
    """A fake user area: Downloads + Documents inside pytest's tmp dir."""
    downloads = tmp_path / "user" / "Downloads"
    documents = tmp_path / "user" / "Documents"
    downloads.mkdir(parents=True)
    documents.mkdir(parents=True)
    return downloads, documents


@pytest.fixture
def service(tmp_path, sandbox):
    store = Store(tmp_path / "ghost.db")
    svc = AutomationService(store, str(tmp_path / "appdata"), settle_seconds=0.0)
    for folder in sandbox:
        svc.add_folder(str(folder))
    yield svc
    svc.stop_watching()
    store.close()


def make_rule(src, dst, exts=("pdf",), atype=ActionType.MOVE, **kw) -> Rule:
    return Rule(name="test", watch_dir=str(src), conditions=Conditions(extensions=list(exts)),
                action=Action(type=atype, target_dir=str(dst) if dst else ""), **kw)
