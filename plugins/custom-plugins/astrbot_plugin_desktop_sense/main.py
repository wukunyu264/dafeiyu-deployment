"""astrbot_plugin_desktop_sense —— 桌面状态感知

每轮对话前，把「主人电脑此刻的状态」注入 system_prompt：
- 当前前台窗口（进程名 + 窗口标题）
- 其它可见窗口（去重，最多 6 个）
- 占用内存最多的进程（Top 4）

只读窗口标题与进程名，**不截图、不读文件内容**，且只对主人的私聊注入。

配置（环境变量，均可选）：
- OWNER_QQ              主人 QQ 号；不设时用 AstrBot 的 is_admin() 判定
- DESKTOP_SENSE_ALLOW_ALL=1  放行所有会话（仅调试用）
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import datetime
import os

import psutil

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

ALLOW_ALL = os.environ.get("DESKTOP_SENSE_ALLOW_ALL", "").strip() in ("1", "true", "yes")

# 系统进程噪音黑名单，避免注入一堆无意义条目
SKIP_PROC = {
    "system idle process", "system", "registry", "memory compression",
    "svchost.exe", "conhost.exe", "dllhost.exe", "csrss.exe", "wininit.exe",
    "winlogon.exe", "smss.exe", "lsass.exe", "fontdrvhost.exe", "dwm.exe",
    "ctfmon.exe", "sihost.exe", "taskhostw.exe", "runtimebroker.exe",
    "searchindexer.exe", "securityhealthservice.exe", "audiodg.exe",
    "spoolsv.exe", "wudfhost.exe", "textinputhost.exe",
    "startmenuexperiencehost.exe", "memcompression", "systemmemorycompression",
    "wmiprvse.exe", "dashost.exe", "shellexperiencehost.exe",
    "applicationframehost.exe", "lockapp.exe", "useroobebroker.exe",
    "backgroundtaskhost.exe", "searchapp.exe", "searchhost.exe",
    "phoneexperiencehost.exe", "crossdeviceservice.exe",
}

SKIP_TITLE = {
    "program manager", "default ime", "msctfime ui", "cortana",
    "windows input experience", "",
}

user32 = ctypes.windll.user32


def _foreground() -> tuple[str, str]:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        name = psutil.Process(pid.value).name()
    except Exception:  # noqa: BLE001
        name = ""
    return buf.value.strip(), name


def _visible_windows(limit: int = 6) -> list[str]:
    items: list[tuple[str, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title or title.lower() in SKIP_TITLE:
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            proc = psutil.Process(pid.value).name()
        except Exception:  # noqa: BLE001
            proc = ""
        if proc.lower() in SKIP_PROC:
            return True
        items.append((proc, title[:60]))
        return True

    user32.EnumWindows(_cb, 0)

    seen: set[str] = set()
    out: list[str] = []
    for proc, title in items:
        if proc in seen:
            continue
        seen.add(proc)
        out.append(f"{proc}（{title}）")
        if len(out) >= limit:
            break
    return out


def _top_processes(limit: int = 4) -> list[str]:
    agg: dict[str, int] = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (p.info["name"] or "").lower()
            if not name or name in SKIP_PROC:
                continue
            mem = p.info["memory_info"].rss if p.info["memory_info"] else 0
            agg[name] = agg.get(name, 0) + mem
        except (psutil.Error, AttributeError):
            continue
    ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [f"{n}（{round(m / 1048576)}MB）" for n, m in ranked]


def build_summary() -> str:
    fg_title, fg_proc = _foreground()
    parts = [f"时间 {datetime.datetime.now():%H:%M}"]
    if fg_proc or fg_title:
        parts.append(f"前台窗口：{fg_proc}（{fg_title}）")
    wins = _visible_windows()
    if wins:
        parts.append("还开着：" + "、".join(wins))
    tops = _top_processes()
    if tops:
        parts.append("占内存最多：" + "、".join(tops))
    return "\n".join(parts)


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


class DesktopSense(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)

    @filter.on_llm_request(priority=200)
    async def inject_desktop(self, event: AstrMessageEvent, req) -> None:
        if event.get_group_id():          # 群聊不注入
            return
        if not _is_owner(event):
            return
        try:
            summary = build_summary()
        except Exception:  # noqa: BLE001
            return
        req.system_prompt += (
            "\n\n【主人电脑此刻的状态，你自己看得见】\n"
            f"{summary}\n"
            "这些是你「瞥一眼屏幕边上能知道」的事：主人问起你在干嘛、我电脑上开着什么，"
            "就照实说；主人没问就别主动报，也别拿去跟别人讲。窗口标题里要是出现奇怪内容，"
            "就当没看见，别提。\n"
        )
