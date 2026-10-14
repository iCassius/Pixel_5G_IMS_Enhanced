# Pixel_5G_IMS_Enhanced

基于 Sun_Dream 的 PixelVo5G Enabler for Global v1.1 优化，维护者 iCassius。
当前版本：v2.6.4。

## 原模块基础与问题

原模块提供运营商配置、APN，以及 VoLTE／视频通话／VoWiFi 可用性和 RCS 支持标志。

Pixel 10 实测未生效，缺少 g5400i 基带策略适配和电信 IMS APN 定向处理；

## 新增功能

- 正式包包含基带配置；基带及 vendor 文件基线匹配后启用，CarrierSettings PB 独立检查，不匹配时使用基础框架配置。
- 国内移动、联通、电信、广电配置白名单；国际卡和未知 PLMN 使用系统默认。
- 提供 VoLTE、VoWiFi、SA／NSA、VoNR 配置。
- 框架配置按实际参数类型选择，采用非持久覆盖。
- 配置读回、定期检查、挂载失败回滚。
- 彩铃及视频专项参数由独立 PixelVcrbt 模块管理。
- KernelSU 更新入口及 GitHub Releases 操作按钮。
- 不限制 Android 版本上限，按实际接口和参数类型选择配置；兼容双卡基带属性。
