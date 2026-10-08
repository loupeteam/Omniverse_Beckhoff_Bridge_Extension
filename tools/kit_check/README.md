# Headless Kit check

Runs the extension with the framework (`loupe.simulation.bridge`) inside a
built Kit app without a window, opens a stage with a 0.2.x PLC prim
(`beckhoff_bridge:*`) and a 0.3 prim (`bridge:driver = "beckhoff"`), and checks:
both extensions start; this extension registers `AdsDriver` as `beckhoff`; both
prims become runtimes, one daemon worker each; an unchanged 0.2.x script
(`BeckhoffBridge.Manager("PLC1")`) gets its deprecation warning, its data on the
0.2.x bus names and its writes through; `Manager()` without a name raises; data
at the refresh rate on the legacy and neutral bus, `on_sample`, `on_sample_main`
(main thread) and `latest()`; the USD mirror and write-back through
`write:value`; write acknowledgement; disconnect on disable; and disabling the
extension removes its PLCs, enabling it brings them back. Live mode needs a
PLC; `inject` mode registers an in-memory driver under `beckhoff` instead.

| File | Role |
|---|---|
| `kit_check.py` | the check, run inside Kit with `--exec`; reads `FIXCHECK_STAGE` and `FIXCHECK_MODE` |
| `fixcheck.kit.template` | a USD Composer app with the bridge as a dependency; `${FIXCHECK_EXTS}`, `${FIXCHECK_FRAMEWORK_EXTS}` and `${FIXCHECK_KIT_ROOT}` are filled in |
| `run.sh`, `run.ps1` | generate the `.kit` in a temp folder, run `kit.exe`, print the check's lines, exit 0 on `OK` |
| `stages/beckhoff_test.usda` | `/PLC/PLC1` in the 0.2.x form and `/PLC/PLC2` in the 0.3 form, both at `127.0.0.1.1.1`, reading `GVL_Moonlight.*` symbols |

## Running

You need a kit-app-template build (the folder holding `kit/kit.exe`, usually
`_build/windows-x86_64/release`) whose `extscache` has USD Composer's
extensions, an Omni-Utils checkout for the framework extension (its `exts/`
folder; default `../Omni-Utils/exts` next to this repo), and the libraries in
place: either the editable installs
(`python tools/dev_link.py <kit build root> --plc-bridge <Omni-Utils>/plc_bridge`)
or the bundled wheels, see the root README.

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
`--framework` / `-Framework` (an Omni-Utils `exts/` folder), `--stage` (default:
`stages/beckhoff_test.usda`), `--mode inject|live`, `--log` (default:
`kit_check.log` in the current folder). Each has an environment variable
fallback: `FIXCHECK_KIT_ROOT`, `FIXCHECK_EXTS`, `FIXCHECK_FRAMEWORK_EXTS`,
`FIXCHECK_STAGE`, `FIXCHECK_MODE`, `FIXCHECK_LOG`.

A run takes about 40 s and ends with `OK -- all fix checks passed` or
`FAIL -- ...`. Kit's exit code is 7 by design: the script quits the app and,
because `omni.kit.window.file` can cancel a headless quit on a dirty stage (the
mirror dirties it), forces the exit after 15 s. The launchers exit 0 on `OK`.

The live run expects the PLC program behind the stage's symbols
(`GVL_Moonlight.Command.*`, `GVL_Moonlight.Axes[i].ActualPosition`) at the
local TwinCAT runtime, in Run; it writes `GVL_Moonlight.Command.Blend`. The
50 Hz rate check is loose (60 % of the nominal sample count) but a second Kit
or other heavy load on the machine can still push it under; edit the stage or pass another with `--stage` for a
different PLC.
