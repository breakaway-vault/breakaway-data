"""Build the standalone app with PyInstaller (used by .github/workflows/release.yml; works locally too).

    python -m pip install pyinstaller -r requirements.txt
    python scripts/build_app.py            # -> dist/Breakaway-Archive-<os>.zip

The app is one file. A zipped copy of data/ is bundled inside it; on first run it is unpacked into a data/
folder next to the app, and from then on that folder is used (so people can update it with fetch/add, or
drop in a newer data/ from the repo).
"""
import os, platform, shutil, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD, DIST = os.path.join(ROOT, "build"), os.path.join(ROOT, "dist")
OSNAME = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
EXE = "breakaway.exe" if OSNAME == "windows" else "breakaway"

README_FIRST = """NHL BREAKAWAY HIGHLIGHT ARCHIVE - standalone app ({os})
Unofficial fan tool, provided AS IS with no warranty. Use at your own risk. See LICENSE.txt.
No Python needed.

START
  {start}
  A window opens with a numbered menu: get covers, get videos, build the spreadsheet,
  open the viewer, make a printable album, add a missing moment, verify, help pin.
  Everything it makes goes into the "output" folder next to the app.
  The first run unpacks the archive data into a "data" folder next to the app (about 50 MB).

SECURITY WARNINGS (the app is not code-signed, so your computer will warn you once)
  Windows: "Windows protected your PC" -> click "More info" -> "Run anyway".
  macOS:   "cannot be opened because the developer cannot be verified" -> right-click (or
           Control-click) the app -> Open -> Open. If that doesn't appear: System Settings ->
           Privacy & Security -> "Open Anyway".
  Linux:   if it won't start, run:  chmod +x breakaway  then  ./breakaway

ADVANCED
  Every command also works from a terminal, e.g.  {cmd} album --player "Ovechkin" --layout 3x3
  {cmd} --help lists all options. Settings can go in breakaway.config.json next to the app.
  To update the data, replace the data folder with a newer one from the project's GitHub page,
  or use menu option 6 to add a moment.

Personal, archival use only. Don't repost the images or videos. Not affiliated with or endorsed by
the NHL, NHLPA, NHLAA, Sweet (SocialSweet Inc.) or any team. All trademarks, names, logos, videos
and images belong to their respective owners.
"""


def main():
    shutil.rmtree(BUILD, ignore_errors=True); os.makedirs(BUILD); os.makedirs(DIST, exist_ok=True)
    dz = os.path.join(BUILD, "data.zip")
    with zipfile.ZipFile(dz, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for d, _, fs in os.walk(os.path.join(ROOT, "data")):
            for f in fs:
                fp = os.path.join(d, f); z.write(fp, os.path.relpath(fp, ROOT))
    sep = ";" if OSNAME == "windows" else ":"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
                    "--name", "breakaway", "--distpath", os.path.join(BUILD, "app"), "--workpath", os.path.join(BUILD, "work"),
                    "--specpath", BUILD, "--add-data", f"{dz}{sep}.",
                    "--collect-submodules", "reportlab", "--hidden-import", "openpyxl", "--hidden-import", "PIL.Image",
                    os.path.join(ROOT, "breakaway.py")], check=True)
    out = os.path.join(DIST, f"Breakaway-Archive-{OSNAME}.zip")
    start = {"windows": "Double-click breakaway.exe.",
             "macos": "Double-click breakaway (first time: right-click -> Open, see below). It opens in Terminal.",
             "linux": "Double-click breakaway, or in a terminal:  ./breakaway"}[OSNAME]
    cmd = EXE if OSNAME == "windows" else "./breakaway"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo(f"Breakaway-Archive/{EXE}"); info.external_attr = 0o100755 << 16   # keep it executable
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, open(os.path.join(BUILD, "app", EXE), "rb").read())
        ri = zipfile.ZipInfo("Breakaway-Archive/README-FIRST.txt"); ri.external_attr = 0o100644 << 16; ri.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(ri, README_FIRST.format(os=f"{OSNAME}, {platform.machine()}", start=start, cmd=cmd))
        lic = os.path.join(ROOT, "LICENSE")
        if os.path.exists(lic): z.write(lic, "Breakaway-Archive/LICENSE.txt")
    print(f"Built {out} ({os.path.getsize(out)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
