"""
scheduler.py — 通用定时推送调度器
支持多任务、多时间点。天气=图片渲染，其他=纯文字，合并转发输出。
"""

import asyncio
import datetime
import html
import base64
import os
import contextlib
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain, Node, Nodes

# ======== 可调度任务注册表 ========
# 每个条目: task_id -> (module_path, fetch_func_name, display_name)
TASK_REGISTRY = {}

def register_task(task_id: str, module_path: str, fetch_func: str, display_name: str):
    """注册可调度的任务"""
    TASK_REGISTRY[task_id] = (module_path, fetch_func, display_name)

# 注册已有的 hotboard 平台
_HOTBOARD_PLATFORMS = {
    "bili": "哔哩哔哩热榜",
    "acfun": "A站热榜",
    "github": "HelloGitHub 热榜",
    "netease_music": "网易云音乐热歌榜",
    "qq_music": "QQ音乐热歌榜",
    "weread": "微信读书热榜",
}

# 所有可选任务（用于默认值和提示）
ALL_TASKS = ["news", "bili", "acfun", "github", "netease_music", "qq_music", "weread", "weather"]


# ======== 热榜文字格式化 ========

_HOTBOARD_EMOJI = {
    "bilibili":      "📺",
    "acfun":         "🍌",
    "hellogithub":   "🐙",
    "netease-music": "🎵",
    "qq-music":      "🎶",
    "weread":        "📖",
}


def format_hotboard_text(platform_id: str, display_name: str, items: list) -> str:
    """将热榜结构化数据格式化为美观的文字输出"""
    icon = _HOTBOARD_EMOJI.get(platform_id, "📊")
    lines = [f"{icon} {display_name}", "━━━━━━━━━━━━━━"]

    for item in items:
        rank = item["index"]
        title = item["title"]
        hot = item.get("hot_value", "")
        extra = item.get("extra", {})

        # 副信息
        sub = ""
        if platform_id == "bilibili":
            up = extra.get("up_name", "")
            sub = f"  UP: {up}" if up else ""
        elif platform_id == "hellogithub":
            lang = extra.get("primary_lang", "")
            repo = extra.get("full_name", "")
            sub = f"  [{lang}] {repo}" if lang else f"  {repo}"
        elif platform_id in ("netease-music", "qq-music"):
            artist = extra.get("artist_names", "")
            dur = extra.get("duration_text", "")
            sub = f"  {artist}" + (f" · {dur}" if dur else "")
        elif platform_id == "weread":
            author = extra.get("author", "")
            sub = f"  {author}" if author else ""

        hot_str = f"  🔥{hot}" if hot else ""
        lines.append(f"#{rank}  {title}{hot_str}")
        if sub:
            lines.append(f"     {sub}")
        url = item.get("url", "")
        if url:
            lines.append(f"     🔗 {url}")

    lines.append("━━━━━━━━━━━━━━")
    lines.append("Powered by UApiPro")
    return "\n".join(lines)


# ======== 任务数据获取 ========

async def _fetch_single_task(task_id: str, token: str, session) -> tuple:
    """
    获取单个任务的数据。
    返回 (ok, data, title)

    data 格式：
      - weather:  HTML 字符串（用于渲染图片）
      - news:     图片文件路径
      - hotboard: dict {"type": "hotboard", "items": [...], "platform_id": "...", "html": "...", "display_name": "..."}
    """
    if task_id == "news":
        from .apis import news
        ok, data, err = await news.fetch(token, session=session)
        title = "📰 每日新闻"
        if ok:
            return ok, data, title
        return False, err, title

    if task_id == "weather":
        from .apis import weather
        city = ""
        if hasattr(session, '_default_city'):
            city = session._default_city or ""
        ok, data, err = await weather.fetch(city, token, session=session)
        title = "🌤️ 今日天气"
        if ok:
            return ok, data, title
        return False, err, title

    if task_id in _HOTBOARD_PLATFORMS:
        from .hotboard.fetcher import fetch
        display = _HOTBOARD_PLATFORMS[task_id]
        ok, payload, err = await fetch(task_id, token, session=session)
        if ok:
            return ok, {
                "type": "hotboard",
                "items": payload["items"],
                "platform_id": payload["platform_id"],
                "html": payload["html"],
                "display_name": payload["display_name"],
            }, display
        return False, err, display

    return False, f"未知任务: {task_id}", task_id


# ======== HTML 合并渲染（保留，供未来可能的图片模式使用） ========

def _render_combined_html(results: list) -> str:
    """
    将多个任务的结果合并为一张 HTML 页面。
    results: [(title, html_content_or_path), ...]
    """
    sections = []
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for title, content in results:
        if content.startswith("http") or content.endswith((".jpg", ".png", ".jpeg")):
            sections.append(f"""
            <div class="task-section">
                <div class="section-header">{html.escape(title)}</div>
                <img class="task-image" src="{html.escape(content)}" referrerpolicy="no-referrer" />
            </div>
            """)
        elif "<html" in content.lower() or "<style" in content or "<div" in content:
            sections.append(f"""
            <div class="task-section">
                <div class="section-header">{html.escape(title)}</div>
                <div class="section-body">{content}</div>
            </div>
            """)
        else:
            sections.append(f"""
            <div class="task-section">
                <div class="section-header">{html.escape(title)}</div>
                <div class="section-text">{html.escape(content).replace(chr(10), '<br>')}</div>
            </div>
            """)

    sections_html = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=540">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ background: #F5F5F7; display: table; width: 100%; }}
    body {{
      display: table-cell;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    .main-card {{
      width: 100%;
      background: #FFFFFF;
      overflow: hidden;
    }}
    .main-header {{
      padding: 24px 20px 16px;
      background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
      color: #FFFFFF;
      text-align: center;
    }}
    .main-header h1 {{
      font-size: 22px; font-weight: 700;
    }}
    .main-header .sub {{
      font-size: 12px; opacity: 0.8; margin-top: 4px;
    }}
    .task-section {{
      border-bottom: 8px solid #F5F5F7;
    }}
    .task-section:last-child {{ border-bottom: none; }}
    .section-header {{
      padding: 14px 18px 10px;
      font-size: 16px; font-weight: 600; color: #1D1D1F;
      background: #FAFAFC;
      border-bottom: 1px solid #EFEFF4;
    }}
    .section-body {{
      padding: 0;
    }}
    .section-body .item,
    .section-body .item-plain {{
      padding: 10px 18px;
    }}
    .section-body .header {{
      padding: 12px 18px 10px;
    }}
    .task-image {{
      display: block; width: 100%; max-width: 100%;
    }}
    .section-text {{
      padding: 16px 18px;
      font-size: 13px; color: #1D1D1F; line-height: 1.7;
    }}
    .footer {{
      padding: 14px 20px; text-align: center;
      font-size: 11px; color: #AEAEB2;
      background: #FAFAFA;
    }}
  </style>
</head>
<body>
  <div class="main-card">
    <div class="main-header">
      <h1>📬 今日推送</h1>
      <div class="sub">{now_str}</div>
    </div>
    {sections_html}
    <div class="footer">Powered by AstrBot · UApiPro</div>
  </div>
</body>
</html>"""


# ======== 定时调度器 ========

class TaskScheduler:
    """
    通用定时任务调度器。
    由主插件初始化，替代原来的 _news_scheduler。
    输出策略：天气=图片渲染，其他=纯文字，合并转发。
    """

    def __init__(self, plugin):
        self.plugin = plugin
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            await asyncio.sleep(30)
            try:
                if not self.plugin.plugin_config.get("schedule_enabled", False):
                    continue

                config = self.plugin.plugin_config
                now = datetime.datetime.now()
                today = now.date().isoformat()

                # 支持多个时间点，用 | 分隔
                time_str = config.get("schedule_time", "08:00").replace("：", ":").strip()
                times = [t.strip() for t in time_str.split("|") if t.strip()]

                for t in times:
                    try:
                        h, m = map(int, t.split(":"))
                    except (ValueError, TypeError):
                        continue

                    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    kv_key = f"schedule_last_push_{t.replace(':', '_')}"

                    if now < target:
                        continue

                    last_date = await self.plugin.get_kv_data(kv_key, None)
                    if last_date == today:
                        continue

                    await self.plugin.put_kv_data(kv_key, today)
                    await self._execute_tasks(config)
                    break  # 一次只触发一个时间点

            except Exception as e:
                logger.error(f"[UApiPro] 调度器异常: {e}")

    async def _execute_tasks(self, config: dict):
        """执行所有配置好的任务，结果合并推送"""
        logger.info("[UApiPro] 开始执行定时推送任务")

        # 检查是否开启了全部推送功能
        if not config.get("push_all_enabled", True):
            logger.info("[UApiPro] 全部推送功能已关闭(push_all_enabled=false)，跳过定时推送")
            return

        tasks = config.get("schedule_tasks", ["news"])
        token = config.get("uapi_token", "")

        # 把默认城市存到 session 上供 _fetch_single_task 读取
        default_city = config.get("schedule_city", "")
        if default_city and hasattr(self.plugin, 'session'):
            self.plugin.session._default_city = default_city

        results = []  # [(task_id, title, data), ...]

        for task_id in tasks:
            task_id = task_id.strip()
            if not task_id:
                continue
            logger.info(f"[UApiPro] 正在获取任务: {task_id}")
            try:
                ok, data, title = await _fetch_single_task(task_id, token, self.plugin.session)
                if ok:
                    results.append((task_id, title, data))
                    logger.info(f"[UApiPro] 任务 {task_id} 成功")
                else:
                    logger.warning(f"[UApiPro] 任务 {task_id} 失败: {data}")
            except Exception as e:
                logger.error(f"[UApiPro] 任务 {task_id} 异常: {e}")

        if not results:
            logger.warning("[UApiPro] 所有任务均失败，跳过推送")
            return

        await self._broadcast(results, config)

    async def _broadcast(self, results: list, config: dict):
        """
        构建合并转发消息并推送到配置的群和用户。
        results: [(task_id, title, data), ...]

        输出规则：
          - weather → 渲染 HTML 为图片 (Image Node)
          - hotboard → 纯文字 (Plain Node)
          - news → 直接使用图片 (Image Node)
        """
        groups = config.get("schedule_groups", [])
        users = config.get("schedule_users", [])
        if not groups and not users:
            logger.info("[UApiPro] 未配置推送目标，跳过")
            return

        # 获取平台标识和 bot_uin
        plat = None
        bot_uin = 1000000
        try:
            plat_insts = self.plugin.context.platform_manager.platform_insts
            if plat_insts:
                meta = plat_insts[0].meta()
                plat = meta.id
                bot_uin = getattr(meta, 'self_id', 1000000) or 1000000
        except Exception:
            pass
        if not plat:
            logger.warning("[UApiPro] 未找到已注册平台，无法推送")
            return

        # ---- 构建 Nodes ----
        nodes = []
        for task_id, title, data in results:
            content = []

            if task_id == "weather":
                # 天气 → 渲染 HTML 为图片
                if isinstance(data, str) and ("<html" in data.lower() or "<style" in data):
                    image_b64 = await self._render_weather_image(data)
                    if image_b64:
                        content.append(Image(file=f"base64://{image_b64}"))
                    else:
                        logger.warning(f"[UApiPro] 天气图片渲染失败，降级文字")
                        content.append(Plain(f"🌤️ {title}\n(天气图片渲染失败，请稍后重试)"))
                else:
                    content.append(Plain(f"🌤️ {title}\n{str(data)[:500]}"))

            elif isinstance(data, dict) and data.get("type") == "hotboard":
                # 热榜 → 纯文字
                text = format_hotboard_text(
                    data["platform_id"], data["display_name"], data["items"]
                )
                content.append(Plain(text))

            elif isinstance(data, str) and (data.startswith("http") or data.endswith((".jpg", ".png", ".jpeg"))):
                # news 图片 → 直接使用
                content.append(Image(file=data))
                content.append(Plain(f"\n{title}"))

            elif isinstance(data, str):
                content.append(Plain(f"{title}\n{str(data)[:500]}"))

            else:
                content.append(Plain(str(data)[:500]))

            if content:
                nodes.append(Node(uin=bot_uin, name=title, content=content))

        if not nodes:
            logger.warning("[UApiPro] 没有可推送的内容")
            return

        # ---- 发送合并转发 ----
        from astrbot.api.event import MessageChain
        forward = Nodes(nodes=nodes)

        for gid in groups:
            try:
                umo = str(gid) if ":" in str(gid) else f"{plat}:GroupMessage:{gid}"
                await self.plugin.context.send_message(umo, MessageChain(chain=[forward]))
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"[UApiPro] 推送失败 [{gid}]: {e}")
        for uid in users:
            try:
                umo = str(uid) if ":" in str(uid) else f"{plat}:FriendMessage:{uid}"
                await self.plugin.context.send_message(umo, MessageChain(chain=[forward]))
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"[UApiPro] 推送失败 [{uid}]: {e}")

        logger.info(f"[UApiPro] 定时推送完成，共 {len(nodes)} 个 Node")

    async def _render_weather_image(self, html_str: str) -> str | None:
        """渲染天气 HTML 为 base64 图片，失败返回 None"""
        if not hasattr(self.plugin, "html_render"):
            return None

        render_strategies = [
            {"full_page": True, "type": "png", "scale": "device", "device_scale_factor_level": "ultra"},
            {"full_page": True, "type": "jpeg", "quality": 100, "scale": "device", "device_scale_factor_level": "ultra"},
            {"full_page": True, "type": "jpeg", "quality": 95, "scale": "device", "device_scale_factor_level": "high"},
            {"full_page": True, "type": "jpeg", "quality": 80, "scale": "device"},
        ]

        async with self.plugin.render_lock:
            for options in render_strategies:
                try:
                    image_data = await self.plugin.html_render(html_str, {}, False, options)
                    if not image_data:
                        continue
                    raw = None
                    if isinstance(image_data, bytes):
                        raw = image_data
                    elif isinstance(image_data, str) and os.path.exists(image_data):
                        with open(image_data, "rb") as f:
                            raw = f.read()
                        with contextlib.suppress(OSError):
                            os.remove(image_data)
                    if not raw:
                        continue
                    if raw[:2] == b"\xff\xd8" or raw[:4] == b"\x89PNG":
                        return base64.b64encode(raw).decode()
                except Exception:
                    pass
        return None

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None
