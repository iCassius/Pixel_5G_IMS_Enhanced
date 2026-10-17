#!/system/bin/sh
MODDIR=${0%/*}
# One supervisor per installed module. PID start time prevents PID reuse mistakes.
LOCK=/dev/enable_pixel_5g_supervisor.lock
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
if ! mkdir "$LOCK" 2>/dev/null; then
    owner=$(cat "$LOCK/pid" 2>/dev/null)
    recorded=$(cat "$LOCK/start" 2>/dev/null)
    case "$owner" in ''|*[!0-9]*) exit 0;; esac
    [ -n "$recorded" ] && [ "$recorded" = "$(start_time "$owner")" ] && exit 0
    [ -z "$recorded" ] && kill -0 "$owner" 2>/dev/null && exit 0
    rm -f "$LOCK/pid" "$LOCK/start"; rmdir "$LOCK" 2>/dev/null
    mkdir "$LOCK" 2>/dev/null || exit 0
fi
printf '%s\n' "$$" > "$LOCK/pid"
start_time "$$" > "$LOCK/start"
export PIXELIMS_SUPERVISOR_PID=$$
export PIXELIMS_SUPERVISOR_START=$(start_time "$$")
reason=supervisor_stopped
health() {
    if ! sh "$MODDIR/health.sh" "$1" "$2" > /dev/null 2> "$MODDIR/health.error"; then
        KSU_MODULE=EnablePixel5G /data/adb/ksud module config set --temp override.description '⚠️ 自检未完成 · 请查看 health.error' 2>/dev/null
    fi
}
cleanup() {
    health stopped "$reason"
    rm -f "$LOCK/pid" "$LOCK/start"; rmdir "$LOCK" 2>/dev/null
}
trap cleanup EXIT
trap 'exit 0' HUP INT TERM
health waiting boot_in_progress
# Verify before sourcing the platform gate.
expected=$(awk '/"compatibility.sh"/ {block=1;next} block && /"sha256"/ {gsub(/.*"sha256"[[:space:]]*:[[:space:]]*"/, "");gsub(/".*/, "");print;exit}' "$MODDIR/manifest.json")
actual=$(sha256sum "$MODDIR/compatibility.sh" 2>/dev/null | awk '{print $1}')
if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then reason=module_integrity_failed; exit 1; fi
. "$MODDIR/compatibility.sh"
pixel_framework_eligible || { reason=unsupported_platform; exit 0; }
waited=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    [ "$waited" -ge 180 ] && { reason=boot_wait_timeout; exit 1; }
    sleep 2; waited=$((waited+2))
done
delay=10
while [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; do
    if [ "$(service check carrier_config 2>/dev/null)" = 'Service carrier_config: found' ]; then
        # The helper validates the exact target SIM, readiness, idle state and all managed values.
        # No-op readback avoids repeated overrides and config-change loops.
        if timeout 45 sh "$MODDIR/control.sh" maintain > "$MODDIR/status.json.new" 2> "$MODDIR/service.error"; then
            if mv "$MODDIR/status.json.new" "$MODDIR/status.json"; then
                health checked framework_readback_completed
                delay=60
            else
                health failed status_record_write_failed
                delay=120
            fi
        else
            rm -f "$MODDIR/status.json.new"
            health failed framework_check_failed
            delay=$((delay*2)); [ "$delay" -gt 120 ] && delay=120
        fi
    else
        health waiting carrier_service_unavailable
        delay=10
    fi
    sleep "$delay"
done
reason=module_disabled_or_removed
