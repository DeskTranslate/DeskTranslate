import hashlib
import json
import platform
from pathlib import Path

import pytest
from tools import release_support


@pytest.mark.parametrize(
    "name",
    [
        "../outside.txt",
        "/outside.txt",
        "C:outside.txt",
        "C:/outside.txt",
        "a/../../x",
        "a\\x",
        "a/x:stream",
        "a/NUL.txt",
        "a/COM1",
        "a/name. ",
        "a//x",
    ],
)
def test_library_license_extraction_refuses_windows_path_tricks(name):
    from tools.library_sources import license_path

    with pytest.raises(RuntimeError, match="archive license path"):
        license_path(name)


def test_library_license_extraction_keeps_normal_nested_attribution():
    from tools.library_sources import license_path

    assert license_path("third-party/LICENSE-2.0.txt") == Path("third-party/LICENSE-2.0.txt")


def test_soak_sampler_tolerates_worker_closure_during_snapshot(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import soak

    class ClosedChild:
        @property
        def pid(self):
            raise ValueError("process object is closed")

    class ClosingChild:
        reads = 0

        @property
        def pid(self):
            self.reads += 1
            if self.reads > 1:
                raise ValueError("process object is closed")
            return 123

    child = ClosingChild()
    monkeypatch.setattr(soak.multiprocessing, "active_children", lambda: [ClosedChild(), child])
    monkeypatch.setattr(soak, "process_resources", lambda pid: {"pid": pid, "available": True})
    assert soak.child_resources() == [{"pid": 123, "available": True}]
    assert child.reads == 1


def test_canonical_versions_and_mismatched_tag() -> None:
    root = Path(__file__).resolve().parents[1]
    release_support.version_gate(root, "v" + release_support.__version__)
    with pytest.raises(ValueError, match="tag"):
        release_support.version_gate(root, "v9.9.9")
    assert release_support.windows_version("2.0.0b2") == "2.0.0.10002"
    assert release_support.windows_version("2.0.0rc1") == "2.0.0.30001"
    assert release_support.windows_version("2.0.0") == "2.0.0.60000"


def test_release_signing_and_stable_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DESKTRANSLATE_SIGNING_THUMBPRINT", raising=False)
    with pytest.raises(ValueError, match="publisher"):
        release_support.Signer()
    monkeypatch.setattr(release_support, "__version__", "2.0.0b2")
    with pytest.raises(ValueError, match="prerelease"):
        release_support.stable_gate(
            Path(__file__).resolve().parents[1], "v" + release_support.__version__
        )
    monkeypatch.setattr(release_support, "__version__", "2.0.0")
    with pytest.raises(ValueError, match="qualification"):
        release_support.stable_gate(Path(__file__).resolve().parents[1], "v2.0.0")


def test_final_build_policy_requires_evidence_but_permits_disclosed_unsigned(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(release_support, "__version__", "2.0.0")
    monkeypatch.setattr(release_support, "version_gate", lambda root, tag: None)
    monkeypatch.setattr(release_support, "stable_gate", lambda root, tag: calls.append(tag))
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "manual-qualification.json").write_text('{"unsigned_release_approved": false}')
    with pytest.raises(ValueError, match="Unsigned"):
        release_support.build_policy(
            tmp_path, installer=True, signed=False, stable=True, tag="v2.0.0", qualification=False
        )
    (docs / "manual-qualification.json").write_text('{"unsigned_release_approved": true}')
    release_support.build_policy(
        tmp_path, installer=True, signed=False, stable=True, tag="v2.0.0", qualification=False
    )
    assert calls == ["v2.0.0", "v2.0.0"]  # Approval never skips source/endurance gates.
    with pytest.raises(ValueError, match="Qualification"):
        release_support.build_policy(
            tmp_path, installer=True, signed=False, stable=True, tag="v2.0.0", qualification=True
        )
    release_support.build_policy(
        tmp_path, installer=False, signed=False, stable=False, tag="", qualification=True
    )


@pytest.mark.parametrize(
    "failure",
    [
        "duration",
        "resources",
        "source",
        "assets",
        "runtime",
        "truthy",
        "nan",
        "incomplete",
        "children",
        "worker_restart",
        "native_child",
        "chaos",
        "harness",
    ],
)
def test_stable_rejects_incomplete_or_changed_soak(tmp_path, monkeypatch, failure):
    root = Path(__file__).resolve().parents[1]
    for name in ["pyproject.toml", "packaging/installer.iss"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / name).read_bytes())
    docs = tmp_path / "docs"
    docs.mkdir()
    manual = json.loads((root / "docs/manual-qualification.json").read_text())
    manual["version"] = "2.0.0"
    manual["gates"] = dict.fromkeys(manual["gates"], True)
    (docs / "manual-qualification.json").write_text(json.dumps(manual))
    source = tmp_path / "src/desktranslate/example.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"qualified = True\n")
    harness = tmp_path / "tools/soak.py"
    harness.parent.mkdir()
    harness.write_bytes(b"qualified_harness = True\n")
    evidence = {
        "version": "2.0.0",
        "elapsed_s": 7200,
        "workload_passed": True,
        "source_unchanged": True,
        "resource_qualification": {"qualified": True},
        "source_hashes": {"example.py": hashlib.sha256(source.read_bytes()).hexdigest()},
        "python_version": platform.python_version(),
        "completed": True,
        "workers_closed": True,
        "remaining_children": 0,
        "mode": "steady",
        "session_restarts": 0,
        "continuous_worker_qualification": {"qualified": True},
        "harness_unchanged": True,
        "harness_sha256": hashlib.sha256(harness.read_bytes()).hexdigest(),
    }
    monkeypatch.setattr(release_support, "__version__", "2.0.0")
    (docs / "soak-2h.json").write_text(json.dumps(evidence))
    chaos = {**evidence, "mode": "chaos"}
    (docs / "soak-chaos.json").write_text(json.dumps(chaos))
    release_support.stable_gate(tmp_path, "v2.0.0")
    if failure == "duration":
        evidence["elapsed_s"] = 7199
    elif failure == "resources":
        evidence["resource_qualification"]["qualified"] = False
    elif failure == "source":
        source.write_bytes(b"qualified = False\n")
    elif failure == "assets":
        (source.parent / "new-asset.bin").write_bytes(b"unqualified")
    elif failure == "truthy":
        evidence["workload_passed"] = "false"
    elif failure == "nan":
        evidence["elapsed_s"] = float("nan")
    elif failure == "incomplete":
        evidence["completed"] = False
    elif failure == "children":
        evidence["remaining_children"] = 1
    elif failure == "worker_restart":
        evidence["session_restarts"] = 1
    elif failure == "native_child":
        evidence["continuous_worker_qualification"]["qualified"] = False
    elif failure == "chaos":
        chaos["completed"] = False
        (docs / "soak-chaos.json").write_text(json.dumps(chaos))
    elif failure == "harness":
        harness.write_bytes(b"modified_harness = True\n")
    else:
        evidence["python_version"] = "0.0.0"
    (docs / "soak-2h.json").write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="soak|source/assets|runtime"):
        release_support.stable_gate(tmp_path, "v2.0.0")


def test_resource_qualification_rejects_unavailable_or_impossible_measurements(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import soak

    samples = [
        {
            "elapsed_s": index * 30,
            "main": {
                "rss_bytes": 1000,
                "private_bytes": 1000,
                "handles": 10,
                "native_threads": 1,
                "tcp_connections": 0,
            },
            "subprocesses": 1,
            "python_threads": 4,
            "frame_queue": 1,
            "text_queue": 1,
            "event_queue": 2,
            "cache_entries": 2,
            "context_pairs": 0,
            "python_heap_bytes": 1000,
        }
        for index in range(70)
    ]
    assert soak.resource_gate(samples, 2100)["qualified"]
    samples[-1]["main"]["native_threads"] = None
    assert not soak.resource_gate(samples, 2100)["qualified"]
    samples[-1]["main"]["native_threads"] = 0
    assert not soak.resource_gate(samples, 2100)["qualified"]


def test_continuous_worker_measurements_reject_restart_growth_or_missing_native_data(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import soak

    samples = [
        {
            "elapsed_s": index * 30,
            "workers": [
                {
                    "pid": 123,
                    "rss_bytes": 1000,
                    "private_bytes": 1000,
                    "handles": 10,
                    "native_threads": 12,
                    "cpu_seconds": index,
                }
            ],
        }
        for index in range(240)
    ]
    assert soak.continuous_worker_gate(samples, 7200)["qualified"]
    assert not soak.continuous_worker_gate(samples, 3600)["qualified"]
    samples[-1]["workers"][0]["pid"] = 124
    assert not soak.continuous_worker_gate(samples, 7200)["qualified"]
    samples[-1]["workers"][0]["pid"] = 123
    samples[-1]["workers"][0]["private_bytes"] = None
    assert not soak.continuous_worker_gate(samples, 7200)["qualified"]
    for sample in samples[-10:]:
        sample["workers"][0]["private_bytes"] = 100 * 1024**2
    assert not soak.continuous_worker_gate(samples, 7200)["qualified"]


@pytest.mark.parametrize("gap", ["start", "middle", "end", "duplicate", "invalid"])
def test_endurance_requires_observations_across_entire_run(monkeypatch, gap):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import soak

    samples = [{"elapsed_s": index * 30} for index in range(61)]
    assert soak.observation_gate(samples, 1800)["qualified"]
    if gap == "start":
        samples = samples[10:]
    elif gap == "middle":
        del samples[20:30]
    elif gap == "end":
        samples = samples[:36]  # Actual failed run ended sampling at 1050 s.
    elif gap == "duplicate":
        samples[30]["elapsed_s"] = samples[29]["elapsed_s"]
    else:
        samples[30]["elapsed_s"] = float("nan")
    assert not soak.observation_gate(samples, 1800)["qualified"]
    assert not soak.resource_gate(samples, 1800)["qualified"]
    assert not soak.continuous_worker_gate(samples, 7200)["qualified"]


@pytest.mark.parametrize("mode,duration", [("chaos", 1800), ("steady", 7200)])
def test_endurance_command_fails_when_completed_workload_exceeds_resource_budget(
    monkeypatch, mode, duration
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import soak

    report = {
        "workload_passed": True,
        "requested_duration_s": duration,
        "mode": mode,
        "resource_qualification": {"qualified": True},
        "continuous_worker_qualification": {"qualified": True},
    }
    assert soak.command_passed(report)
    report["resource_qualification"]["qualified"] = False
    assert not soak.command_passed(report)
    report["resource_qualification"]["qualified"] = True
    if mode == "steady":
        report["continuous_worker_qualification"]["qualified"] = False
        assert not soak.command_passed(report)
