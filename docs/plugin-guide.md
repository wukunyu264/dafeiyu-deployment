# 插件清单与自研插件

## 一、用到的第三方插件（从插件市场安装，不在本仓库分发）

| 插件 | 作用 | 备注 |
|---|---|---|
| LivingMemory | 长期记忆：抽取、结构化、向量检索 | 需要 Embedding 服务 |
| meme_manager | 表情包管理与发送 | 依赖表情包资源包 |
| proactive_chat | 主动发起消息（间隔、免打扰、未回复上限） | 默认 1:00–7:00 静默 |
| qzone | QQ 空间：发说说、看说说、点赞评论 | 自动发说说由 cron 控制 |
| qqprofile | 改头像、昵称、签名、在线状态 | 需管理员权限 |
| seed_audio_tts | 豆包 Seed Audio 语音合成 | 按语音时长计费 |
| group_chat_plus | 群聊插话节奏增强 | 群聊才生效 |

> 安装方式：AstrBot 后台 → 插件 → 插件市场 → 搜索安装。请遵守各自开源许可证。

## 二、配置包自带的插件

「大肥鱼配置包」内含四个插件（语音、唱歌、改签名、回复防串台），由配置包的导入工具安装到 `data/plugins`。它们随配置包发布，本仓库不分发。

## 三、自研插件

都放在 [`plugins/custom-plugins/`](../plugins/custom-plugins)。

### 3.1 astrbot_plugin_web_sense

**解决**：她不知道你在聊天里发的链接里写了什么；问天气、问热搜只能瞎答。

**行为**（只在主人的私聊生效）：

| 触发 | 动作 |
|---|---|
| 消息里出现 `http(s)://` 链接 | 抓取网页，提取标题 + 正文前 2500 字，注入上下文 |
| 消息里出现「天气」 | 调 `wttr.in` 取当前天气（自动识别 27 个城市名，默认杭州） |
| 消息里出现「热搜 / 新闻 / 热点 / 头条」 | 抓百度热搜前 10 条注入 |

**实现要点**：

- 用 `httpx + certifi`（不依赖系统证书链，避免 Windows 证书库问题）
- 抓取放在 `asyncio.to_thread` 里，不阻塞事件循环
- 同一 URL 结果缓存 10 分钟
- 任何一路失败都注入「（抓取失败）」，避免她编造内容
- 天气描述做中英映射（`Patchy rain nearby` → `局部有雨`），否则会冒出英文

**安装**：

```text
把 astrbot_plugin_web_sense 文件夹放到
  <AstrBot>\data\plugins\astrbot_plugin_web_sense\
确认路径是 ...\plugins\astrbot_plugin_web_sense\main.py（只一层）
后台 → 插件 → 刷新（或重启 AstrBot）
```

**配置**：默认城市改 `main.py` 里的 `DEFAULT_CITY`。

### 3.2 astrbot_plugin_desktop_sense

**解决**：她不知道你在电脑上做什么，问「我在干嘛」只能猜。

**行为**：每轮对话把下面这些注入系统提示词（只对主人私聊）：

```
时间 21:03
前台窗口：chrome.exe（GitHub - AstrBotDevs/AstrBot）
还开着：Weixin.exe（微信）、Code.exe（main.py - VSCode）…
占内存最多：chrome.exe（812MB）、python.exe（420MB）
```

**实现要点**：

- `ctypes` 调 `user32` 拿前台窗口与可见窗口列表，`psutil` 取进程名与内存
- 维护一份系统进程黑名单（`svchost`、`dwm`、`RuntimeBroker` 等），避免刷屏
- **只读窗口标题和进程名，不截图、不读文件内容**

## 四、为什么用注入而不是工具调用

这两个插件最初都做成 LLM 工具（`@filter.llm_tool`），实际跑下来失败率高：模型在强人设下**倾向用角色口吻回答，而不是调用工具**。

实测例子：

| 用户说 | 期望 | 实际 |
|---|---|---|
| 「给我唱首歌」 | 调用唱歌工具 | 回「？唱什么」 |
| 「调用 xxx 工具查一下」 | 调用工具 | 回「我哪来的这工具」 |

工具本身是注册成功的（后台工具列表可见、`active: true`），所以问题不在配置，而在模型的选择倾向。

改成**注入上下文**后行为变得确定：只要消息命中关键词，数据就一定在她的上下文里，她不用「决定要不要查」。

代价是每轮都带一点额外 token（状态快照约 200–400 字），可接受。

## 五、写一个类似插件的骨架

```python
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star


class MyPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)

    @filter.on_llm_request(priority=150)   # 数字越小越先执行
    async def inject(self, event: AstrMessageEvent, req) -> None:
        # 只服务主人私聊
        if event.get_group_id():
            return
        text = event.message_str or ""
        if "关键词" not in text:
            return
        data = "……"                        # 取数据（耗时操作放 asyncio.to_thread）
        req.system_prompt += f"\n\n【补充信息】\n{data}\n"
```

要点：

1. `on_llm_request` 里改 `req.system_prompt` 或 `req.contexts`
2. 耗时 IO 一定用 `await asyncio.to_thread(...)`，否则阻塞整个事件循环
3. 一定要做失败兜底，宁可注入「查不到」，也不要让模型自由发挥
4. 位置参数：放在 `data/plugins/<插件名>/{main.py, metadata.yaml}`，**只有一层目录**
