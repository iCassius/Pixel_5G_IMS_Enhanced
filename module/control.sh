#!/system/bin/sh
# Public module-only entry point. No companion package or LSPosed dependency.
MODDIR=${0%/*}
ACTION=${1:-status}
PROFILE_FILE="$MODDIR/profile.conf"
case "$ACTION" in status) EXTRA=--status;; maintain|base|vcrbt) EXTRA=;; *) echo '[ERROR] Expected status|base|vcrbt' >&2; exit 1;; esac
LOCK="/dev/enable_pixel_5g_control.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    owner=$(cat "$LOCK/pid" 2>/dev/null)
    [ -z "$owner" ] && exit 75
    if [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null; then echo '[BUSY] Control already running' >&2; exit 75; fi
    rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null
    mkdir "$LOCK" 2>/dev/null || exit 75
fi
printf '%s\n' "$$" > "$LOCK/pid"
RUNDIR="/dev/enable_pixel_5g_helper_$$"
cleanup() { rm -f "$RUNDIR/override.dex" "$RUNDIR/policy.json" "$RUNDIR/status.json"; rmdir "$RUNDIR" 2>/dev/null; rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
# Read the current profile under the lock. A supervisor never writes its stale selection back.
PROFILE=base
[ -f "$PROFILE_FILE" ] && PROFILE=$(tr -d '\r\n' < "$PROFILE_FILE")
case "$PROFILE" in base|vcrbt) ;; *) echo '[ERROR] Invalid saved profile' >&2; exit 1;; esac
case "$ACTION" in base|vcrbt) PROFILE=$ACTION;; esac
hash_for() {
    awk -v key="\"$1\"" '$0 ~ key {block=1;next} block && /"sha256"/ {gsub(/.*"sha256"[[:space:]]*:[[:space:]]*"/, "");gsub(/".*/, "");print;exit}' "$MODDIR/manifest.json"
}
for node in override.dex policy.json compatibility.sh full-files.tsv; do
    expected=$(hash_for "$node")
    actual=$(sha256sum "$MODDIR/$node" 2>/dev/null | awk '{print $1}')
    if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then echo "[ERROR] Integrity failure: $node" >&2; exit 1; fi
done
mkdir "$RUNDIR" && chmod 0755 "$RUNDIR" || exit 1
for node in override.dex policy.json; do
    cp "$MODDIR/$node" "$RUNDIR/$node" && chmod 0444 "$RUNDIR/$node" && chcon u:object_r:system_file:s0 "$RUNDIR/$node" || exit 1
done
# Keep CDMA unchanged unless separately managed. Profile writes never clear unrelated overrides.
su 1000 -c "CLASSPATH=$RUNDIR/override.dex app_process /system/bin ApplyCarrierOverride --policy $RUNDIR/policy.json --profile $PROFILE $EXTRA" > "$RUNDIR/status.json"
result=$?
cat "$RUNDIR/status.json"
if [ "$result" -eq 0 ] && { [ "$ACTION" = base ] || [ "$ACTION" = vcrbt ]; }; then
    printf '%s\n' "$PROFILE" > "$PROFILE_FILE.new" && mv "$PROFILE_FILE.new" "$PROFILE_FILE" || exit 1
fi
exit "$result"
