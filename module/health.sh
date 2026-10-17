#!/system/bin/sh
# Read-only phone/config collector. Only health records and temporary card text are written.
MODDIR=${0%/*}
PHASE=${1:-waiting}
REASON=${2:-check_pending}
case "$PHASE" in checked|failed|waiting|stopped|inspect|summary|probe) ;; *) exit 2;; esac
LOCK=/dev/enable_pixel_5g_health.lock
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
if ! mkdir "$LOCK" 2>/dev/null; then
    owner=$(cat "$LOCK/pid" 2>/dev/null)
    saved=$(cat "$LOCK/start" 2>/dev/null)
    case "$owner" in ''|*[!0-9]*) exit 75;; esac
    actual_start=$(start_time "$owner")
    if kill -0 "$owner" 2>/dev/null; then
        [ -z "$saved" ] || [ -z "$actual_start" ] || [ "$saved" = "$actual_start" ] && exit 75
    fi
    rm -f "$LOCK/pid" "$LOCK/start"; rmdir "$LOCK" 2>/dev/null
    mkdir "$LOCK" 2>/dev/null || exit 75
fi
printf '%s\n' "$$" > "$LOCK/pid"
start_time "$$" > "$LOCK/start"
RUNDIR=/dev/enable_pixel_5g_health_$$
cleanup() { rm -f "$RUNDIR/override.dex"; rmdir "$RUNDIR" 2>/dev/null; rm -f "$LOCK/pid" "$LOCK/start"; rmdir "$LOCK" 2>/dev/null; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
hash_for() {
    awk -v key="\"$1\"" '$0 ~ key {block=1;next} block && /"sha256"/ {gsub(/.*"sha256"[[:space:]]*:[[:space:]]*"/, "");gsub(/".*/, "");print;exit}' "$MODDIR/manifest.json"
}
# Never execute an unverified root collector. Do not rewrite manifest-covered module.prop.
for node in override.dex health.sh; do
    expected=$(hash_for "$node")
    actual=$(sha256sum "$MODDIR/$node" 2>/dev/null | awk '{print $1}')
    [ -n "$expected" ] && [ "$expected" = "$actual" ] || {
        if [ "$PHASE" != probe ] && [ "$PHASE" != inspect ] && [ "$PHASE" != summary ]; then
            KSU_MODULE=EnablePixel5G /data/adb/ksud module config set --temp override.description '❌ 自检文件异常 · 无法确认当前状态' 2>/dev/null
        fi
        exit 1
    }
done
mkdir "$RUNDIR" && chmod 0700 "$RUNDIR" || exit 1
cp "$MODDIR/override.dex" "$RUNDIR/override.dex" || exit 1
[ "$(sha256sum "$RUNDIR/override.dex" | awk '{print $1}')" = "$(hash_for override.dex)" ] || exit 1
CLASSPATH="$RUNDIR/override.dex" timeout 30 app_process /system/bin ModuleHealth "$MODDIR" "$PHASE" "$REASON"
