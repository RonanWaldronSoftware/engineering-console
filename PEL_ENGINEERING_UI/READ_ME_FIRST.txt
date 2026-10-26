PEL ENGINEERING UI — COMPLETE BUNDLE
====================================

Recommended setup
-----------------
1. Extract this ZIP directly to C:\
2. Confirm the resulting folder is:
       C:\PEL_ENGINEERING_UI
3. Double-click:
       C:\PEL_ENGINEERING_UI\START_PEL_CONSOLE.bat

Why C:\PEL_ENGINEERING_UI?
--------------------------
The existing compiled v0.7/v0.11 applications contain references to
C:\PEL_ENGINEERING_UI. The new console can find its own location, but keeping
this canonical path gives the legacy applications the environment they expect.

Included
--------
- Existing v0.7.1 application
- Existing v0.11.1 application
- Existing UNITS, GROUPS, audio and firmware data
- FTDI driver package
- New PEL Engineering Console (no Python installation required)
- Direct fallback launchers for v0.7 and v0.11

FTDI DLL change
---------------
The app-local ftd2xx.dll files beside the 64-bit onedir executables have been
replaced with the bundled x64 FTDI D2XX library (ftd2xx64.dll copied under the
name ftd2xx.dll).

The original x86 app-local copies are backed up here:
  PEL_CONSOLE\backups\v0.7_ftd2xx_32bit_original.dll
  PEL_CONSOLE\backups\v0.11_ftd2xx_32bit_original.dll

This does not install the Windows FTDI device driver. If a new PC does not
already have the driver, use the included CDM-v2.12.36.4-WHQL-Certified package.

Fallback
--------
If Windows policy blocks HTA/mshta on your organisation's machines, use:
  START_V0.7.bat
  START_V0.11.bat
The original applications remain present and independent of the console.
