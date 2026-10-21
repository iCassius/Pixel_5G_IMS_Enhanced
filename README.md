# Pixel_5G_IMS_Enhanced

基于 Sun_Dream 的 PixelVo5G Enabler for Global v1.1 优化，维护者 [iCassius](https://github.com/iCassius)。

**适配 Pixel 10 全系列，实验性支持 Pixel 9 系列；其他系列直接提示安装失败。**包含两代的标准版、Pro、Pro XL、Pro Fold 和 a 机型。要求 Google 原厂品牌及型号属性、Android API 31 或以上，没有 Android 版本上限。

已发布版本：[v2.6.5](https://github.com/iCassius/Pixel_5G_IMS_Enhanced/releases/tag/v2.6.5)。本页说明当前开发候选 **v2.6.6-dev2** 的行为，已发布版本仍采用旧的适配条件。安装或更新后重启一次。

## 提供的功能

- 提供运营商专用配置及 VoLTE、VoWiFi、SA／NSA、VoNR 框架参数。
- 按 Pixel 10／9 系列选择，不限制基带字符串或系统原文件摘要；各组目标文件存在且可读时，在开机早期尝试挂载。
- 框架参数仅处理国内移动、联通、电信、广电白名单订阅，只修改存在且类型正确的参数；原值符合则跳过，写入采用非持久覆盖并读回验证。
- 保留模块载荷完整性、镜像内容、挂载冲突检查及失败回滚。专用文件为系统级挂载，不按 SIM 隔离。
- 原文件内容已经符合载荷时无需重复挂载，自检同样识别为通过。未执行检查显示“未检查”。
- 管理器已暂存完整更新且活动版本信息与暂存包一致时，提示“更新已暂存，重启后生效”；真正的文件异常继续报错。
- 挂载事务未完成时提示重启复查；不在电话进程启动后补挂。操作按钮执行只读复查。
- 彩铃及视频专项功能由独立 PixelVcrbt 模块管理。

## 如何看状态

模块卡片中的“文件 4/4、框架通过”表示当前文件内容及框架参数检查通过，可以包含原文件本来就符合要求的情况。跳过检查、旧记录、缺失进程或实际异常分别报告，不能仅凭绿勾判断 IMS 注册或 VoNR／VoWiFi 通话成功。

Pixel 10 全系列是当前适配范围，实机证据目前来自 Pixel 10 Pro XL；Pixel 9 系列标注为实验性支持。此前 v2.6.5 已在 Pixel 10 Pro XL／Android 17／中国电信确认早期挂载、配置读回及 5G SA／IMS over NR 注册，新候选和其他机型仍需对应验证。

[适用范围与运行说明](docs/COMPATIBILITY.md) · [本次修复验证](docs/VALIDATION_v2.6.6-dev2.md) · [历史实机记录](docs/VALIDATION.md)
