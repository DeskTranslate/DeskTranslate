# Upgrading and retaining your data

## DeskTranslate 1.x

Archived 1.x source at `a687ad4` reads language CSVs as catalogs and keeps selection, languages, and appearance in memory. It has no persisted user-preference schema to migrate. Those CSVs are not saved user preferences. V2 starts with a new settings file and setup guide, preserves v1's translation target coverage, and offers optional Tesseract sources separately from managed OCR.

The published1.1a package identifies itself as InstallForge1.4.4 and requires separately configured Tesseract. The v2 per-user Inno product identity is different. V2 does not silently uninstall the old application, modify its startup entries, delete its files, or remove Tesseract/traineddata. Install v2 separately, qualify your workflow, and remove the old application through its Windows uninstall entry when ready. Physical 1.1a-to-v2 installation/uninstall in a clean account remains NOT TESTED; beta-to-candidate reinstall is not a substitute.

V1 Pons/Linguee/MyMemory scraping choices and blocking speech are not retained as supported v2 adapters. V2 offers the documented conventional/AI providers. Speech remains deferred. These are deliberate compatibility limits, rather than successful migration claims.

## V2 reinstall and future upgrades

Installed builds keep settings/models/logs in `%LOCALAPPDATA%\DeskTranslate`, outside the program directory. Reinstall replaces the managed runtime, including obsolete files, and retains data. Cleanup refuses unrecognized runtimes and directory links/junctions. Uninstall removes program files and its registry entry; settings/models remain for reinstall. Remove the data directory yourself only when you want to erase it. Delete keys through the app or Windows Credential Manager.

Portable builds use `DeskTranslateData` beside the executable. Retain that folder when extracting a newer archive. Keep `portable-mode`: it selects portable isolation. Keys remain per-user in Windows Credential Manager and are not transported in the ZIP.

Prototype schema 1 settings migrate only validated source/target choices. Unknown or secret fields are discarded rather than backed up. Damaged or unsupported configuration is retained on disk while temporary defaults run in memory. Automatic saves refuse to overwrite it. Review it privately or explicitly choose Reset settings in Preferences. Reset retains currently readable profiles and keys; it does not claim to recover malformed profile data.

Provider, recognition, appearance, language, and preference Apply actions activate configuration only after a successful write. Disk/permissions errors stay visible. Profile import/export excludes keys; portable profile import strips capture identity and requires fresh local consent.
