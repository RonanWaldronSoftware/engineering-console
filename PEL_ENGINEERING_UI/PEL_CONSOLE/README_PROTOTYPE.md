# PEL Engineering Console — revamp prototype

This is a **non-destructive front-end prototype** for the existing PEL Engineering UI installation. It does not replace or patch v0.7 or v0.11.

## What it provides

- Modern, consistent dark engineering-console UI
- Dashboard with counts for units, groups, audio and firmware
- Explicit first-class launch controls for **v0.7 and v0.11**
- Searchable unit browser
- Group browser
- Audio and firmware asset browser with hash-sidecar visibility
- Read-only diagnostics for missing required files, malformed `0...` network values, missing/mismatched SHA-256 sidecars, firmware-folder naming, and Unicode-escaped audio filenames
- Dynamic installation-path discovery instead of hard-coding `C:\PEL_ENGINEERING_UI`

## Run

Place this folder next to `PEL_ENGINEERING_UI`, then run:

```bat
run_console.bat
```

Or with Python 3:

```text
python pel_console.py --root C:\PEL_ENGINEERING_UI
```

Headless diagnostic mode:

```text
python pel_console.py --root C:\PEL_ENGINEERING_UI --diagnostics
```

## Important limitation

The supplied archive contains compiled PyInstaller applications, not the original `.py` application source. This console can improve the overall operator experience and safely orchestrate both existing versions, but changing the internal screens/workflows of v0.7 and v0.11 themselves requires the original source project.

## Recommended next phase with source code

Rebuild both product modes inside one shared application shell, with a common design system and service layer while preserving version-specific behaviour. Suggested modules: Dashboard, Units, Groups, Device Detail, Jobs, Network, Audio, Firmware, Diagnostics, Logs, and Settings. Risky operations should use clear pre-flight validation, progress, results, and recovery rather than modal-message-heavy flows.
