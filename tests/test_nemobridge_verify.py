"""
Integration test: run verify_spike_kb.py as a subprocess.

Skipped automatically when /home/user/bin/nmo is absent.
"""

import os
import subprocess
import sys
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
NEMO_BIN = "/home/user/bin/nmo"
VERIFY_SCRIPT = os.path.join(REPO_ROOT, "experiments", "h5_phase1", "verify_spike_kb.py")


@pytest.mark.skipif(
    not os.path.isfile(NEMO_BIN),
    reason=f"nmo binary not found at {NEMO_BIN}; obtain nemo-cli v0.10.0 as per experiments/h5_spike/README.md",
)
def test_verify_spike_kb_passes():
    """verify_spike_kb.py must exit 0 (R1=49/49, R2=6/6)."""
    result = subprocess.run(
        [sys.executable, VERIFY_SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"verify_spike_kb.py exited with code {result.returncode}.\nOutput:\n{output[:3000]}"
    )
    assert "VERIFICATION: PASS" in output
