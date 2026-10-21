#!/system/bin/sh
SKIPMOUNT=true
. "$MODPATH/compatibility.sh"
pixel_framework_eligible || abort 'Requires Google Pixel 9/10 series and Android API 31 or later'
ui_print '- Maintainer: iCassius; original module: Sun_Dream'
ui_print '- Framework policy probes actual interfaces and parameter types'
ui_print '- Pixel 9/10 experimental: no baseband or original-file hash restriction'
ui_print '- Cross-model support is experimental; network capabilities need device validation'
set_perm_recursive "$MODPATH" 0 0 0755 0644
for script in post-fs-data.sh service.sh control.sh compatibility.sh health.sh diagnose.sh action.sh; do
    set_perm "$MODPATH/$script" 0 0 0755
done
