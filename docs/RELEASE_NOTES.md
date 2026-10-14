# Pixel_5G_IMS_Enhanced v2.6.2-experimental

基于 Sun_Dream 的 PixelVo5G Enabler for Global v1.1，后续维护 iCassius。

提供国内移动、联通、电信、广电的 VoLTE／VoWiFi／SA／NSA／VoNR 框架配置，保留国际及未知 PLMN 的原有配置。
本次公开 ZIP 仅框架兜底，不含 mustang 的 vendor／PB 基带载荷；Base／VCRBT 在框架层均不启用厂商视频实验参数。

新增模块更新入口和 Releases 按钮，预发布版本通过独立更新源通知。修复守护与手动切换的 Profile 回写竞争。

Android API 31～36 的 Google Pixel 6～11 型号名称为实验入口范围，VoNR 参数要求 API 34+；未知 SDK 停止安装／写入。
新版本只完成离线构建与模拟检查，未验证跨型号或四家真实网络能力。旧安装的持久覆盖不会自动清除；禁用后需重启并审计残留。

ZIP 对应 SHA256 和 update-framework.json 为本 Release 附件。模块 ID 仍为 EnablePixel5G，请勿与旧模块并行安装。
