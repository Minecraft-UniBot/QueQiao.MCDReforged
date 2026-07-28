'''
QueQiao MCDR 插件 - 服务器状态采集
基于 psutil 获取 Minecraft 服务器进程的 CPU 和内存占用
'''
import psutil

from mcdreforged.api.all import PluginServerInterface


def _get_server_processes(server: PluginServerInterface):
	'''获取服务器进程及其所有子进程（JVM 通常是 bash 的子进程）'''
	pids = server.get_server_pid_all()
	procs = []
	for pid in pids:
		try:
			procs.append(psutil.Process(pid))
		except (psutil.NoSuchProcess, psutil.AccessDenied):
			continue
	return procs


def get_memory_info(server: PluginServerInterface):
	'''返回 (rss_mb, vms_mb)，获取失败返回 (None, None)'''
	procs = _get_server_processes(server)
	if not procs:
		return None, None
	rss = 0.0
	vms = 0.0
	for p in procs:
		try:
			mem = p.memory_info()
			rss += mem.rss or 0
			vms += mem.vms or 0
		except (psutil.NoSuchProcess, psutil.AccessDenied):
			continue
	# 字节 -> MB
	rss_mb = rss / (1024 * 1024)
	vms_mb = vms / (1024 * 1024)
	return rss_mb, vms_mb


def get_cpu_percent(server: PluginServerInterface, interval: float = 0.0):
	'''
	返回服务器进程总 CPU 占用率（百分比，按逻辑核心数归一化）。
	获取失败返回 None。
	'''
	procs = _get_server_processes(server)
	if not procs:
		return None
	total = 0.0
	for p in procs:
		try:
			total += p.cpu_percent(interval=interval)
		except (psutil.NoSuchProcess, psutil.AccessDenied):
			continue
	return total
