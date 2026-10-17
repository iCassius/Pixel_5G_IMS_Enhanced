#!/system/bin/sh
# Public module-only entry point. No companion package or LSPosed dependency.
MODDIR=${0%/*}
ACTION=${1:-status}
case "$ACTION" in status) EXTRA=--status;; maintain|apply) EXTRA=;; *) echo '[ERROR] Expected status|maintain|apply' >&2; exit 1;; esac
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
cleanup() { rm -f "$RUNDIR/override.dex" "$RUNDIR/policy.json" "$RUNDIR/status.json" "$RUNDIR/boot-mount.json"; rmdir "$RUNDIR" 2>/dev/null; rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
hash_for() {
    awk -v key="\"$1\"" '$0 ~ key {block=1;next} block && /"sha256"/ {gsub(/.*"sha256"[[:space:]]*:[[:space:]]*"/, "");gsub(/".*/, "");print;exit}' "$MODDIR/manifest.json"
}
for node in override.dex policy.json compatibility.sh early-modem.sh full-files.tsv; do
    expected=$(hash_for "$node")
    actual=$(sha256sum "$MODDIR/$node" 2>/dev/null | awk '{print $1}')
    if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then echo "[ERROR] Integrity failure: $node" >&2; exit 1; fi
done
mkdir "$RUNDIR" && chmod 0755 "$RUNDIR" || exit 1
for node in override.dex policy.json; do
    cp "$MODDIR/$node" "$RUNDIR/$node" && chmod 0444 "$RUNDIR/$node" && chcon u:object_r:system_file:s0 "$RUNDIR/$node" || exit 1
done
# A snapshot for the system-UID helper; missing/stale observations remain unknown.
if [ -f "$MODDIR/boot-mount.json" ]; then
    cp "$MODDIR/boot-mount.json" "$RUNDIR/boot-mount.json" || exit 1
else
    printf '{}\n' > "$RUNDIR/boot-mount.json" || exit 1
fi
chmod 0444 "$RUNDIR/boot-mount.json" && chcon u:object_r:system_file:s0 "$RUNDIR/boot-mount.json" || exit 1
manifest_sha=$(sha256sum "$MODDIR/manifest.json" 2>/dev/null | awk '{print $1}')
case "$manifest_sha" in ''|*[!0-9a-f]*) exit 1;; esac
[ "${#manifest_sha}" -eq 64 ] || exit 1
# Manage communication parameters only; never select a video profile.
su 1000 -c "CLASSPATH=$RUNDIR/override.dex app_process /system/bin ApplyCarrierOverride --policy $RUNDIR/policy.json --boot-status $RUNDIR/boot-mount.json --manifest-sha256 $manifest_sha $EXTRA" > "$RUNDIR/status.json"
result=$?
cat "$RUNDIR/status.json"
exit "$result"
