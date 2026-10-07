# Headless Kit check

Runs the extension inside a built Kit app without a window, opens a stage with
`/PLC` prims, and checks: startup, one daemon worker per PLC, the options
setter, data delivery (message bus, `on_sample`, `latest()`), the USD mirror,
write-back through `write:value`, write acknowledgement, and disconnect on
disable. Live mode needs a PLC; `inject` mode feeds synthetic data.

| File | Role |
|---|---|
| `kit_check.py` | the check, run inside Kit with `--exec`; reads `FIXCHECK_STAGE` and `FIXCHECK_MODE` |
| `fixcheck.kit.template` | a USD Composer app with the bridge as a dependency; `${FIXCHECK_EXTS}` and `${FIXCHECK_KIT_ROOT}` are filled in |
| `run.sh`, `run.ps1` | generate the `.kit` in a temp folder, run `kit.exe`, print the check's lines, exit 0 on `OK` |
| `stages/mirror_test.usda` | one `/PLC/PLC1` prim at `127.0.0.1.1.1` reading five `GVL_Moonlight.*` symbols |

## Running

You need a kit-app-template build (the folder holding `kit/kit.exe`, usually
`_build/windows-x86_64/release`) whose `extscache` has USD Composer's
extensions, and the extension's libraries in place: either the bundled wheels
(`python tools/build_wheels.py`) or the editable installs
(`python tools/dev_link.py <kit build root>`), see the root README.

```bash
# no PLC: synthetic data
tools/kit_check/run.sh --kit D:/kit-app-template/_build/windows-x86_64/release --mode inject

# live, against the PLC named in the stage
tools/kit_check/run.sh --kit D:/kit-app-template/_build/windows-x86_64/release --log live.log
```

```powershell
tools\kit_check\run.ps1 -Kit D:\kit-app-template\_build\windows-x86_64\release -Mode inject
```

Options: `--kit` / `-Kit` (required), `--exts` (default: this repo's `exts/`),
`--stage` (default: `stages/mirror_test.usda`), `--mode inject|live`, `--log`
(default: `kit_check.log` in the current folder). Each has an environment
variable fallback: `FIXCHECK_KIT_ROOT`, `FIXCHECK_EXTS`, `FIXCHECK_STAGE`,
`FIXCHECK_MODE`, `FIXCHECK_LOG`.

A run takes about 40 s and ends with `OK -- all fix checks passed` or
`FAIL -- ...`. Kit's exit code is 7 by design: the script quits the app and,
because `omni.kit.window.file` can cancel a headless quit on a dirty stage (the
mirror dirties it), forces the exit after 15 s. The launchers exit 0 on `OK`.

The live run expects the PLC program behind the stage's symbols
(`GVL_Moonlight.Command.*`, `GVL_Moonlight.Axes[i].ActualPosition`) at the
local TwinCAT runtime; edit the stage or pass another with `--stage` for a
different PLC.
