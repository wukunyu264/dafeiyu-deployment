# 从零部署

> 环境：Windows 10 / 11 或 Windows Server 2022（本文以 `C:\大肥鱼` 为部署根目录）
> 前置：一个**专用小号** QQ（不要用主账号，非官方客户端有风控风险）

## 0. 顺序很重要

```
QQ NT → VC++ 运行库 → Python 3.12 → ffmpeg → AstrBot 源码 + 依赖
      → NapCat（版本要对上 QQ）→ 配置反向 WS → 启动 → 扫码 → 后台配置
```

先装软件再改 PATH，最后才启动 AstrBot；**任何 PATH 变更后都必须重启 AstrBot**。

---

## 1. 安装 QQ NT

官网下载 Windows 版安装，装完**先不要登录**。

查看已装版本：`C:\Program Files\Tencent\QQNT\versions\` 下的文件夹名即为版本号。

> ⚠️ **记下版本号**。NapCat 对 QQ 版本有兼容范围，版本对不上会出现「文件已损坏，请重新安装QQ」。

## 2. 安装 VC++ 运行库

NapCat 的注入器是 C++ 编译的，干净系统缺 `MSVCP140.dll`。

```
https://aka.ms/vs/17/release/vc_redist.x64.exe
```

**装完重启**（或至少关掉所有命令行窗口）。

## 3. 安装 Python 3.12

```
https://www.python.org/downloads/windows/
```

安装第一屏**必须勾选 `Add python.exe to PATH`**。

验证（新开 cmd）：

```bat
python --version
where python
```

> PATH 只在进程启动时读取一次。装完 Python 后，**之前打开的 cmd 窗口仍然找不到 python**，必须重开。

## 4. 安装 ffmpeg

语音消息走 mp3 → wav/silk 转码，AstrBot 调用系统 `ffmpeg`。

```text
下载 Windows 构建：https://github.com/BtbN/FFmpeg-Builds/releases
解压到 C:\ffmpeg（确保 C:\ffmpeg\bin\ffmpeg.exe 存在）
系统变量 Path 追加：C:\ffmpeg\bin
```

验证（**新开的** cmd）：

```bat
ffmpeg -version
```

> 加完 PATH 必须**重启 AstrBot**，否则它仍然找不到 ffmpeg。

## 5. AstrBot

```bat
cd /d C:\大肥鱼
git clone https://github.com/AstrBotDevs/AstrBot.git
cd AstrBot
python -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

验证依赖：

```bat
.venv\Scripts\python.exe -c "import quart,fastapi,aiocqhttp,openai,faiss;print('OK')"
```

> WebUI 静态资源：从源码运行时，若后台页面空白，需要从 AstrBot 的 Release 页面下载 `dashboard` 构建产物解压到 `astrbot/dashboard/dist`。

首次启动会生成 `data/cmd_config.json`，并自动生成随机后台密码（打印在控制台里）。

## 6. NapCat

从 Release 下载 `NapCat.Shell.zip`，解压到 `C:\大肥鱼\NapCat`。

**版本选择**：NapCat 版本必须 ≥ 所支持的 QQ 版本。QQ 升级后若出现「文件已损坏」，先升级 NapCat。

启动（会自提权，需要管理员）：

```bat
cd /d C:\大肥鱼\NapCat
launcher.bat <QQ号>
```

不传 QQ 号则走扫码登录；传了则尝试快速登录，失败时自动回退到扫码。

**二维码**有两份：
- 控制台打印的字符码
- `NapCat\cache\qrcode.png`（图片，约每 2 分钟刷新）

> 字符码的行距容易被终端字体撑歪导致扫不出，优先看 PNG。

## 7. 配置反向 WebSocket

登录成功后，NapCat 会为**每个 QQ 号**生成 `config/onebot11_<QQ号>.json`。把 `websocketClients` 填成：

```json
{
  "network": {
    "websocketClients": [
      {
        "name": "astrbot",
        "enable": true,
        "url": "ws://127.0.0.1:6199/ws",
        "messagePostFormat": "array",
        "reportSelfMessage": false,
        "token": "<随机串，和 AstrBot 的 ws_reverse_token 一致>",
        "reconnectInterval": 5000,
        "heartInterval": 30000
      }
    ]
  }
}
```

AstrBot 侧对应配置：

```json
{
  "platform": [
    {
      "id": "napcat",
      "type": "aiocqhttp",
      "enable": true,
      "ws_reverse_host": "127.0.0.1",
      "ws_reverse_port": 6199,
      "ws_reverse_token": "<同一个随机串>"
    }
  ]
}
```

改完重启 NapCat 生效。AstrBot 日志出现下面这行即接通：

```
aiocqhttp(OneBot v11) 适配器已连接。
```

## 8. 后台配置（WebUI :6185）

1. **模型**：新增对话模型（OpenAI 兼容：`api_base` + `key` + `model`），设为默认
2. **Embedding**：新增向量嵌入模型（本机 Ollama 或云端 API），维度要与模型一致
3. **人格**：导入人格文本
4. **白名单**：`平台名:FriendMessage:主人QQ号`
5. **管理员**：主人 QQ 号
6. **电脑操作能力**：保持关闭（`computer_use_runtime = none`）

## 9. 验证清单

| 检查 | 预期 |
|---|---|
| `http://127.0.0.1:6185` | 能打开登录页 |
| 日志 `适配器已连接` | 出现，且时间是刚才 |
| `netstat -ano \| findstr 6199` | 有 `LISTENING` |
| QQ 私聊发消息 | 有回复 |
| 发 `/reset` | 清空会话上下文 |

## 10. 服务器上的额外事项

- **安全组**：只放行 3389；6185/6199/6099 不要对公网开放
- **虚拟内存**：2GB 内存的机型务必把页面文件设到 4–8GB，否则插件初始化容易失败
- **中文路径**：Windows 服务端建议部署在纯 ASCII 路径下（如 `C:\dafeiyu`），可避免部分脚本与工具的编码问题
- **强杀 QQ 会破坏注入状态**：优先正常退出 QQ，别用 `taskkill /f`
