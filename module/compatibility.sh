#!/system/bin/sh
# Maintained by iCassius. Never source data supplied by the device as shell code.
pixel_framework_eligible() {
    [ "$(getprop ro.product.manufacturer)" = Google ] || return 1
    [ "$(getprop ro.product.brand)" = google ] || return 1
    case "$(getprop ro.product.model)" in
        'Pixel 6'|'Pixel 6 Pro'|'Pixel 6a'|'Pixel 7'|'Pixel 7 Pro'|'Pixel 7a'|\
        'Pixel 8'|'Pixel 8 Pro'|'Pixel 8a'|'Pixel 9'|'Pixel 9 Pro'|'Pixel 9 Pro XL'|'Pixel 9 Pro Fold'|'Pixel 9a'|\
        'Pixel 10'|'Pixel 10 Pro'|'Pixel 10 Pro XL'|'Pixel 10 Pro Fold'|'Pixel 10a'|\
        'Pixel 11'|'Pixel 11 Pro'|'Pixel 11 Pro XL'|'Pixel 11 Pro Fold'|'Pixel 11a') ;;
        *) return 1;;
    esac
    # DEX is built for API 31. There is no Android version ceiling.
    sdk=$(getprop ro.build.version.sdk)
    case "$sdk" in ''|*[!0-9]*) return 1;; esac
    [ "$sdk" -ge 31 ]
}
pixel_modem_matches() {
    getprop gsm.version.baseband | awk -F',' -v expected='g5400i-260604-260807-B-16035863' '
        { if (NF == 0) exit 1; for (i=1;i<=NF;i++) {gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i); if ($i != expected) exit 1} seen=1 }
        END {if (!seen) exit 1}'
}
pixel_vendor_identity() { pixel_modem_matches; }
pixel_product_identity() {
    [ "$(getprop ro.product.device)" = mustang ] &&
    [ "$(getprop ro.build.display.id)" = CP3A.260905.009 ] &&
    pixel_modem_matches
}
pixel_files_compatible() {
    requested_group=$1
    [ -s "$MODDIR/full-files.tsv" ] || return 1
    matched=0
    while IFS=' ' read -r group target accepted; do
        [ "$group" = "$requested_group" ] || continue
        [ -n "$target" ] && [ -n "$accepted" ] || return 1
        actual=$(sha256sum "$target" 2>/dev/null | awk '{print $1}')
        [ -n "$actual" ] || return 1
        case ",$accepted," in *",$actual,"*) ;; *) return 1;; esac
        matched=$((matched+1))
    done < "$MODDIR/full-files.tsv"
    [ "$matched" -eq 2 ]
}
