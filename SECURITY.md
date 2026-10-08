# Security policy

DeskTranslate 2 beta is the actively developed line. The prototype 1.x does not receive security fixes here. This is a screen-capture application: keep reports free of confidential screenshots, dialogue, tokens and API keys.

Report vulnerabilities privately through [GitHub's vulnerability reporting](https://github.com/DeskTranslate/DeskTranslate/security/advisories/new) if available. If private reporting is unavailable, contact a listed maintainer through their public contact method; do not disclose credentials in a public issue. No response SLA is promised.

Keys must remain in an OS-native credential vault. Remote endpoints require verified HTTPS; provider redirects and URL credentials are rejected. Local HTTP is restricted to loopback. OCR resources must match pinned SHA-256 values. Memory/cache/queue/context limits and native OCR process isolation are security boundaries worth regression testing.

Binary hashes accompany releases, but this beta has no publisher code-signing certificate. Check that artifacts came from this repository. Build from source if organizational policy requires signed executables. See [privacy](docs/privacy.md) for data flows and cleanup.
