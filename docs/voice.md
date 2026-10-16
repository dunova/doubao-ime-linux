# 可选豆包语音

本项目包含 Linux 录音协调器、结果校验和独立的 Fcitx 提交插件。
ASR 协议来自外部社区适配器；没有把它的代码或设备凭据放进发行包。

可以单独使用 [fcitx5-vinput](https://github.com/xifan2333/fcitx5-vinput) 管理语音，
同时使用本项目的豆包键盘。需要使用这里的语音协调器时，按下述步骤配置。

## 外部适配器

参考适配器是 [vinput-registry 的 doubaoime/streaming](https://github.com/xifan2333/vinput-registry/tree/38e203e328118e5575722d2d4dd74dd736b6c8d8/resources/providers/doubaoime/streaming)，
固定修订 `38e203e328118e5575722d2d4dd74dd736b6c8d8`。
按上游说明取得适配器并满足其依赖，将 `entry.py` 的绝对路径写入
`config.local.json` 的 `asr_entry`。本项目不自动拉取或重新分发该适配器。

适配器通过 stdin/stdout JSONL 传输 16 kHz 单声道 PCM、音频结束及识别结果。
`scripts/provider.py` 校验依赖的接口存在，将设备凭据保存在 `work/private/`，
并关闭失败后自动删除凭据、重复注册设备的行为。首次使用仍可能自动注册设备。
上游协议是非官方接口，服务端或适配器更新可能导致失效。

```sh
# 还未安装时追加 --voice；如已有安装，先按 README 停用服务并卸载入口。
python3 scripts/install.py install --voice --settings
systemctl --user daemon-reload
systemctl --user enable --now doubao-keyboard.service doubao-voice.service
```

可以在桌面快捷键设置中绑定 `doubao-voice toggle` 与 `doubao-voice cancel`。
`doubao-voice status` 查看状态。

## 右 Alt 快捷键

可选的 Fcitx 按键处理对应官方 Windows 客户端的两种默认绑定：

- 长按 **右 Alt** 开始说话，松开结束录音并提交；短按不启动。
- **右 Alt + 空格** 开始持续录音，再按一次结束；按住说话时按空格可转为持续录音。
- **Esc**、切换输入框或录音中打字会取消。密码框和存在未提交拼音时不启动按键听写。

先释放其他插件占用的右 Alt，然后在 Fcitx 配置工具的「豆包语音提交」附加组件中
启用右 Alt，或编辑 `~/.config/fcitx5/conf/doubaovoice.conf`：

```ini
EnableHotkeys=True
HoldThresholdMs=250
```

首次安装新模块后重启 Fcitx；之后修改这个配置可执行
`busctl --user call org.fcitx.Fcitx5 /controller org.fcitx.Fcitx.Controller1 ReloadAddonConfig s doubaovoice`。
快捷键默认关闭，安装脚本不自动修改其他插件。它在普通 Fcitx 输入框中生效，
可搭配豆包、英文键盘或其他输入法，不依赖桌面全局按键监听。

开始后先录音，在云端连接建立前只缓存在进程内存中，最多 20 秒；连接成功才发送。
连接期间松开右 Alt 会结束采集，并在连接就绪后发送已经采集的短句；取消则丢弃未发送的缓存。

## 实时转写预览

录音期间，中间识别结果通过 Fcitx 预编辑显示，后续结果会替换和修订预览。
右 Alt 按住说话和右 Alt + 空格持续录音均支持；具体样式和显示位置由应用及
Fcitx 决定，通常是输入光标旁的带下划线文字。它仍是临时文字，尚未提交给应用。

停止录音后，预览保留到最终识别完成，再一次性提交最终文字。Esc、打字、切换
输入框或识别失败会清除临时预览，不删除已有正文；语音协调器断开连接也会清除预览。
网络连接建立前不会有识别文字，流式预览不会改变连接等待时间。
文字按服务端中间结果更新，可能成批出现或回改，并不保证逐字匀速显示。

升级已有安装时需要同时更新 `doubaovoice.so` 和语音协调器，并重启 Fcitx 与
`doubao-voice.service`。可选智能文字整理见下节。

## 范围

- 录音使用 `parec`；可通过服务环境 `DOUBAO_AUDIO_SOURCE` 指定麦克风。
- 最长录音 120 秒。密码/敏感输入框不发放提交许可；文字不会通过剪贴板粘贴。
- 仅接受匹配的分段最终结果和整句结束确认；取消、断线或旧会话不提交。
- Fcitx 的提交许可绑定调用进程和当前输入框，只能使用一次。
- 整理结果允许换行；明确声明多行能力的普通输入框保留段落，终端或未声明多行能力的输入框将换行转为空格。其他控制字符仍被拒绝。
- 官方设置里的 Windows 语音热键、麦克风和标点选项不控制这个 Linux 录音器；上述绑定由 Fcitx 配置管理。

默认遵守用户的代理配置。如果出现特定域名握手失败，可自行设置 `asr_no_proxy`，
例如 `log.snssdk.com,is.snssdk.com,frontier-audio-ime-ws.doubao.com`；此设置只影响适配器子进程。
不要把携带签名、设备 ID、令牌的日志直接提交到 issue。

`asr_ipv4_only` 默认是 `false`，省略时也不会限制地址族，沿用系统的 IPv4/IPv6 选择。
若本机到语音入口的 IPv6 不通、IPv4 正常，可在 `config.local.json` 设置
`"asr_ipv4_only": true`。这只让适配器子进程用 IPv4 连接豆包语音 WebSocket
域名，避免先等待 IPv6 超时；不会修改系统网络或固定服务器 IP。
改回 `false` 或删除该项即可恢复默认行为；配置在下一次听写启动适配器时生效。
松开右 Alt 后请等“已输入”提示再打字，识别完成前打字会取消本次提交。

## 智能文字整理（0.9.2.7，本机实验支持）

Linux 录音和流式预览沿用现有适配器。最终转写通过独立 Wine 环境中的官方 Windows 客户端和网络 SDK 请求豆包整理服务；完成后一次性落字。不是本地规则替换。官方模型决定是否改写，未必每次都改变原文。

```sh
python3 scripts/prepare_organize.py
doubao-voice organize-on
doubao-voice organize-off
```

也可在“豆包设置 → 语音输入 → 智能文字整理”切换，关闭设置窗口后应用，下一次听写生效。该开关存放于私有 `work/smart-organize.json`，避免活动键盘引擎保存旧配置时覆盖 Linux 偏好。`doubao-voice status` 会显示当前开关和上次整理状态。

准备工具验证固定版本的官方组件，只在 `work/organize-prefix` 内建立运行环境。两个小型开源适配 DLL 分别通过官方 AppLog 设备设置 API 复用现有语音适配器的设备 ID，并把 UTF-8 stdin 请求和官方 SSE 响应接到 Linux；键盘和设置副本中的官方 DLL 不被替换。设备凭据必须已经由现有语音适配器取得，不新建账号。

初始化与录音同时开始，当前保留约 12 秒的官方加密初始化等待；短句可能多等几秒。ASR 得到最终转写后最多再等待 25 秒。网络失败、整理失败或不完整结果会退回原始转写；Esc、打字、焦点切换会取消，取消后不提交整理结果或原文。中间整理片段不会提前落字。

允许的排版控制字符只有 LF 换行。明确声明多行能力的输入框保留段落；终端、单行和未声明多行能力的客户端统一转为空格。部分 GTK 3 客户端不声明多行能力，因此也会收到单行整理文本。Windows 的 Ctrl+Z“恢复识别原文”尚未迁移；应用自身的普通撤销行为不变。

转写文本会发送到豆包官方文字整理服务。音频和转写正文不写入生产整理日志；原始识别预览仍在应用的临时预编辑里。准备日志只用于 Wine 初始化和编译。测试目录中保留的语音、请求和 SSE 均为公开片段或人工合成样本，不进入源码包。

本机验证发现：`enable_asr_format` 对两段音频的开关对比没有产生额外整理，不能代替独立整理接口。官方测试入口的设备初始化和 UTF-8 请求适配已打通；需给网络 SDK 足够初始化时间。服务协议仍是未公开的固定版本接口。
