# Gamedata

读取 Steam 官方 Web API，生成本地个人游戏库快照，为后续热门游戏筛选、未玩游戏识别和个性化推荐提供稳定数据源。

当前版本只负责**确定性数据采集**，不包含推荐算法、Agent、数据库、SteamDB 爬虫或 MCP 服务。

## 能力

- 读取完整 Steam 游戏库
- 读取总游玩时长
- 读取最近两周游玩时长
- 读取最后游玩时间
- 按时长生成基础游玩状态
- 提供指定 AppID 的成就读取接口
- 提供最近游玩游戏接口

## 目录

```text
Gamedata/
├── README.md
├── requirements.txt
├── .env.example
├── steam_client.py
└── collect.py
```

运行后会在本地生成：

```text
Gamedata/data/steam_library.json
```

`data/` 与 `.env` 不应提交到 GitHub。

## 前置条件

需要：

1. Steam Web API Key
2. SteamID64
3. Steam 隐私设置中的“游戏详情”允许 API 读取
4. Python 3.9+

不要把真实 API Key 写入代码或提交到 GitHub。

## 安装

```bash
cd Gamedata
python -m pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

Windows PowerShell 可使用：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`：

```env
STEAM_API_KEY=your_real_key
STEAM_ID64=your_real_steam_id64
```

## 采集游戏库

```bash
python collect.py
```

成功时会输出类似：

```text
Collected 253 games -> .../Gamedata/data/steam_library.json
```

JSON 结构：

```json
{
  "collected_at": "2026-08-31T12:00:00+00:00",
  "game_count": 253,
  "games": [
    {
      "appid": 292030,
      "name": "The Witcher 3: Wild Hunt",
      "playtime_hours": 158.7,
      "recent_hours": 0.0,
      "last_played": 1712345678,
      "status": "deeply_played"
    }
  ]
}
```

## 游玩状态

当前仅使用总时长做粗分类：

| 状态 | 条件 |
|---|---|
| `unplayed` | < 0.2 h |
| `barely_played` | < 2 h |
| `sampled` | < 10 h |
| `played` | < 40 h |
| `deeply_played` | >= 40 h |

这只是数据层标签，不代表最终推荐结论。后续如果真实使用证明阈值不合理，再调整。

## 指定游戏成就

不要默认遍历整个游戏库请求成就。成就接口按 AppID 单独请求，适合在需要分析某款游戏时惰性调用。

示例：

```python
from steam_client import SteamClient

client = SteamClient()
achievements = client.get_achievements(292030)

if achievements:
    unlocked = sum(item["achieved"] for item in achievements)
    total = len(achievements)
    print(unlocked, total)
```

## 最近游玩

```python
from steam_client import SteamClient

client = SteamClient()
recent = client.get_recent_games(count=20)
```

## 当前边界

本工具只解决：

```text
Steam 私人行为数据 -> 结构化本地快照
```

热门游戏、近期发售、Steam 商店评价、SteamDB 热度、Reddit 讨论等属于实时公共信息，优先由 Web 检索层处理，不在本工具内重复建设爬虫。

后续只有在真实工作流需要时，再考虑将这些函数暴露为 MCP/API 工具。
