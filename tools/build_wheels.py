"""Build the wheels the Beckhoff extension bundles until the packages are on PyPI.

The extension lists `plc-bridge` and `beckhoff-bridge` as pip requirements and
points pipapi's `archiveDirs` at `exts/loupe.simulation.beckhoff_bridge/wheels/`.
This script fills that folder from the local checkouts:

  plc_bridge       the Omni-Utils submodule under the extension
                   (exts/.../loupe/simulation/common/plc_bridge)
  beckhoff_bridge  beckhoff_bridge/ at the repo root

The archive has to hold everything the install needs: pipapi runs pip with
`--target`, which ignores packages already installed, and `--no-index`, so a
dependency missing from the folder fails the whole install (quietly, since
pipapi then falls back to the online index). beckhoff_bridge is therefore
built with its dependencies resolved, which also downloads `pyads` and
whatever it needs into the folder.

Run it before packaging the extension for a registry, and again after a
version bump. Wheels of the two Loupe packages already in the folder are
removed first, so a stale version cannot shadow the new one.

Usage:
    python tools/build_wheels.py [--out DIR] [--python EXE]

`--python` is the interpreter whose pip builds the wheels (the wheels are
pure Python, so any 3.10+ works; it defaults to the one running this script).
"""

import argparse
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "exts", "loupe.simulation.beckhoff_bridge")
PACKAGES = {
    "plc_bridge": os.path.join(EXT, "loupe", "simulation", "common", "plc_bridge"),
    "beckhoff_bridge": os.path.join(ROOT, "beckhoff_bridge"),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(EXT, "wheels"),
                    help="archive folder (default: the extension's wheels/)")
    ap.add_argument("--python", default=sys.executable, help="interpreter whose pip builds the wheels")
    args = ap.parse_args(argv)

    for name, src in PACKAGES.items():
        if not os.path.isfile(os.path.join(src, "pyproject.toml")):
            sys.exit("{}: no pyproject.toml at {}\n"
                     "(plc_bridge: run 'git submodule update --init' first)".format(name, src))
    os.makedirs(args.out, exist_ok=True)

    for name in PACKAGES:
        for old in glob.glob(os.path.join(args.out, name + "-*.whl")):
            os.remove(old)
            print("removed  {}".format(os.path.basename(old)))

    # plc_bridge has no dependencies. beckhoff_bridge is resolved against the
    # folder (so it takes the plc_bridge wheel just built) and the index for the
    # rest, which lands pyads and its dependencies in the folder as well.
    for name, src, deps in (
        ("plc_bridge", PACKAGES["plc_bridge"], False),
        ("beckhoff_bridge", PACKAGES["beckhoff_bridge"], True),
    ):
        print("building {} from {}{}".format(name, os.path.relpath(src, ROOT), " with dependencies" if deps else ""))
        cmd = [args.python, "-m", "pip", "wheel", "--wheel-dir", args.out]
        cmd += ["--find-links", args.out] if deps else ["--no-deps"]
        subprocess.run(cmd + [src], check=True, stdout=subprocess.DEVNULL)

    print("\n{}:".format(os.path.relpath(args.out, ROOT)))
    for whl in sorted(glob.glob(os.path.join(args.out, "*.whl"))):
        print("  " + os.path.basename(whl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
