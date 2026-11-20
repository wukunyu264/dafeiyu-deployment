# 架构与运行环境

## 组件

| 组件 | 作用 | 运行位置 |
|---|---|---|
| QQ NT | 真实 QQ 客户端，登录机器人小号 | Windows 桌面进程 |
| NapCat | 注入 QQ，把消息事件转成 OneBot v11，提供 HTTP / WS 接口 | 注入到 QQ 进程内 |
| AstrBot | Agent 主体：会话、人格、模型调用、插件、记忆 | Python 进程，监听 6185 |
| 对话模型 | 生成回复（OpenAI 兼容接口） | 云端 API |
| Embedding 模型 | 把消息转成向量，供长期记忆检索 | 本机 Ollama 或云端 API |
| TTS | 语音合成 | 云端 API |

## 端口

| 端口 | 归属 | 用途 | 是否需要对公网开放 |
|---|---|---|---|
| 6185 | AstrBot | WebUI 后台 + 管理 API | 否（建议只在本机/内网访问） |
| 6199 | AstrBot | OneBot v11 反向 WebSocket 服务端 | 否 |
| 6099 | NapCat | NapCat 自己的 WebUI | 否 |
| 3389 | Windows | 远程桌面 | 是（限制来源 IP） |

> 6185 / 6199 / 6099 都只需**本机回环**通信。云服务器上不要对公网开放 6199 / 6099，否则任何人都能接入你的机器人。

## 数据流

```
QQ 消息
  → QQ NT 收到
  → NapCat 解析成 OneBot v11 事件
  → 反向 WS（带 token）推给 AstrBot:6199
  → AstrBot 管线：白名单 → 唤醒词 → 限流 → 人格/记忆检索 → 模型调用
  → 回复文本 → 可选 TTS / 表情包 / 分段
  → 通过 WS 回给 NapCat → QQ 发出
```

## 目录约定

部署根目录（本文档统一用 `C:\大肥鱼` 举例，脚本用 `%~dp0` 自动定位）：

```
C:\大肥鱼\
├── AstrBot\                    # AstrBot 源码 + .venv + data
│   └── data\                   # ★ 唯一需要备份的目录
│       ├── cmd_config.json     # 全部配置
│       ├── data_v4.db          # 会话、人格、聊天记录
│       ├── plugins\            # 已安装插件
│       └── plugin_data\        # 插件数据（含长期记忆）
├── NapCat\                     # NapCat Shell
│   └── config\
│       └── onebot11_<QQ号>.json  # 反向 WS 地址与 token
├── dafeiyu-config-pack\        # 配置包（人格、插件清单、导入工具）
├── 后台.txt                     # WebUI 地址/账号/密码（不入库）
├── 大号QQ.txt                   # 主人 QQ（不入库）
├── deepseek-key.txt            # 模型 API Key（不入库）
├── 豆包语音.txt                  # TTS 凭据（不入库）
├── start-astrbot.bat           # 见 scripts/
└── start-napcat.bat
```

> 凭据单独放文本文件、由脚本/插件按需读取，而不是写进代码或配置文件，这样**配置文件本身可以脱敏后公开**，也便于轮换。

## 关键配置项

AstrBot 侧（`data/cmd_config.json`）：

| 配置 | 说明 |
|---|---|
| `platform[].type = aiocqhttp` | OneBot v11 适配器 |
| `ws_reverse_host / port / token` | 反向 WS 监听与鉴权，需与 NapCat 一致 |
| `provider_sources[]` | 模型来源（api_base + key） |
| `provider[]` | 具体模型（对话 / 嵌入 / TTS） |
| `admins_id[]` | 管理员（能改签名、发说说等） |
| `platform_settings.id_whitelist[]` | 允许对话的会话 ID，格式 `平台名:FriendMessage:QQ号` |
| `provider_settings.computer_use_runtime` | 电脑操作能力，本实践保持 `none`（关闭） |

NapCat 侧（`config/onebot11_<QQ号>.json`）：

```json
{
  "network": {
    "websocketClients": [
      {
        "name": "astrbot",
        "enable": true,
        "url": "ws://127.0.0.1:6199/ws",
        "messagePostFormat": "array",
        "token": "<与 AstrBot 的 ws_reverse_token 一致>",
        "reconnectInterval": 5000,
        "heartInterval": 30000
      }
    ]
  }
}
```

## 白名单与会话 ID

AstrBot 的白名单比对的是 **完整会话 ID**，不是裸 QQ 号：

```
平台实例名:FriendMessage:QQ号      例如  napcat:FriendMessage:123456789
平台实例名:GroupMessage:群号
```

只填裸 QQ 号匹配不上。若同时把该号设为管理员，管理员豁免会掩盖这个问题——两者的区别在 [`docs/troubleshooting.md`](troubleshooting.md) 里有记录。
