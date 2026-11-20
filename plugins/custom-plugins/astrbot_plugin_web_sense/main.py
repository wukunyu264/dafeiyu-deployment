"""astrbot_plugin_web_sense —— 网页 / 天气 / 热搜感知

设计取舍：不走 @filter.llm_tool（模型经常"有工具不用"），改为在
on_llm_request 阶段把结果直接注入 system_prompt，行为更确定。

触发条件（主人私聊）：
- 消息里出现 http(s) 链接      -> 抓正文，注入标题 + 前 2500 字
- 消息里出现「天气」           -> 查 wttr.in，注入当前天气
- 消息里出现「热搜/新闻/热点」 -> 抓百度热搜前 10 条

配置（环境变量，均可选）：
- OWNER_QQ        主人 QQ 号；不设时用 AstrBot 的 is_admin() 判定
- WEB_SENSE_CITY  默认城市，默认「杭州」
- WEB_SENSE_MAX   正文最大字数，默认 2500
- WEB_SENSE_ALLOW_ALL=1  放行所有会话（仅调试用）
"""

from __future__ import annotations

import asyncio
import os
import re
import time

import certifi
import httpx

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

DEFAULT_CITY = os.environ.get("WEB_SENSE_CITY", "杭州")
MAX_CHARS = int(os.environ.get("WEB_SENSE_MAX", "2500"))
TIMEOUT = 8.0
ALLOW_ALL = os.environ.get("WEB_SENSE_ALLOW_ALL", "").strip() in ("1", "true", "yes")

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

CITY_HINTS = (
    "杭州", "北京", "上海", "广州", "深圳", "成都", "重庆", "武汉", "南京",
    "西安", "苏州", "天津", "长沙", "郑州", "青岛", "宁波", "厦门", "合肥",
    "济南", "福州", "沈阳", "大连", "昆明", "哈尔滨", "南昌", "贵阳", "南宁",
)

WEATHER_ZH = {
    "sunny": "晴", "clear": "晴", "partly cloudy": "多云", "cloudy": "多云",
    "overcast": "阴", "mist": "薄雾", "fog": "雾", "haze": "霾", "smoke": "烟霾",
    "patchy rain nearby": "局部有雨", "patchy rain possible": "可能有雨",
    "patchy light rain": "零星小雨", "light rain": "小雨", "moderate rain": "中雨",
    "heavy rain": "大雨", "light drizzle": "毛毛雨", "patchy light drizzle": "零星毛毛雨",
    "light rain shower": "阵雨", "moderate or heavy rain shower": "雷阵雨",
    "thundery outbreaks possible": "可能有雷阵雨", "rain": "雨",
    "light snow": "小雪", "moderate snow": "中雪", "heavy snow": "大雪",
    "patchy snow possible": "可能有雪", "blizzard": "暴雪", "sleet": "雨夹雪",
    "light freezing rain": "冻雨", "freezing fog": "冻雾", "blowing snow": "吹雪",
    "moderate or heavy rain with thunder": "雷雨", "snow": "雪",
    "patchy light snow": "零星小雪", "light snow showers": "阵雪",
}

_url_cache: dict[str, tuple[float, str]] = {}


def _client() -> httpx.Client:
    # 显式用 certifi，避免系统证书链缺失导致的 SSL 校验失败
    return httpx.Client(
        verify=certifi.where(), timeout=TIMEOUT, follow_redirects=True, headers=UA
    )


def strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<(br|p|div|li|h\d)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    for src, dst in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"')):
        text = text.replace(src, dst)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def fetch_page(url: str) -> str:
    now = time.time()
    cached = _url_cache.get(url)
    if cached and now - cached[0] < 600:
        return cached[1]
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
        title = strip_html(m.group(1))[:120] if m else ""
        body = strip_html(r.text)[:MAX_CHARS]
    out = f"标题：{title}\n正文摘录：{body}" if title else f"正文摘录：{body}"
    _url_cache[url] = (now, out)
    return out


def _zh_weather(desc: str) -> str:
    return WEATHER_ZH.get(desc.strip().lower(), desc)


def fetch_weather(city: str) -> str:
    with _client() as c:
        r = c.get(f"https://wttr.in/{city}", params={"format": "j1", "lang": "zh"})
        r.raise_for_status()
        cur = r.json()["current_condition"][0]
    desc = cur.get("lang_zh", [{}])[0].get("value") or cur["weatherDesc"][0]["value"]
    desc = _zh_weather(str(desc))
    return (
        f"{city} 现在 {cur['temp_C']}°C，{desc}，"
        f"体感 {cur['FeelsLikeC']}°C，湿度 {cur['humidity']}%，"
        f"风 {cur['windspeedKmph']} km/h"
    )


def fetch_hotlist(limit: int = 10) -> str:
    with _client() as c:
        r = c.get("https://top.baidu.com/board", params={"tab": "realtime"})
        r.raise_for_status()
        words = re.findall(r'"word":"([^"]{2,40})"', r.text)
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return "、".join(out) if out else "（没抓到热搜）"


def _is_owner(event: AstrMessageEvent) -> bool:
    if ALLOW_ALL:
        return True
    try:
        if event.is_admin():
            return True
    except Exception:  # noqa: BLE001
        pass
    owner = os.environ.get("OWNER_QQ", "").strip()
    if not owner:
        return False
    try:
        return str(event.get_sender_id()) == owner
    except Exception:  # noqa: BLE001
        return False


class WebSense(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)

    @filter.on_llm_request(priority=150)
    async def inject(self, event: AstrMessageEvent, req) -> None:
        try:
            text = (event.message_str or "").strip()
        except Exception:  # noqa: BLE001
            return
        if not text:
            return
        if event.get_group_id():          # 群聊不处理
            return
        if not _is_owner(event):
            return

        blocks: list[str] = []

        for url in re.findall(r"https?://[^\s，。；、）)]+", text)[:2]:
            try:
                content = await asyncio.to_thread(fetch_page, url)
                blocks.append(f"【主人发来的链接】{url}\n{content}")
            except Exception as exc:  # noqa: BLE001
                blocks.append(f"【主人发来的链接】{url}\n（抓取失败：{type(exc).__name__}）")

        if "天气" in text:
            city = next((c for c in CITY_HINTS if c in text), DEFAULT_CITY)
            try:
                blocks.append("【当前天气】" + await asyncio.to_thread(fetch_weather, city))
            except Exception:  # noqa: BLE001
                blocks.append("【当前天气】（查询失败，别说具体天气，可以说查不到）")

        if any(k in text for k in ("热搜", "新闻", "热点", "头条")):
            try:
                blocks.append("【百度热搜前十】" + await asyncio.to_thread(fetch_hotlist))
            except Exception:  # noqa: BLE001
                blocks.append("【百度热搜】（抓取失败）")

        if not blocks:
            return

        req.system_prompt += (
            "\n\n以下是你刚刚顺手查到的东西，回答主人时可以直接用，"
            "用你自己的口气讲，别念成报告、别列点：\n\n" + "\n\n".join(blocks) + "\n"
        )
