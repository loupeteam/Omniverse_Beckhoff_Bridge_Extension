# Release 0.3.0: verification

Step 5.2 of [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Everything below
ran on 2026-10-08 against the `release/0.3.0` branches of the three repos. Each
is cut from `rc/0.3.0` and carries only the version bump to 0.3.0 and
documentation:

| Repo | Branch | Cut from | PR |
|---|---|---|---|
| Omni-Utils (OU) | `release/0.3.0` | `rc/0.3.0` at 51f8c82 | loupeteam/Omni-Utils#15 |
| Beckhoff bridge (BK) | `release/0.3.0` | `rc/0.3.0` at 95572f1 | #24 |
| B&R bridge (BR) | `release/0.3.0` | `rc/0.3.0` at 1009437 | loupeteam/Omniverse_BnR_Bridge_Extension#21 |

Nothing is merged to `main`, tagged or published. Steps 5.3 (architecture
review) and 5.4 (merge, tag, publish) are still open.

## Environment

- Windows 11; Python 3.12 and 3.11 from python.org. Python 3.10 runs only in CI.
- Kit 110.3.0, the kit-app-template build in the Moonlight sandbox
  (`D:\prj\Sandboxed\Moonlight\kit-app-template\_build\windows-x86_64\release`),
  Kit Python 3.12. Kit jobs ran one at a time.
- The libraries reached Kit as the bundled wheels (`tools/build_wheels.py` in
  each repo, all 0.3.0): no `dev_link`, nothing in Kit's own Python, except for
  row 10. The pipapi folders of the test apps still held the 0.3.0rc1 packages
  and were moved aside first, so every run installed 0.3.0 (finding 1).
- TwinCAT: this PC's usermode runtime `UmRT_Default` (AMS `127.0.0.1.1.1`)
  with the Moonlight PLC program, trial licence valid to 2026-10-15. A
  simulator; no real PLC was involved.
- ARsim: `test/AS Project` (AS 6.7.0.187, AR 6.7.6), built and deployed with
  the `bnr-build` skill to its own instance at simulation IP `127.0.0.3`,
  because another session's simulator held `127.0.0.1`. Its `LuxProg` still
  binds OMJSON to `127.0.0.1:8000`, and that worked from the `127.0.0.3`
  instance (`AR000.exe` from that instance owned the port).

## Matrix

| # | Check | Command | Result | Output excerpt |
|---|---|---|---|---|
| 1 | `plc_bridge` pytest on 3.12 and 3.11 | `pip install "./plc_bridge[test]"` (not editable) into a clean venv, then `pytest` in `plc_bridge/` | PASS | `104 passed in 7.18s` (3.12); `104 passed in 7.19s` (3.11) |
| 2 | `beckhoff_bridge` pytest on 3.12 and 3.11 | same, `beckhoff_bridge/` | PASS | `47 passed in 0.11s`; `47 passed in 0.08s` |
| 3 | `br_bridge` pytest on 3.12 and 3.11 | same, `br_bridge/` | PASS | `37 passed in 2.00s`; `37 passed in 1.96s` |
| 4 | The three libraries on Python 3.10 | CI only: `.github/workflows/*-bridge.yml`, matrix 3.10 and 3.12 | PASS on `rc/0.3.0`; the release PRs rerun it | last green runs on rc: OU 37676866898 (d2aa452), BK 37839221723 (9e89362), BR 37845364130 (1009437). The BK and BR release PRs resolve `plc-bridge>=0.3.0` only after OU#15 is merged into OU `rc/0.3.0`; until then their CI fails at install |
| 5 | OU Kit tests | `tools\kit_test.ps1 -Kit <kit>` | PASS | `Ran 39 tests ... OK`; pipapi: `install ... plc-bridge==0.3.0 --no-index --find-links=...\loupe.simulation.bridge\wheels` |
| 6 | BK Kit tests | `tools\kit_test.ps1 -Kit <kit> -Framework <OU>\exts` | PASS | `Ran 11 tests ... OK`; `[OK] All 2 tests processes returned 0.` |
| 7 | BR Kit tests | `tools\kit_test.ps1 -Kit <kit> -BridgeExts <OU>\exts` | PASS | `Ran 5 tests ... OK` |
| 8 | BK harness live on TwinCAT: a 0.2.x prim, a 0.3 prim, an unchanged 0.2.x script | `tools\kit_check\run.ps1 -Kit <kit> -Framework <OU>\exts` | PASS | `PLC1 legacy bus=192 neutral bus=192 on_sample=193 on_sample_main=142`; `PLC2 neutral bus=205 on_sample=205`; mirror, write-back, 0.2.x `write_variable`, write ack, disable/re-enable the extension; `OK -- all fix checks passed` |
| 9 | BR harness live on ARsim: a 0.3.0rc1 prim, a neutral prim, a 0.1.x script | `tools\kit_check\run.ps1 -Kit <kit> -BridgeExts <OU>\exts -Mode arsim` | PASS on the 2nd run; the 1st failed the rate check only | run 1: all functional checks passed, then `FAIL -- plc1_cb well below 50 Hz: 137 in 5.0s; br2_cb well below 50 Hz: 138 in 5.0s` (five ARsim instances on the PC). Run 2: `PLC1 ... on_sample=248`, `BR2 ... on_sample=248 on_sample_main=244 main_thread_only=True`, writes read back (`lreal` 1, `counter` 42, `counter2` 99), `restore ... ok=[True, True]`, `OK -- all fix checks passed` |
| 10 | Mixed stage: a legacy Beckhoff prim and a neutral B&R prim under one `System` | OU `tools\kit_check\run.ps1 -Kit <kit>` (`stages/mixed_test.usda`): TwinCAT plus the mock OMJSON server | PASS | `drivers {'beckhoff': True, 'br': True}`; `PLC1: legacy bus=249 neutral bus=249 Manager(legacy)=249`; `BR1: legacy bus=250 neutral bus=250`; `main_thread_only=True seq gaps=4`; B&R write-back as `TestProg:lreal`; autoConnect; `OK`. This harness registers the drivers itself, so the 0.3.0 wheels of `beckhoff-bridge`, `br-bridge`, `pyads` and `websockets` went into Kit's Python (`--no-deps`) for this run and came out again (`pip list` identical before and after) |
| 11 | Legacy-only stage | Moonlight's `stage\wolf_head.usda`: one `/PLC/PLC1` prim with only `beckhoff_bridge:*` attributes, driven by Moonlight's 0.2.x rig extension (row 12) | PASS | `component PLC1 from the stage -> runtimes: ['PLC1']`, `subscribed 9 symbols`, the prim read as driver `beckhoff` with its deprecation warning, live values and commands as in row 12 |
| 12 | Moonlight sandbox on the three extensions from these branches | `kit.exe moonlight_release.kit --exec tools\kit_plc_check.py --/persistent/loupe.simulation.beckhoff_bridge/ENABLE_COMMUNICATION=true`, where the `.kit` is Moonlight's built `moonlight_composer.kit` with its vendored 0.2.x bridge folder replaced by the BK, OU and BR release `exts` and `loupe.simulation.br_bridge` added | PASS with one import changed in Moonlight's check script; FAIL unchanged | unchanged: reads work, then `No module named 'loupe.simulation.common'` at `from loupe.simulation.common.RuntimeBase import get_stream_name` (finding 3). With that import taken from `BeckhoffBridge`: `write-request events seen: 13`, `jaw is now 34.967° after 1.4s`, `every axis matches rig.json after 1.4s`, gamepad claim and release, `OK -- live values arrived from the PLC and land inside every axis limit.` The rig extension (`BeckhoffBridge`, `Communication`, `global_variables`, `beckhoff_bridge:*`) ran unchanged |
| 13 | Packaged-wheel install path in Kit, no `dev_link` | rows 5 to 9 and 12: each extension's `wheels/`, fresh pipapi folders, nothing in Kit's Python | PASS for OU, BK and BR | `startup clean; plc_bridge ...\pip3-envs\default-3.12\plc_bridge, beckhoff_bridge ...\pip3-envs\default-3.12\beckhoff_bridge`; `beckhoff-bridge>=0.3.0,<0.4 --no-index --find-links=...\loupe.simulation.beckhoff_bridge\wheels` |
| 14 | Soak: 32 min on TwinCAT, the PLC dropped and restored once | see "Soak" | PASS: reconnect, no zombie workers. Memory: slow growth while data flows, see "Soak" | `samples PLC1 92634 PLC2 92645`; drop seen in 0.23 s; `Connected` 1.85 s / 2.09 s after the restart command; 2 workers at every one of 192 samples; 0 after the stage closed; working set 5,042 -> 5,047 -> 5,068 MB (1 / 10 / 31 min) |

## Soak

`tools/kit_check/soak.py` runs inside the BK harness's
app (`tools/kit_check/fixcheck.kit.template`, both release extensions, bundled
wheels) on `tools/kit_check/stages/beckhoff_test.usda`: PLC1 a 0.2.x prim with
five symbols, PLC2 a 0.3 prim with three, both at 50 Hz, USD mirror on. Every
10 s it logs samples per PLC, connection state, the `*-plc` worker threads and
its own working set; once a minute it queues a write to
`GVL_Moonlight.Command.Blend` on PLC2. An outside script logged the Kit process
every minute (working set, private bytes, threads, handles).

The drop: 10 minutes in, the TwinCAT system was switched to Config over ADS
(`write_control(ADSSTATE_RECONFIG)` on port 10000), left there 61 s, and
restarted into Run (`ADSSTATE_RESET`). The usermode runtime process itself kept
running; its PLC port 851 went away and came back.

| | Value |
|---|---|
| Duration | 1,920 s with both PLCs enabled (14:39:53 to 15:11:53 local) |
| Samples | PLC1 92,634, PLC2 92,645 (48.2 per second per PLC, outage included); `on_sample_main` 91,985 and 91,974 |
| Drop at 14:50:01.09 | first `Error Reading` at 14:50:01.18, `Disconnected` at 14:50:01.32 (0.23 s); then `Error Connecting: ... Target port not found (6)` about once a second per PLC (71 status events in 61 s) |
| Restore at 14:51:02.19 | `Connected` + `Reading OK`: PLC1 14:51:04.04 (1.85 s), PLC2 14:51:04.28 (2.09 s). TwinCAT itself reported Run at the next 5 s poll, 14:51:07 |
| Unplanned | at 14:40:18 one PLC2 read timed out (`ADSError: timeout elapsed (1861)`); both PLCs reconnected by themselves within 0.6 s |
| Worker threads | `['PLC1-plc', 'PLC2-plc']` at every one of the 192 samples, before, during and after the drop; Python threads 4 throughout. Disabling both kept their idle workers (by design: `stop()` ends them, `enabled = False` does not); closing the stage removed the components and left 0 workers, 2 Python threads |
| Kit process, start / mid / end | working set 5,042 / 5,052 / 5,068 MB (14:40:59 / 14:55:02 / 15:11:05); private 7,807 / 7,786 / 7,802 MB; threads 148 / 145 / 144; handles 2,753 / 2,749 / 2,748 |

Memory is not flat in the strict sense: while data flows the working set
grows about 1 MB a minute (5,047 to 5,068 MB over the 20 minutes after the
drop; private bytes 7,780 to 7,802 MB). Two control runs separate it:

| Run | Working set | Private bytes |
|---|---|---|
| Same app and stage, both PLCs left disabled, 12 min | 5,080 -> 5,069 MB (falls) | 7,894 -> 7,834 MB |
| Both PLCs enabled, mirror off (`bridge:MirrorToUsd = false`), 15 min | 5,042 -> 5,052 MB over the last 10 min | 7,748 -> 7,757 MB |

So the growth follows the data, at about 1 MB a minute for 100 samples a
second, with or without the mirror. A third run (mirror off, 8 min) traced
Python allocations with `tracemalloc` for 7 minutes: Python's traced heap grew
by 0.1 MB in total (largest site 10 KiB, in Kit's viewport widget; the
only bridge site in the top twelve is 1 KiB where `PlcRuntime` builds the
current `Sample`),
while the process grew about 4 MB (private 7,747 to 7,751 MB). The growth is
therefore native, not Python objects held by the bridge: candidates are the
carb message bus (four pushes per sample pair with `legacyBusNames` on) and
`TcAdsDll` under pyads. Not narrowed further.
Threads and handles stay flat. At this rate an 8-hour session grows by about
half a gigabyte on a 5 GB process; finding 5.

## Findings

1. **pipapi keeps an old library across an extension upgrade.** Kit's pipapi
   skips a requirement whose module imports, whatever its version. The test
   apps' pipapi folders still held `plc-bridge`, `beckhoff-bridge` and
   `br-bridge` 0.3.0rc1, and the 0.3.0 extensions would have run that rc1 code;
   the framework's exact `plc-bridge==0.3.0` pin is not checked either. Anyone
   who tried an rc build, and every later upgrade (0.3.0 to 0.3.1), meets the
   same. Recorded in the BK README; not fixed. Options: the framework and the
   vendor extensions compare `importlib.metadata.version()` with their pin at
   startup and log an error naming the folder to delete (catches it, adds code
   to three extensions); or the release notes tell users to delete
   `%LOCALAPPDATA%\ov\data\Kit\<app>\<version>\pip3-envs` when upgrading (no
   code, relies on people reading it).
2. **The BR harness rate check is load sensitive.** On a PC running five ARsim
   instances one run fell to 27 Hz and failed that check alone; the next read
   50 Hz. Not a bridge defect; the threshold is 60 % of nominal.
3. **Moonlight's `kit_plc_check.py` imports the removed submodule**
   (`loupe.simulation.common.RuntimeBase.get_stream_name`). Expected, and in
   BK `MIGRATION.md`; Moonlight changes that one import when it moves to 0.3.0.
   Its rig extension needs no change.
4. **Sparse arrays change shape on the bus.** A PLC that reads `Axes[2]` and
   `Axes[3]` but not `Axes[0]` gets `Axes = [None, None, {...}, {...}]` in its
   nested sample. carb cannot hold `None` in an event payload: it logs
   `Unknown type in sequence being written to item` per element (844 lines in
   row 8's 5 s) and a bus subscriber receives a dict keyed by index strings,
   `{'2': {...}, '3': {...}}`, instead of a list (checked by pushing such a
   payload through the message bus in Kit 110.3). 0.2.x padded arrays the same
   way, so this is not new in 0.3.0, and `on_sample`, `on_sample_main` and
   `latest()` get the real list. Not fixed in this run; loupeteam/Omni-Utils#16
   sends sparse arrays on the bus as dicts with string keys on purpose, which
   drops the warning (and the memory growth of finding 5).
5. **Memory grows about 1 MB a minute while data flows** (soak). Native, not
   Python (tracemalloc). Cause, found after this run: finding 4. carb cannot
   hold `None` in a bus payload, so every `None` that pads a sparse array
   logs `Unknown type in sequence being written to item` on every push (about
   200 warnings a second for the soak's PLC2 with neutral and legacy names),
   and Kit keeps the log lines. The fix is loupeteam/Omni-Utils#16: the bus
   sends sparse arrays as index-string dicts, as carb already delivered
   them. With it, growth fell from about 0.85 MB a minute to under 0.1 in a 15-minute
   soak on TwinCAT.
6. **TwinCAT dropped to Config by itself once.** At 15:57 the Windows event
   log shows `TwinCAT system stop completed` and a start into AdsState 15
   (Config) that nothing in this session issued (no XAE was running). It is the
   Moonlight PLC's known "loses its program some minutes later" behaviour, or
   another session. A run started after it read nothing; TwinCAT was restarted
   into Run (16:10) and that run repeated. The bridge kept reporting
   `Error Connecting ... (6)` and would have reconnected, as the soak shows.
7. OMJSON echoes a write to an unknown symbol as written; the driver catches it
   only when the symbol's last read failed. OMJSON is deprecated upstream and
   will not be fixed, so this stays (recorded in `br_bridge/README.md` and the
   B&R changelog).

## Not run

- Python 3.10 locally (not installed); CI covers it (row 4).
- A real PLC, by rule: only the local TwinCAT usermode runtime and ARsim.
- The window (`Loupe / PLC Bridge`) by hand; every run here is headless.

## Left for the release (5.4)

- Merge order: OU#15 into OU `rc/0.3.0` first, re-run BK and BR CI, then the
  BK and BR release PRs.
- Date the `[0.3.0] - Unreleased` changelog headings at the merge to `main`.
- Move `PLC_BRIDGE_REF` in the BK and BR workflows from `rc/0.3.0` to the
  Omni-Utils 0.3.0 tag. OU's publish workflow fires on `plc-bridge-v*`, not
  `v0.3.0`; decide which tag(s) to cut.
- Decide finding 1 before publishing.
