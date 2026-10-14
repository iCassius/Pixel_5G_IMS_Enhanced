# Pixel_5G_IMS_Enhanced

基于 PixelVo5G Enabler for Global v1.1 By Sun_Dream 模块更新优化
当前 v2.6.2-experimental。

## 原模块基础与问题

原模块提供运营商配置、APN，以及 VoLTE／视频通话／VoWiFi 可用性和 RCS 支持标志。

Pixel 10 实测未生效，缺少 g5400i 基带策略适配和电信 IMS APN 定向处理；

## 新增功能

- Pixel 10 专用基带包要求型号、系统、基带和文件均匹配；不匹配时跳过。公开框架包不含基带载荷。
- 国内移动、联通、电信、广电配置白名单；国际卡和未知 PLMN 使用系统默认。
- 提供 VoLTE、VoWiFi、SA／NSA、VoNR 配置，实际能力需实机验证；
- 配置读回、定期检查、Base／VCRBT 切换及挂载失败回滚。
- KernelSU 更新入口及 GitHub Releases 操作按钮。

当前新版仅完成离线检查，尚未作跨型号、四家运营商实机验收。
