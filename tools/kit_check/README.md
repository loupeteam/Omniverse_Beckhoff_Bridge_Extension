# Headless Kit check

Runs the extension inside a built Kit app without a window, opens a stage with
`/PLC` prims, and checks: startup, one daemon worker per PLC, the options
setter, data delivery (message bus, `on_sample`, `latest()`), the USD mirror,
write-back through `write:value`, write acknowledgement, and disconnect on
disable. Live mode needs a PLC; `FIXCHECK_MODE=inject` feeds synthetic data.

Today it is wired to the Moonlight sandbox (`D:\prj\Sandboxed\Moonlight`);
`run.sh` carries those paths and `fixcheck.kit.template` is that app's `.kit`
with the extension folder taken from `FIXCHECK_EXTS`. Phase 1 of
`docs/IMPLEMENTATION_PLAN.md` generalises it.

```bash
FIXCHECK_STAGE=tools/kit_check/stages/mirror_test.usda FIXCHECK_MODE=inject bash tools/kit_check/run.sh <exts folder> out.log
```
