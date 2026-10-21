# 适用范围与运行条件

v2.6.6 适配 Pixel 10 全系列，实验性支持 Pixel 9 系列；其他系列提示安装失败。维护者 iCassius，保留原作者 Sun_Dream 和原始来源。

## 安装

要求制造商 Google、品牌 google，型号为 Pixel 9、9 Pro、9 Pro XL、9 Pro Fold、9a，或 Pixel 10、10 Pro、10 Pro XL、10 Pro Fold、10a。Android API 最低为 31（DEX 运行要求），没有版本上限。其他型号拒绝安装，后台和配置助手也重复检查。

## 专用文件挂载

正式载荷包包含 cfg.db、open_carrier_info.dat、others.pb、default.pb。按设备系列选择，不限制基带字符串，也不要求系统原文件的摘要在历史清单内；g5400c、g5400i、未知或尚未就绪的基带均不阻止挂载。不再核验 modem 分区、镜像、CBD 程序及启动脚本。

vendor 和 product 两组独立检查，各组的两个目标文件必须存在且可读。模块自身检测脚本、策略、目标表及载荷仍核验 SHA256。挂载仅在 CBD、Zygote 启动前、系统尚未完成开机且当前挂载命名空间与 init 一致时进行，没有晚期补挂。

使用新的 /dev 会话镜像执行 bind mount，验证镜像内容、SELinux 上下文及挂载内容。相同内容跳过，不覆盖内容不同的已有挂载；失败逆序撤销本次新增挂载，撤销失败保留镜像。

这些检查证明文件部署结果，不证明跨机型配置兼容，也不证明消费者已解析或采用配置。Pixel 10 全系列是适配范围，Pixel 9 系列是实验支持范围，两者均不等于逐型号实机验证。

## 框架参数与幂等

仅处理移动 46000／46002／46004／46007／46008、联通 46001／46006／46009、电信 46003／46005／46011、广电 46015 的就绪订阅；国际卡和未知 PLMN 跳过框架修改。专用文件挂载是系统级操作，不按 SIM 隔离。

只选择实际存在且类型正确的 carrier_volte_available_bool、carrier_wfc_ims_available_bool、vonr_enabled_bool、vonr_on_by_default_bool、vonr_setting_visibility_bool、carrier_nr_availabilities_int_array。未知 NR 枚举保留。写入前重新检查订阅身份、SIM、运营商配置及通话空闲；原值符合则不写，写入使用 persistent=false 并读回验证。定期维护和挂载分别加锁。

不清空其他模块的覆盖，不清理历史持久覆盖。禁用或卸载后重启撤销本版挂载及非持久覆盖。彩铃与视频专项功能继续由 PixelVcrbt 管理。

## 自检

自检关联本次开机和模块清单，检查四项载荷在 init、cbd、rild_exynos、IMS、phone 和 carrier 进程中的可见性，以及所有目标订阅的六项框架参数。绿勾只表示挂载和框架读回通过；Pixel 9 的卡片附加实验适配提示。原文件已符合载荷且本次开机记录为 already_identical 时，无需独立挂载项，也可通过检查。不再以固定基带判断健康状态。

框架状态使用 statusSchema=3，自检状态使用 schema=2。mountedFiles 表示实际独立挂载且内容通过的数量，verifiedFiles 包含原文件已相同的情况；mountCheckPerformed=false 时这两个数量和 consumerViewsVerified 为 null，卡片显示未检查。状态包含 compatibilityMode=pixel9_10_experimental、firmwareValidation=not_performed；observedBaseband 仅记录观测值。consumerLoad 和 businessValidation 继续表示尚未证明消费者采用配置及真实业务结果。旧版读取方需要适配新字段，不能依赖已移除的 runtimeModemMatches、modemBaseline、allowedFilesMatch 等字段。

更新期间，只有存在 update 标记、活动目录仅 module.prop 不符、完整暂存包符合其清单、活动 module.prop 与暂存包完全一致且模块 ID／版本元信息一致时，才识别为等待重启。暂存包缺失、损坏、核心文件或载荷异常仍报错。integrityDifferences 保留版本信息差异，updatePending 单独记录；未完成检查不能回报文件丢失。升级后仍需重启，旧记录不能证明新版本挂载成功。

## 挂载中断

挂载锁记录 PID 和进程启动时间。可确认原进程已退出或 PID 已被复用时，串行回收失效锁；无法确认拥有者时保持拒绝执行，重启清理 /dev 锁。第一次 bind 前写入含本次 boot ID 的事务意图，成功提交开机记录后清除；正常回滚完成也清除。SIGKILL 无法执行回滚，未完成意图会被自检和后续调用识别，提示重启，不执行晚期补挂或卸载。重启后按新的 boot ID 重新挂载。

并发回收标记也位于 /dev；如果进程恰好在创建锁、写入拥有者或回收标记期间被强杀，可能需要重启，不能声称所有强制终止场景都能原地自动恢复。

## 验证范围

此前 v2.6.5 在 Pixel 10 Pro XL 上验证过早期挂载、框架读回及 5G SA／IMS over NR 注册。本版改变了准入规则，旧结果不能替代新版或其他型号的安装、开机和通信验证。历史调查见 BOOT_MOUNT_RESEARCH.md、VALIDATION.md。
