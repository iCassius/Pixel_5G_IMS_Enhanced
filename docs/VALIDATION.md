# 发布前验证

## GitHub 发布记录 — 2026-10-14

仓库 iCassius/Pixel_5G_IMS_Enhanced 已公开，v2.6.2-experimental 预发布及四个附件已上传。
发布流程 38579430764 的 build／release 均成功。下载包 SHA256 为 64ca90bae7ad6bce5f85f90a626b69c86620b18ef1355df2cbcde2d03417ff4e，与发布附件校验文件一致，内部 manifest 全部匹配。
在线更新源与 Release JSON 一致，versionCode 28；发布正文及更新说明已同步为中文功能和历史实机记录。
发布包来自 GitHub Linux 构建，下面的 Windows SHA256 属于本地发布前候选，不将两者写成同一包身份。

## v2.6.2 — 2026-10-14

- 模块／README／安装包名称统一 Pixel_5G_IMS_Enhanced；版本 v2.6.2-experimental，versionCode 28。
- 47 项 Java 规则断言、63 项离线检查通过，新增更新资产检查和守护保持当前 Profile 的回归。
- Windows 本地三个包编译、D8、ZIP 校验通过；框架包重复构建 SHA256 一致：56b9070e06a73f44077425247469a32d9542bc20149b6b3bd25a101241ea653b。
- 公开资产目录仅框架 ZIP、SHA256、update-framework.json、CHANGELOG.md；私有 mustang 包隔离在 dist/private/。
- GitHub Actions YAML 已解析，各 run 块通过 Bash 语法检查，依赖固定 SHA。跨平台工具定位已实现，但未运行 Linux 或远端 CI。
- 本地源码列表未包含厂商二进制／原始日志，常见 GitHub token 与私钥格式扫描无命中；原作者来源说明保留，许可证来源仍未确认。
- GitHub 连接确认用户 iCassius；目标仓库为 iCassius/Pixel_5G_IMS_Enhanced，尚未创建或上传。本地 origin 仅配置目标地址。
- 当前新版本无 Android Binder 写入、按钮、真实挂载、IMS 注册／呼叫或跨型号实机验证。准备为实验发布，不能归为稳定版验收。

机器记录：build/validation.json、build/release_preparation.json；这些文件仅本地保留。

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
