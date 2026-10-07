"""Run the Beckhoff extension from a git clone without building wheels.

The extension declares `plc-bridge` and `beckhoff-bridge` as pip requirements.
Kit's pipapi tries to import each requirement's module before it calls pip and
skips the install when the import works, so installing the two checkouts
editable into Kit's own Python makes Kit use the working tree directly: edit
`beckhoff_bridge/src` or the submodule and restart the app, no wheel build.

  plc_bridge       exts/loupe.simulation.beckhoff_bridge/loupe/simulation/common/plc_bridge
  beckhoff_bridge  beckhoff_bridge/

`pyads` is pulled in by beckhoff-bridge's own dependency list.

Usage:
    python tools/dev_link.py <kit build root | kit/python/python.exe>
    python tools/dev_link.py <...> --uninstall

The first form takes the folder that holds `kit/kit.exe` (a kit-app-template
`_build/<platform>/release`), a Kit SDK root, or the interpreter itself.
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "exts", "loupe.simulation.beckhoff_bridge")
PACKAGES = {
    "plc_bridge": os.path.join(EXT, "loupe", "simulation", "common", "plc_bridge"),
    "beckhoff_bridge": os.path.join(ROOT, "beckhoff_bridge"),
}
PIP_NAMES = ["plc-bridge", "beckhoff-bridge"]
EXE = "python.exe" if sys.platform == "win32" else "python3"


def kit_python(path):
    """Resolve a Kit build root, Kit SDK root or interpreter path to the interpreter."""
    path = os.path.abspath(path)
    if os.path.isfile(path):
        return path
    for candidate in (
        os.path.join(path, "kit", "python", EXE),          # kit-app-template build
        os.path.join(path, "kit", "python", "bin", EXE),   # same, Linux
        os.path.join(path, "python", EXE),                 # Kit SDK
        os.path.join(path, "python", "bin", EXE),
    ):
        if os.path.isfile(candidate):
            return candidate
    sys.exit("no Kit Python under {}: expected kit/python/{} or python/{}".format(path, EXE, EXE))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kit", help="Kit build root, Kit SDK root, or its python executable")
    ap.add_argument("--uninstall", action="store_true", help="remove the editable installs again")
    args = ap.parse_args(argv)

    python = kit_python(args.kit)
    print("Kit Python: {}".format(python))

    if args.uninstall:
        cmd = [python, "-m", "pip", "uninstall", "-y"] + PIP_NAMES
    else:
        for name, src in PACKAGES.items():
            if not os.path.isfile(os.path.join(src, "pyproject.toml")):
                sys.exit("{}: no pyproject.toml at {}\n"
                         "(plc_bridge: run 'git submodule update --init' first)".format(name, src))
        cmd = [python, "-m", "pip", "install"]
        for src in PACKAGES.values():
            cmd += ["-e", src]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

    if not args.uninstall:
        check = [python, "-c", "import plc_bridge, beckhoff_bridge; "
                               "print(plc_bridge.__file__); print(beckhoff_bridge.__file__)"]
        out = subprocess.run(check, check=True, capture_output=True, text=True).stdout
        print("\nKit's Python now imports:\n" + out)
        print("The extension's wheels/ folder is ignored while these are installed;\n"
              "run again with --uninstall to go back to the bundled wheels.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
