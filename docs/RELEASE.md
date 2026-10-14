# 正式发布

维护者 iCassius；原作者 Sun_Dream。版本来自 module/module.prop。
正式版 v2.6.4，versionCode 31。

正式包只有 Pixel_5G_IMS_Enhanced-v2.6.4.zip，包含经过校验的 vendor／CarrierSettings 载荷，不提供 Base／VCRBT 分包。
厂商二进制保留在本地 private/；不加入 Git 源码。公开 CI 构建 dist/development/ 框架开发包并检查源码，不自动将开发包发布为正式版。

正式发布步骤：

1. 更新版本号、中文功能说明和真实设备记录。
2. 本地执行 python build.py --with-private-payload --official-release。
3. 执行 python tests/run.py 与 python tools/verify_package.py dist/release/<版本>/Pixel_5G_IMS_Enhanced-<版本>.zip --official。
4. 提交源码并推送对应版本标签，确认 CI 成功，再上传已核验的正式 ZIP。
5. 更新 updates 分支中的 update-framework.json 与 release-notes.md，下载 Release ZIP 再次核验。
6. 新版发布核验通过后移除被替代的旧 Release。

沿用 update-framework.json 地址供旧模块更新至统一正式包。module.prop 的 updateJson 由 KernelSU 管理器处理，action.sh 打开 GitHub Releases。
Release 仅上传 ZIP；哈希及构建检查记录本地保留。安装升级由用户手动执行。

仓库：https://github.com/iCassius/Pixel_5G_IMS_Enhanced
