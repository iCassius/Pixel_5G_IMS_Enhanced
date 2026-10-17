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
    PIXEL_COMPAT_REASON=modem_read_failed
    pixel_baseband=$(getprop gsm.version.baseband) || return 1
    PIXEL_COMPAT_REASON=modem_unavailable
    [ -n "$pixel_baseband" ] || return 1
    PIXEL_COMPAT_REASON=modem_unverified
    printf '%s\n' "$pixel_baseband" | awk -F',' -v expected='g5400i-260604-260807-B-16035863' '
        { if (NR != 1 || NF == 0) exit 1; for (i=1;i<=NF;i++) {gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i); if ($i != expected) exit 1} seen=1 }
        END {if (!seen) exit 1}' || return 1
    PIXEL_COMPAT_REASON=verified
}
pixel_vendor_identity() { pixel_modem_matches; }
# Exact file hashes gate each group; matching content needs no build-number guess.
pixel_product_identity() { pixel_modem_matches; }
pixel_mount_identity() {
    PIXEL_MODEM_EVIDENCE=none
    # Refuse live re-execution, even if the runtime version has since appeared.
    for pixel_consumer in cpboot-daemon zygote; do
        pixel_consumer_state=$(getprop "init.svc.$pixel_consumer") || { PIXEL_COMPAT_REASON=early_property_unreadable; return 1; }
        case "$pixel_consumer_state" in ''|stopped) ;; *) PIXEL_COMPAT_REASON=early_window_closed; return 1;; esac
    done
    pixel_boot_completed=$(getprop sys.boot_completed) || { PIXEL_COMPAT_REASON=early_property_unreadable; return 1; }
    if [ "$pixel_boot_completed" = 1 ]; then PIXEL_COMPAT_REASON=early_window_closed; return 1; fi
    if pixel_modem_matches; then
        PIXEL_MODEM_EVIDENCE=runtime_property
        return 0
    fi
    # A conflicting/nonempty runtime version always wins: never fall back around it.
    [ "$PIXEL_COMPAT_REASON" = modem_unavailable ] || return 1
    early_result=$(timeout 3 sh "$MODDIR/early-modem.sh" probe 2>/dev/null)
    early_rc=$?
    if [ "$early_rc" -eq 0 ] && [ "$early_result" = verified_active_modem_partition ]; then
        PIXEL_MODEM_EVIDENCE=verified_active_modem_partition
        PIXEL_COMPAT_REASON=verified
        return 0
    fi
    case "$early_result" in early_[a-z_]*) PIXEL_COMPAT_REASON=$early_result;; *) PIXEL_COMPAT_REASON=early_probe_failed_or_timed_out;; esac
    return 1
}
pixel_files_compatible() {
    requested_group=$1
    PIXEL_COMPAT_TARGET=""; PIXEL_COMPAT_HASH=""
    PIXEL_COMPAT_REASON=file_table_unavailable
    [ -s "$MODDIR/full-files.tsv" ] || return 1
    matched=0
    while IFS=' ' read -r group target accepted; do
        [ "$group" = "$requested_group" ] || continue
        PIXEL_COMPAT_TARGET=$target; PIXEL_COMPAT_HASH=""
        PIXEL_COMPAT_REASON=file_table_invalid
        [ -n "$target" ] && [ -n "$accepted" ] || return 1
        PIXEL_COMPAT_REASON=target_missing
        [ -f "$target" ] || return 1
        PIXEL_COMPAT_REASON=target_read_failed
        digest_line=$(sha256sum "$target" 2>/dev/null) || return 1
        actual=${digest_line%% *}
        PIXEL_COMPAT_HASH=$actual
        [ "${#actual}" -eq 64 ] || return 1
        case "$actual" in *[!0-9a-f]*) return 1;; esac
        PIXEL_COMPAT_REASON=target_hash_unverified
        case ",$accepted," in *",$actual,"*) ;; *) return 1;; esac
        matched=$((matched+1))
    done < "$MODDIR/full-files.tsv"
    PIXEL_COMPAT_REASON=file_table_invalid
    [ "$matched" -eq 2 ] || return 1
    PIXEL_COMPAT_REASON=verified
}
