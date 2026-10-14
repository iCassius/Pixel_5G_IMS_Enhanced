#!/system/bin/sh
MODDIR=${0%/*}
. "$MODDIR/compatibility.sh"
pixel_framework_eligible || exit 0
# One supervisor per installed module. KernelSU owns its boot lifetime.
LOCK=/dev/enable_pixel_5g_supervisor.lock
if ! mkdir "$LOCK" 2>/dev/null; then
    owner=$(cat "$LOCK/pid" 2>/dev/null)
    [ -z "$owner" ] && exit 0
    [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null && exit 0
    rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null
    mkdir "$LOCK" 2>/dev/null || exit 0
fi
printf '%s\n' "$$" > "$LOCK/pid"
trap 'rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null' EXIT
trap 'exit 0' HUP INT TERM
waited=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    [ "$waited" -ge 180 ] && exit 1
    sleep 2; waited=$((waited+2))
done
delay=10
while [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; do
    if [ "$(service check carrier_config 2>/dev/null)" = 'Service carrier_config: found' ]; then
        profile=base
        [ -f "$MODDIR/profile.conf" ] && profile=$(tr -d '\r\n' < "$MODDIR/profile.conf")
        # The helper validates the exact target SIM, readiness, idle state and all managed values.
        # No-op readback avoids repeated overrides and config-change loops.
        if sh "$MODDIR/control.sh" "$profile" > "$MODDIR/status.json.new" 2> "$MODDIR/service.error"; then
            mv "$MODDIR/status.json.new" "$MODDIR/status.json"
            delay=60
        else
            rm -f "$MODDIR/status.json.new"
            delay=$((delay*2)); [ "$delay" -gt 120 ] && delay=120
        fi
    fi
    sleep "$delay"
done
