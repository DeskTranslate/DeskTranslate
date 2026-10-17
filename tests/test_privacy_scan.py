import hashlib
import importlib.metadata
import io

from tools.privacy_scan import scan_stream, signatures, vendor_metadata


def test_pem_marker_is_distinct_from_private_key_material():
    marker = b"-----BEGIN PRIVATE KEY-----"
    assert not scan_stream(io.BytesIO(marker), signatures())[0]
    assert (
        "credential_signature"
        in scan_stream(io.BytesIO(marker + b"\n" + b"A" * 128), signatures())[0]
    )


def test_token_signature_crosses_stream_boundary():
    body = b"x" * (1024 * 1024 - 10) + b"ghp_" + b"A" * 40
    assert "credential_signature" in scan_stream(io.BytesIO(body), signatures())[0]


def test_google_and_deepl_key_signatures_are_detected_without_echoing_keys():
    for token in (b"AI" + b"za" + b"a" * 35, b"a" * 32 + b":fx"):
        assert "credential_signature" in scan_stream(io.BytesIO(token), signatures())[0]


def test_vendor_metadata_never_exempts_application_source_or_changed_binaries():
    assert vendor_metadata("tree/src/desktranslate/app.py", "0" * 64, None) is None
    assert (
        vendor_metadata("app/_internal/shapely/_geos.cp312-win_amd64.pyd", "0" * 64, None) is None
    )


def test_published_bidi_build_path_requires_exact_wheel_binary(monkeypatch):
    distribution = importlib.metadata.distribution("python-bidi")
    path = distribution.locate_file("bidi/bidi.cp312-win_amd64.pyd")
    binary = path.read_bytes()
    digest = hashlib.sha256(binary).hexdigest()
    # The public wheel was built by upstream on a hosted Windows account. A
    # downstream hosted build must not mistake that unmodified metadata for a
    # developer's path. RECORD and exact binary equality are both required.
    monkeypatch.setenv("USERPROFILE", chr(92).join(("C:", "Users", "runner" + "admin")))
    assert "private_build_home" in scan_stream(io.BytesIO(binary), signatures())[0]
    location = "app/_internal/bidi/bidi.cp312-win_amd64.pyd"
    metadata = vendor_metadata(location, digest, None)
    assert metadata and metadata["package"] == "python-bidi"
    assert metadata["source_sha256"] == digest
    assert vendor_metadata(location, hashlib.sha256(binary + b"changed").hexdigest(), None) is None
    assert vendor_metadata("tree/src/app.py", digest, None) is None
    assert vendor_metadata("app/_internal/other/bidi.cp312-win_amd64.pyd", digest, None) is None
