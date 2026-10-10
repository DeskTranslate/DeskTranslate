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


def test_vendor_metadata_never_exempts_application_source_or_changed_binaries():
    assert vendor_metadata("tree/src/desktranslate/app.py", "0" * 64, None) is None
    assert (
        vendor_metadata("app/_internal/shapely/_geos.cp312-win_amd64.pyd", "0" * 64, None) is None
    )
