# v2.6.0 离线验证

## v2.6.1 更新入口验证 — 2026-10-14

47 项规则断言、57 项离线检查通过。包括新增 action.sh 语法、模拟浏览器启动／失败／非法仓库、三个更新渠道独立性、ZIP 与 update JSON 版本和下载资产一致性。
三个 v2.6.1 ZIP 构建成功。检查包含 dist 内保留的 v2.6.0 ZIP，因此总数包含历史 ZIP 的 LF 和 manifest 校验。
未连接 Android 验证管理器按钮，未发布 GitHub Release，也未完成真实在线下载／安装验证。README 保留用户修改。

## v2.6.0 历史记录

日期：2026-10-14；维护：iCassius。

- Android SDK 36.1 / JDK 21 编译与 D8 转换成功，三个 ZIP 构建成功。
- CompatibilityTest：47 项纯 Java 断言通过，涵盖机型／SDK／基带／运营商及参数存在性、类型、未来枚举保护。
- tests/run.py：34 项检查通过，涵盖脚本语法、基带为空／未知／早期报告值、OTA、其他型号、文件缺失／变化的零挂载，精确匹配挂载、重入、部分失败回滚及失败时镜像保留。
- 控制入口只读查询、切换成功才保存、DEX／策略／兼容脚本完整性检查通过。
- ZIP 内 shell 全部 LF；所有 manifest 产物哈希一致；默认框架 ZIP 不含 vendor／PB 载荷。
- 测试以临时目录、合成字节、模拟 getprop／mount／su 执行；没有 Android Binder 写入、真实 bind 挂载、SELinux 或任何新版本实机通话证据。

机器可读记录位于本地 build/validation.json；产物及 SHA256 位于 dist/，均不提交到源代码 Git。
private/ 仅保存既有 v2.5 登记载荷，build.py 按原 manifest 核验后导入；本轮没有重新改写 PB 或数据库。
旧模块源码和 PixelVcrbt 工作树保持原状。Pixel 6～11／四家／海外卡完整验收仍需后续实机矩阵。
