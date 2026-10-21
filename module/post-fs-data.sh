#!/system/bin/sh
# ==============================================================================
# Pixel_5G_IMS_Enhanced - KernelSU / Magisk Early Boot Mount Script
# Experimental Pixel 9/10 family selection; payload integrity is still required
# Vendor and CarrierSettings groups require readable targets and intact payloads
# Note          : /dev mirror is an isolated workaround for namespace-specific unmounts
# ==============================================================================

MODDIR="$(dirname "$0")"
if [ "$MODDIR" = "." ] || [ -z "$MODDIR" ]; then
    MODDIR="$(pwd)"
fi
LOGFILE="$MODDIR/mount.log"
MANIFEST_FILE="$MODDIR/manifest.json"
MIRROR_DIR=""
MOUNTED_LIST=""
# iCassius: observations describe this boot, never authority to bypass firmware gates.
MOUNT_LOCK=/dev/enable_pixel_5g_mount.lock
mkdir "$MOUNT_LOCK" 2>/dev/null || exit 75
BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
case "$BOOT_ID" in *[!0-9a-f-]*) BOOT_ID="";; esac
MANIFEST_SHA=$(sha256sum "$MANIFEST_FILE" 2>/dev/null | awk '{print $1}')
case "$MANIFEST_SHA" in *[!0-9a-f]*) MANIFEST_SHA="";; esac
VENDOR_READY=0
PRODUCT_READY=0
VENDOR_REASON=not_checked
PRODUCT_REASON=not_checked
BOOT_RESULT=aborted
BOOT_REASON=precheck_incomplete
PIXEL_MODEM_EVIDENCE=none
FILE_1=not_attempted; FILE_2=not_attempted; FILE_3=not_attempted; FILE_4=not_attempted
write_boot_status() {
    boot_uptime=$(awk '{print $1}' /proc/uptime 2>/dev/null)
    case "$boot_uptime" in ''|*[!0-9.]*) boot_uptime=0;; esac
    # All interpolated strings are internal enums or restricted hexadecimal values.
    printf '{"schema":1,"bootId":"%s","manifestSha256":"%s","stage":"post-fs-data","uptimeSeconds":%s,"result":"%s","reason":"%s","modemEvidence":"%s","groups":{"vendor":{"eligible":%s,"reason":"%s"},"product":{"eligible":%s,"reason":"%s"}},"files":{"vendor_override/cfg.db":"%s","vendor_override/open_carrier_info.dat":"%s","product_override/others.pb":"%s","product_override/default.pb":"%s"}}\n' \
        "$BOOT_ID" "$MANIFEST_SHA" "$boot_uptime" "$BOOT_RESULT" "$BOOT_REASON" \
        "$PIXEL_MODEM_EVIDENCE" \
        "$VENDOR_READY" "$VENDOR_REASON" "$PRODUCT_READY" "$PRODUCT_REASON" \
        "$FILE_1" "$FILE_2" "$FILE_3" "$FILE_4" > "$MODDIR/boot-mount.json.new" &&
        mv "$MODDIR/boot-mount.json.new" "$MODDIR/boot-mount.json"
}
finish_boot() {
    boot_exit=$?
    trap - EXIT
    write_boot_status || { log_msg '[ERROR] Could not persist boot mount observation.'; boot_exit=1; }
    rmdir "$MOUNT_LOCK" 2>/dev/null
    exit "$boot_exit"
}
trap finish_boot EXIT

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [uptime=$(cut -d' ' -f1 /proc/uptime)] $1" >> "$LOGFILE"
}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === EnablePixel5G v2.6 post-fs-data started ===" > "$LOGFILE"
log_msg "[CONTEXT] namespace=$(readlink /proc/self/ns/mnt) ASH_STANDALONE=${ASH_STANDALONE:-unset} KSU_VER=${KSU_VER:-unset}"
write_boot_status || exit 1

# ------------------------------------------------------------------------------
# 1. Pixel 9/10 系列与开机阶段检查
# ------------------------------------------------------------------------------
# Check module integrity, device family and boot phase before preparing mounts.
# Reject corrupted guards/tables before sourcing or evaluating them.
for node in compatibility.sh full-files.tsv policy.json; do
    expected=$(awk -v key="\"$node\"" 'index($0,key) {block=1;next} block && /"sha256"/ {gsub(/.*"sha256"[[:space:]]*:[[:space:]]*"/, "");gsub(/".*/, "");print;exit}' "$MANIFEST_FILE" 2>/dev/null)
    actual=$(sha256sum "$MODDIR/$node" 2>/dev/null | awk '{print $1}')
    if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
        BOOT_REASON=integrity_failed
        log_msg "[ABORT] Integrity failure: $node; zero mounts."
        exit 1
    fi
done
. "$MODDIR/compatibility.sh"
if ! pixel_framework_eligible; then
    BOOT_RESULT=skipped; BOOT_REASON=unsupported_platform
    log_msg "[SKIP] Unsupported platform; no mounts or policy writes."
    exit 0
fi
MOUNT_IDENTITY_READY=0
# A framework-only package has no specialist files to select or image to attest.
if [ -s "$MODDIR/full-files.tsv" ]; then
    log_msg "[EARLY SELECTION] boot_slot='$(getprop ro.boot.slot_suffix)' cbd_partition='$(getprop vendor.cbd.partition)'"
    if pixel_mount_identity; then MOUNT_IDENTITY_READY=1; fi
else
    PIXEL_COMPAT_REASON=file_table_unavailable
fi
MOUNT_IDENTITY_REASON=$PIXEL_COMPAT_REASON
log_msg "[MOUNT SELECTION] reason=$MOUNT_IDENTITY_REASON evidence=$PIXEL_MODEM_EVIDENCE"
if [ "$MOUNT_IDENTITY_READY" -eq 1 ] && pixel_files_compatible vendor; then VENDOR_READY=1; fi
VENDOR_REASON=$PIXEL_COMPAT_REASON
log_msg "[VENDOR CHECK] reason=$VENDOR_REASON baseband='$(getprop gsm.version.baseband)' target='${PIXEL_COMPAT_TARGET:-}' sha256='${PIXEL_COMPAT_HASH:-}'"
PIXEL_COMPAT_TARGET=""; PIXEL_COMPAT_HASH=""
PIXEL_COMPAT_REASON=$MOUNT_IDENTITY_REASON
if [ "$MOUNT_IDENTITY_READY" -eq 1 ] && pixel_files_compatible product; then PRODUCT_READY=1; fi
PRODUCT_REASON=$PIXEL_COMPAT_REASON
log_msg "[PRODUCT CHECK] reason=$PRODUCT_REASON baseband='$(getprop gsm.version.baseband)' target='${PIXEL_COMPAT_TARGET:-}' sha256='${PIXEL_COMPAT_HASH:-}'"
log_msg "[SELECTED GROUPS] vendor=$VENDOR_READY product=$PRODUCT_READY"
if [ "$VENDOR_READY" -eq 0 ] && [ "$PRODUCT_READY" -eq 0 ]; then
    BOOT_RESULT=skipped; BOOT_REASON=no_eligible_group
    log_msg "[FRAMEWORK ONLY] No eligible payload group; see modem/file reasons above. Zero mounts."
    exit 0
fi

# ------------------------------------------------------------------------------
# 2. 定义映射路径、相对键名与镜像路径
# ------------------------------------------------------------------------------
mkdir -p /dev/enable_pixel_5g || exit 1
MIRROR_DIR=$(mktemp -d /dev/enable_pixel_5g/session.XXXXXX) || exit 1
REL_1="vendor_override/cfg.db"
ORIG_SRC_1="$MODDIR/$REL_1"
MIRROR_SRC_1="$MIRROR_DIR/$REL_1"
TGT_1="/vendor/firmware/carrierconfig/cfg.db"
CTX_1="u:object_r:vendor_fw_file:s0"

REL_2="vendor_override/open_carrier_info.dat"
ORIG_SRC_2="$MODDIR/$REL_2"
MIRROR_SRC_2="$MIRROR_DIR/$REL_2"
TGT_2="/vendor/etc/open_carrier_info.dat"
CTX_2="u:object_r:vendor_configs_file:s0"

REL_3="product_override/others.pb"
ORIG_SRC_3="$MODDIR/$REL_3"
MIRROR_SRC_3="$MIRROR_DIR/$REL_3"
TGT_3="/product/etc/CarrierSettings/others.pb"
CTX_3="u:object_r:system_file:s0"

REL_4="product_override/default.pb"
ORIG_SRC_4="$MODDIR/$REL_4"
MIRROR_SRC_4="$MIRROR_DIR/$REL_4"
TGT_4="/product/etc/CarrierSettings/default.pb"
CTX_4="u:object_r:system_file:s0"

# ------------------------------------------------------------------------------
# 3. 精确 mountinfo 字段解析、SHA256 与 manifest.json 完整性锚点核验 (R3 + B1)
# ------------------------------------------------------------------------------
is_target_mounted() {
    awk -v tgt="$1" '$5 == tgt { found=1; exit } END { exit !found }' /proc/self/mountinfo 2>/dev/null
}

set_file_state() {
    case "$1" in
        "$TGT_1") FILE_1=$2;; "$TGT_2") FILE_2=$2;;
        "$TGT_3") FILE_3=$2;; "$TGT_4") FILE_4=$2;;
    esac
}

get_sha256() {
    sha256sum "$1" 2>/dev/null | awk '{print $1}'
}

get_manifest_expected_sha256() {
    _rel="$1"
    awk -v key="\"$_rel\"" '
        $0 ~ key { in_block=1; next }
        in_block && $0 ~ /"sha256"/ {
            gsub(/.*"sha256"[[:space:]]*:[[:space:]]*"/, "", $0)
            gsub(/".*/, "", $0)
            print $0
            exit
        }
    ' "$MANIFEST_FILE" 2>/dev/null
}

verify_content_match() {
    _s_hash=$(get_sha256 "$1")
    _t_hash=$(get_sha256 "$2")
    if [ -z "$_s_hash" ] || [ -z "$_t_hash" ] || [ "$_s_hash" != "$_t_hash" ]; then
        return 1
    fi
    return 0
}

# ------------------------------------------------------------------------------
# 4. 会话级逆序回滚保护函数 (R3: 逆序卸载本次挂载节点，并清理 /dev 临时镜像)
# ------------------------------------------------------------------------------
rollback_session_mounts() {
    BOOT_RESULT=rolled_back; BOOT_REASON=mount_transaction_failed
    log_msg "[ROLLBACK] Initiating reverse-order rollback for session mounts: $MOUNTED_LIST"
    ROLLBACK_OK=1
    for mnt in $MOUNTED_LIST; do
        if umount "$mnt" 2>>"$LOGFILE"; then
            if is_target_mounted "$mnt"; then
                log_msg "[ROLLBACK ERROR] umount returned 0 but $mnt still present in mountinfo!"
                ROLLBACK_OK=0
                set_file_state "$mnt" rollback_failed
            else
                set_file_state "$mnt" rolled_back
                log_msg "[ROLLBACK] Unmounted and verified removed: $mnt"
            fi
        else
            log_msg "[ROLLBACK ERROR] Failed to umount: $mnt"
            ROLLBACK_OK=0
            set_file_state "$mnt" rollback_failed
        fi
    done

    # 清理 /dev 镜像目录
    if [ "$ROLLBACK_OK" -eq 1 ] && [ -d "$MIRROR_DIR" ]; then
        rm -rf "$MIRROR_DIR" 2>>"$LOGFILE"
        log_msg "[ROLLBACK] Cleaned up mirror directory: $MIRROR_DIR"
    fi

    if [ "$ROLLBACK_OK" -eq 1 ]; then
        log_msg "[ROLLBACK] Session rollback completed cleanly."
    else
        BOOT_RESULT=rollback_failed; BOOT_REASON=rollback_failed
        log_msg "[ROLLBACK WARN] Session rollback finished with errors."
    fi
}

# ------------------------------------------------------------------------------
# 5. 全量前置预检、源文件校验与 /dev 隔离镜像构建
# ------------------------------------------------------------------------------
trap 'rollback_session_mounts; BOOT_REASON=interrupted; exit 1' HUP INT TERM

if [ ! -s "$MANIFEST_FILE" ]; then
    log_msg "[PRECHECK ERROR] Release manifest missing or empty: $MANIFEST_FILE"
    exit 1
fi

prepare_mirror_node() {
    _rel="$1"
    _orig_src="$2"
    _mirror_src="$3"
    _tgt="$4"
    _ctx="$5"

    if [ ! -s "$_orig_src" ]; then
        log_msg "[PRECHECK ERROR] Original source missing or empty: $_orig_src"
        return 1
    fi
    if [ ! -f "$_tgt" ]; then
        log_msg "[PRECHECK ERROR] Target file missing on ROM: $_tgt"
        return 1
    fi

    # 校验源文件 SHA256 必须与 manifest.json 严格一致
    _exp_sha=$(get_manifest_expected_sha256 "$_rel")
    _act_sha=$(get_sha256 "$_orig_src")
    if [ -z "$_exp_sha" ] || [ -z "$_act_sha" ] || [ "$_exp_sha" != "$_act_sha" ]; then
        log_msg "[PRECHECK ERROR] Source integrity mismatch for $_rel (actual='$_act_sha', expected='$_exp_sha')"
        return 1
    fi

    # 确保镜像父目录存在
    _mirror_parent=$(dirname "$_mirror_src")
    mkdir -p "$_mirror_parent" 2>>"$LOGFILE"
    chmod 0755 "$_mirror_parent" 2>>"$LOGFILE"

    # Every invocation uses new inodes; never overwrite a currently bind-mounted mirror.
    cp -f "$_orig_src" "$_mirror_src" 2>>"$LOGFILE"
    if [ ! -s "$_mirror_src" ]; then
        log_msg "[PRECHECK ERROR] Failed to create mirror file: $_mirror_src"
        return 1
    fi

    # 验证镜像文件 SHA256 与源文件完全一致
    if ! verify_content_match "$_orig_src" "$_mirror_src"; then
        log_msg "[PRECHECK ERROR] Mirror copy corrupted: $_mirror_src"
        return 1
    fi

    # 权限与 SELinux 上下文设置 (严格沿用目标上下文，不依赖默认 device:s0)
    chmod 0644 "$_mirror_src" 2>>"$LOGFILE"
    if ! chcon --reference="$_tgt" "$_mirror_src" 2>/dev/null; then
        if ! chcon "$_ctx" "$_mirror_src" 2>>"$LOGFILE"; then
            log_msg "[PRECHECK ERROR] chcon $_ctx failed on $_mirror_src"
            return 1
        fi
    fi

    log_msg "[MIRROR READY] Prepared $_rel in mirror -> $_mirror_src ($(ls -Z "$_mirror_src" 2>/dev/null))"
    return 0
}

# 逐一构建镜像
PREPARED=1
if [ "$VENDOR_READY" -eq 1 ]; then
    prepare_mirror_node "$REL_1" "$ORIG_SRC_1" "$MIRROR_SRC_1" "$TGT_1" "$CTX_1" &&
    prepare_mirror_node "$REL_2" "$ORIG_SRC_2" "$MIRROR_SRC_2" "$TGT_2" "$CTX_2" || PREPARED=0
fi
if [ "$PRODUCT_READY" -eq 1 ]; then
    prepare_mirror_node "$REL_3" "$ORIG_SRC_3" "$MIRROR_SRC_3" "$TGT_3" "$CTX_3" &&
    prepare_mirror_node "$REL_4" "$ORIG_SRC_4" "$MIRROR_SRC_4" "$TGT_4" "$CTX_4" || PREPARED=0
fi
if [ "$PREPARED" -eq 0 ]; then
    BOOT_REASON=mirror_preparation_failed
    log_msg "[ABORT] Pre-flight mirror preparation failed. Zero mounts executed."
    rm -rf "$MIRROR_DIR" 2>/dev/null
    exit 1
fi

# ------------------------------------------------------------------------------
# 6. 挂载身份核验与立即登记 (R3: 从 /dev 镜像执行 bind mount，核验 mountinfo 与哈希)
# ------------------------------------------------------------------------------
mount_node() {
    _src="$1"
    _tgt="$2"
    set_file_state "$_tgt" failed

    if is_target_mounted "$_tgt"; then
        if verify_content_match "$_src" "$_tgt"; then
            set_file_state "$_tgt" already_mounted
            log_msg "[IDEMPOTENT] Target already mounted with matching candidate SHA256: $_tgt"
            return 0
        else
            log_msg "[CONFLICT ERROR] Target $_tgt is already mounted with different content!"
            return 1
        fi
    fi

    if verify_content_match "$_src" "$_tgt"; then
        set_file_state "$_tgt" already_identical
        log_msg "[NO-OP] Source and unmounted target are already byte-identical, skipping bind mount: $_tgt"
        return 0
    fi

    if mount -o bind "$_src" "$_tgt" 2>>"$LOGFILE"; then
        MOUNTED_LIST="$_tgt $MOUNTED_LIST"
        if ! is_target_mounted "$_tgt"; then
            log_msg "[VERIFY ERROR] Newly mounted target missing in /proc/self/mountinfo column 5: $_tgt"
            return 1
        fi
        if ! verify_content_match "$_src" "$_tgt"; then
            log_msg "[VERIFY ERROR] Newly mounted target SHA256 does not match candidate source: $_tgt"
            return 1
        fi
        log_msg "[OK] Mounted from mirror and verified: $_tgt"
        set_file_state "$_tgt" mounted_verified
        return 0
    else
        log_msg "[MOUNT ERROR] mount -o bind failed for $_tgt"
        return 1
    fi
}

MOUNT_OK=1
if [ "$VENDOR_READY" -eq 1 ]; then
    mount_node "$MIRROR_SRC_1" "$TGT_1" && mount_node "$MIRROR_SRC_2" "$TGT_2" || MOUNT_OK=0
fi
if [ "$MOUNT_OK" -eq 1 ] && [ "$PRODUCT_READY" -eq 1 ]; then
    mount_node "$MIRROR_SRC_3" "$TGT_3" && mount_node "$MIRROR_SRC_4" "$TGT_4" || MOUNT_OK=0
fi
if [ "$MOUNT_OK" -eq 0 ]; then
    rollback_session_mounts
    exit 1
fi

if [ -z "$MOUNTED_LIST" ]; then
    rm -rf "$MIRROR_DIR"
fi
log_msg "=== EnablePixel5G v2.6 post-fs-data completed and verified with /dev mirror ==="
BOOT_RESULT=verified_in_script_namespace; BOOT_REASON=completed
exit 0
