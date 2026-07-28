# QueQiao MCDR

鹊桥 V2 协议对接 MCDR 插件，支持**正向 WebSocket（客户端）**和**反向 WebSocket（服务端）**两种连接方式，实现 Minecraft 服务端与外部系统的实时消息互通。

## 功能

- ✅ 客户端模式：作为 WebSocket 客户端连接到鹊桥服务端
- ✅ 服务端模式：作为 WebSocket 服务端等待鹊桥客户端连入
- ✅ 自动重连（客户端模式）
- ✅ Header 鉴权校验（`x-self-name`、`Authorization`、`x-client-origin`）
- ✅ API 处理：接收鹊桥 API 请求并执行（广播、私聊、标题、ActionBar、RCON、状态查询）
- ✅ 游戏事件转发：监听 MCDR 内置事件和 MoreGameEvents 事件，发送到鹊桥
- ✅ 玩家数据丰富：通过 Minecraft Data API 获取坐标、维度、生命值
- ✅ MCDR 命令系统（`!!queqiao`）
- ✅ 热重载支持

## 依赖

- MCDReforged >= 2.15.0
- Python >= 3.12
- websockets >= 16.0
- PyYAML >= 6.0
- [MoreGameEvents](https://mcdreforged.com/zh-CN/plugin/mg_events)（游戏事件监听：死亡、成就）
- [Minecraft Data API](https://mcdreforged.com/zh-CN/plugin/minecraft_data_api)（玩家数据查询：坐标、维度、生命值）

## 安装

使用 uv 作为包管理器：

```bash
uv sync
```

将本目录作为 MCDR 的 Directory Plugin 放入插件目录，或使用 `python -m mcdreforged pack` 打包。

## 配置

首次加载会在 `config/queqiao_mcdr/config.json` 生成默认配置：

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

### Minecraft 服务器地址

`minecraft.host` / `minecraft.port` 用于 Server List Ping 获取 MOTD、最大玩家数等信息。留空则自动从 MCDR 解析的服务器信息获取，解析不到时回退 `127.0.0.1:25565`。若 MCDR 无法正确解析端口（如非标准端口），请手动填写。

### 客户端模式

将 `client.enable` 设为 `true`，填写鹊桥服务端的 WebSocket 地址。需与鹊桥 `config.yml` 中的 `websocket_server` 配置对应。

### 服务端模式

将 `server.enable` 设为 `true`，插件将启动 WebSocket 服务端。需在鹊桥 `config.yml` 的 `websocket_client.url_list` 中填写本插件的监听地址。

## 命令

| 命令 | 说明 |
|------|------|
| `!!queqiao` | 显示帮助 |
| `!!queqiao status` | 查看连接状态 |
| `!!queqiao reload` | 重载配置并重新连接 |

## 支持的 API（鹊桥 → MCDR）

| API | 说明 |
|-----|------|
| `broadcast` | 广播消息到游戏 |
| `send_private_msg` | 发送私聊消息给指定玩家 |
| `send_title` | 发送标题/副标题 |
| `send_actionbar` | 发送 ActionBar 消息 |
| `send_rcon_command` | 执行 RCON 命令 |
| `get_status` | 查询服务器状态 |

## 项目结构

```
queqiao_mcdr/
├── __init__.py          # 插件入口、命令注册
├── config.py            # 配置管理
├── websocket_manager.py # WebSocket 连接管理（客户端/服务端）
├── api_handler.py       # 处理鹊桥 API 请求（WS → MCDR）
└── game_events.py       # 游戏事件转发到鹊桥（MCDR → WS）
```

## 参考

- [鹊桥文档](https://github.com/17TheWord/QueQiao)
- [MCDReforged 文档](https://docs.mcdreforged.com/)
