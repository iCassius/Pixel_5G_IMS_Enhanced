# Pixel_5G_IMS_Enhanced

基于 Sun_Dream 的 PixelVo5G Enabler for Global v1.1 优化，维护者 iCassius。
已发布版本：[v2.6.5](https://github.com/iCassius/Pixel_5G_IMS_Enhanced/releases/tag/v2.6.5)。安装后重启一次。

Pixel 10 Pro XL／Android 17／中国电信已确认早期挂载、配置回读、模块卡片自检和 5G SA／IMS over NR 注册。实际通话及其他机型、固件仍需验证，详见 [验证记录](docs/VALIDATION.md)。

开发候选：v2.6.6-dev1，安装范围为 Pixel 9／10 系列（含 a、Fold）；取消基带和系统原文件摘要限制，跨机型通信效果待验证。

## 原模块基础与问题

原模块提供运营商配置、APN，以及 VoLTE／视频通话／VoWiFi 可用性和 RCS 支持标志。

Pixel 10 实测未生效，缺少 g5400i 基带策略适配和电信 IMS APN 定向处理；

## 新增功能

- 载荷包提供 vendor 和 CarrierSettings PB 配置；Pixel 9／10 系列按各组目标文件是否存在、可读选择挂载，模块载荷继续核验完整性。
- 框架参数仅处理国内移动、联通、电信、广电白名单订阅；专用文件挂载为系统级操作。
- 提供 VoLTE、VoWiFi、SA／NSA、VoNR 配置。
- 框架配置按实际参数类型选择，采用非持久覆盖。
- 配置读回、定期检查、挂载失败回滚。
- 开机挂载逐文件记录；当前兼容检查、开机挂载结果与框架回读分别报告，未验证的专项加载与业务效果保持未知。
- 仅在开机早期、与 init 相同的挂载命名空间加载；不进行晚期补挂。
- 彩铃及视频专项参数由独立 PixelVcrbt 模块管理。
- 模块卡片显示带检查时间的状态；操作按钮执行只读复查，更新仍使用 KernelSU 更新按钮。
- 自检关联本次开机和模块清单，核对六类进程的挂载与载荷；检查失败不沿用旧绿勾，真实通话单独验证。
- 不限制 Android 版本上限，按实际接口和参数类型选择配置；兼容双卡基带属性。
