# Pixel_5G_IMS_Enhanced v2.6.4

## 功能

- 国内移动、联通、电信、广电的 VoLTE／VoWiFi／SA／NSA／VoNR 框架配置。
- 正式包包含基带配置，按基带版本及 vendor／CarrierSettings 文件基线分别加载；不匹配时使用基础框架配置。
- 支持双卡基带识别，不限制 Android API 上限。
- 保留原生视频能力，移除 Base／VCRBT 策略及 CDMA 修改入口。
- 框架配置采用非持久覆盖，支持配置读回、定期维护和挂载失败回滚。
- 保留国际运营商配置，提供 KernelSU 更新入口及 GitHub Releases 按钮。

## 实机记录

2026-10-15，Pixel 10 Pro XL、Android 17、中国电信：安装前检查通过；双卡基带及文件基线匹配；六项运营商参数只读获取成功，配置覆盖接口及通话状态接口可用。
