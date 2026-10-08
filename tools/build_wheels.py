"""Build the wheels the Beckhoff extension bundles until the packages are on PyPI.

The extension lists `beckhoff-bridge` as a pip requirement and points pipapi's
`archiveDirs` at `exts/loupe.simulation.beckhoff_bridge/wheels/`. This script
fills that folder from the local checkouts:

  beckhoff_bridge  beckhoff_bridge/ at the repo root
  plc_bridge       plc_bridge/ in an Omni-Utils checkout (--plc-bridge, the
                   PLC_BRIDGE_SRC environment variable, or ../Omni-Utils next
                   to this repo)

The framework extension (loupe.simulation.bridge) owns the plc-bridge pin and
installs it first, but beckhoff-bridge depends on it, so its wheel has to be
in this archive as well.

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
    python tools/build_wheels.py [--out DIR] [--python EXE] [--plc-bridge DIR]

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
DEFAULT_PLC_BRIDGE = os.environ.get("PLC_BRIDGE_SRC") or os.path.join(
    os.path.dirname(ROOT), "Omni-Utils", "plc_bridge")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(EXT, "wheels"),
                    help="archive folder (default: the extension's wheels/)")
    ap.add_argument("--python", default=sys.executable, help="interpreter whose pip builds the wheels")
    ap.add_argument("--plc-bridge", default=DEFAULT_PLC_BRIDGE,
                    help="plc_bridge/ of an Omni-Utils checkout (default: %(default)s)")
    args = ap.parse_args(argv)

    PACKAGES = {"plc_bridge": os.path.abspath(args.plc_bridge),
                "beckhoff_bridge": os.path.join(ROOT, "beckhoff_bridge")}
    for name, src in PACKAGES.items():
        if not os.path.isfile(os.path.join(src, "pyproject.toml")):
            sys.exit("{}: no pyproject.toml at {}\n"
                     "(plc_bridge: clone loupeteam/Omni-Utils and pass --plc-bridge)".format(name, src))
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
        print("building {} from {}{}".format(name, src, " with dependencies" if deps else ""))
        cmd = [args.python, "-m", "pip", "wheel", "--wheel-dir", args.out]
        cmd += ["--find-links", args.out] if deps else ["--no-deps"]
        subprocess.run(cmd + [src], check=True, stdout=subprocess.DEVNULL)

    print("\n{}:".format(args.out))
    for whl in sorted(glob.glob(os.path.join(args.out, "*.whl"))):
        print("  " + os.path.basename(whl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
