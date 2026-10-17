# 本机确认的豆包 RPC 接口（0.9.0.0 / 0.9.2.7）

这是从本地官方二进制调用点及实际输入测试得出的接口记录，不是公开稳定 API。

| 文件 | SHA-256 |
| --- | --- |
| `rpc.dll` | `a3ead1a55850257bac01a878c899f42291a1f41bd2b834e0caa5c5b66a674e02` |
| `tsf-oime-core.dll` | `77d58bfc5bbc9016ee58135967603fbab19a30e79a1c338bce6a2df62ce60a83` |

所有 `RpcPipe_*` 函数第一个参数是管道路径字符串 `\\.\pipe\ObricIme\oime-server`，不是 `CreateRpcClient()` 返回的 C++ 对象。

```c
void RpcPipe_EnsureServerRunning(void);
void RpcPipe_FocusIn(const char *endpoint, const char *host_application);
void RpcPipe_FocusOut(const char *endpoint);
int RpcPipe_KeyDown(const char *endpoint, unsigned packed_key,
                    uint64_t timestamp_us, const char *host_application);
int RpcPipe_KeyUp(const char *endpoint, unsigned packed_key);
int RpcPipe_GetCompTextUtf8(const char *endpoint, char *text, int capacity, int *cursor);
int RpcPipe_GetCommitTextUtf8(const char *endpoint, char *text, int capacity);
int RpcPipe_GetCandidateListUtf8(const char *endpoint, char *text, int capacity,
                                int *selected, int *has_previous, int *has_next);
void RpcPipe_SetUIElementShowState(const char *endpoint, int show);
```

`tsf-oime-core.dll` 的 RVA `0x7c10` 将 Windows VK 与状态位合并：Ctrl `0x0400`、Alt `0x0800`、Shift `0x1000`、CapsLock `0x2000`。左右修饰键先转换为各自的 VK（Shift 为 `0xa0/0xa1`）。CapsLock 按下时翻转 `0x2000`，使事件携带切换后的状态。

RVA `0xe8d3` 起用 `GetTickCount64() * 1000` 生成微秒时间；RVA `0xdaf0` 从当前模块路径取得宿主程序名，供后续按键调用使用。**第三个参数不是 Windows lParam，第四个参数不是输入字符。** 只传普通字母键码能输入拼音，但会丢失 Shift 大写及组合标点，因此初版冒烟测试不足以验证这些参数。

本桥接从 Fcitx `rawKey()` 取得布局转换后的键及状态，转换为上述编码；Ctrl/Alt/Super 应用快捷键由应用处理。RPC 宿主使用自己的单调时间，并以 `fcitx5-doubao.exe` 标识宿主。普通中文标点由官方引擎转换。

候选列表是换行分隔的 UTF-8 字符串，函数返回文本长度，不是候选数量。分段选词可能仅改变预编辑，如 `ni'hao` → `尼hao`；不能假定每次选词都会提交整句。当前宿主通过方向键移动官方选中项后按空格选择，保留引擎的分段行为。

观察到 KeyDown 返回 0 为未消费、1 为已处理、3 为发生提交；负值按错误处理。提交文本通过 `GetCommitTextUtf8()` 取出，随后应为空，避免重复提交。

## 2026-10-16：0.9.2.7 本机验证

新版 `rpc.dll` SHA-256：`e3ee88527bf6bd38156e86b93413ca004a829809ad51f064a42db44814e9a5d5`。上表保留的是原 0.9.0.0 校验值。
现有键盘调用兼容新版，已通过 11 项 RPC 测试、真实 Fcitx/GTK 落字和输入焦点保护检查；小鹤、自然码、五笔86和繁简输出测试通过。
`enableEmoji=False` 时仍观察到 emoji 候选，不能宣称该选项在新版有效。

新版额外导出 SmartUndo 等接口，目前未接入。智能文字整理的云端请求和原文恢复不属于现有键盘 RPC 桥接。


## Local keyboard socket transport

The Linux frontend connects to a same-user Unix stream socket owned by
`keyboard_broker.py`. Each connection carries **one command and one response**:

1. Open a new connection for each request.
2. Send one ASCII command terminated by LF.
3. Read the complete UTF-8 JSON response, terminated by LF.
4. Close the connection. The broker also closes its side after the response.

Do not pipeline commands or reuse a connection for a second request. Sending `K`
and then `F` through the same connection is unsupported and can produce EOF,
`BrokenPipeError`, or a reset. The existing frontend and integration client open
one connection per request.

Commands are `F` (focus in), `R` (focus out/reset), `K <packed-key> <release>`
(`release` is 0 for key down and 1 for key up), and `S <candidate-index>`
(zero-based selection). The response contains the engine result, preedit and
commit text, candidates and selection metadata. Invalid commands or clients
may be disconnected without a response.

A socket file alone does not establish readiness: it may remain after an
interrupted run, or exist before `listen()` succeeds. The keyboard integration
test waits up to 45 seconds for a successful connection while checking that its
broker process is alive. Startup timeout and early exit point to the broker log.
A readiness probe does not unlink the socket; the broker already probes and
removes refused stale endpoints before binding, and refuses an active endpoint.
