# QueQiao MCDR

<p align="center">
  <strong>鹊桥 V2 协议对接 MCDReforged 插件</strong><br>
  <em>A MCDReforged plugin bridging the QueQiao V2 protocol</em>
</p>
<p align="center">
  <a href="https://github.com/Minecraft-UniBot/QueQiao.MCDReforged/releases"><img alt="Version" src="https://img.shields.io/badge/version-1.0.0-blue"></a>
  <a href="https://docs.mcdreforged.com/"><img alt="MCDR" src="https://img.shields.io/badge/MCDReforged-%3E%3D2.15.0-orange"></a>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-%3E%3D3.12-green"></a>
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-lightgrey"></a>
</p>

> 基于 MCDReforged 的鹊桥 V2 协议端，支持**正向 WebSocket（客户端）**与**反向 WebSocket（服务端）**两种连接方式，实现 Minecraft 服务端与外部系统（如 NoneBot / 鹊桥服务端）的实时消息互通。
>
> A QueQiao V2 protocol endpoint based on MCDReforged, supporting both **forward WebSocket (client)** and **reverse WebSocket (server)** connection modes for real-time message exchange between a Minecraft server and external systems (e.g. NoneBot / QueQiao server).

## ✨ 功能特性

### 连接能力
- 🔌 **双模式 WebSocket**：客户端模式主动连接鹊桥服务端；服务端模式被动等待鹊桥客户端接入
- 🔁 **自动重连**（客户端模式）：可配置重连间隔与最大重试次数
- 🔥 **热重载**：`!!queqiao reload` 重载配置并复用旧连接，无需重启服务器

### API 处理（鹊桥 → MCDR）
| API | 说明 |
|-----|------|
| `broadcast` | 广播消息到游戏 |
| `send_private_msg` | 发送私聊消息给指定玩家 |
| `send_title` | 发送标题/副标题（可配置淡入/停留/淡出时长） |
| `send_actionbar` | 发送 ActionBar 消息 |
| `send_rcon_command` | 执行 RCON 命令并返回结果 |
| `get_status` | 查询服务器状态（CPU/内存/玩家/MOTD 等） |

### 游戏事件转发（MCDR → 鹊桥）
| 事件 | 来源 |
|------|------|
| 玩家加入 / 退出 | MCDR 内置事件 |
| 玩家聊天 / 命令 | MCDR `USER_INFO` 事件 |
| 玩家死亡 | [MoreGameEvents](https://mcdreforged.com/zh-CN/plugin/mg_events) `PlayerDeathEvent` |
| 玩家成就 | [MoreGameEvents](https://mcdreforged.com/zh-CN/plugin/mg_events) `PlayerAdvancementEvent` |

## 📦 安装

### 方式一：直接下载 .mcdr 包
从 [Releases](https://github.com/Minecraft-UniBot/QueQiao.MCDReforged/releases) 下载 `queqiao-vX.X.X.mcdr`，放入 MCDR 的 `plugins/` 目录即可。

### 方式二：源码安装
```bash
git clone https://github.com/Minecraft-UniBot/QueQiao.MCDReforged.git
cd MCDReforged
uv sync
```
将整个目录作为 Directory Plugin 放入 MCDR 插件目录，或自行打包：
```bash
uv run python -m mcdreforged pack
```

## 🔧 配置

首次加载会在 `config/queqiao/config.json` 生成默认配置：

```json
{
  "server_name": "MCDR",
  "access_token": "",
  "client_origin": "mcdr",
  "minecraft": {
    "host": "",
    "port": 0
  },
  "client": {
    "enable": false,
    "url": "ws://127.0.0.1:8080/minecraft/ws",
    "reconnect_interval": 5,
    "reconnect_max_times": 0
  },
  "server": {
    "enable": false,
    "host": "0.0.0.0",
    "port": 8080
  },
  "log_events": true
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `server_name` | 本服务器名称，用于 Header `x-self-name` 与事件标识 |
| `access_token` | 鉴权 Token，留空则不发送 `Authorization` 头 |
| `client_origin` | 客户端来源标识，默认 `mcdr` |
| `minecraft.host` / `minecraft.port` | MC 服务器地址，用于 Server List Ping。留空则自动从 MCDR 解析，解析不到时回退 `127.0.0.1:25565` |
| `client.enable` | 启用客户端模式 |
| `client.url` | 鹊桥服务端 WebSocket 地址 |
| `client.reconnect_interval` | 重连间隔（秒） |
| `client.reconnect_max_times` | 最大重连次数，`0` 表示无限重试 |
| `server.enable` | 启用服务端模式 |
| `server.host` / `server.port` | WebSocket 服务端监听地址 |
| `log_events` | 是否在日志中打印事件转发记录 |

### 客户端模式
将 `client.enable` 设为 `true`，填写鹊桥服务端的 WebSocket 地址。需与鹊桥 `config.yml` 中的 `websocket_server` 配置对应。

### 服务端模式
将 `server.enable` 设为 `true`，插件将启动 WebSocket 服务端。需在鹊桥 `config.yml` 的 `websocket_client.url_list` 中填写本插件的监听地址。

## 🎮 命令

| 命令 | 权限 | 说明 |
|------|------|------|
| `!!queqiao` | 2 | 显示帮助 |
| `!!queqiao status` | 2 | 查看连接状态（模式、玩家、CPU、内存、MOTD 等） |
| `!!queqiao reload` | 2 | 重载配置并重新连接 |

## 📋 依赖

### 运行环境
- **MCDReforged** >= 2.15.0
- **Python** >= 3.12

### Python 包
- `websockets` >= 16.0
- `PyYAML` >= 6.0
- `psutil` >= 5.9

### MCDR 插件依赖
| 插件 | 用途 | 必需 |
|------|------|------|
| [MoreGameEvents](https://mcdreforged.com/zh-CN/plugin/mg_events) | 玩家死亡、成就事件 | ✅ |
| [Minecraft Data API](https://mcdreforged.com/zh-CN/plugin/minecraft_data_api) | 玩家坐标、生命值、经验等级 | ✅ |
| [online_player_api](https://mcdreforged.com/zh-CN/plugin/online_player_api) | 在线玩家列表 | ⚠️ 可选（缺失时回退 MCDR 内置接口） |

## 📁 项目结构

```
MCDReforged/
├── queqiao/
│   ├── __init__.py        # 插件入口、命令注册、生命周期管理
│   ├── config.py          # 配置加载与默认配置
│   ├── websocket.py       # WebSocket 连接管理（客户端/服务端）
│   ├── handler.py         # 鹊桥 API 请求处理（WS → MCDR）
│   ├── events.py          # 游戏事件转发（MCDR → WS）
│   ├── schema.py          # QueQiao V2 协议事件结构构建
│   ├── status.py          # 服务器状态采集（CPU/内存/玩家）
│   └── server_ping.py     # MC Server List Ping 协议实现
├── lang/                  # 多语言文件
│   ├── en_us.json
│   └── zh_cn.json
├── mcdreforged.plugin.json  # MCDR 插件元数据
├── pyproject.toml           # Python 项目配置
└── requirements.txt         # 依赖声明
```

## 🛠️ 开发

本项目使用 [uv](https://github.com/astral-sh/uv) 作为包管理器：

```bash
# 安装依赖
uv sync

# 打包 .mcdr
uv run python -m mcdreforged pack

# 运行测试 / 调试
uv run python -c "import queqiao"
```

## 📚 对接

- [UniBot](https://github.com/MineJPGcraft/UniBot) — Minecraft 跨平台机器人，本插件为其 MCDR 端实现
- [nonebot-adapter-minecraft](https://github.com/17TheWord/nonebot-adapter-minecraft) — NoneBot 的 Minecraft 适配器，通过鹊桥协议与本插件互通
- [鹊桥项目](https://github.com/17TheWord/QueQiao) — 鹊桥协议官方实现

## 📄 License

[MIT](./LICENSE)
