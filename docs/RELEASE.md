# GitHub Release 更新

维护：iCassius。默认仓库目标 iCassius/PixelIMS；当前本地尚未配置 remote 或发布。
如使用其他仓库，构建时传 `--update-repository owner/repository`，模块按钮与更新源一起生成。

更新入口采用 KernelSU 官方 `module.prop updateJson` 和 `action.sh`，由管理器处理下载、安装与重启提示。
操作按钮打开 Releases，供手动查看或下载实验版本；不在后台自行安装。

每次发布先提高 module/module.prop 的 versionCode，修改 version 和 CHANGELOG，再构建。
构建以 module.prop 为唯一版本来源，生成对应 ZIP、SHA256 和 update-<渠道>.json。
Release 标签必须等于模块 version；上传对应 ZIP、update JSON、CHANGELOG.md 和 SHA256。

| 构建 | 更新描述文件 |
|---|---|
| 默认框架包 | update-framework.json |
| 私有 mustang Base | update-private-mustang-base.json |
| 私有 mustang VCRBT | update-private-mustang-vcrbt.json |

各包只指向自身渠道，缺少对应资产时报错，不回落到其他渠道。私有载荷仍不自动公开上传。
更新源使用 raw.githubusercontent.com/<仓库>/updates/update-<渠道>.json，支持 experimental prerelease。
GitHub Actions 仅在 v* 标签匹配 module.prop 且构建／检查通过后发布框架包，并在 Release 资产存在后更新 updates 分支。
更新源拒绝版本号倒退或同一 versionCode 指向不同版本；已匹配的重试不改写。
私有基带渠道不自动发布；没有对应更新源文件时不会误装框架包。
框架资产在 dist/release/<版本>/；基带资产在 dist/private/<版本>/，公开 workflow 只上传前者。
当前不存在的仓库／Release 地址不代表更新已上线；尚未执行远端 CI。
仓库私有时管理器无法匿名下载，需手动获取包或提供可公开访问的独立分发仓库。

官方定义：https://kernelsu.org/guide/module.html 。安装升级后原有机型／基带守卫仍会运行。
