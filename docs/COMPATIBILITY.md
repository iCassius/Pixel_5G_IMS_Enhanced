# 参数与兼容边界

## 来源与署名

原模块为 PixelVo5G Enabler for Global / EnablePixel5G，备份版本 v1.1、versionCode 10，作者 Sun_Dream（Sun）。原描述为 Pixel56789TenVoLTE+VoNR for Global。
原始属性包括 persist.dbg.volte_avail_ovr、persist.dbg.vt_avail_ovr、persist.dbg.wfc_avail_ovr、persist.rcs.supported。
原始文本保留在 upstream/original_module.prop.txt 和 upstream/original_system.prop.txt；没有确认原作者的 GitHub 地址。

本项目由 v2.5-mustang-experimental 工程派生，该阶段署名 Cassius & Antigravity。自 v2.6.0 起由 [iCassius](https://github.com/iCassius) 维护，保留 EnablePixel5G 模块 ID 以支持原位升级。
来源备份未提供明确许可证，未重新标注为 MIT。厂商文件不提交源码；正式 ZIP 携带经过哈希校验的载荷，构建输入保留在本地 private/。

## 设备与基带判断

安装、挂载和框架助手均限定 Google／google 的 Pixel 6～11 型号白名单。DEX 最低 API 31，无 API 上限。
基带精确匹配 g5400i-260604-260807-B-16035863；按逗号拆分、去除首尾空白，接受双卡相同版本，拒绝未知、混合和空字段。

- vendor：基带匹配且 cfg.db／open_carrier_info.dat 两项当前哈希均登记后才加载。
- product：基带匹配且 others.pb／default.pb 两项当前哈希均登记后才加载。
- 两组独立选择；不以 build ID 或 API 数字替代实际文件内容核验。
- 挂载前核验检测脚本、基线表、策略及所有选中载荷的完整性。使用 /dev 会话镜像 bind mount，不覆盖系统分区原文件。
- 同内容跳过重复挂载，冲突停止；失败逆序卸载本次挂载，卸载失败保留镜像供排查。

## 基础框架能力

移动 46000／46002／46004／46007／46008；联通 46001／46006／46009；电信 46003／46005／46011；广电 46015。
其他 PLMN 跳过；只按 SIM 主运营商匹配，不按当前驻留网络改写国际卡。

所有国内订阅仅选择实际存在且类型正确的六项基础键：
carrier_volte_available_bool、carrier_wfc_ims_available_bool、vonr_enabled_bool、vonr_on_by_default_bool、vonr_setting_visibility_bool、carrier_nr_availabilities_int_array。
前五项写 true；SA／NSA 数组仅在现有值为空或只包含已知枚举 1／2 时写 [1,2]，未知枚举保留。
来源：[Android CarrierConfigManager](https://developer.android.com/reference/android/telephony/CarrierConfigManager)。

写入前检查运营商已识别、SIM 已加载、订阅身份未变化、Telecom 通话空闲和 Binder 接口可用；写入后读回核验。
所有新框架写入均使用 persistent=false。专项能力由已通过基线检查的 vendor／PB 文件提供，基带不匹配时不挂载这些文件。
定期守护维持框架参数；运行时不写视频、彩铃、CDMA、APN 或未知厂商键。

## 视频与旧版本边界

正式包修复旧 Base PB 对电信 46011 carrier_vt_available_bool 的 false 覆盖，保留原生视频可用性。
不包含 Base／VCRBT 配置档或切换入口，不读取旧 profile.conf。彩铃专项功能由独立 PixelVcrbt 维护。
不调用全局覆盖清空；历史版本已经持久化的参数不属于本版新增写入，不以删除其他模块配置的方式迁移。
禁用／卸载后通过重启撤销本版 bind mount 和非持久框架覆盖；不把它描述为清除历史版本的持久数据。

## 实机证据

2026-10-15，Pixel 10 Pro XL／Android 17 API 37／中国电信：安装前检查、双卡基带识别、文件基线匹配及六项框架参数只读获取通过。
本次没有执行安装、覆盖写入、真实挂载或重启；网络开通与实际呼叫结果需以升级后的实机行为为准。
载荷保留登记输入中的 683 个非目标运营商原始字节和所有 APN 子消息；本版 PB 修补仅纠正上述原生视频布尔值。
