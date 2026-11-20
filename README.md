# 大肥鱼部署实践 · AstrBot + NapCat 个人 AI Agent

> 把自己部署的 QQ AI Agent 整理成可复现的工程实践：**运行环境搭建、插件集成、长期记忆接入、服务运维与数据备份**。
>
> 本仓库不包含任何第三方源码、二进制安装包、账号凭据或个人数据，只包含**我编写的脚本、插件、配置模板与部署文档**。

---

## 这是什么

「大肥鱼」是一套跑在个人服务器上的 QQ AI Agent：

- **大脑**：AstrBot（Python，负责模型调用、人格、插件、记忆）
- **嘴**：NapCat（把 QQ 客户端包装成 OneBot v11 协议，供 AstrBot 收发消息）
- **说话**：DeepSeek API（对话）
- **记忆**：向量嵌入服务（本机 Ollama / 硅基流动）+ LivingMemory 插件
- **表达**：豆包 Seed Audio（语音）、表情包、QQ 空间说说、个性签名

我做的事情不是「写一个 Agent 框架」，而是：

1. 从零搭起可运行的 Windows 服务环境（QQ NT + Python + AstrBot + NapCat）
2. 部署并调优第三方配置包与插件
3. 接入长期记忆（Embedding 服务选型与故障排查）
4. 解决部署过程中一连串真实故障（版本兼容、缺 DLL、缺 ffmpeg、编码、端口、内存）
5. 写自己的插件补足能力（网页/天气/热搜感知、桌面状态感知）
6. 维护配置、日志与数据备份

---

## 架构

```
                    ┌─────────────────────────────┐
   手机 QQ ────────▶│  QQ NT（Windows 客户端）     │
                    │      ▲                      │
                    │      │ 注入                 │
                    │  NapCat（OneBot v11）       │
                    └──────┼──────────────────────┘
                           │ 反向 WebSocket
                           │ ws://127.0.0.1:6199/ws  (token 鉴权)
                    ┌──────▼──────────────────────┐
                    │  AstrBot :6185              │
                    │  ├─ 人格 / 会话管理          │
                    │  ├─ 插件：记忆/表情/语音/空间 │
                    │  ├─ 自研：web_sense          │
                    │  └─ 自研：desktop_sense      │
                    └──────┬──────────────┬───────┘
                           │              │
                  DeepSeek API     Embedding API
                  （对话模型）      （向量检索）
```

端口与路径约定见 [`docs/architecture.md`](docs/architecture.md)。

---

## 自研插件

| 插件 | 解决什么问题 |
|---|---|
| [`astrbot_plugin_web_sense`](plugins/custom-plugins/astrbot_plugin_web_sense) | 主人私聊里出现链接 / 「天气」/「热搜」时，自动抓取内容**注入上下文**，不依赖模型主动调用工具 |
| [`astrbot_plugin_desktop_sense`](plugins/custom-plugins/astrbot_plugin_desktop_sense) | 每轮对话把「当前前台窗口、正在运行的程序」注入上下文，让她知道你在电脑上做什么（只读窗口标题与进程名，不截图） |

> 两个插件都采用 **注入上下文** 而非 **暴露工具** 的设计。原因见 [`docs/plugin-guide.md`](docs/plugin-guide.md#为什么用注入而不是工具调用)。

---

## 快速开始

完整步骤见 [`docs/installation.md`](docs/installation.md)，这里只列主干：

```text
1. 装 QQ NT（Windows 版），装完先不要登录
2. 装 Python 3.12（务必勾选 Add python.exe to PATH）
3. 安装 VC++ 运行库（NapCat 注入器依赖 msvcp140.dll）
4. 安装 ffmpeg（语音发送依赖），加入 PATH 后重启 AstrBot
5. 拉取 AstrBot 源码，建 venv，装依赖
6. 放 NapCat（注意 QQ 版本与 NapCat 版本的对应关系）
7. 配置 OneBot v11 反向 WS（端口 6199 + token）
8. 启动 AstrBot → 启动 NapCat → 扫码登录
9. 在 AstrBot 后台配置：对话模型、Embedding、人格、白名单、管理员
```

启动 / 重启 / 备份脚本见 [`scripts/`](scripts)。

---

## 目录结构

```
dafeiyu-deployment/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── architecture.md      架构、端口、路径、数据流
│   ├── installation.md      从零部署（含踩坑顺序）
│   ├── plugin-guide.md      插件清单、自研插件设计取舍
│   ├── backup-guide.md      备份与恢复（data 目录）
│   └── troubleshooting.md   真实故障与解法速查
├── config/
│   ├── config.example.json  脱敏后的关键配置片段
│   └── model.example.env    模型与凭据的环境变量模板
├── scripts/
│   ├── start-astrbot.bat
│   ├── start-napcat.bat
│   ├── restart-napcat.bat
│   ├── backup-data.bat
│   └── check-port.bat
├── plugins/custom-plugins/
│   ├── astrbot_plugin_desktop_sense/
│   └── astrbot_plugin_web_sense/
└── screenshots/
```

---

## 部署中真实遇到的坑（价值最高的部分）

完整清单见 [`docs/troubleshooting.md`](docs/troubleshooting.md)，几个代表性的：

| 现象 | 根因 |
|---|---|
| QQ 启动报「文件已损坏，请重新安装QQ」 | NapCat 版本比 QQ 版本旧，注入不兼容；强杀 QQ 也会导致补丁文件未还原 |
| `MSVCP140.dll 缺失` | 服务器是干净系统，缺 VC++ 运行库 |
| 语音合成成功但发不出去 | 缺 ffmpeg；且改完 PATH **必须重启** AstrBot，进程只在启动时读环境变量 |
| 记忆一直 `Connection error` | Embedding 服务不可用；或是热改配置后插件仍持有旧客户端（需重启进程） |
| 启动脚本报「字符串缺少终止符」 | `.ps1` 存成 UTF-8 无 BOM，PowerShell 5.1 按 GBK 读，中文路径撑断引号 |
| `消息0不存在` | 消息带了失效的引用；或分段回复与图片消息一起导致的协议问题 |
| 内存 2GB 装不下本地向量模型 | bge-m3 加载约占 1.5GB，改用云端 Embedding API 释放内存 |

---

## 合规与边界

- 机器人**只用小号**运行，不使用主账号；非官方客户端存在风控风险，本文档不鼓励在主账号上运行。
- 只对**主人的私聊**开放对话，群聊与他人消息默认不响应（白名单 + 管理员配置）。
- 「桌面感知」只读取**窗口标题与进程名**，不截图、不读取文件内容。
- 本仓库**不包含**：聊天记录、长期记忆数据库、任何 API Key / Token / Cookie / 账号密码。
- 「大肥鱼」人格与配置包版权归原配置包作者；AstrBot、NapCat 及第三方插件遵循各自开源许可证，本仓库不分发它们的源码或二进制。

## 致谢

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) —— Agent 运行框架
- [NapCatQQ](https://github.com/NapNeko/NapCatQQ) —— QQ ↔ OneBot v11 桥接
- 大肥鱼配置包及其插件作者

## License

本仓库中**我编写的**代码与文档采用 [MIT](LICENSE)。第三方组件不在此许可范围内。
