'''
QueQiao MCDR 插件 - WebSocket 连接管理器
支持客户端模式和服务端模式

数据流：
- MCDR → WS：游戏事件（玩家聊天、加入、退出、死亡、成就等）
- WS → MCDR：API 请求（broadcast、send_private_msg 等）
- MCDR → WS：API 响应（post_type: 'response'）
'''
import asyncio
import json
import threading
from typing import Optional, Callable

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.server import ServerConnection, serve

from mcdreforged.api.all import PluginServerInterface

from queqiao.config import Config


class QueQiaoConnection:
	'''
	鹊桥 WebSocket 连接管理器
	- 客户端模式：作为 WebSocket 客户端连接到鹊桥服务端
	- 服务端模式：作为 WebSocket 服务端等待鹊桥客户端连接
	'''

	def __init__(self, server: PluginServerInterface, config: Config):
		self.server = server
		self.config = config
		self._loop: Optional[asyncio.AbstractEventLoop] = None
		self._thread: Optional[threading.Thread] = None
		self._running = False
		self._main_tasks: list[asyncio.Task] = []

		# 客户端模式
		self._client_ws: Optional[ClientConnection] = None
		self._client_connected = False

		# 服务端模式
		self._ws_server = None
		self._server_clients: dict[str, ServerConnection] = {}

		# 收到 API 请求时的回调，返回响应 dict
		self.on_api_request: Optional[Callable[[dict], dict]] = None

	def _build_headers(self) -> dict:
		'''构建 WebSocket 连接头'''
		headers = {
			'x-self-name': self.config.server_name,
			'x-client-origin': self.config.client_origin,
		}
		if self.config.access_token:
			headers['Authorization'] = f'Bearer {self.config.access_token}'
		return headers

	# ==================== 生命周期 ====================

	def start(self):
		'''启动连接管理器'''
		if self._running:
			return
		self._running = True
		self._thread = threading.Thread(target=self._run_loop, name='QueQiao-WS', daemon=True)
		self._thread.start()

	def stop(self):
		'''停止连接管理器'''
		self._running = False
		if self._loop and self._loop.is_running():
			self._loop.call_soon_threadsafe(self._cancel_all_tasks)
		if self._thread and self._thread.is_alive():
			self._thread.join(timeout=5)
		self._client_connected = False
		self._client_ws = None
		self._server_clients.clear()

	def _cancel_all_tasks(self):
		'''在事件循环线程中取消所有任务'''
		for task in self._main_tasks:
			if not task.done():
				task.cancel()

	def _run_loop(self):
		'''在独立线程中运行 asyncio 事件循环'''
		self._loop = asyncio.new_event_loop()
		asyncio.set_event_loop(self._loop)
		try:
			self._loop.run_until_complete(self._main())
		except Exception as e:
			self.server.logger.error(f'[QueQiao] 事件循环异常: {e}')
		finally:
			self._loop.close()
			self._loop = None

	async def _main(self):
		'''主协程：同时管理正向和反向连接'''
		self._main_tasks = []
		if self.config.client_enable:
			self._main_tasks.append(asyncio.create_task(self._client_loop()))
		if self.config.server_enable:
			self._main_tasks.append(asyncio.create_task(self._server_loop()))

		if not self._main_tasks:
			self.server.logger.warning('[QueQiao] 客户端和服务端模式均未启用')
			return

		await asyncio.gather(*self._main_tasks, return_exceptions=True)

	# ==================== 客户端模式 ====================

	async def _client_loop(self):
		'''客户端模式循环，支持自动重连'''
		reconnect_count = 0
		max_times = self.config.client_reconnect_max_times
		interval = self.config.client_reconnect_interval

		while self._running:
			try:
				headers = self._build_headers()
				self.server.logger.info(f'[QueQiao] 正在连接鹊桥服务端: {self.config.client_url}')
				async with websockets.connect(
					self.config.client_url,
					additional_headers=headers,
					ping_interval=30,
					ping_timeout=10,
				) as ws:
					self._client_ws = ws
					self._client_connected = True
					reconnect_count = 0
					self.server.logger.info(self.server.tr('queqiao_mcdr.connected', self.config.client_url))
					await self._handle_connection(ws)
			except asyncio.CancelledError:
				break
			except Exception as e:
				self._client_connected = False
				self._client_ws = None
				if not self._running:
					break
				reconnect_count += 1
				self.server.logger.warning(
					self.server.tr('queqiao_mcdr.connect_failed', str(e))
				)
				if max_times > 0 and reconnect_count >= max_times:
					self.server.logger.error(f'[QueQiao] 已达最大重连次数 ({max_times})，停止重连')
					break
				self.server.logger.info(f'[QueQiao] {interval} 秒后尝试重连... (第 {reconnect_count} 次)')
				await asyncio.sleep(interval)

		self._client_connected = False
		self._client_ws = None

	# ==================== 服务端模式 ====================

	async def _server_loop(self):
		'''服务端模式：启动 WebSocket 服务端'''
		host = self.config.server_host
		port = self.config.server_port
		self.server.logger.info(f'[QueQiao] WebSocket 服务端启动: {host}:{port}')

		try:
			async with serve(
				self._on_server_client,
				host,
				port,
			) as server:
				self._ws_server = server
				await asyncio.Future()  # 永远运行
		except asyncio.CancelledError:
			pass
		except Exception as e:
			self.server.logger.error(f'[QueQiao] WebSocket 服务端启动失败: {e}')
		finally:
			self._ws_server = None

	async def _on_server_client(self, ws: ServerConnection):
		'''处理服务端模式的客户端连接'''
		# 校验 Header
		request = ws.request
		headers = request.headers if request else {}

		self_name = headers.get('x-self-name', '')
		auth = headers.get('Authorization', '')
		origin = headers.get('x-client-origin', '')

		# 校验 server_name
		if self_name != self.config.server_name:
			self.server.logger.warning(
				f'[QueQiao] 客户端 server_name 不匹配: "{self_name}" != "{self.config.server_name}"，拒绝连接'
			)
			await ws.close(4001, 'server_name mismatch')
			return

		# 校验 access_token
		if self.config.access_token:
			expected = f'Bearer {self.config.access_token}'
			if auth != expected:
				self.server.logger.warning('[QueQiao] 客户端鉴权失败，拒绝连接')
				await ws.close(4003, 'authentication failed')
				return

		# 检查重复连接
		client_id = f'{origin or 'unknown'}_{ws.remote_address}'
		if origin and any(
			c.request.headers.get('x-client-origin') == origin
			for c in self._server_clients.values()
			if c.request
		):
			self.server.logger.warning(f'[QueQiao] 拒绝相同来源的重复连接: {origin}')
			await ws.close(4002, 'duplicate origin')
			return

		self._server_clients[client_id] = ws
		self.server.logger.info(
			self.server.tr('queqiao_mcdr.client_connected', client_id)
		)

		try:
			await self._handle_connection(ws)
		finally:
			self._server_clients.pop(client_id, None)
			self.server.logger.info(
				self.server.tr('queqiao_mcdr.client_disconnected', client_id)
			)

	# ==================== 消息处理 ====================

	async def _handle_connection(self, ws):
		'''处理 WebSocket 连接收到的消息'''
		async for raw in ws:
			try:
				data = json.loads(raw)

				if 'api' in data:
					# API 请求：鹊桥要求 MCDR 执行操作
					await self._handle_api_request(ws, data)
				else:
					self.server.logger.debug(f'[QueQiao] 未知消息: {data}')
			except json.JSONDecodeError:
				self.server.logger.warning(f'[QueQiao] 收到非 JSON 消息: {raw}')
			except Exception as e:
				self.server.logger.error(f'[QueQiao] 处理消息异常: {e}')

	async def _handle_api_request(self, ws, data: dict):
		'''处理 API 请求并返回响应'''
		api_name = data.get('api', 'unknown')
		echo = data.get('echo', '')

		if self.config.log_events:
			self.server.logger.info(f'[QueQiao] 收到 API 请求: {api_name}')

		if not self.on_api_request:
			resp = {
				'code': 500,
				'api': api_name,
				'post_type': 'response',
				'status': 'FAILED',
				'message': 'No API handler registered',
			}
			if echo:
				resp['echo'] = echo
		else:
			# 在线程池中执行 API（可能涉及阻塞操作如 rcon_query）
			loop = asyncio.get_running_loop()
			resp = await loop.run_in_executor(None, self.on_api_request, data)

		try:
			await ws.send(json.dumps(resp, ensure_ascii=False))
		except Exception as e:
			self.server.logger.error(f'[QueQiao] 发送 API 响应失败: {e}')

	# ==================== 事件发送（MCDR → WS） ====================

	def send_event(self, event_data: dict):
		'''线程安全：向所有 WebSocket 连接发送游戏事件'''
		if not self._loop or not self._running:
			return
		try:
			asyncio.run_coroutine_threadsafe(
				self._async_send_event(event_data),
				self._loop
			)
		except Exception as e:
			self.server.logger.error(f'[QueQiao] 发送事件异常: {e}')

	async def _async_send_event(self, event_data: dict):
		'''向所有 WebSocket 连接发送事件'''
		message = json.dumps(event_data, ensure_ascii=False)

		if self._client_ws and self._client_connected:
			try:
				await self._client_ws.send(message)
			except Exception as e:
				self.server.logger.warning(f'[QueQiao] 客户端连接发送事件失败: {e}')

		for cid, ws in list(self._server_clients.items()):
			try:
				await ws.send(message)
			except Exception:
				self._server_clients.pop(cid, None)

	# ==================== 状态 ====================

	@property
	def is_client_connected(self) -> bool:
		return self._client_connected

	@property
	def server_client_count(self) -> int:
		return len(self._server_clients)

	@property
	def is_connected(self) -> bool:
		'''是否有任何可用连接'''
		return self._client_connected or len(self._server_clients) > 0
