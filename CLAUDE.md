# CLAUDE.md — astrbot_plugin_uapipro_toolbox

## 项目概述

基于 https://github.com/lingyun14beta/astrbot_plugin_uapipro_toolbox 的 AStrBot 插件，支持多数据源热榜/新闻定时推送 + `/u` 指令手动推送。

原始项目所有输出均为 HTML→图片渲染。本项目在此基础上增加了：
- `/u 当天全部热榜` — 手动触发全部已配置数据源，合并转发输出
- 天气任务（weather）— 定时/手动推送指定城市天气
- `schedule_city` — 定时推送默认城市配置
- `push_all_enabled` — 控制是否执行定时全天推送的开关
- `/u 指定城市推送 <城市>` — 手动推送指定城市天气

## 目录结构

| 路径 | 说明 | Git Commit |
|------|------|------------|
| `V:\astrbotplugin` | **当前工作目录**（已 push 到 origin/main） | `1ae27c5` |
| `V:\astrbotchajianbeifeng\newspush` | **正常工作的备份**（无天气、无 push_all_enabled） | `5af4438` |

## 备份版 vs 当前版

| 功能 | 备份 (5af4438) | 当前 (1ae27c5) |
|------|:--:|:--:|
| 多热榜合并转发 | ✅ | ✅ |
| Nodes + send_message 合并转发 | ✅ | ✅ |
| weather 天气任务 | ❌ | ✅ |
| schedule_city 默认城市 | ❌ | ✅ |
| push_all_enabled 开关 | ❌ | ✅ |
| /u 指定城市推送 | ❌ | ✅ |
| 内容分类推送 | ❌ | ✅ |

## 核心问题

t2i.rcfortress.site/text2img 渲染服务不稳定，报错：
```
[WARN] Endpoint https://t2i.rcfortress.site/text2img failed: [Errno 32] Broken pipe
```
导致 5 分钟超时等待后渲染失败，所有内容无法正常输出。

## 解决方案（最终确认）

**核心原则：只有天气保留图片渲染，其他全部走纯文字输出。**

### 输出方式
| 任务类型 | 输出方式 | 说明 |
|----------|----------|------|
| weather（天气） | **图片渲染** | 保留 html_render → 图片输出，天气图卡 |
| 其他所有（bili、acfun、github、netease_music、qq_music、weread、news 等） | **纯文字** | 不调用 html_render，直接拼文字 |

### 文字输出模板
```
📊 哔哩哔哩热榜
1. xxx
2. xxx
3. xxx
...

📊 GitHub 热榜
1. xxx
2. xxx
3. xxx
...

📊 <来源名称>
1. xxx
2. xxx
...
```

### 合并转发结构
- 天气图片 → 一个 Node（图片消息）
- 其他每个热榜/新闻任务 → 各一个 Node（文字消息）
- 全部 Node 通过 `send_message` 合并转发为一条聊天记录

### 降级策略
- 图片渲染失败时：**立即降级为文字输出**，不等待、不重试、不等 5 分钟

### 指令行为
| 指令 | 行为 |
|------|------|
| `/u 当天全部热榜` | 推送全部已配置任务（天气=图，其他=文字），合并转发 |
| `/u 天气 <城市>` | 推送指定城市天气图片 |
| 定时推送 | 与 `/u 当天全部热榜` 输出一致，天气=图，其他=文字 |

## 实施策略

1. **基准代码**：以 `V:\astrbotchajianbeifeng\newspush`（5af4438）为基准
2. **保留功能**：weather 任务、schedule_city、push_all_enabled、/u 城市推送、内容分类 — 全部保留
3. **修改范围**：只改输出逻辑 — weather 走 html_render 图片，其他走纯文字
4. **不改动**：原项目的 API 调用、数据获取、任务调度逻辑均不变

## Git 历史（当前仓库）

```
1ae27c5 feat: 内容分类推送 + 天气任务 + 新指令支持
11ef831 feat: 新增schedule_city配置和/u 指定城市推送指令
5af4438 fix: 改用 Nodes + send_message 发送合并转发        ← 备份版
3080bfe fix: 去掉预先提示，确保全部Node一次合并转发
ede7a54 feat: /u 当天全部热榜 改用合并转发(Node)形式
f65973f feat: 添加 /u 当天全部热榜 指令
f5e6d8c v3.1.0: 支持多任务定时推送，合并多数据源到一张图
```

## 约束

- 所有改动必须保证原项目全部功能可用
- 新增功能只是扩展，不破坏已有行为
- 任何不确定的细节必须先与用户确认，不要自己动手

---

## 本次修改日志（2026-06-23）

### 背景

用户发现当前版本（1ae27c5）在 `/u 当天全部热榜` 和定时推送时出现问题：
- t2i.rcfortress.site 渲染服务报 `Broken pipe`，每轮重试 5 分钟
- 所有内容走图片渲染，一旦服务挂了全部卡住
- 推送消息无法正常发出

### 对话流程

1. **用户描述问题**：渲染服务不可用导致长时间等待和推送失败
2. **多轮确认需求**：
   - 不是「全部改成文字」，而是「只有天气保留图片，其他全部文字」
   - 备份版本 `V:\astrbotchajianbeifeng\newspush`（5af4438）是正常工作的基准
   - 以备份为基础，保留 1ae27c5 的全部新功能（weather、push_all_enabled、schedule_city、/u 指定城市推送）
   - 输出格式：天气图片 + 其他文字，合并转发
3. **确认后写入 CLAUDE.md** 作为需求文档
4. **实现改动**：scheduler.py（核心重写）、main.py（cmd_push_all 重写）、_conf_schema.json（描述更新）

### 设计决策

| 决策 | 结论 |
|------|------|
| weather 输出 | 保留 HTML→图片渲染（`html_render`），失败立即降级文字 |
| hotboard（bili/acfun/github/netease_music/qq_music/weread）输出 | 纯文字，使用结构化 `items` 数据格式化，不调用任何渲染 |
| news 输出 | 保留 API 直出图片（news API 返回 JPG 二进制，非 HTML 渲染） |
| 合并转发 | 每个任务一个 Node，weather=Image Node，hotboard=Plain Node，news=Image Node |
| 渲染降级 | 立即返回 None，不重试、不等待、不走多策略轮询 |
| `uapi_text_mode` 配置 | 在 `/u 当天全部热榜` 和定时推送中不再使用（因为 hotboard 本来就是文字了），单条指令仍正常使用 |
| 基准代码 | 实际以 1ae27c5 为基础修改（因为已有所有新功能），而非回退到 5af4438 再重加 |

### 代码改动详情

#### scheduler.py（244 行变更）

- **`_fetch_single_task`**：hotboard 平台返回 dict：
  ```python
  {"type": "hotboard", "items": [...], "platform_id": "...", "html": "...", "display_name": "..."}
  ```
  weather 返回 HTML 字符串（供渲染），news 返回图片路径

- **新增 `format_hotboard_text()`**：模块级函数，把热榜结构化数据格式化为美观文字
  - 每个平台有专属 emoji（📺🍌🐙🎵🎶📖）
  - 排版：`#排名  标题  🔥热度值` + 副信息行 + 链接行
  - 分隔线 + Powered by UApiPro 收尾

- **`_execute_tasks`**：results 格式从 `[(title, data)]` 改为 `[(task_id, title, data)]`，保留 `push_all_enabled` 检查

- **`_broadcast` 完全重写**：
  - 旧：合并所有结果 HTML → 一张大图 → 推送图片
  - 新：逐个任务构建 Node → Nodes 合并转发 → send_message
  - weather → `_render_weather_image()` 渲染图片
  - hotboard → `format_hotboard_text()` 文字
  - news → 直接 Image(file=path)

- **新增 `_render_weather_image()`**：只渲染天气 HTML，策略用尽即返回 None（不留连等待）

- **移除**：`get_all_task_defaults()`（死代码）、`_broadcast` 中的 `uapi_text_mode` 分支

#### main.py（44 行变更）

- **`cmd_push_all` 重写**：按 `task_id` 分支处理
  - `task_id == "weather"` → `_render_html_to_image()` 渲染图片
  - `data.get("type") == "hotboard"` → `format_hotboard_text()` 文字
  - 其他 → 图片或文字 fallback
- import 增加 `format_hotboard_text`
- 帮助文本增加 `/u 指定城市推送` 说明
- 其他所有方法未改动

#### _conf_schema.json（4 行变更）

- `schedule_tasks` 描述：`结果合并到一张图` → `天气=图片，其他=文字，合并转发`
- hint：`weather(天气)` → `weather(天气·图片)`

### 输出效果示例

合并转发聊天记录内容：

```
┌─ 🌤️ 今日天气 ─────────────────┐
│  [天气图卡图片]                  │
└────────────────────────────────┘

┌─ 哔哩哔哩热榜 ─────────────────┐
│ 📺 哔哩哔哩热榜                  │
│ ━━━━━━━━━━━━━━                  │
│ #1  标题一  🔥100万              │
│      UP: xxx                    │
│      🔗 https://...             │
│ #2  标题二  🔥80万               │
│ ...                             │
└────────────────────────────────┘

┌─ HelloGitHub 热榜 ─────────────┐
│ 🐙 HelloGitHub 热榜             │
│ ━━━━━━━━━━━━━━                  │
│ #1  项目名                      │
│      [Python] owner/repo        │
│      🔗 https://...             │
│ ...                             │
└────────────────────────────────┘

┌─ 📰 每日新闻 ──────────────────┐
│  [新闻图片]                      │
└────────────────────────────────┘
```

### 保留的全部功能

- ✅ `/u 天气 <城市>` — 正常
- ✅ `/u 热榜 <平台>` — 正常（单平台仍走 html_render 图片模式）
- ✅ `/u 当天全部热榜` — weather=图片，其他=文字，合并转发
- ✅ `/u 指定城市推送 <城市>` — 正常
- ✅ 定时推送 — 输出格式与 `/u 当天全部热榜` 一致
- ✅ `push_all_enabled` — 控制定时推送开关
- ✅ `schedule_city` — 定时推送默认城市
- ✅ `schedule_time` 多时间点
- ✅ `schedule_groups` / `schedule_users` 多目标推送
- ✅ `uapi_text_mode` — 单条指令仍可用
- ✅ `llm_tools_enabled` — 不受影响
- ✅ 所有 `/u` 单条指令 — 不受影响

---

## Bug 修复日志（2026-06-23 第二轮）

### Bug 1: acfun/网易云/QQ音乐/微信读书 获取失败

**现象**：配置全部任务后，只有 bili、github、weather、news 能正常推送，acfun、netease_music、qq_music、weread 静默失败。

**根因**：`hotboard/fetcher.py` 的 `PLATFORM_MAP` 的 key 是中文别名：
```
"bili" | "a站" | "github" | "网易云" | "qq音乐" | "微信读书"
```
但 `_fetch_single_task` 把 task_id 原样传给 `fetch()`：
```
"bili" | "acfun" | "github" | "netease_music" | "qq_music" | "weread"
```
只有 `"bili"` 和 `"github"` 碰巧中英文一致能匹配上，其余全部命中 `alias not in PLATFORM_MAP` 返回错误。

**修复**：新增 `_HOTBOARD_ALIAS_MAP` 映射表（scheduler.py）：
```python
_HOTBOARD_ALIAS_MAP = {
    "bili":           "bili",
    "acfun":          "a站",
    "github":         "github",
    "netease_music":  "网易云",
    "qq_music":       "qq音乐",
    "weread":         "微信读书",
}
```
`_fetch_single_task` 调用 `fetch()` 前先查映射转换别名。

### Bug 2: 音乐热榜输出格式优化

**用户要求**：音乐热榜不要专辑封面、不要🔥热度值、不要时长，只保留歌名 + 歌手 + 链接。

**修复**（`format_hotboard_text`，scheduler.py）：
- 去掉 `duration_text`（时长）显示
- 音乐平台（netease-music, qq-music）跳过 `🔥热度值`

**音乐输出格式**：
```
🎵 网易云音乐热歌榜
━━━━━━━━━━━━━━
#1  歌名
     歌手名
     🔗 https://...
━━━━━━━━━━━━━━
Powered by UApiPro
```

### 优化: 交互提示改进

- 旧：推送完毕后输出 `📬 已推送全部热榜（合并转发）`
- 新：在获取数据前先输出 `🔍 正在搜寻热榜喵！`，推送完毕后不输出确认消息
- 用户体验：发指令 → 立即看到喵提示 → 等待数据 → 收到合并转发 → 干净利落

### 涉及文件

| 文件 | 改动 |
|------|------|
| scheduler.py | +`_HOTBOARD_ALIAS_MAP`，`_fetch_single_task` 别名转换，`format_hotboard_text` 音乐精简 |
| main.py | `cmd_push_all` 加 `🔍正在搜寻热榜喵！`，去 `📬已推送` 确认 |
