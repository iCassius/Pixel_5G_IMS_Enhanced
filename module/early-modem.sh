#!/system/bin/sh
# iCassius: read-only attestation of the one audited early modem selection.
# Invoked under a three-second timeout; stdout is an internal result enum only.
reject() { printf '%s\n' "$1"; exit 1; }
[ "${1:-}" = probe ] || reject early_invalid_action
[ "$(getprop ro.product.device)" = mustang ] || reject early_device_unverified
MODEM_VERSION=g5400i-260604-260807-B-16035863
[ "$(getprop ro.build.expect.baseband)" = "$MODEM_VERSION" ] || reject early_expected_version_mismatch
# Do not use this path for live hot-mounting or after a consumer may have started.
early_cbd_state=$(getprop init.svc.cpboot-daemon) || reject early_property_unreadable
early_zygote_state=$(getprop init.svc.zygote) || reject early_property_unreadable
early_boot_completed=$(getprop sys.boot_completed) || reject early_property_unreadable
case "$early_cbd_state" in ''|stopped) ;; *) reject early_window_closed;; esac
case "$early_zygote_state" in ''|stopped) ;; *) reject early_window_closed;; esac
[ "$early_boot_completed" != 1 ] || reject early_window_closed
early_namespace=$(readlink /proc/self/ns/mnt) || reject early_namespace_unverified
early_init_namespace=$(readlink /proc/1/ns/mnt) || reject early_namespace_unverified
[ -n "$early_namespace" ] && [ "$early_namespace" = "$early_init_namespace" ] || reject early_namespace_unverified
# Overrides/recovery may select a different image than the audited default.
for property in persist.vendor.cbd.modem_bin_path persist.vendor.modem.recovery.enabled vendor.modem.recovery.state; do
    early_override=$(getprop "$property") || reject early_property_unreadable
    [ -z "$early_override" ] || reject early_selection_override
done
early_bin_type=$(getprop vendor.cbd.modem_bin_type) || reject early_property_unreadable
case "$early_bin_type" in ''|2) ;; *) reject early_selection_override;; esac
early_radio_image=$(getprop telephony.TnNtn.image_switch) || reject early_property_unreadable
case "$early_radio_image" in ''|tn) ;; *) reject early_selection_override;; esac
early_path=$(getprop vendor.modem.bin.path) || reject early_property_unreadable
case "$early_path" in ''|/mnt/vendor/modem_img/images/default/modem.bin|/mnt/vendor/modem_img/images/default//modem.bin) ;; *) reject early_selection_override;; esac
early_slot=$(getprop ro.boot.slot_suffix)
case "$early_slot" in _a|_b) ;; *) reject early_slot_unverified;; esac
early_partition=$(getprop vendor.cbd.partition) || reject early_property_unreadable
# cbd.rc sets "modem" during fs; its slot-suffix property action runs AFTER
# post-fs-data. The actual mounted block device below is authoritative here.
case "$early_partition" in ''|modem|"modem$early_slot") ;; *) reject early_partition_property_conflict;; esac
early_block=$(readlink -f "/dev/block/by-name/modem$early_slot") || reject early_partition_unavailable
[ -b "$early_block" ] || reject early_partition_unavailable
[ "$(blockdev --getsize64 "$early_block")" = 314572800 ] || reject early_partition_size_mismatch
# Reject alternate filesystems, bind roots, writable mounts and nested overrides.
early_source=$(awk '
    $5=="/mnt/vendor/modem_img" {
        count++
        for(i=7;i<=NF;i++) if($i=="-" && $(i+1)=="ext4" && $4=="/" &&
            $6 ~ /(^|,)ro(,|$)/ && $(i+3) ~ /(^|,)ro(,|$)/) source=$(i+2)
    }
    index($5,"/mnt/vendor/modem_img/")==1 {nested=1}
    END {if(count!=1 || nested || source=="")exit 1; print source}
' /proc/self/mountinfo) || reject early_mount_unverified
[ "$(readlink -f "$early_source")" = "$early_block" ] || reject early_mounted_slot_mismatch
[ "$(readlink -f /mnt/vendor/modem_img/images/default/modem.bin)" = "/mnt/vendor/modem_img/images/$MODEM_VERSION/modem.bin" ] || reject early_image_path_unverified
check_hash() {
    # Use Android's accelerated SHA implementation for the 300 MiB partition.
    early_line=$(/system/bin/sha256sum "$1" 2>/dev/null) || reject "early_content_unreadable_$3"
    [ "${early_line%% *}" = "$2" ] || reject "early_content_unverified_$3"
}
# Whole active partition, not a remembered property or the directory name.
check_hash "$early_block" 772237701676d2485d5fa35ae111eaa3382d8288bdcbd2f298ca55b93d2af1b2 modem_partition
check_hash /mnt/vendor/modem_img/images/default/modem.bin 6e84cc9797c6281da41dda94009e566be1174ed3aa9267d94727ea28338aff7c modem_image
# Pin the observed selection program and boot instructions as part of this profile.
check_hash /vendor/bin/cbd 5d7d6cdd363a2735812f7ae47205b55c88d5a56f9db0ff02f8923b686795c4a9 cbd
check_hash /vendor/etc/init/cbd.rc a4b1e90dddf2c246da2d5a4d33d0356f25acb0f1593bcef8652b3df160200bf1 cbd_rc
check_hash /vendor/etc/fstab.modem c99236a10b2b97e3b637058ac18b04410de6d2c0e75697dd3012f35e61b448f8 modem_fstab
check_hash /vendor/etc/init/hw/init.laguna.rc 555ac2ec19840d36ee4760860b3d56ce42fac383fa99366f6c8e5d2193723a5a device_init_rc
printf 'verified_active_modem_partition\n'
