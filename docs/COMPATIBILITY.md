# 适用范围与运行条件

v2.6.6-dev1 按用户要求改为 Pixel 9／10 系列实验适配。维护者 iCassius，保留原作者 Sun_Dream 和原始来源。

## 安装

要求制造商 Google、品牌 google，型号为 Pixel 9、9 Pro、9 Pro XL、9 Pro Fold、9a，或 Pixel 10、10 Pro、10 Pro XL、10 Pro Fold、10a。Android API 最低为 31（DEX 运行要求），没有版本上限。其他型号拒绝安装，后台和配置助手也重复检查。

## 专用文件挂载

正式载荷包包含 cfg.db、open_carrier_info.dat、others.pb、default.pb。按设备系列选择，不限制基带字符串，也不要求系统原文件的摘要在历史清单内；g5400c、g5400i、未知或尚未就绪的基带均不阻止挂载。不再核验 modem 分区、镜像、CBD 程序及启动脚本。

vendor 和 product 两组独立检查，各组的两个目标文件必须存在且可读。模块自身检测脚本、策略、目标表及载荷仍核验 SHA256。挂载仅在 CBD、Zygote 启动前、系统尚未完成开机且当前挂载命名空间与 init 一致时进行，没有晚期补挂。

使用新的 /dev 会话镜像执行 bind mount，验证镜像内容、SELinux 上下文及挂载内容。相同内容跳过，不覆盖内容不同的已有挂载；失败逆序撤销本次新增挂载，撤销失败保留镜像。

这些检查证明文件部署结果，不证明跨机型配置兼容，也不证明消费者已解析或采用配置。Pixel 9／10 的实验适配范围不等于实机验证范围。

## 框架参数与幂等

仅处理移动 46000／46002／46004／46007／46008、联通 46001／46006／46009、电信 46003／46005／46011、广电 46015 的就绪订阅；国际卡和未知 PLMN 跳过框架修改。专用文件挂载是系统级操作，不按 SIM 隔离。

只选择实际存在且类型正确的 carrier_volte_available_bool、carrier_wfc_ims_available_bool、vonr_enabled_bool、vonr_on_by_default_bool、vonr_setting_visibility_bool、carrier_nr_availabilities_int_array。未知 NR 枚举保留。写入前重新检查订阅身份、SIM、运营商配置及通话空闲；原值符合则不写，写入使用 persistent=false 并读回验证。定期维护和挂载分别加锁。

不清空其他模块的覆盖，不清理历史持久覆盖。禁用或卸载后重启撤销本版挂载及非持久覆盖。彩铃与视频专项功能继续由 PixelVcrbt 管理。

## 自检

自检关联本次开机和模块清单，检查四项载荷在 init、cbd、rild_exynos、IMS、phone 和 carrier 进程中的可见性，以及所有目标订阅的六项框架参数。绿勾只表示挂载和框架读回通过；卡片保留“适配待验证”。不再以固定基带判断健康状态。

框架状态使用 statusSchema=3。状态包含 compatibilityMode=pixel9_10_experimental、firmwareValidation=not_performed；observedBaseband 仅记录观测值。consumerLoad 和 businessValidation 继续表示尚未证明消费者采用配置及真实业务结果。旧版读取方需要适配新字段，不能依赖已移除的 runtimeModemMatches、modemBaseline、allowedFilesMatch 等字段。

管理器暂存更新时可能先改活动 module.prop，导致旧清单报警；此问题本次未修复。升级后需要重启，旧记录不能证明新版本开机挂载成功。

## 验证范围

此前 v2.6.5 在 Pixel 10 Pro XL 上验证过早期挂载、框架读回及 5G SA／IMS over NR 注册。本次候选改变了准入规则，旧结果不能替代新版或其他型号的安装、开机和通信验证。历史调查见 BOOT_MOUNT_RESEARCH.md、VALIDATION.md。
