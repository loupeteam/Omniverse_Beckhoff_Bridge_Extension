"""Run the Beckhoff extension from a git clone without building wheels.

The extension declares `beckhoff-bridge` as a pip requirement and depends on
the framework extension `loupe.simulation.bridge`, which declares
`plc-bridge`. Kit's pipapi tries to import each requirement's module before it
calls pip and skips the install when the import works, so installing the
checkouts editable into Kit's own Python makes Kit use the working tree
directly: edit `beckhoff_bridge/src` and restart the app, no wheel build.

  beckhoff_bridge  beckhoff_bridge/ at this repo's root
  plc_bridge       plc_bridge/ of an Omni-Utils checkout, with --plc-bridge DIR
                   (leave it out when Omni-Utils' own tools/dev_link.py has
                   already installed it)

`pyads` is pulled in by beckhoff-bridge's own dependency list. Kit also needs
the framework extension: add the Omni-Utils checkout's `exts/` folder to the
app's extension search paths.

Usage:
    python tools/dev_link.py <kit build root | kit/python/python.exe> [--plc-bridge DIR]
    python tools/dev_link.py <...> --uninstall

The first form takes the folder that holds `kit/kit.exe` (a kit-app-template
`_build/<platform>/release`), a Kit SDK root, or the interpreter itself.
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BECKHOFF_BRIDGE = os.path.join(ROOT, "beckhoff_bridge")
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
    ap.add_argument("--plc-bridge", help="also install this plc_bridge/ checkout editable (Omni-Utils)")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove the editable install again (and plc-bridge with --plc-bridge)")
    args = ap.parse_args(argv)

    python = kit_python(args.kit)
    print("Kit Python: {}".format(python))

    if args.uninstall:
        cmd = [python, "-m", "pip", "uninstall", "-y", "beckhoff-bridge"]
        if args.plc_bridge:
            cmd.append("plc-bridge")
    else:
        sources = [BECKHOFF_BRIDGE] + ([os.path.abspath(args.plc_bridge)] if args.plc_bridge else [])
        for src in sources:
            if not os.path.isfile(os.path.join(src, "pyproject.toml")):
                sys.exit("no pyproject.toml at {}".format(src))
        # One pip call, so beckhoff-bridge's plc-bridge requirement resolves to the
        # checkout (or the copy already installed) and pip never asks an index for it.
        cmd = [python, "-m", "pip", "install"]
        for src in sources:
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
