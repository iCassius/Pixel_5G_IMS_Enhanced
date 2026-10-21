#!/system/bin/sh
# Maintained by iCassius. Never source data supplied by the device as shell code.
pixel_framework_eligible() {
    [ "$(getprop ro.product.manufacturer)" = Google ] || return 1
    [ "$(getprop ro.product.brand)" = google ] || return 1
    case "$(getprop ro.product.model)" in
        'Pixel 9'|'Pixel 9 Pro'|'Pixel 9 Pro XL'|'Pixel 9 Pro Fold'|'Pixel 9a'|\
        'Pixel 10'|'Pixel 10 Pro'|'Pixel 10 Pro XL'|'Pixel 10 Pro Fold'|'Pixel 10a') ;;
        *) return 1;;
    esac
    # DEX is built for API 31. There is no Android version ceiling.
    sdk=$(getprop ro.build.version.sdk)
    case "$sdk" in ''|*[!0-9]*) return 1;; esac
    [ "$sdk" -ge 31 ]
}
# Device-family selection is explicitly experimental. No firmware attestation.
pixel_mount_identity() {
    PIXEL_MODEM_EVIDENCE=model_family_policy
    pixel_framework_eligible || { PIXEL_COMPAT_REASON=unsupported_platform; return 1; }
    for pixel_consumer in cpboot-daemon zygote; do
        pixel_consumer_state=$(getprop "init.svc.$pixel_consumer") || { PIXEL_COMPAT_REASON=early_property_unreadable; return 1; }
        case "$pixel_consumer_state" in ''|stopped) ;; *) PIXEL_COMPAT_REASON=early_window_closed; return 1;; esac
    done
    pixel_boot_completed=$(getprop sys.boot_completed) || { PIXEL_COMPAT_REASON=early_property_unreadable; return 1; }
    [ "$pixel_boot_completed" != 1 ] || { PIXEL_COMPAT_REASON=early_window_closed; return 1; }
    pixel_namespace=$(readlink /proc/self/ns/mnt) || { PIXEL_COMPAT_REASON=early_namespace_unverified; return 1; }
    pixel_init_namespace=$(readlink /proc/1/ns/mnt) || { PIXEL_COMPAT_REASON=early_namespace_unverified; return 1; }
    [ -n "$pixel_namespace" ] && [ "$pixel_namespace" = "$pixel_init_namespace" ] || { PIXEL_COMPAT_REASON=early_namespace_unverified; return 1; }
    PIXEL_COMPAT_REASON=model_family_selected
}
pixel_files_compatible() {
    requested_group=$1
    PIXEL_COMPAT_TARGET=""; PIXEL_COMPAT_HASH=""
    PIXEL_COMPAT_REASON=file_table_unavailable
    [ -s "$MODDIR/full-files.tsv" ] || return 1
    matched=0
    while IFS=' ' read -r group target accepted; do
        [ "$group" = "$requested_group" ] || continue
        PIXEL_COMPAT_TARGET=$target
        PIXEL_COMPAT_REASON=target_missing_or_unreadable
        [ -f "$target" ] && [ -r "$target" ] || return 1
        matched=$((matched+1))
    done < "$MODDIR/full-files.tsv"
    PIXEL_COMPAT_REASON=file_table_invalid
    [ "$matched" -eq 2 ] || return 1
    PIXEL_COMPAT_REASON=target_files_present
}
