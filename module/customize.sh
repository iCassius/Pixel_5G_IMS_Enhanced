#!/system/bin/sh
SKIPMOUNT=true
. "$MODPATH/compatibility.sh"
pixel_framework_eligible || abort '安装失败：仅适配 Google Pixel 10 全系列，实验性支持 Pixel 9 系列；要求 Android API 31 或以上。'
ui_print '- Maintainer: iCassius; original module: Sun_Dream'
ui_print '- Framework policy probes actual interfaces and parameter types'
ui_print '- 适配 Pixel 10 全系列；实验性支持 Pixel 9 系列（含 a、Fold）'
ui_print '- 不限制基带和系统原文件摘要；通信效果以对应手机与网络为准'
set_perm_recursive "$MODPATH" 0 0 0755 0644
for script in post-fs-data.sh service.sh control.sh compatibility.sh health.sh diagnose.sh action.sh; do
    set_perm "$MODPATH/$script" 0 0 0755
done
