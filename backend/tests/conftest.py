import os
import sys
import tempfile
from pathlib import Path

# Configure the app for tests BEFORE anything imports app.core.config
_tmp = tempfile.mkdtemp(prefix="livetruth-test-")
os.environ.update({
    "APP_ENV": "test",
    "JWT_SECRET": "test-secret-" + "x" * 40,
    "STORAGE_DIR": _tmp,
    "VECTOR_STORE": "memory",
    "OPENAI_API_KEY": "test-key",
    "SEARCH_PROVIDER": "wikipedia",
    "MIN_EVIDENCE_SCORE": "0.3",
    "TRUST_FETCH_METADATA": "false",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_segments():
    import json

    return json.loads((FIXTURES / "sample_transcript.json").read_text())["segments"]
