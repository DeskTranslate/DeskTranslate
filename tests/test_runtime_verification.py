from desktranslate.runtime_verification import verify_credentials


def test_vault_probe_reports_failed_cleanup_even_after_successful_roundtrip():
    class AuthoredVault:
        def set(self, account, value):
            self.value = value

        def get(self, account):
            return self.value

        def delete(self, account):
            raise OSError("This message must not be recorded")

    report = verify_credentials(AuthoredVault(), "temporary authored account")
    assert report["credential_roundtrip"] is True
    assert report["credential_cleanup"] is False
    assert report["credential_cleanup_error"] == "OSError"
    assert "This message" not in str(report)


def test_vault_probe_cleans_up_after_read_failure():
    class AuthoredVault:
        deleted = False

        def set(self, account, value):
            pass

        def get(self, account):
            raise OSError("Authored failure")

        def delete(self, account):
            self.deleted = True

    vault = AuthoredVault()
    report = verify_credentials(vault, "temporary authored account")
    assert vault.deleted and report["credential_cleanup"] is True
    assert report["credential_error"] == "OSError"
    assert "credential_roundtrip" not in report
