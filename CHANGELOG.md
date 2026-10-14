# 变更记录

## v2.6.2-experimental — 2026-10-14 — iCassius

- 模块与安装包统一名称 Pixel_5G_IMS_Enhanced，保留 EnablePixel5G 模块 ID。
- 增加 Windows／Linux 构建支持和 GitHub Actions 发布流程。
- 更新源改为独立 updates 分支，实验预发布也可通知更新。
- 公开框架产物与私有基带包隔离，固定 ZIP 元数据以便核验。
- 修复守护与手动切换之间的旧 Profile 回写竞争。

## v2.6.1-experimental — 2026-10-14 — iCassius

- 增加 KernelSU 原生更新源及操作按钮，按钮打开 GitHub Releases。
- 各安装包独立更新渠道，避免框架／mustang Base／VCRBT 互相替换。
- 从 module.prop 统一生成版本、下载链接、更新描述文件及 Release 校验文件。
- 保留用户修改的 README，未改写现有描述。

## v2.6.0-experimental — 2026-10-14 — iCassius

- 从 v2.5 拆出独立 PixelIMS 项目，保留 Sun_Dream 原始署名、模块 ID、历史阶段署名。
- 默认构建只携带框架策略；厂商载荷仅本地 private/ 输入，逐项核验既有 manifest。
- 新增基带精确匹配以及四项 ROM 文件哈希守卫；取消 FORCE_OTA_BYPASS。
- 基带／机型／系统／文件不一致时跳过全部 vendor 和 PB 文件，转为国内四家框架兜底。
- 框架兜底按现有键类型及 API 级别筛选，临时覆盖并读回，保留未知参数和国际订阅。
- 状态返回实际兼容层、请求和有效策略、受管参数数量；双国内卡分别检查，国际卡跳过。
- 原有视频实验保持在已核验 mustang 电信完整策略内，不推广到其他机型。
