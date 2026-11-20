# 故障速查（真实踩过的坑）

按「现象 → 根因 → 处理」组织，都是部署过程中实际遇到的。

---

## 1. 启动 NapCat 报 `MSVCP140.dll` 缺失

**现象**

```
NapCatWinBootMain.exe - 系统错误
由于找不到 MSVCP140.dll，无法继续执行代码。
```

**根因**：干净 Windows 缺 VC++ 运行库，NapCat 的注入器依赖它。

**处理**

```
https://aka.ms/vs/17/release/vc_redist.x64.exe
```

装 x64 版本，**装完重启**。

---

## 2. QQ 弹「文件已损坏，请重新安装QQ」

**现象**：NapCat 启动后 QQ 自己弹窗拒绝运行。

**根因**（两个都可能）：

1. **NapCat 版本比 QQ 版本旧**，注入补丁不兼容。判断方法：看 QQ 安装目录 `versions\` 下的版本号，对比 NapCat Release 说明。
2. **强行结束 QQ 进程**（`taskkill /f`）导致注入前的文件替换没有还原，QQ 自检失败。

**处理**

- 先升级 NapCat 到最新 Release（更新日志里常有「支持新版本」）
- 仍不行则卸载重装 QQ，并**先手动启动一次 QQ**确认干净，再用 NapCat 启动
- 日常**不要 `taskkill /f` 杀 QQ**，用托盘「退出」

---

## 3. 语音合成成功但发送失败：`ffmpeg not found`

**现象**

```
[SeedAudio] 整条语音 12.6s：……
Failed to send the message chain: ... error = ffmpeg not found
```

**根因**：AstrBot 用系统 `ffmpeg` 转码音频，机器上没装或没进 PATH。

**处理**

1. 装 ffmpeg，把 `...\bin` 加进**系统变量 Path**
2. **重启 AstrBot**（进程只在启动时读 PATH）
3. 验证：新开 cmd 跑 `ffmpeg -version`

> 症状细节：语音其实**已经合成成功并计费**，只是最后一步转码失败，所以 QQ 里收不到。

---

## 4. 记忆一直 `Connection error`

**现象**

```
Retrieval route 向量 failed: Connection error.
未找到相关记忆
```

**根因**

1. Embedding 服务没配 / 地址不通（本机 Ollama 未启动、端口 11434 没监听）
2. **热改 provider 后没有重启进程** —— 插件仍持有旧的 HTTP 客户端，报错变成
   `Cannot send a request, as the client has been closed.`

**处理**

- 后台配好 Embedding：`api_base` + `key` + 模型名 + **维度**
- 改完**重启 AstrBot**（重载插件不够，必须重启进程）
- 云端 Embedding 示例：`https://api.siliconflow.cn/v1` + `BAAI/bge-m3`（1024 维）

---

## 5. 2GB 内存装不下本地向量模型

**现象**：装完 Ollama 后系统极卡、QQ 掉线、记忆检索超时。

**根因**：Windows Server 自身约 1GB + AstrBot 0.4GB + QQ 0.5GB ≈ 1.9GB，bge-m3 加载还要 1.2–1.5GB。

**处理**

- 改用云端 Embedding API（内存占用 0），或
- 升配到 4GB 内存，或
- 换小模型（质量下降，仍会轻微交换）

---

## 6. 启动脚本报「字符串缺少终止符」

**现象**：PowerShell 脚本里提示

```
字符串缺少终止符: '。
表达式或语句中包含意外的标记 "AstrBot"
```

**根因**：`.ps1` 存成 **UTF-8 无 BOM**，而 Windows PowerShell 5.1 按 **GBK** 解析，中文路径被读成乱码，把引号撑断。

**处理**（任选）

- 脚本里**不出现中文**：中文路径用 `[char]0x5927 + [char]0x80A5 + [char]0x9C7C` 拼
- 或存成 **UTF-8 with BOM**
- 或干脆改用 `.bat` + `%~dp0` 相对路径

> `.bat` 同理：必须 **CRLF + ANSI(GBK)** 编码，UTF-8 会让 `set VAR=...` 之类断词报错。

---

## 7. 插件装了但列表里没有

**根因**：AstrBot 只在**启动时**扫描插件目录；后台的刷新按钮只刷新显示。

**处理**

- 确认路径只有一层：`data\plugins\astrbot_plugin_xxx\main.py`
  （多套一层是最常见错误：`...\astrbot_plugin_xxx\astrbot_plugin_xxx\main.py`）
- 重启 AstrBot
- 仍没有 → 看日志里的 `ImportError / SyntaxError`

---

## 8. `消息0不存在` / `ActionFailed retcode=1200`

**现象**：发指令后 QQ 侧报错，NapCat 日志里：

```
接收 <- 私聊 (xxx) /写说说
发生错误 Error: 消息0不存在
```

**根因**（按可能性）：

1. 消息带了**失效的引用**（被引用消息已不在 NapCat 缓存，常见于重启后）
2. 「分段回复」与图片类消息一起发送时的协议处理问题

**处理**

- 发指令时**不要用「回复」方式**，直接在输入框发
- 关掉 `platform_settings.segmented_reply.enable`
- 重启 NapCat 后先正常聊两句再发指令

---

## 9. 端口冲突：启动后 6185 打不开

**根因**：AstrBot 已经在跑，再启动一个新实例会因端口占用失败退出。

**处理**：先结束所有 `python.exe`（任务管理器 → 详细信息），再启动。

诊断命令：

```bat
netstat -ano | findstr 6185
netstat -ano | findstr 6199
```

---

## 10. 白名单填了裸 QQ 号不生效

**根因**：AstrBot 白名单比对的是**完整会话 ID**：`平台名:FriendMessage:QQ号`。

**坑**：如果把同一个号也设成了管理员，`wl_ignore_admin_on_friend` 会让管理员**绕过白名单**——于是「看似生效」，一旦取消管理员就立刻失效。

**处理**：白名单里写完整会话 ID。

---

## 11. 装依赖时 `Read timed out` / TLS 中断

**根因**：镜像源抖动；或机器上开着代理软件劫持了本地 TLS。

**处理**

```bat
set UV_HTTP_TIMEOUT=300
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

失败就重跑（pip 会断点续传已下载的 wheel）；确认代理软件不要把 `127.0.0.1` 也代理走。

---

## 12. QQ 扫码总是「二维码已失效」

**根因**：二维码约 2 分钟换一张。经过聊天工具转发图片会消耗 30–60 秒。

**处理**

- 直接看 NapCat 控制台里的二维码，或
- 打开 `NapCat\cache\qrcode.png`（会被自动覆盖更新），或
- 做一个置顶小窗定时重新加载该 PNG（见 `scripts/` 的说明）
- 手机提前停在「扫一扫」界面，再去看码

---

## 13. 一个常见误解：AI 能「操作电脑 / 刷抖音」

**事实**：AstrBot 的电脑操作能力（`computer_use_runtime`）默认是 `none`，此时模型**没有任何**文件、命令、鼠标键盘权限，只能发消息、发表情、改自己的 QQ 资料、发说说。

**要做界面自动化**需要额外开启 Computer Use（截图 + 模拟输入）或外挂 Playwright / ADB，且：

- 2GB 内存的机器扛不住浏览器/模拟器
- 自动化操作第三方 App 通常违反其服务条款，风控风险高

本实践**保持关闭**。
