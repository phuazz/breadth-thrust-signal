"""Guard: the synthetic --self-test must never overwrite the canonical outputs.

``--self-test`` used to render straight over ``data/signals.json`` and
``docs/index.html``. The first is the filed study record that later workstreams
reconcile against; the second is what GitHub Pages serves. A self-test run at
the wrong moment on a dirty tree destroys either irrecoverably, and silently —
the run reports success either way. These tests pin the scratch destinations so
that cannot recur, while confirming the smoke test still covers the full render
path end to end.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import pipeline  # noqa: E402


CANONICAL = (pipeline.DATA / "signals.json", pipeline.DOCS / "index.html")
SCRATCH = (pipeline.SELFTEST_DATA, pipeline.SELFTEST_DOCS)


def _fingerprint(path: Path):
    """(exists, sha256). Absence is as much a state to preserve as content —
    a self-test that creates a canonical file where there was none is also a
    failure, because the next run would treat fabricated numbers as the record.
    """
    if not path.exists():
        return (False, None)
    return (True, hashlib.sha256(path.read_bytes()).hexdigest())


def test_selftest_destinations_are_distinct_from_canonical():
    """Static invariant, cheap to check: pointing either scratch constant back
    at the canonical directory reintroduces the whole failure mode."""
    assert pipeline.SELFTEST_DATA != pipeline.DATA
    assert pipeline.SELFTEST_DOCS != pipeline.DOCS
    assert pipeline.SELFTEST_DATA / "signals.json" not in CANONICAL
    assert pipeline.SELFTEST_DOCS / "index.html" not in CANONICAL


def test_self_test_leaves_canonical_outputs_untouched(monkeypatch):
    before = {p: _fingerprint(p) for p in CANONICAL}
    pre_existing = {d: d.exists() for d in SCRATCH}

    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--self-test"])
    try:
        assert pipeline.main() == 0

        for path in CANONICAL:
            assert _fingerprint(path) == before[path], (
                f"--self-test modified {path} — it must write only to scratch"
            )

        # Coverage must survive the redirection: both artefacts are still
        # produced, from the same render path, with real payload content.
        signals = pipeline.SELFTEST_DATA / "signals.json"
        assert signals.exists()
        payload = json.loads(signals.read_text(encoding="utf-8"))
        for key in ("current", "formation", "last_signal", "study", "timeline"):
            assert key in payload, f"self-test payload is missing {key}"
        assert 0 <= payload["current"]["n_dimensions"] <= 4

        if pipeline.TEMPLATE.exists():
            index = pipeline.SELFTEST_DOCS / "index.html"
            assert index.exists()
            html = index.read_text(encoding="utf-8")
            # The data island is filled, so the placeholder is fully consumed.
            # The fetch-fallback sentinel is written split ("__SIGNALS" +
            # "_JSON__") in the template precisely so injection cannot splice
            # JSON into that string literal; it must survive intact.
            assert "__SIGNALS_JSON__" not in html
            assert '"__SIGNALS" + "_JSON__"' in html
            assert payload["current"]["as_of"] in html
    finally:
        for directory, existed in pre_existing.items():
            if not existed and directory.exists():
                shutil.rmtree(directory)
