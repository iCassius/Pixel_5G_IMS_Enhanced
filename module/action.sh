#!/system/bin/sh
# iCassius: open releases; downloading/installing updates belongs to the root manager.
MODDIR=${0%/*}
repository=$(cat "$MODDIR/update-repository" 2>/dev/null)
case "$repository" in
    *[!a-zA-Z0-9_./-]*|'') echo '[ERROR] Invalid update repository'; exit 1;;
esac
case "$repository" in */*) ;; *) echo '[ERROR] Missing repository owner'; exit 1;; esac
echo '请在 KernelSU 模块卡片点击更新；实验版本可在 GitHub Releases 手动下载。'
if ! /system/bin/am start --user current -a android.intent.action.VIEW -d "https://github.com/$repository/releases"; then
    echo "[ERROR] 无法打开浏览器：https://github.com/$repository/releases"
    exit 1
fi
