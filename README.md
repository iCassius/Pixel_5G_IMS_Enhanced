# PixelIMS

独立维护的 KernelSU 国内运营商 IMS／VoNR／SA 配置模块。维护者 [iCassius](https://github.com/iCassius)，原作者 Sun_Dream；见 [来源说明](NOTICE.md)。当前 v2.6.0-experimental。

- 国内移动、联通、电信、广电按 SIM 本身的 MCC／MNC 白名单匹配；国际卡与未知 PLMN 不写配置。
- Google Pixel 6～11 型号名称、Android API 31～36 为框架兜底入口范围，不代表逐机型实测通过。Pixel 11 暂为预留名称；未知 SDK（包括 37）停止写入，等待适配。
- 基带、机型、系统版本和四项目标文件哈希全部匹配，才允许 mustang 私有载荷挂载；空基带、OTA 或文件不匹配时跳过所有 vendor／PB 挂载。
- 框架兜底只应用当前配置存在且类型正确的 AOSP 键；VoNR 要求 API 34+。保留原生视频、APN、CDMA、紧急呼叫、Wi-Fi 呼叫路由和厂商参数。
- 兜底使用临时 CarrierConfig 覆盖，守护重新读回；不是基带解锁，也不绕过运营商开通或 IMS provisioning。
- 默认产物仅框架兜底；私有 mustang 包保留完整策略。LSPosed 彩铃伴侣独立维护。

构建：安装 JDK 21、Android SDK android-36.1 / build-tools 35.0.0，设置 JAVA_HOME／ANDROID_SDK_ROOT 后运行：

```sh
python tests/run.py
python build.py
# 本地已登记载荷可选，不作为公开发布附件
python build.py --with-private-payload --profile base
python build.py --with-private-payload --profile vcrbt
```

控制入口：`sh /data/adb/modules/EnablePixel5G/control.sh status|base|vcrbt`。
在框架兜底层，base／vcrbt 均仅应用框架白名单，不开启厂商视频实验。status 为只读。
禁用／卸载不会清除历史持久覆盖，Base 也不是出厂恢复；旧 v2.5 用户需先核对旧覆盖所有权。

参数和证据边界见 [兼容说明](docs/COMPATIBILITY.md)，变更见 [CHANGELOG](CHANGELOG.md)。
