#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnablePixel5G v2.4-mustang 端到端无损构建、来源准入校验与全文件事务回滚发布工具
================================================================================
适用机型: Google Pixel 10 Pro XL (mustang / Tensor G5 / Exynos Modem 5400i g5400i)
已验证基线: Android 16 (CP3A.260905.009)
核心特性 (v2.4 针对 Codex 第四轮复审 B1 / B2 / C1 全面闭环):
  1. [B1 修复: 独立来源清单准入校验]
     默认构建必须读取并校验独立登记的 source_manifest.json，逐一核对 4 项输入文件的
     SHA256 与字节长度 (支持已登记的基线哈希及合法候选切换哈希)；任何单字节篡改、
     未知来源或清单缺失/损坏立即抛出 RuntimeError 拒绝构建；仅在显式传入
     --allow-unverified-source 时允许实验性构建并在输出 manifest 标记 source_verified=False。
  2. [B2 修复: 全文件事务发布与异常自动回滚保护]
     构建与自检在临时 staging 目录完成后，发布阶段执行严格的全文件快照备份与逆序恢复
     事务 (publish_atomically_with_rollback)：在替换目标文件与 manifest.json 前将目标
     目录原有文件完整备份至回滚槽，若第 1/2/3/4 个文件或 manifest.json 写入期间发生任何
     OSError / 异常，立即自动清理半成品并 100% 恢复原有候选文件与原有 manifest.json，
     确保绝不产生新旧混合的损坏状态。
  3. [C1 修复: 旧全局修改版 default.pb 的可信基线恢复]
     当 allow_global_default=False 且输入 default.pb 为已修改的 79000000100 版本时，
     不再调用拒绝降级的 patch_single_carrier_settings 猜测恢复，而是强制要求提供经
     source_manifest.json 哈希核验的可信原始 79000000099 default.pb 直接复制恢复并校验
     SHA256；若无登记的可信原始基线则立即抛出 RuntimeError 拒绝恢复。
"""

import os
import sys
import json
import copy
import sqlite3
import hashlib
import shutil
import tempfile
import argparse
from typing import Dict, List, Tuple, Any, Callable, Optional

# 已登记的输入基线版本与目标版本常量
EXPECTED_OTHERS_IN_VERSIONS = {79000000952, 79000000953}
TARGET_OTHERS_VERSION = 79000000953

EXPECTED_DEFAULT_IN_VERSIONS = {79000000099, 79000000100}
TARGET_DEFAULT_VERSION = 79000000100

DEFAULT_SOURCE_MANIFEST_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "private", "stock_baseline", "source_manifest.json")
)

# VCRBT Phase 1 专属实验键集合
VCRBT_EXPERIMENTAL_KEYS = {
    "imsvt.video_on_default_bearer_supported_bool",
    "imsvt.video_qos_precondition_supported_bool",
    "ims.capability_type_video_int_array",
    "vendor.ims.carrier_video_over_lte_bool",
    "vendor.ims.carrier_video_over_wifi_bool",
    "vendor.ims.network_video_sdp_is_multiple_fmtp_support_bool",
    "vendor.ims.network_video_feature_prevent_downgrade_from_audio_crbt_bool",
}


# ==============================================================================
# 第一部分：严格有界 Protobuf Wire-Format 编解码原语 (零外部依赖，防截断/防溢出)
# ==============================================================================

def encode_varint(val: int) -> bytes:
    """将 64-bit 整数编码为 Protobuf Base-128 Varint (兼容负数补码)"""
    if val < 0:
        val += (1 << 64)
    if val < 0 or val >= (1 << 64):
        raise ValueError(f"Varint value out of 64-bit bounds: {val}")
    out = bytearray()
    while True:
        byte = val & 0x7F
        val >>= 7
        if val:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


def decode_varint(buf: bytes, pos: int) -> Tuple[int, int]:
    """从字节流指定位置有界解码 Varint，严格拦截截断输入与超过 64-bit 的畸形编码"""
    result = 0
    shift = 0
    n = len(buf)
    if pos >= n:
        raise ValueError(f"Truncated varint at EOF (pos={pos}, len={n})")
    while True:
        if pos >= n:
            raise ValueError(f"Truncated varint: unexpected EOF at pos={pos}")
        b = buf[pos]
        pos += 1
        if shift >= 64 or (shift == 63 and (b & 0x7F) > 1):
            raise ValueError(f"Varint overflow (>64 bits) at pos={pos}")
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7


def to_signed_int64(val: int) -> int:
    """将无符号 64-bit 整数还原为有符号整数"""
    if val >= (1 << 63):
        return val - (1 << 64)
    return val


def parse_pb_fields(buf: bytes) -> List[Tuple[int, int, Any]]:
    """有界解析 Protobuf 消息层级的全部字段，对任何截断或非法字段立即抛出 ValueError"""
    pos = 0
    fields = []
    n = len(buf)
    while pos < n:
        tag, pos = decode_varint(buf, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07
        if field_num <= 0:
            raise ValueError(f"Invalid Protobuf field_num={field_num} (tag=0x{tag:x}) at pos={pos}")
        if wire_type == 0:  # Varint
            val, pos = decode_varint(buf, pos)
            fields.append((field_num, wire_type, val))
        elif wire_type == 1:  # 64-bit fixed
            if pos + 8 > n:
                raise ValueError(f"Truncated 64-bit fixed field {field_num}: need 8 bytes, have {n - pos}")
            fields.append((field_num, wire_type, buf[pos:pos + 8]))
            pos += 8
        elif wire_type == 2:  # Length-delimited
            length, pos = decode_varint(buf, pos)
            if length < 0 or pos + length > n:
                raise ValueError(
                    f"Truncated length-delimited field {field_num}: declared length={length}, remaining={n - pos}"
                )
            fields.append((field_num, wire_type, buf[pos:pos + length]))
            pos += length
        elif wire_type == 5:  # 32-bit fixed
            if pos + 4 > n:
                raise ValueError(f"Truncated 32-bit fixed field {field_num}: need 4 bytes, have {n - pos}")
            fields.append((field_num, wire_type, buf[pos:pos + 4]))
            pos += 4
        else:
            raise ValueError(f"Unsupported or invalid Protobuf wire_type={wire_type} at offset={pos}")
    return fields


def serialize_pb_fields(fields: List[Tuple[int, int, Any]]) -> bytes:
    """将字段列表无损序列化回二进制字节流"""
    out = bytearray()
    for field_num, wire_type, val in fields:
        if field_num <= 0:
            raise ValueError(f"Cannot serialize invalid field_num={field_num}")
        tag = (field_num << 3) | wire_type
        out.extend(encode_varint(tag))
        if wire_type == 0:
            out.extend(encode_varint(val))
        elif wire_type in (1, 5):
            if len(val) != (8 if wire_type == 1 else 4):
                raise ValueError(f"Invalid fixed wire_type={wire_type} byte length={len(val)}")
            out.extend(val)
        elif wire_type == 2:
            out.extend(encode_varint(len(val)))
            out.extend(val)
        else:
            raise ValueError(f"Unsupported wire_type={wire_type}")
    return bytes(out)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# ==============================================================================
# 第二部分：AOSP CarrierSettings 专属键值对与 APN 构造器 (严格对齐官方 Schema)
# ==============================================================================

def make_kv_bool(key: str, val: bool) -> bytes:
    return serialize_pb_fields([
        (1, 2, key.encode("utf-8")),
        (5, 0, 1 if val else 0)
    ])


def make_kv_int(key: str, val: int) -> bytes:
    return serialize_pb_fields([
        (1, 2, key.encode("utf-8")),
        (3, 0, val)
    ])


def make_kv_string(key: str, val: str) -> bytes:
    return serialize_pb_fields([
        (1, 2, key.encode("utf-8")),
        (2, 2, val.encode("utf-8"))
    ])


def make_kv_int_array(key: str, vals: List[int]) -> bytes:
    inner = serialize_pb_fields([(1, 0, v) for v in vals])
    return serialize_pb_fields([
        (1, 2, key.encode("utf-8")),
        (7, 2, inner)
    ])


def make_ct_ims_apn_item() -> bytes:
    """
    按 AOSP ApnItem schema 构造中国电信标准大写 IMS APN:
      field 1 (string): name = '中国电信(IMS)'
      field 2 (string): value = 'IMS'
      field 3 (enum varint): type = 7 (APN_TYPE_IMS)
      field 14 (enum varint): protocol = 2 (IPV4V6)
      field 15 (enum varint): roaming_protocol = 2 (IPV4V6)
      field 24 (bool varint): user_editable = false (0, 禁止用户在 UI 误改 IMS 专用承载)
    """
    return serialize_pb_fields([
        (1, 2, "中国电信(IMS)".encode("utf-8")),
        (2, 2, b"IMS"),
        (3, 0, 7),
        (14, 0, 2),
        (15, 0, 2),
        (24, 0, 0),
    ])


# ==============================================================================
# 第三部分：B1 独立来源清单准入校验器 (Source Manifest Admission Control)
# ==============================================================================

def load_and_verify_source_admission(
    in_dir: str,
    source_manifest_path: str = DEFAULT_SOURCE_MANIFEST_PATH,
    allow_unverified_source: bool = False
) -> Dict[str, Any]:
    """
    [B1 修复] 读取独立登记的 source_manifest.json 并对 in_dir 下的 4 项输入文件执行严格哈希准入控制：
      - 若 source_manifest_path 缺失或 JSON 格式损坏，且未开启 allow_unverified_source，立即抛出 RuntimeError。
      - 对 cfg.db / open_carrier_info.dat / others.pb / default.pb 逐项计算实际 SHA256：
        1. 若全部匹配 source_manifest['inputs']，则准入通过 (admission_mode='primary_baseline', source_verified=True)；
        2. 若匹配 source_manifest['allowed_profile_switch_inputs'] (如已登记的候选输出用于 Profile 切换或重跑幂等测试)，
           则准入通过 (admission_mode='registered_candidate_switch', source_verified=True)；
        3. 若存在任何未知哈希 (例如单字节篡改)，默认立即抛出 RuntimeError 拒绝构建！
           仅当 allow_unverified_source=True 时允许继续，并强制标记 source_verified=False。
    """
    required_inputs = ["cfg.db", "open_carrier_info.dat", "others.pb", "default.pb"]
    actual_inputs = {}
    for req in required_inputs:
        p = os.path.join(in_dir, req)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Required input file missing: {p}")
        actual_inputs[req] = {
            "sha256": sha256_file(p),
            "size_bytes": os.path.getsize(p),
        }

    if not os.path.isfile(source_manifest_path):
        if allow_unverified_source:
            return {
                "source_verified": False,
                "admission_mode": "unverified_missing_manifest",
                "source_manifest_sha256": None,
                "baseline_id": "unverified",
                "trusted_default_pb_sha256": None,
                "actual_inputs": actual_inputs,
            }
        raise RuntimeError(f"Source manifest missing: {source_manifest_path}")

    try:
        with open(source_manifest_path, "r", encoding="utf-8") as f:
            src_manifest = json.load(f)
    except Exception as e:
        if allow_unverified_source:
            return {
                "source_verified": False,
                "admission_mode": f"unverified_corrupt_manifest: {e}",
                "source_manifest_sha256": None,
                "baseline_id": "unverified",
                "trusted_default_pb_sha256": None,
                "actual_inputs": actual_inputs,
            }
        raise RuntimeError(f"Corrupt source manifest {source_manifest_path}: {e}") from e

    if not isinstance(src_manifest, dict) or "inputs" not in src_manifest:
        if allow_unverified_source:
            return {
                "source_verified": False,
                "admission_mode": "unverified_invalid_manifest_schema",
                "source_manifest_sha256": None,
                "baseline_id": "unverified",
                "trusted_default_pb_sha256": None,
                "actual_inputs": actual_inputs,
            }
        raise RuntimeError(f"Invalid source manifest schema in {source_manifest_path}")

    manifest_hash = sha256_file(source_manifest_path)
    expected_primary = src_manifest["inputs"]
    allowed_switch = src_manifest.get("allowed_profile_switch_inputs", {})
    trusted_default_sha = expected_primary.get("default.pb", {}).get("sha256")

    all_primary = True
    unregistered_files = []

    for req in required_inputs:
        act_sha = actual_inputs[req]["sha256"]
        exp_entry = expected_primary.get(req, {})
        exp_sha = exp_entry.get("sha256") if isinstance(exp_entry, dict) else exp_entry
        exp_size = exp_entry.get("size_bytes") if isinstance(exp_entry, dict) else None

        if act_sha == exp_sha and (exp_size is None or actual_inputs[req]["size_bytes"] == exp_size):
            continue

        all_primary = False
        switch_list = allowed_switch.get(req, [])
        if act_sha in switch_list:
            continue

        unregistered_files.append((req, act_sha, exp_sha))

    if unregistered_files:
        if not allow_unverified_source:
            details = "; ".join(f"{r}: actual={a}, expected={e}" for r, a, e in unregistered_files)
            raise RuntimeError(f"Unregistered input baseline rejected by source manifest: {details}")
        return {
            "source_verified": False,
            "admission_mode": "unverified_override",
            "source_manifest_sha256": manifest_hash,
            "baseline_id": src_manifest.get("baseline_id", "unverified"),
            "trusted_default_pb_sha256": trusted_default_sha,
            "actual_inputs": actual_inputs,
        }

    return {
        "source_verified": True,
        "admission_mode": "primary_baseline" if all_primary else "registered_candidate_switch",
        "source_manifest_sha256": manifest_hash,
        "baseline_id": src_manifest.get("baseline_id", "unknown"),
        "trusted_default_pb_sha256": trusted_default_sha,
        "actual_inputs": actual_inputs,
    }


# ==============================================================================
# 第四部分：Layer 2 基带配置修补函数 (cfg.db & open_carrier_info.dat)
# ==============================================================================

def patch_cfg_db(input_db_path: str, output_db_path: str) -> Dict[str, Any]:
    """修补 /vendor/firmware/carrierconfig/cfg.db (R1 规范实现)"""
    os.makedirs(os.path.dirname(os.path.abspath(output_db_path)), exist_ok=True)
    shutil.copy2(input_db_path, output_db_path)

    conn = sqlite3.connect(output_db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM confmap WHERE carrier_id = '20033'")
    if cur.fetchone()[0] != 1:
        conn.close()
        raise RuntimeError("Target policy carrier_id='20033' (wildcard_5gsa) missing in confmap!")

    target_cids = ('1435', '1436', '2237', '2427')
    cur.execute(
        "UPDATE confmap SET parent_id = '20033' WHERE carrier_id IN ('1435', '1436', '2237', '2427')"
    )

    columns = [row[1] for row in cur.execute("PRAGMA table_info(carrier_info)").fetchall()]
    expected_cols = [
        "carrier_id", "mccmnc", "imsi_prefix_xpattern", "spn", "plmn_name",
        "gid1", "gid2", "preferred_apn", "iccid_prefix", "privelege_access_rule"
    ]
    if columns != expected_cols:
        conn.close()
        raise RuntimeError(f"Unexpected carrier_info schema columns: {columns}")

    quoted_cols = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
    rows = cur.execute(
        f"SELECT rowid, {quoted_cols} FROM carrier_info WHERE mccmnc IN (?, ?) ORDER BY rowid",
        ("46005", "46015")
    ).fetchall()

    seen_signatures = set()
    for row in rows:
        rowid = row[0]
        full_sig = tuple(row[1:])
        if full_sig in seen_signatures:
            cur.execute("DELETE FROM carrier_info WHERE rowid = ?", (rowid,))
        else:
            seen_signatures.add(full_sig)

    wildcard_where = """
        mccmnc = ?
        AND imsi_prefix_xpattern = '%'
        AND spn = '%'
        AND plmn_name IS NULL
        AND gid1 = '%'
        AND gid2 = '%'
        AND preferred_apn IS NULL
        AND iccid_prefix IS NULL
        AND privelege_access_rule IS NULL
    """
    for target_mccmnc, target_cid, allowed_old_cids in [
        ("46005", 2237, {2237}),
        ("46015", 20033, {20033, 20031}),
    ]:
        w_rows = cur.execute(
            f"SELECT rowid, carrier_id FROM carrier_info WHERE {wildcard_where} ORDER BY rowid",
            (target_mccmnc,)
        ).fetchall()
        if len(w_rows) == 0:
            cur.execute(
                "INSERT INTO carrier_info (carrier_id, mccmnc, imsi_prefix_xpattern, spn, gid1, gid2) "
                "VALUES (?, ?, '%', '%', '%', '%')",
                (target_cid, target_mccmnc)
            )
        elif len(w_rows) == 1:
            existing_rowid, existing_cid = w_rows[0]
            if existing_cid not in allowed_old_cids:
                conn.close()
                raise RuntimeError(
                    f"Conflicting wildcard rule for mccmnc={target_mccmnc}: unexpected carrier_id={existing_cid}"
                )
            if existing_cid != target_cid:
                cur.execute("UPDATE carrier_info SET carrier_id = ? WHERE rowid = ?", (target_cid, existing_rowid))
        else:
            conn.close()
            raise RuntimeError(f"Multiple conflicting wildcard rules found for mccmnc={target_mccmnc}: {w_rows}")

    cur.execute("UPDATE regional_fallback SET carrier_id = '0' WHERE country_code = '0'")
    conn.commit()

    cur.execute("PRAGMA integrity_check")
    integrity = cur.fetchone()[0]
    if integrity != "ok":
        conn.close()
        raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

    cur.execute("SELECT carrier_id, parent_id FROM confmap WHERE carrier_id IN ('1435', '1436', '2237', '2427')")
    confmap_state = dict(cur.fetchall())
    for cid in target_cids:
        if confmap_state.get(cid) != "20033":
            conn.close()
            raise RuntimeError(f"confmap {cid} parent_id mismatch: {confmap_state.get(cid)}")

    wildcard_counts = {}
    for target_mccmnc, target_cid in [("46005", 2237), ("46015", 20033)]:
        w_check = cur.execute(
            f"SELECT carrier_id FROM carrier_info WHERE {wildcard_where}",
            (target_mccmnc,)
        ).fetchall()
        if w_check != [(target_cid,)]:
            conn.close()
            raise RuntimeError(f"Wildcard rule verification failed for {target_mccmnc}: {w_check}")
        wildcard_counts[target_mccmnc] = len(w_check)

    cur.execute("SELECT carrier_id FROM regional_fallback WHERE country_code = '0'")
    rf_val = cur.fetchone()[0]
    if rf_val != "0":
        conn.close()
        raise RuntimeError(f"regional_fallback expected '0', got '{rf_val}'")

    conn.close()
    return {
        "integrity": integrity,
        "confmap": confmap_state,
        "wildcard_rule_counts": wildcard_counts,
        "regional_fallback_0": rf_val,
    }


def patch_open_carrier_info(input_dat_path: str, output_dat_path: str) -> int:
    """修补 /vendor/etc/open_carrier_info.dat (文本映射表)"""
    with open(input_dat_path, "rb") as f:
        text = f.read().decode("utf-8")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out_lines = []
    found_ctc = False
    for line in lines:
        if line.startswith("OC_CTC "):
            found_ctc = True
            parts = line.split()
            oc_name, oc_hex = parts[0], parts[1]
            plmns = parts[3:]
            for ct_plmn in ("46003", "46005", "46011"):
                if ct_plmn not in plmns:
                    plmns.append(ct_plmn)
            out_lines.append(f"{oc_name} {oc_hex} {len(plmns)} " + " ".join(plmns))
        else:
            out_lines.append(line)

    if not found_ctc:
        raise RuntimeError("OC_CTC line missing in open_carrier_info.dat!")

    out_bytes = ("\n".join(out_lines) + "\n").encode("utf-8")
    os.makedirs(os.path.dirname(os.path.abspath(output_dat_path)), exist_ok=True)
    with open(output_dat_path, "wb") as f:
        f.write(out_bytes)

    return len(out_lines) - 1


# ==============================================================================
# 第五部分：Layer 1 CarrierSettings 原地修补引擎 (others.pb & default.pb)
# ==============================================================================

def build_cn_kv_overrides(profile: str = "base") -> Dict[str, bytes]:
    kvs = {
        "carrier_nr_availabilities_int_array": make_kv_int_array("carrier_nr_availabilities_int_array", [1, 2]),
        "additional_nr_advanced_bands_int_array": make_kv_int_array("additional_nr_advanced_bands_int_array", [1, 28, 41, 77, 78, 79]),
        "5g_nr_ssrsrp_thresholds_int_array": make_kv_int_array("5g_nr_ssrsrp_thresholds_int_array", [-115, -105, -95, -85]),
        "lte_rsrp_thresholds_int_array": make_kv_int_array("lte_rsrp_thresholds_int_array", [-120, -110, -100, -90]),
        "carrier_volte_available_bool": make_kv_bool("carrier_volte_available_bool", True),
        "carrier_vt_available_bool": make_kv_bool("carrier_vt_available_bool", True),
        "carrier_wfc_ims_available_bool": make_kv_bool("carrier_wfc_ims_available_bool", True),
        "carrier_default_wfc_ims_enabled_bool": make_kv_bool("carrier_default_wfc_ims_enabled_bool", True),
        "carrier_default_wfc_ims_mode_int": make_kv_int("carrier_default_wfc_ims_mode_int", 1),
        "vonr_enabled_bool": make_kv_bool("vonr_enabled_bool", True),
        "vonr_on_by_default_bool": make_kv_bool("vonr_on_by_default_bool", True),
        "vonr_setting_visibility_bool": make_kv_bool("vonr_setting_visibility_bool", True),
        "enhanced_4g_lte_on_by_default_bool": make_kv_bool("enhanced_4g_lte_on_by_default_bool", True),
        "hide_enhanced_4g_lte_bool": make_kv_bool("hide_enhanced_4g_lte_bool", False),
        "carrier_supports_ss_over_ut_bool": make_kv_bool("carrier_supports_ss_over_ut_bool", True),
        "show_wifi_calling_icon_in_status_bar_bool": make_kv_bool("show_wifi_calling_icon_in_status_bar_bool", True),
    }

    if profile == "vcrbt":
        kvs.update({
            "imsvt.video_on_default_bearer_supported_bool": make_kv_bool("imsvt.video_on_default_bearer_supported_bool", True),
            "imsvt.video_qos_precondition_supported_bool": make_kv_bool("imsvt.video_qos_precondition_supported_bool", False),
            "ims.capability_type_video_int_array": make_kv_int_array("ims.capability_type_video_int_array", [0, 1, 3]),
            "vendor.ims.carrier_video_over_lte_bool": make_kv_bool("vendor.ims.carrier_video_over_lte_bool", True),
            "vendor.ims.carrier_video_over_wifi_bool": make_kv_bool("vendor.ims.carrier_video_over_wifi_bool", True),
            "vendor.ims.network_video_sdp_is_multiple_fmtp_support_bool": make_kv_bool("vendor.ims.network_video_sdp_is_multiple_fmtp_support_bool", True),
            "vendor.ims.network_video_feature_prevent_downgrade_from_audio_crbt_bool": make_kv_bool("vendor.ims.network_video_feature_prevent_downgrade_from_audio_crbt_bool", True),
        })

    return kvs


def patch_carrier_config_submessage(
    config_bytes: bytes,
    kv_overrides: Dict[str, bytes],
    keys_to_remove: set = None
) -> bytes:
    local_kvs = copy.deepcopy(kv_overrides)
    remove_set = keys_to_remove or set()
    fields = parse_pb_fields(config_bytes)
    new_fields = []
    seen_keys = set()

    for fn, wt, val in fields:
        if fn == 2 and wt == 2:
            kv_sub = parse_pb_fields(val)
            key_name = None
            for kfn, kwt, kval in kv_sub:
                if kfn == 1 and kwt == 2:
                    key_name = kval.decode("utf-8")
                    break
            if not key_name:
                raise ValueError("Invalid CarrierConfig.Config item without key name (field 1)")
            if key_name in seen_keys:
                continue
            seen_keys.add(key_name)

            if key_name in remove_set and key_name not in local_kvs:
                continue
            if key_name in local_kvs:
                new_fields.append((2, 2, local_kvs.pop(key_name)))
            else:
                new_fields.append((fn, wt, val))
        else:
            new_fields.append((fn, wt, val))

    for key_name in sorted(local_kvs.keys()):
        new_fields.append((2, 2, local_kvs[key_name]))

    return serialize_pb_fields(new_fields)


def ensure_ct_ims_apn_in_carrier_apns(apns_bytes: bytes) -> bytes:
    fields = parse_pb_fields(apns_bytes)
    new_fields = []
    has_ims_apn = False

    for fn, wt, val in fields:
        if fn == 2 and wt == 2:
            apn_fields = parse_pb_fields(val)
            types = [v for afn, awt, v in apn_fields if afn == 3 and awt == 0]
            if 7 in types:
                has_ims_apn = True
                updated_apn_fields = []
                for afn, awt, aval in apn_fields:
                    if afn == 2 and awt == 2:
                        updated_apn_fields.append((2, 2, b"IMS"))
                    else:
                        updated_apn_fields.append((afn, awt, aval))
                new_fields.append((2, 2, serialize_pb_fields(updated_apn_fields)))
            else:
                new_fields.append((fn, wt, val))
        else:
            new_fields.append((fn, wt, val))

    if not has_ims_apn:
        new_fields.append((2, 2, make_ct_ims_apn_item()))

    return serialize_pb_fields(new_fields)


def patch_single_carrier_settings(
    cs_bytes: bytes,
    kv_overrides: Dict[str, bytes],
    keys_to_remove: set = None,
    is_ct: bool = False,
    bump_version: int = None
) -> bytes:
    """修补单个 CarrierSettings 消息，严格拒绝任何版本降级"""
    fields = parse_pb_fields(cs_bytes)
    new_fields = []
    has_version = False
    has_apns = False
    has_configs = False

    for fn, wt, val in fields:
        if fn == 2 and wt == 0:
            has_version = True
            if bump_version is not None:
                if val > bump_version:
                    raise ValueError(
                        f"Input CarrierSettings version ({val}) is newer than target ({bump_version}); refusing downgrade!"
                    )
                new_fields.append((2, 0, bump_version))
            else:
                new_fields.append((2, 0, val))
        elif fn == 3 and wt == 2:
            has_apns = True
            if is_ct:
                new_fields.append((3, 2, ensure_ct_ims_apn_in_carrier_apns(val)))
            else:
                new_fields.append((3, 2, val))
        elif fn == 4 and wt == 2:
            has_configs = True
            new_fields.append((4, 2, patch_carrier_config_submessage(val, kv_overrides, keys_to_remove)))
        else:
            new_fields.append((fn, wt, val))

    if bump_version is not None and not has_version:
        new_fields.insert(1, (2, 0, bump_version))
    if is_ct and not has_apns:
        new_fields.append((3, 2, serialize_pb_fields([(2, 2, make_ct_ims_apn_item())])))
    if not has_configs:
        new_fields.append((4, 2, patch_carrier_config_submessage(b"", kv_overrides, keys_to_remove)))

    return serialize_pb_fields(new_fields)


def patch_others_pb(
    input_pb_path: str,
    output_pb_path: str,
    profile: str = "base",
    target_version: int = TARGET_OTHERS_VERSION
) -> List[str]:
    with open(input_pb_path, "rb") as f:
        raw = f.read()

    top_fields = parse_pb_fields(raw)
    new_top_fields = []
    target_cnames = {"46001", "46003", "46005", "46009", "46011", "chinamobile_cn"}
    ct_cnames = {"46003", "46005", "46011"}
    kv_template = build_cn_kv_overrides(profile=profile)
    remove_keys = VCRBT_EXPERIMENTAL_KEYS if profile == "base" else set()
    patched_cnames = []
    found_version = False

    for fn, wt, val in top_fields:
        if fn == 1 and wt == 0:
            found_version = True
            if val > target_version or val not in EXPECTED_OTHERS_IN_VERSIONS:
                raise ValueError(
                    f"Unrecognized or newer others.pb input version={val} (expected in {EXPECTED_OTHERS_IN_VERSIONS}, target={target_version})"
                )
            new_top_fields.append((1, 0, target_version))
        elif fn == 2 and wt == 2:
            cs_fields = parse_pb_fields(val)
            cname = None
            for cfn, cwt, cval in cs_fields:
                if cfn == 1 and cwt == 2:
                    cname = cval.decode("utf-8")
                    break
            if cname in target_cnames:
                patched_cs = patch_single_carrier_settings(
                    val,
                    kv_overrides=kv_template,
                    keys_to_remove=remove_keys,
                    is_ct=(cname in ct_cnames),
                    bump_version=target_version
                )
                new_top_fields.append((2, 2, patched_cs))
                patched_cnames.append(cname)
            else:
                new_top_fields.append((fn, wt, val))
        else:
            new_top_fields.append((fn, wt, val))

    if not found_version:
        raise ValueError("Missing top-level version (field 1) in others.pb")

    out_bytes = serialize_pb_fields(new_top_fields)
    os.makedirs(os.path.dirname(os.path.abspath(output_pb_path)), exist_ok=True)
    with open(output_pb_path, "wb") as f:
        f.write(out_bytes)

    return patched_cnames


def patch_default_pb(
    input_pb_path: str,
    output_pb_path: str,
    profile: str = "base",
    allow_global_default: bool = False,
    trusted_baseline_default_pb_path: Optional[str] = None,
    trusted_baseline_default_pb_sha256: Optional[str] = None,
    target_version: int = TARGET_DEFAULT_VERSION
) -> Dict[str, Any]:
    """
    处理 default.pb (R2 + C1 规范实现):
      - 当 allow_global_default=False 时:
        1. 若输入本身是未修改的 79000000099，且如提供了 trusted_baseline_default_pb_sha256 则核对一致后直接复制；
        2. [C1 修复] 若输入是曾被修改过的 79000000100，严禁通过删除部分键和降级版本号猜测恢复！
           必须提供经 trusted_baseline_default_pb_sha256 哈希核验的可信原始 default.pb 路径进行字节级完整恢复；
           若未提供或可信源文件哈希不匹配，立即抛出 RuntimeError 拒绝恢复。
    """
    with open(input_pb_path, "rb") as f:
        raw = f.read()

    in_fields = parse_pb_fields(raw)
    in_ver = None
    for fn, wt, val in in_fields:
        if fn == 2 and wt == 0:
            in_ver = val
            break
    if in_ver is None or in_ver > target_version or in_ver not in EXPECTED_DEFAULT_IN_VERSIONS:
        raise ValueError(f"Unrecognized or newer default.pb input version={in_ver}")

    os.makedirs(os.path.dirname(os.path.abspath(output_pb_path)), exist_ok=True)

    if not allow_global_default:
        if in_ver == 79000000099:
            in_sha = sha256_file(input_pb_path)
            if trusted_baseline_default_pb_sha256 and in_sha != trusted_baseline_default_pb_sha256:
                raise RuntimeError(
                    f"Input default.pb (v79000000099) SHA256 ({in_sha}) does not match registered baseline ({trusted_baseline_default_pb_sha256})"
                )
            shutil.copy2(input_pb_path, output_pb_path)
            return {"mode": "passthrough_untouched", "version": 79000000099, "sha256": in_sha}
        else:
            # [C1 修复] 从已登记的可信原始 default.pb 恢复，绝不猜测或降级修补
            if not trusted_baseline_default_pb_path or not os.path.isfile(trusted_baseline_default_pb_path):
                raise RuntimeError(
                    "Cannot restore modified default.pb (v79000000100) without a registered trusted_baseline_default_pb_path!"
                )
            if not trusted_baseline_default_pb_sha256:
                raise RuntimeError(
                    "Cannot restore modified default.pb (v79000000100) without a registered trusted_baseline_default_pb_sha256!"
                )
            trusted_actual_sha = sha256_file(trusted_baseline_default_pb_path)
            if trusted_actual_sha != trusted_baseline_default_pb_sha256:
                raise RuntimeError(
                    f"Trusted baseline default.pb SHA256 mismatch: actual={trusted_actual_sha}, expected={trusted_baseline_default_pb_sha256}"
                )
            shutil.copy2(trusted_baseline_default_pb_path, output_pb_path)
            if sha256_file(output_pb_path) != trusted_baseline_default_pb_sha256:
                raise RuntimeError("Restored default.pb failed post-copy SHA256 verification!")
            return {
                "mode": "restored_from_trusted_baseline",
                "version": 79000000099,
                "sha256": trusted_baseline_default_pb_sha256,
            }

    default_kvs = {
        "carrier_nr_availabilities_int_array": make_kv_int_array("carrier_nr_availabilities_int_array", [1, 2]),
        "additional_nr_advanced_bands_int_array": make_kv_int_array("additional_nr_advanced_bands_int_array", [1, 28, 41, 77, 78, 79]),
        "5g_nr_ssrsrp_thresholds_int_array": make_kv_int_array("5g_nr_ssrsrp_thresholds_int_array", [-115, -105, -95, -85]),
        "carrier_volte_available_bool": make_kv_bool("carrier_volte_available_bool", True),
        "carrier_vt_available_bool": make_kv_bool("carrier_vt_available_bool", True),
        "carrier_wfc_ims_available_bool": make_kv_bool("carrier_wfc_ims_available_bool", True),
        "vonr_enabled_bool": make_kv_bool("vonr_enabled_bool", True),
        "vonr_on_by_default_bool": make_kv_bool("vonr_on_by_default_bool", True),
        "vonr_setting_visibility_bool": make_kv_bool("vonr_setting_visibility_bool", True),
    }
    remove_keys = set()
    if profile == "vcrbt":
        default_kvs.update({
            "imsvt.video_on_default_bearer_supported_bool": make_kv_bool("imsvt.video_on_default_bearer_supported_bool", True),
            "imsvt.video_qos_precondition_supported_bool": make_kv_bool("imsvt.video_qos_precondition_supported_bool", False),
        })
    else:
        remove_keys = VCRBT_EXPERIMENTAL_KEYS

    out_bytes = patch_single_carrier_settings(
        raw,
        kv_overrides=default_kvs,
        keys_to_remove=remove_keys,
        is_ct=False,
        bump_version=target_version
    )
    with open(output_pb_path, "wb") as f:
        f.write(out_bytes)

    return {"mode": "global_default_patched", "version": target_version, "sha256": sha256_file(output_pb_path)}


# ==============================================================================
# 第六部分：第二遍解码自检器与 B2 异常可回滚发布器
# ==============================================================================

def decode_carrier_settings_dict(cs_bytes: bytes) -> Dict[str, Any]:
    info = {
        "canonical_name": None,
        "version": None,
        "apns_raw": [],
        "apns": [],
        "configs": {},
        "other_fields_raw": []
    }
    for fn, wt, val in parse_pb_fields(cs_bytes):
        if fn == 1 and wt == 2:
            info["canonical_name"] = val.decode("utf-8")
        elif fn == 2 and wt == 0:
            info["version"] = val
        elif fn == 3 and wt == 2:
            for afn, awt, aval in parse_pb_fields(val):
                if afn == 2 and awt == 2:
                    info["apns_raw"].append(aval)
                    apn_item = {}
                    for xfn, xwt, xval in parse_pb_fields(aval):
                        if xfn == 1 and xwt == 2:
                            apn_item["name"] = xval.decode("utf-8")
                        elif xfn == 2 and xwt == 2:
                            apn_item["value"] = xval.decode("utf-8")
                        elif xfn == 3 and xwt == 0:
                            apn_item.setdefault("types", []).append(xval)
                        elif xfn == 14 and xwt == 0:
                            apn_item["protocol"] = xval
                        elif xfn == 15 and xwt == 0:
                            apn_item["roaming_protocol"] = xval
                    info["apns"].append(apn_item)
                else:
                    info["other_fields_raw"].append((3, afn, awt, aval))
        elif fn == 4 and wt == 2:
            for cfn, cwt, cval in parse_pb_fields(val):
                if cfn == 2 and cwt == 2:
                    kv_fields = parse_pb_fields(cval)
                    kname = None
                    kval_parsed = None
                    for kfn, kwt, kv in kv_fields:
                        if kfn == 1 and kwt == 2:
                            kname = kv.decode("utf-8")
                        elif kfn == 2 and kwt == 2:
                            kval_parsed = ("string", kv.decode("utf-8"))
                        elif kfn == 3 and kwt == 0:
                            kval_parsed = ("int", to_signed_int64(kv))
                        elif kfn == 4 and kwt == 0:
                            kval_parsed = ("long", to_signed_int64(kv))
                        elif kfn == 5 and kwt == 0:
                            kval_parsed = ("bool", bool(kv))
                        elif kfn == 6 and kwt == 2:
                            arr = [sv.decode("utf-8") for sfn, swt, sv in parse_pb_fields(kv) if sfn == 1 and swt == 2]
                            kval_parsed = ("string_array", arr)
                        elif kfn == 7 and kwt == 2:
                            arr = [to_signed_int64(iv) for ifn, iwt, iv in parse_pb_fields(kv) if ifn == 1 and iwt == 0]
                            kval_parsed = ("int_array", arr)
                    if not kname:
                        raise RuntimeError("Decoded Config item missing key")
                    if kname in info["configs"]:
                        raise RuntimeError(f"Duplicate Config key '{kname}' detected in {info['canonical_name']}")
                    info["configs"][kname] = kval_parsed
                else:
                    info["other_fields_raw"].append((4, cfn, cwt, cval))
        else:
            info["other_fields_raw"].append((fn, wt, val))
    return info


def verify_all_outputs(
    input_dir: str,
    output_dir: str,
    profile: str = "base",
    allow_global_default: bool = False,
    trusted_baseline_default_pb_path: Optional[str] = None
) -> Dict[str, Any]:
    others_in = os.path.join(input_dir, "others.pb")
    others_out = os.path.join(output_dir, "product_override", "others.pb")
    default_in = trusted_baseline_default_pb_path if (trusted_baseline_default_pb_path and os.path.isfile(trusted_baseline_default_pb_path)) else os.path.join(input_dir, "default.pb")
    default_out = os.path.join(output_dir, "product_override", "default.pb")

    with open(others_in, "rb") as f:
        in_top = parse_pb_fields(f.read())
    with open(others_out, "rb") as f:
        out_top = parse_pb_fields(f.read())

    if len(in_top) != len(out_top):
        raise RuntimeError(f"Top field count mismatch: {len(in_top)} vs {len(out_top)}")
    if out_top[0] != (1, 0, TARGET_OTHERS_VERSION):
        raise RuntimeError(f"others.pb version mismatch: {out_top[0]}")

    target_cnames = {"46001", "46003", "46005", "46009", "46011", "chinamobile_cn"}
    verified_targets = set()
    unchanged_carrier_count = 0
    preserved_top_unknown_count = 0

    for (ifn, iwt, ival), (ofn, owt, oval) in zip(in_top[1:], out_top[1:]):
        if ifn != ofn or iwt != owt:
            raise RuntimeError(f"Top field tag/wire mismatch: ({ifn},{iwt}) vs ({ofn},{owt})")
        if ofn == 2 and owt == 2:
            in_cs = decode_carrier_settings_dict(ival)
            out_cs = decode_carrier_settings_dict(oval)
            cname = out_cs["canonical_name"]

            if cname in target_cnames:
                verified_targets.add(cname)
                if out_cs["version"] != TARGET_OTHERS_VERSION:
                    raise RuntimeError(f"{cname} internal version mismatch: expected {TARGET_OTHERS_VERSION}, got {out_cs['version']}")
                if out_cs["other_fields_raw"] != in_cs["other_fields_raw"]:
                    raise RuntimeError(f"{cname} unknown fields changed!")
                if len(out_cs["apns"]) < len(in_cs["apns"]):
                    raise RuntimeError(f"{cname} lost APNs!")

                in_non_ims = [raw for raw, parsed in zip(in_cs["apns_raw"], in_cs["apns"]) if 7 not in parsed.get("types", [])]
                out_non_ims = [raw for raw, parsed in zip(out_cs["apns_raw"], out_cs["apns"]) if 7 not in parsed.get("types", [])]
                if in_non_ims != out_non_ims:
                    raise RuntimeError(f"{cname} non-IMS APN raw bytes were altered!")

                if cname in {"46003", "46005", "46011"}:
                    ims_apns = [a for a in out_cs["apns"] if 7 in a.get("types", [])]
                    if len(ims_apns) != 1 or ims_apns[0]["value"] != "IMS":
                        raise RuntimeError(f"{cname} IMS APN invalid: {ims_apns}")

                cfg = out_cs["configs"]
                expected_override_keys = set(build_cn_kv_overrides(profile).keys())
                for orig_k, orig_v in in_cs["configs"].items():
                    if orig_k not in expected_override_keys and orig_k not in VCRBT_EXPERIMENTAL_KEYS:
                        if cfg.get(orig_k) != orig_v:
                            raise RuntimeError(f"{cname} unoverridden key '{orig_k}' changed!")

                if cfg.get("vonr_enabled_bool") != ("bool", True):
                    raise RuntimeError(f"{cname} vonr_enabled_bool failed")
                if cfg.get("carrier_vt_available_bool") != ("bool", True):
                    raise RuntimeError(f"{cname} carrier_vt_available_bool failed")
                if cfg.get("5g_nr_ssrsrp_thresholds_int_array") != ("int_array", [-115, -105, -95, -85]):
                    raise RuntimeError(f"{cname} threshold failed")

                if profile == "vcrbt":
                    if cfg.get("imsvt.video_on_default_bearer_supported_bool") != ("bool", True):
                        raise RuntimeError(f"{cname} default_bearer failed")
                    if cfg.get("imsvt.video_qos_precondition_supported_bool") != ("bool", False):
                        raise RuntimeError(f"{cname} qos_precondition failed")
                    if cfg.get("ims.capability_type_video_int_array") != ("int_array", [0, 1, 3]):
                        raise RuntimeError(f"{cname} video_int_array failed")
                    if cfg.get("vendor.ims.network_video_sdp_is_multiple_fmtp_support_bool") != ("bool", True):
                        raise RuntimeError(f"{cname} multiple_fmtp failed")
                else:
                    for exp_k in VCRBT_EXPERIMENTAL_KEYS:
                        if exp_k in cfg:
                            raise RuntimeError(f"{cname} in 'base' profile still contains experimental key '{exp_k}'!")
            else:
                if ival != oval:
                    raise RuntimeError(f"Non-target carrier {cname} was unexpectedly modified!")
                unchanged_carrier_count += 1
        else:
            if ival != oval:
                raise RuntimeError(f"Top-level unknown field {ofn} was modified!")
            preserved_top_unknown_count += 1

    if verified_targets != target_cnames:
        raise RuntimeError(f"Missing targets: {target_cnames - verified_targets}")

    with open(default_in, "rb") as f:
        def_in_raw = f.read()
    with open(default_out, "rb") as f:
        def_out_raw = f.read()
    def_in_dict = decode_carrier_settings_dict(def_in_raw)
    def_out_dict = decode_carrier_settings_dict(def_out_raw)

    if def_out_dict["other_fields_raw"] != def_in_dict["other_fields_raw"]:
        raise RuntimeError("default.pb unknown fields raw bytes were altered!")

    if not allow_global_default:
        if def_out_dict["version"] != 79000000099:
            raise RuntimeError(f"default.pb expected baseline version 79000000099, got {def_out_dict['version']}")
        for exp_k in VCRBT_EXPERIMENTAL_KEYS:
            if exp_k in def_out_dict["configs"]:
                raise RuntimeError(f"default.pb contains experimental key '{exp_k}' when allow_global_default=False")
    else:
        if def_out_dict["version"] != TARGET_DEFAULT_VERSION:
            raise RuntimeError(f"default.pb version mismatch: {def_out_dict['version']}")

    print(
        f"[SELF-CHECK PASS] others.pb: {len(verified_targets)} target carriers verified, "
        f"{unchanged_carrier_count} non-target carriers 100% byte-identical, "
        f"{preserved_top_unknown_count} top-level unknown field(s) preserved!"
    )
    return {
        "target_carriers_patched": len(verified_targets),
        "non_target_carriers_unchanged": unchanged_carrier_count,
        "top_unknown_fields_preserved": preserved_top_unknown_count,
        "default_pb_version": def_out_dict["version"],
    }


def recover_from_retained_backup(
    rollback_dir: str,
    out_dir: Optional[str] = None,
    restore_copy_fn: Optional[Callable[[str, str], Any]] = None,
    remove_fn: Optional[Callable[[str], Any]] = None,
    verify_sha_fn: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """
    从保留的回滚备份槽 (rollback_dir) 恢复候选目录文件并逐项校验：
      - 对每个待恢复目标单独捕获异常，单点失败不中断其余目标恢复；
      - 仅操作本次候选目标列表 (all_rel_targets)，绝不触碰或删除模块目录中的无关文件；
      - 逐项校验旧文件（含旧 manifest.json）的 SHA256 哈希，以及原先不存在的新增文件是否已彻底移除；
      - 若任一目标恢复/删除/校验失败，必须完整保留 rollback_dir 并抛出含绝对备份路径的异常；
      - 仅当全部目标恢复且校验通过后，才清理 rollback_dir。
    """
    rollback_dir = os.path.abspath(rollback_dir)
    meta_path = os.path.join(rollback_dir, "_rollback_meta.json")
    if not os.path.isfile(meta_path):
        raise RuntimeError(f"Recovery metadata missing in retained backup: {meta_path}")

    with open(meta_path, "r", encoding="utf-8") as mf:
        meta = json.load(mf)

    target_out_dir = os.path.abspath(out_dir if out_dir is not None else meta["out_dir"])
    all_rel_targets: List[str] = meta["all_rel_targets"]
    existed_before: Dict[str, bool] = meta["existed_before"]
    pre_hashes: Dict[str, Optional[str]] = meta["pre_hashes"]

    actual_restore_copy = restore_copy_fn if restore_copy_fn is not None else shutil.copy2
    actual_remove = remove_fn if remove_fn is not None else os.remove
    actual_verify_sha = verify_sha_fn if verify_sha_fn is not None else sha256_file

    def _safe_target_path(rel_path: str) -> str:
        norm_rel = os.path.normpath(rel_path)
        if os.path.isabs(norm_rel) or norm_rel.startswith(".."):
            raise RuntimeError(f"Unsafe relative target path rejected: {rel_path}")
        full_p = os.path.abspath(os.path.join(target_out_dir, norm_rel))
        if os.path.commonpath([target_out_dir, full_p]) != target_out_dir or full_p == target_out_dir:
            raise RuntimeError(f"Target path escapes candidate output directory: {full_p}")
        return full_p

    def restore_one(rel_path: str) -> None:
        dst_f = _safe_target_path(rel_path)
        if existed_before.get(rel_path, False):
            bak_f = os.path.join(rollback_dir, rel_path)
            if not os.path.isfile(bak_f):
                raise FileNotFoundError(f"Backup file missing in rollback slot: {bak_f}")
            os.makedirs(os.path.dirname(dst_f), exist_ok=True)
            actual_restore_copy(bak_f, dst_f)
        else:
            if os.path.exists(dst_f):
                actual_remove(dst_f)

    def verify_restored(rel_path: str) -> None:
        dst_f = _safe_target_path(rel_path)
        if existed_before.get(rel_path, False):
            if not os.path.isfile(dst_f):
                raise RuntimeError(f"Restored file missing after restore: {dst_f}")
            expected_sha = pre_hashes.get(rel_path)
            actual_sha = actual_verify_sha(dst_f)
            if actual_sha != expected_sha:
                raise RuntimeError(
                    f"Restored SHA256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"
                )
        else:
            if os.path.exists(dst_f):
                raise RuntimeError(f"Newly created file was not removed during rollback: {dst_f}")

    rollback_errors = []
    for rel in all_rel_targets:
        try:
            restore_one(rel)
            verify_restored(rel)
        except Exception as error:
            rollback_errors.append((rel, str(error)))

    if rollback_errors:
        raise RuntimeError(
            f"Recovery incomplete; retain backup at {rollback_dir}: {rollback_errors}"
        )

    shutil.rmtree(rollback_dir)
    return {
        "status": "recovered",
        "rollback_dir": rollback_dir,
        "backup_cleaned": not os.path.exists(rollback_dir),
        "restored_targets": all_rel_targets,
    }


def publish_atomically_with_rollback(
    staging_dir: str,
    out_dir: str,
    rel_files: List[str],
    manifest_data: Dict[str, Any],
    copy_fn: Optional[Callable[[str, str], Any]] = None,
    write_manifest_fn: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    restore_copy_fn: Optional[Callable[[str, str], Any]] = None,
    remove_fn: Optional[Callable[[str], Any]] = None,
    verify_sha_fn: Optional[Callable[[str], str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    [B2 修复] 异常可回滚发布器 (带持久备份槽、单目标隔离恢复与完整性校验):
      - 注意：多文件逐次替换属于“异常可回滚发布”，不保证并发读取或进程骤停时的全文件原子可见性；
        部署阶段应保持离线候选构建与受控切换。
      1. 在 staging_dir 中先生成完整 manifest.json 并计算全部 4 项产物的哈希与大小；
      2. 将 out_dir 中已存在的候选文件与 manifest.json 完整备份至持久回滚槽 rollback_dir，
         并写入 _rollback_meta.json（记录存在性与旧文件 SHA256）；
      3. 依次将 4 项文件与 manifest.json 发布到 out_dir（先写同目录 .tmp 临时文件再 os.replace）；
      4. 若发布或发布后校验发生异常，调用 recover_from_retained_backup() 逐个恢复并校验：
         - 仅在全部目标恢复并校验成功后清理 rollback_dir；
         - 若任一目标恢复/删除/校验失败，保留 rollback_dir 并在异常中报告绝对备份路径。
    """
    out_dir = os.path.abspath(out_dir)
    actual_copy_fn = copy_fn if copy_fn is not None else shutil.copy2

    output_manifest = {}
    for rel in rel_files:
        src_f = os.path.join(staging_dir, rel)
        output_manifest[rel.replace("\\", "/")] = {
            "sha256": sha256_file(src_f),
            "size_bytes": os.path.getsize(src_f),
        }

    manifest_data["outputs"] = output_manifest
    staging_manifest_path = os.path.join(staging_dir, "manifest.json")
    with open(staging_manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest_data, mf, indent=2, ensure_ascii=False)
    expected_manifest_sha = sha256_file(staging_manifest_path)

    all_rel_targets = list(rel_files) + ["manifest.json"]
    rollback_dir = os.path.abspath(tempfile.mkdtemp(prefix="enablepixel5g_rollback_"))

    existed_before: Dict[str, bool] = {}
    pre_hashes: Dict[str, Optional[str]] = {}
    try:
        for rel in all_rel_targets:
            dst_f = os.path.join(out_dir, rel)
            if os.path.isfile(dst_f):
                existed_before[rel] = True
                bak_f = os.path.join(rollback_dir, rel)
                os.makedirs(os.path.dirname(bak_f), exist_ok=True)
                shutil.copy2(dst_f, bak_f)
                pre_hashes[rel] = sha256_file(bak_f)
            else:
                existed_before[rel] = False
                pre_hashes[rel] = None

        meta_path = os.path.join(rollback_dir, "_rollback_meta.json")
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(
                {
                    "out_dir": out_dir,
                    "all_rel_targets": all_rel_targets,
                    "existed_before": existed_before,
                    "pre_hashes": pre_hashes,
                },
                mf,
                indent=2,
                ensure_ascii=False,
            )
    except Exception:
        shutil.rmtree(rollback_dir, ignore_errors=True)
        raise

    try:
        for rel in rel_files:
            src_f = os.path.join(staging_dir, rel)
            dst_f = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(dst_f), exist_ok=True)
            tmp_dst = dst_f + ".publishing.tmp"
            try:
                actual_copy_fn(src_f, tmp_dst)
                os.replace(tmp_dst, dst_f)
            finally:
                if os.path.exists(tmp_dst):
                    try:
                        os.remove(tmp_dst)
                    except OSError:
                        pass

        dst_manifest = os.path.join(out_dir, "manifest.json")
        if write_manifest_fn is not None:
            write_manifest_fn(dst_manifest, manifest_data)
        else:
            tmp_mf = dst_manifest + ".publishing.tmp"
            try:
                actual_copy_fn(staging_manifest_path, tmp_mf)
                os.replace(tmp_mf, dst_manifest)
            finally:
                if os.path.exists(tmp_mf):
                    try:
                        os.remove(tmp_mf)
                    except OSError:
                        pass

        # 发布后最终一致性校验
        for rel in rel_files:
            dst_f = os.path.join(out_dir, rel)
            expected_sha = output_manifest[rel.replace("\\", "/")]["sha256"]
            if not os.path.isfile(dst_f) or sha256_file(dst_f) != expected_sha:
                raise RuntimeError(f"Post-publish verification failed for {dst_f}")
        if not os.path.isfile(dst_manifest):
            raise RuntimeError("Post-publish verification failed: manifest.json missing")
        if write_manifest_fn is None and sha256_file(dst_manifest) != expected_manifest_sha:
            raise RuntimeError("Post-publish verification failed: manifest.json hash mismatch")

    except Exception as pub_err:
        try:
            recover_from_retained_backup(
                rollback_dir=rollback_dir,
                out_dir=out_dir,
                restore_copy_fn=restore_copy_fn if restore_copy_fn is not None else copy_fn,
                remove_fn=remove_fn,
                verify_sha_fn=verify_sha_fn,
            )
        except Exception as rec_err:
            raise RuntimeError(f"Publish failed ({pub_err}); {rec_err}") from rec_err
        raise RuntimeError(f"Exception-rollbackable publish failed and rolled back cleanly: {pub_err}") from pub_err

    # 发布并校验全部成功后清理回滚槽
    shutil.rmtree(rollback_dir, ignore_errors=True)
    return output_manifest


def run_build(
    in_dir: str,
    out_dir: str,
    profile: str = "base",
    allow_global_default: bool = False,
    source_manifest_path: str = DEFAULT_SOURCE_MANIFEST_PATH,
    allow_unverified_source: bool = False,
    trusted_baseline_default_pb_path: Optional[str] = None,
    copy_fn: Optional[Callable[[str, str], Any]] = None,
    write_manifest_fn: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    restore_copy_fn: Optional[Callable[[str, str], Any]] = None,
    remove_fn: Optional[Callable[[str], Any]] = None,
    verify_sha_fn: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """可编程调用的完整构建入口 (便于自动化故障注入测试)"""
    in_dir = os.path.abspath(in_dir)
    out_dir = os.path.abspath(out_dir)

    # 1. [B1] 执行独立来源清单准入校验
    admission = load_and_verify_source_admission(
        in_dir=in_dir,
        source_manifest_path=source_manifest_path,
        allow_unverified_source=allow_unverified_source
    )

    if trusted_baseline_default_pb_path is None and os.path.isfile(source_manifest_path):
        candidate_trusted_default = os.path.join(os.path.dirname(os.path.abspath(source_manifest_path)), "default.pb")
        if os.path.isfile(candidate_trusted_default):
            trusted_baseline_default_pb_path = candidate_trusted_default

    rel_files = [
        os.path.join("vendor_override", "cfg.db"),
        os.path.join("vendor_override", "open_carrier_info.dat"),
        os.path.join("product_override", "others.pb"),
        os.path.join("product_override", "default.pb"),
    ]

    with tempfile.TemporaryDirectory(prefix="enablepixel5g_build_") as staging_dir:
        cfg_out = os.path.join(staging_dir, "vendor_override", "cfg.db")
        dat_out = os.path.join(staging_dir, "vendor_override", "open_carrier_info.dat")
        others_out = os.path.join(staging_dir, "product_override", "others.pb")
        default_out = os.path.join(staging_dir, "product_override", "default.pb")

        db_res = patch_cfg_db(os.path.join(in_dir, "cfg.db"), cfg_out)
        print(f"[1/4] cfg.db patched & verified: {db_res}")

        rec_cnt = patch_open_carrier_info(os.path.join(in_dir, "open_carrier_info.dat"), dat_out)
        print(f"[2/4] open_carrier_info.dat patched: {rec_cnt} OC records")

        patched_list = patch_others_pb(os.path.join(in_dir, "others.pb"), others_out, profile=profile)
        print(f"[3/4] others.pb patched ({len(patched_list)} targets): {patched_list}")

        def_res = patch_default_pb(
            os.path.join(in_dir, "default.pb"),
            default_out,
            profile=profile,
            allow_global_default=allow_global_default,
            trusted_baseline_default_pb_path=trusted_baseline_default_pb_path,
            trusted_baseline_default_pb_sha256=admission.get("trusted_default_pb_sha256")
        )
        print(f"[4/4] default.pb processed: {def_res}")

        check_summary = verify_all_outputs(
            in_dir,
            staging_dir,
            profile=profile,
            allow_global_default=allow_global_default,
            trusted_baseline_default_pb_path=trusted_baseline_default_pb_path
        )

        manifest_data = {
            "module_version": "v2.4-mustang",
            "target_device": "mustang",
            "validated_build_id": "CP3A.260905.009",
            "profile": profile,
            "allow_global_default": allow_global_default,
            "source_verified": admission["source_verified"],
            "source_admission_mode": admission["admission_mode"],
            "source_manifest_sha256": admission["source_manifest_sha256"],
            "baseline_id": admission["baseline_id"],
            "python_version": sys.version.split()[0],
            "sqlite_runtime_version": sqlite3.sqlite_version,
            "builder_sha256": sha256_file(os.path.abspath(__file__)),
            "inputs": {k: v["sha256"] for k, v in admission["actual_inputs"].items()},
            "outputs": {},
            "verification": check_summary,
        }

        output_manifest = publish_atomically_with_rollback(
            staging_dir=staging_dir,
            out_dir=out_dir,
            rel_files=rel_files,
            manifest_data=manifest_data,
            copy_fn=copy_fn,
            write_manifest_fn=write_manifest_fn,
            restore_copy_fn=restore_copy_fn,
            remove_fn=remove_fn,
            verify_sha_fn=verify_sha_fn,
        )

    print("\n=== Artifact SHA256 Manifest (written to manifest.json) ===")
    for rel_key, meta in output_manifest.items():
        print(f"  {rel_key:38s} : {meta['sha256']} ({meta['size_bytes']} bytes)")

    return manifest_data


def main():
    parser = argparse.ArgumentParser(description="EnablePixel5G v2.4 Transactional Builder & Source Verifier")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Input directory containing baseline files"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output module directory"
    )
    parser.add_argument(
        "--profile",
        choices=["base", "vcrbt"],
        default="base",
        help="Build profile: 'base' (default) or 'vcrbt'"
    )
    parser.add_argument(
        "--allow-global-default",
        action="store_true",
        default=False,
        help="Explicitly patch global default.pb (disabled by default)"
    )
    parser.add_argument(
        "--source-manifest",
        default=DEFAULT_SOURCE_MANIFEST_PATH,
        help="Path to registered source_manifest.json for input hash admission control"
    )
    parser.add_argument(
        "--allow-unverified-source",
        action="store_true",
        default=False,
        help="Explicitly allow building from unregistered input hashes (marks source_verified=false in manifest)"
    )
    parser.add_argument(
        "--trusted-default-pb",
        default=None,
        help="Path to trusted baseline default.pb when restoring from a modified global default.pb"
    )
    args = parser.parse_args()

    print(
        f"=== EnablePixel5G v2.4-mustang Builder "
        f"(Profile: {args.profile}, GlobalDefault: {args.allow_global_default}, "
        f"AllowUnverifiedSource: {args.allow_unverified_source}) ==="
    )
    run_build(
        in_dir=args.input_dir,
        out_dir=args.output_dir,
        profile=args.profile,
        allow_global_default=args.allow_global_default,
        source_manifest_path=args.source_manifest,
        allow_unverified_source=args.allow_unverified_source,
        trusted_baseline_default_pb_path=args.trusted_default_pb
    )


if __name__ == "__main__":
    main()
