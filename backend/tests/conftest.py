import os
import sys
import tempfile
from pathlib import Path

os.environ["PAPERCREW_FAKE_LLM"] = "1"
os.environ["PAPERCREW_DB"] = str(
    Path(tempfile.mkdtemp(prefix="papercrew-test-")) / "test.db"
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
