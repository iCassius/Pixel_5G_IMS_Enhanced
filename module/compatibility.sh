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
    case "$(getprop ro.build.version.sdk)" in 31|32|33|34|35|36) return 0;; *) return 1;; esac
}
pixel_full_identity() {
    [ "$(getprop ro.product.device)" = mustang ] &&
    [ "$(getprop ro.build.display.id)" = CP3A.260905.009 ] &&
    [ "$(getprop gsm.version.baseband)" = g5400i-260604-260807-B-16035863 ]
}
pixel_full_files() {
    [ -s "$MODDIR/full-files.tsv" ] || return 1
    while IFS=' ' read -r target accepted; do
        [ -n "$target" ] && [ -n "$accepted" ] || return 1
        actual=$(sha256sum "$target" 2>/dev/null | awk '{print $1}')
        [ -n "$actual" ] || return 1
        case ",$accepted," in *",$actual,"*) ;; *) return 1;; esac
    done < "$MODDIR/full-files.tsv"
}
