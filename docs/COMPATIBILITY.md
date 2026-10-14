# 参数与兼容边界

## 来源与署名

原模块为 PixelVo5G Enabler for Global / EnablePixel5G，备份版本 v1.1、versionCode 10，作者 Sun_Dream（Sun）。原描述为 Pixel56789TenVoLTE+VoNR for Global。
原始属性包括 persist.dbg.volte_avail_ovr、persist.dbg.vt_avail_ovr、persist.dbg.wfc_avail_ovr、persist.rcs.supported。
原始文本保留在 upstream/original_module.prop.txt 和 upstream/original_system.prop.txt；没有确认原作者的 GitHub 地址。

本项目由 v2.5-mustang-experimental 工程派生，该阶段署名 Cassius & Antigravity。自 v2.6.0 起由 [iCassius](https://github.com/iCassius) 维护，保留 EnablePixel5G 模块 ID 以支持原位升级。
来源备份未提供明确许可证，未重新标注为 MIT。厂商 PB／数据库等保留在本地 private/，公开框架包不包含这些载荷。

维护：iCassius，2026-10-14。当前只保留 mustang / CP3A.260905.009 的历史设备证据；新 v2.6 尚未部署。

## 可以共用的候选

| 参数 | 平台定义 | 兜底规则 |
|---|---|---|
| carrier_volte_available_bool | AOSP VoLTE 可用性，API 23 | 已识别国内订阅且实际值为 Boolean 才写 true |
| carrier_wfc_ims_available_bool | AOSP VoWiFi 可用性，API 23 | 同上；不改用户开关、默认路由或漫游模式 |
| carrier_nr_availabilities_int_array | AOSP SA／NSA 可用性，API 31 | 必须存在且为 int[]，仅含已知枚举或空数组；写 [1,2] |
| vonr_enabled_bool | AOSP VoNR 启用，API 34 | API 34+ 且实际值为 Boolean |
| vonr_on_by_default_bool | AOSP VoNR 默认用户偏好，API 34 | 同上；不保证覆盖既有用户选择 |
| vonr_setting_visibility_bool | AOSP VoNR 菜单，API 34 | 同上 |

来源：[Android CarrierConfigManager 官方定义](https://developer.android.com/reference/android/telephony/CarrierConfigManager)。
配置键共用是 API／语义层判断，不是基带硬件、网络开通、IMS 注册或真实呼叫兼容证明。
没有对应键或类型异常就跳过，不制造 false，不写厂商同名替代键。空策略不发 Binder 写入。

## 仅当前 Pixel 10 基线

- 机型 mustang、系统 CP3A.260905.009、基带 g5400i-260604-260807-B-16035863；必须精确匹配且四项文件哈希在登记集合中。
- cfg.db、open_carrier_info.dat、others.pb、default.pb：全部按同一完整基线门控，任意一项不匹配均零挂载。
- imsvt.*、vendor.ims.*、视频 QoS／SDP／音频彩铃防降级、电信 IMS APN 和网络显示阈值不推广。
- 基带早期报告值 g5400i-250605-250825-B-13984049 与后续呼叫日志不一致，旧值不加入许可名单。
- 所谓“完整策略”仅电信 carrierId 2237／46011 使用持久 Binder 配置；其他国内订阅使用框架兜底。
- 私有载荷来自 v2.5 已登记候选，不是根据任意 ROM 自动生成。基线快照含历史修改，不能称为纯出厂数据。

## 四家与国际运营商

移动 46000／46002／46004／46007／46008；联通 46001／46006／46009；电信 46003／46005／46011；广电 46015。
该白名单用于国内主网络范围，不声称覆盖所有虚拟运营商或未来新号段。其他 PLMN 直接跳过，SIM 本身标识用于匹配，不按驻留网络判断。
国内／国际双卡：仅国内订阅发差量覆盖；全部国际卡时输出 targetCount=0、零写入。
完整私有载荷对其他运营商的保留继承自 v2.5 构建的非目标字节保留，不等于本轮所有国际网络实测。

## 生命周期与退回

框架兜底 persistent=false，不把新策略永久落盘；运行守护周期检查和恢复。写入前重新确认 SIM 身份、LOADED、运营商识别与 Telecom 空闲。
它不能事务性锁定换卡或通话发生的瞬间，也不保证所有系统都会接受 Binder 接口；接口不可用则报错并退避。
不能清除其他所有者覆盖；旧 v2.5 持久厂商配置不会因新版本兼容门控自动删除。如要跨 OTA 升级旧安装，需先审计旧覆盖。
profile=vcrbt 在兜底模式只使用 framework 策略，不加载视频实验；状态区分 requestedProfile 和 effectiveProfile。

## 设备验证矩阵

Pixel 6～11 为需求目标，当前框架入口接受 Google 型号名称及 API 31～36；没有逐代实机验收。
Pixel 11 的名称仅预留，Android 17／API 37 未审核，当前停止安装／写入，等待实际基线后适配。
v2.6 Java 编译、DEX 构建、纯规则测试、shell 模拟和 ZIP 检查属于离线证据。
还需逐机型／运营商测试 IMS 注册、SA／NSA、VoLTE／VoNR／VoWiFi、双卡、海外卡、冷启动、SIM 切换、OTA、禁用后的行为。
