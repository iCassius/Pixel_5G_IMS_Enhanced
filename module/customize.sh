#!/system/bin/sh
SKIPMOUNT=true
. "$MODPATH/compatibility.sh"
pixel_framework_eligible || abort 'Requires a supported Google Pixel and Android API 31 or later'
ui_print '- Maintainer: iCassius; original module: Sun_Dream'
ui_print '- Framework policy probes actual interfaces and parameter types'
ui_print '- Vendor: modem + file baseline; CarrierSettings: independent baseline'
ui_print '- Cross-model support is experimental; network capabilities need device validation'
set_perm_recursive "$MODPATH" 0 0 0755 0644
for script in post-fs-data.sh service.sh control.sh compatibility.sh early-modem.sh health.sh diagnose.sh action.sh; do
    set_perm "$MODPATH/$script" 0 0 0755
done
