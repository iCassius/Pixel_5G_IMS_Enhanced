#!/system/bin/sh
SKIPMOUNT=true
. "$MODPATH/compatibility.sh"
pixel_framework_eligible || abort 'Requires Google Pixel 6-11 model / Android API 31-36; unknown versions fail closed'
ui_print '- Maintainer: iCassius; original module: Sun_Dream'
ui_print '- Unknown modem/build: framework-only, no vendor or PB mounts'
ui_print '- Cross-model support is experimental; network capabilities need device validation'
set_perm_recursive "$MODPATH" 0 0 0755 0644
for script in post-fs-data.sh service.sh control.sh compatibility.sh action.sh; do
    set_perm "$MODPATH/$script" 0 0 0755
done
