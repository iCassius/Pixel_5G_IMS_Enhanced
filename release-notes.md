# Pixel_5G_IMS_Enhanced v2.6.3

## 功能

- 国内移动、联通、电信、广电的 VoLTE／VoWiFi／SA／NSA／VoNR 框架配置。
- 国际卡和未知 PLMN 保留系统配置。
- 按系统版本、参数存在性和类型选择配置，基带不匹配时使用框架兜底。
- 配置读回和定期维护，支持 Base／VCRBT 策略选择。
- KernelSU 更新入口和 GitHub Releases 按钮。
- 本次发布为框架包。
- 移除 Android API 上限，按可用接口和参数类型判断配置能力。
- 支持双卡重复基带值，vendor 与 CarrierSettings PB 分别检查文件基线。

## 本机记录（Android 17）

2026-10-15，Pixel 10 Pro XL、中国电信：安装前检查通过；双卡基带版本识别一致；读取六项运营商参数，配置覆盖接口和通话状态接口可用。

## 已有实机记录（KSU v2.5）

2026-10-14，Pixel 10 Pro XL（mustang）、Android 16 CP3A.260905.009、中国电信 46011：

- 四项配置挂载完成，文件哈希和 SELinux 标签核验通过。
- VCRBT 策略写入及受管值读回成功，日志记录 `matchesPolicy=true`。
- 开机守护生成成功的 `status.json`。
- VoLTE、VoWiFi、VoNR 参数读回为启用。
