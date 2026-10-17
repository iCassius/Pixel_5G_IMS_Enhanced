#!/system/bin/sh
# Explicit readback only. The update button remains owned by the root manager.
MODDIR=${0%/*}
SNAPSHOT="$MODDIR/status.manual.$$"
trap 'rm -f "$SNAPSHOT"' EXIT
trap 'exit 1' HUP INT TERM
echo '正在只读检查配置和挂载，不会修改通信配置或重启进程。'
if timeout 45 sh "$MODDIR/control.sh" status > "$SNAPSHOT" 2> "$MODDIR/diagnose.error"; then
    mv "$SNAPSHOT" "$MODDIR/status.json" || exit 1
    sh "$MODDIR/health.sh" checked manual_readback > /dev/null || exit 1
else
    sh "$MODDIR/health.sh" failed framework_check_failed > /dev/null
    echo '配置检查未完成，请查看 diagnose.error。'
    exit 1
fi
sh "$MODDIR/health.sh" summary manual_readback
echo '结果仅代表挂载和配置检查；真实通话仍需验证。'
