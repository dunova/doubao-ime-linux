# 0.1.0-rc.1 验证记录

日期：2026-09-17。以下是本次独立源码预发布目录的实际验证结果。

环境为 Arch Linux x86_64、Fcitx 5 **5.1.22**、发行版原始 Wine **11.17**、
Wine Mono **11.3.0**、豆包 Windows 输入法 **0.9.0.0**。
Windows 宿主使用 Clang **22.1.8**、LLD 和标准 MinGW-w64 **14.0.0** 头文件及库编译。
所有 Wine prefix 都由源码中的准备工具重新初始化，没有复制既有用户配置。
设置字体仅为 Noto Sans CJK SC。

| 检查 | 结果 |
|---|---|
| 原生 Fcitx 键盘与独立语音提交模块 | 编译通过 |
| Windows RPC 宿主与设置检查工具 | 标准 MinGW 接口编译通过 |
| 单元测试 | 21 项通过：语音结果/取消、配置合并/冲突、服务归属、安装保护及源码包校验 |
| 官方键盘 RPC | 11 项通过：预编辑、候选词、首选/非首选、分段选词、退格、清空、焦点重置及异常客户端 |
| 私有 GTK/Fcitx 输入 | 15 项通过：真实键盘输入及语音提交端点的焦点、调用方、敏感框、控制字符和一次性校验 |
| 官方引擎键盘选项 | 全拼、繁简、小鹤、自然码、86 五笔共 5 项通过 |
| 官方设置窗口 | 干净环境中显示可读中文；正常关闭，活动键盘配置保持不变 |
| 暂存安装/卸载 | 12 个入口及插件文件；带空格路径、systemd 单元语法、完整移除和无关文件保留均通过 |

表情开关仍有已知问题：关闭后「你好」候选仍可能包含表情，未计为通过。

本次没有进行真人录音或连接外部 ASR 服务的完整听写回归；语音集成检查验证的是
真实 Fcitx 提交端点和协调逻辑，不代表外部云端接口当前可用。
Windows 设置中的每一个选项、账号同步、长时稳定性及其他发行版尚未全部验证。
GTK 集成测试使用私有 X11 显示；本预发布版本未替换当前桌面插件做新的 Wayland 回归。
首轮 GitHub Actions 构建与单元检查[已通过](https://github.com/royess/doubao-ime-linux/actions/runs/35185628495)。
现有 CI 扩展了 GCC/Clang、仅键盘构建、模拟引擎下的真实 Fcitx/GTK 测试、暂存安装与可重复打包；
最新状态见 [GitHub Actions](https://github.com/royess/doubao-ime-linux/actions/workflows/ci.yml)。
模拟引擎只提供固定候选词，不能替代上表中的官方引擎实测。

## 后续右 Alt 与图标验证（2026-09-17）

- 29 项单元测试通过，包括连接建立前的音频缓存、提前松键、取消清空、容量上限及子进程回收。
- 模拟键盘和录音会话的真实 Fcitx/GTK 集成共 37 项通过，包括右 Alt 长按/短按、松开提交、
  右 Alt + 空格持续录音、Esc/焦点取消、密码框/拼音预编辑保护及运行中停用热键。
- 带独立图标的暂存安装/卸载覆盖 13 个文件。
- 上述新增测试全部纳入 GitHub Actions 的 GCC/Clang 矩阵：单元测试使用 `test_*.py`
  自动发现，快捷键测试位于现有 `integration_fcitx.py --mock-engine` 入口。

此处模拟录音会话和 ASR 协议边界，没有使用真实麦克风或云端识别服务。
官方引擎、官方设置窗口的手动验证仍需要另行准备 Wine 和官方组件；它们不是托管 CI 中的在线测试。

## 实时预览验证（2026-09-24）

- 40 项单元测试通过，包括流式中间结果、修订去重、取消后的旧事件、识别错误后的清理，
  以及仅有 partial 时禁止提交的规则。
- 私有 Xvfb / D-Bus 的真实 Fcitx / GTK 集成通过：预览不写入正文、修订替换、
  等待最终结果时保留预览、一次性提交、焦点/按键/服务断开清理，及两种右 Alt 操作。
- 本机安装更新后的语音模块，在 niri Wayland 的 GTK 输入框和 Alacritty 中验证
  预览修订、最终落字和取消。Alacritty 的 Wayland 协议收到预编辑更新，终端 PTY
  只收到一次最终文字；临时预览没有作为键盘输入写入终端。
- 真人麦克风与云端识别的 Alacritty 测试由用户确认：说话时显示文字，最终文字正常。
- 按正常速度发送固定中文音频时，服务端 partial 更新间隔中位数约 0.64 秒，
  表现为文字分批出现。独立测试将 `cell_compress_rate` 从 8 改为 4 后间隔无明显变化，
  未将此实验参数作为配置或默认值发布。

Wayland 与真人验证是本机实测，不属于托管 CI；服务端更新频率和识别质量仍受外部服务影响。

## 复现命令

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/doctor.py
python3 scripts/headless.py --prefix keyboard -- python3 tests/integration_keyboard.py
python3 scripts/headless.py --prefix keyboard -- dbus-run-session -- python3 tests/integration_fcitx.py
python3 scripts/headless.py --prefix settings -- python3 tests/integration_settings_engine.py
python3 scripts/headless.py --prefix none -- python3 tests/integration_settings_ui.py
python3 tests/integration_install.py
python3 scripts/headless.py --prefix none -- dbus-run-session -- python3 tests/integration_fcitx.py --mock-engine
python3 scripts/package.py --check
python3 scripts/package.py
python3 scripts/check_package.py --rebuild
```

运行集成测试前停止**这个源码目录**的键盘服务、关闭设置窗口。测试有 prefix 排他锁，
不得通过删除锁文件绕过。原始日志和截图保存在 `work/`，不进入发布包。
通过其他机器或发行版验证后，请补充环境和对应结果，不要据此扩大本表的现有结论。

## 2026-10-16 本机 Windows 引擎升级

官方官网版本接口返回 V0.9.2，发布日期 2026.10.10，安装包实际版本 0.9.2.7。
安装包 SHA-256：`d777027cc822a67dac04ba502616f6e6216a54c06681e21f8f45ef0a89cec5db`。
已完成独立 Wine 副本验证：40 项单元测试、11 项官方 RPC 检查、真实 Fcitx/GTK 集成检查、小鹤/自然码/五笔86/繁简检查；新版设置窗口可打开和关闭，中文显示已检查。未做本次真人 Wayland 输入或真实语音回归。
完整旧版代码、PE helpers 与两个 Wine prefix 保存在本机 `work/upgrade-20261016/backup/`。回退命令：`python3 work/upgrade-20261016/rollback.py`。
智能文字整理随后已通过 UTF-8 请求桥接打通官方接口，迁移验证见下一节；音频识别仍沿用原有适配器。

## 2026-10-16 智能文字整理迁移

- 官方 Windows 0.9.2.7 客户端及网络 SDK，在独立 `organize-prefix` 中通过 UTF-8 管道接入；原键盘、设置副本的官方组件不替换。
- 人工中文样本通过官方服务返回了编号列表、段落、口头语清理与标点整理。`scene.completed` 的全文覆盖流式片段，避免把中间排版重复落字。
- 47 项单元检查通过，覆盖 SSE 截断、无改写、服务错误、非法控制字符、超时回退、取消时不提交原文等路径。
- 隔离 Fcitx/GTK 集成检查共 60 项通过，包含真实官方整理后落字、焦点切换期间取消、一次性提交、原有右 Alt 两类快捷键和密码框保护。键盘部分使用确定性 fixture，不重复启动活动键盘前缀。
- GTK 3 测试客户端没有声明 Multiline 能力，已验证段落降级为空格；带 Multiline 标志的分支按客户端能力保留 LF。终端始终降级为空格。
- Windows Ctrl+Z 恢复识别原文尚未迁移。生产整理路径不记录语音转写正文或设备凭据。

- 完整合成语音流水线验证：18.17 秒中文口述，通过真实 ASR 和官方整理服务返回了编号列表与段落，总耗时 19.76 秒，识别进程正常退出。该测试替换的是麦克风采集源，未使用真人麦克风输入。
- 本机已安装更新后的语音提交模块并启用智能整理，语音服务与键盘服务均为 active；Fcitx 已重新加载语音模块。


## 2026-10-17 口头修正与内容保护（issue #2）

- 57 项单元测试通过，新增明确时间/日期/数量改口、长段落回头修正、引号/假设/歧义保护、数值/否定/强调重复/收件人丢失拒绝、原文回退及关闭整理的验证。
- `python3 tests/integration_cleanup.py` 的 9 组人工样例全部通过真实官方服务，均未触发回退：中英文时间、日期、数量、比较、否定、强调重复、口头语和长段落。长段落的会议时间从 3 点改为 4 点，末尾修正过程删除，王小明、20 万元、两场比较和否定约束保留。
- 修复官方诊断入口对空 `no_rewrite` 完成事件提前结束读取的问题：桥接先捕获真实 SSE，再向原业务解析器提供空白心跳，由 Python 独立校验完整结果。
- 隔离 Fcitx/GTK 集成的 61 项检查通过，包括真实官方整理的回头改口落字、一次性提交、焦点取消、密码框保护和原有右 Alt 快捷键。
- 65 个源码文件的发布白名单、归档校验和可复现重建通过；官方组件、设备凭据和联网样例输出均不进入发布包。
- 单独启动整理进程的 9 个样例耗时约 16.2–17.2 秒，包含初始化；生产路径会与录音并行初始化，原有最终转写后 25 秒上限不变。

上述结果验证固定样例和可观察到的内容保护，不构成对任意口述语义的完整保证；歧义修正保留原文。未进行本次真人麦克风回归。


## 2026-10-17: Keyboard startup regression (issue #3)

- The keyboard integration harness now waits for a successful Unix socket
  connection, rather than treating an existing path as readiness. It reports a
  bounded startup timeout or an early broker exit with the log location.
- 62 unit tests passed, including stale/missing endpoints, delayed listeners,
  startup timeout, early exit and permission-error handling.
- The real 0.9.2.7 official keyboard engine passed all 11 RPC checks twice on
  this machine: once with a deliberately abandoned test socket, then with a
  clean endpoint. The keyboard service was stopped for exclusive prefix access
  and restored after validation. No production endpoint was deleted.
- The local socket's one-command/one-response-per-connection contract is now
  documented in `docs/keyboard-abi.md`. No persistent-connection or Xvfb change
  was needed.
- The 66-file source manifest and reproducible source archive checks passed.

The [community environment report](https://github.com/royess/doubao-ime-linux/issues/3)
provides additional Arch/Omarchy and Hyprland installation observations and
machine-specific measurements. This regression run does not independently
reproduce those benchmarks or establish complete Hyprland/Wayland coverage.


## 0.1.0-rc.2 source release preparation

The release includes the validations recorded above. The release source manifest
contains 67 reviewed files; archive content, README links, SHA-256 and byte-for-byte
rebuild checks pass. Tag publication reruns the reusable GCC/Clang CI before
creating the release assets. No official components or private runtime files are
included in the source archive.


## 2026-10-17: Official-only versus local cleanup

Twenty sequential requests to the same official runtime/service compared ten
artificial transcripts, once per mode. No network/protocol failure or fallback
occurred. Each mode satisfied nine of ten content expectations; the differences
were substantive:

| Input | Official only | Local rules + official |
| --- | --- | --- |
| A long passage revising the meeting from 3 to 4 | Updates the first time, but retains the trailing spoken correction | Removes the superseded time and trailing correction |
| `周三提交，哦不，周四完成。` | `周四完成。` | `周四提交完成。` (incorrectly retains the abandoned predicate) |

The other eight cases passed in both modes: Chinese/English time corrections,
weekday, quantity, comparison, negation, emphasis and filler/stutter removal.
These are single observations of a small sample set, not general model quality
rates. Separate local checks also show that the heuristic guard rejects the
reasonable wording change `会议不能取消。` → `会议不得取消。`.

Consequently the local rewrite and semantic-check layer is retained as an
optional experiment and disabled by default. Official-only mode sends the full
unmodified final transcript and preserves protocol validation, bounded waiting,
focus/cancellation guards and accepted-transcript fallback on processing errors.
`organize_local_cleanup` in `config.local.json`, or the daemon environment
`DOUBAO_ORGANIZE_LOCAL_CLEANUP`, controls the optional layer independently.

65 unit tests passed, including original-payload forwarding, official-wording
acceptance, opt-in compatibility and configuration/environment precedence. The
comparison is reproducible with `python3 tests/integration_cleanup.py --mode
compare`; its content assertions intentionally expose both known limitations and
return nonzero when an expectation is unmet. Raw artificial-sample outputs are
kept in ignored `work/cleanup-comparison/`, outside production logs and releases.

The default official-only path also passed all 60 isolated Fcitx/GTK checks,
including actual official organization, one-time commit and focus cancellation.
The 67-file manifest and reproducible source archive checks pass.
