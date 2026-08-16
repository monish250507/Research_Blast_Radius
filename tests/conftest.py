import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(__file__))

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

os.environ.setdefault("RBR_DB_URL", "sqlite+pysqlite:///./rbr_test.db")


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_golden_fixture():
    import bootstrap_fixture

    bootstrap_fixture.ensure_fixture_git()
    yield
    bootstrap_fixture.teardown_fixture_git()


@pytest.fixture()
def db_path(tmp_path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture()
def settings(db_path: str):
    from rbr.config import Settings

    os.environ["RBR_DB_URL"] = f"sqlite+pysqlite:///{db_path}"
    return Settings()
