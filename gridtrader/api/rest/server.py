"""
REST API Server with WebSocket Support for Grid Trader
"""

import asyncio
import json
import logging
from threading import Thread
from typing import Dict, Set

from aiohttp import web
import aiohttp

from gridtrader.event import Event, EVENT_LOG, EVENT_CTA_STRATEGY, EVENT_ORDER, EVENT_TRADE, EVENT_ACCOUNT, EVENT_POSITION
from gridtrader.api.rest.handlers import (
    StrategyHandler,
    AccountHandler,
    LogHandler,
    GatewayHandler,
    SystemHandler
)

logger = logging.getLogger("GridTrader.ApiServer")


class WebSocketManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.clients: Set[web.WebSocketResponse] = set()
        self.lock = asyncio.Lock()
    
    async def broadcast(self, message: dict):
        """广播消息到所有客户端"""
        async with self.lock:
            disconnected = set()
            
            for client in self.clients:
                try:
                    await client.send_json(message)
                except Exception:
                    disconnected.add(client)
            
            # 清理断开的连接
            for client in disconnected:
                self.clients.discard(client)
    
    async def register(self, ws: web.WebSocketResponse):
        """注册新客户端"""
        async with self.lock:
            self.clients.add(ws)
    
    async def unregister(self, ws: web.WebSocketResponse):
        """取消注册客户端"""
        async with self.lock:
            self.clients.discard(ws)


class ApiServer:
    """
    REST API 服务器
    
    提供策略管理的 HTTP API 和 WebSocket 实时推送
    """
    
    def __init__(
        self,
        main_engine,
        event_engine,
        host: str = "0.0.0.0",
        port: int = 8765,
        ws_port: int = 8766
    ):
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.host = host
        self.port = port
        self.ws_port = ws_port
        
        self.app: web.Application = None
        self.runner: web.AppRunner = None
        self.ws_runner: web.AppRunner = None
        self.site: web.TCPSite = None
        self.ws_site: web.TCPSite = None
        
        self.ws_manager = WebSocketManager()
        
        # 初始化处理器
        cta_engine = main_engine.get_engine('strategy')
        self.strategy_handler = StrategyHandler(main_engine, cta_engine)
        self.account_handler = AccountHandler(main_engine)
        self.log_handler = LogHandler(event_engine)
        self.gateway_handler = GatewayHandler(main_engine)
        self.system_handler = SystemHandler(main_engine)
        
        self._running = False
        self._event_thread: Thread = None
    
    def _setup_routes(self):
        """设置路由"""
        app = self.app
        
        # CORS 中间件
        async def cors_middleware(app, handler):
            async def middleware_handler(request):
                if request.method == 'OPTIONS':
                    response = web.Response()
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                    return response
                
                response = await handler(request)
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
            return middleware_handler
        
        self.app.middlewares.append(cors_middleware)
        
        # === 系统路由 ===
        app.router.add_get('/api/health', self.system_handler.health_check)
        app.router.add_get('/api/strategy-classes', self.system_handler.get_strategy_classes)
        
        # === 策略路由 ===
        app.router.add_get('/api/strategies', self.strategy_handler.list_strategies)
        app.router.add_post('/api/strategies', self.strategy_handler.add_strategy)
        app.router.add_get('/api/strategies/{strategy_name}', self.strategy_handler.get_strategy)
        app.router.add_put('/api/strategies/{strategy_name}', self.strategy_handler.edit_strategy)
        app.router.add_delete('/api/strategies/{strategy_name}', self.strategy_handler.remove_strategy)
        app.router.add_post('/api/strategies/{strategy_name}/init', self.strategy_handler.init_strategy)
        app.router.add_post('/api/strategies/{strategy_name}/start', self.strategy_handler.start_strategy)
        app.router.add_post('/api/strategies/{strategy_name}/stop', self.strategy_handler.stop_strategy)
        
        # === 账户路由 ===
        app.router.add_get('/api/accounts', self.account_handler.get_accounts)
        app.router.add_get('/api/positions', self.account_handler.get_positions)
        app.router.add_get('/api/orders', self.account_handler.get_orders)
        
        # === 日志路由 ===
        app.router.add_get('/api/logs', self.log_handler.get_logs)
        
        # === 网关路由 ===
        app.router.add_post('/api/gateways/{gateway_name}/connect', self.gateway_handler.connect_gateway)
        app.router.add_get('/api/gateways/{gateway_name}/status', self.gateway_handler.get_gateway_status)
        
        # === WebSocket 路由 ===
        app.router.add_get('/ws', self._handle_websocket)
        
        # === 前端路由 (SPA) ===
        app.router.add_get('/', self._serve_index)
        app.router.add_get('/dashboard', self._serve_dashboard)
        app.router.add_static('/static', 'gridtrader/web/static', show_index=True)
    
    async def _serve_index(self, request: web.Request) -> web.Response:
        """服务前端页面"""
        return web.FileResponse('gridtrader/web/templates/index.html')
    
    async def _serve_dashboard(self, request: web.Request) -> web.Response:
        """服务仪表盘页面"""
        return web.FileResponse('gridtrader/web/templates/dashboard.html')
    
    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """处理 WebSocket 连接"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        await self.ws_manager.register(ws)
        logger.info(f"WebSocket client connected. Total clients: {len(self.ws_manager.clients)}")
        
        try:
            # 发送欢迎消息
            await ws.send_json({
                "type": "connected",
                "message": "Connected to GridTrader WebSocket"
            })
            
            # 持续处理消息
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_ws_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_json({
                            "type": "error",
                            "message": "Invalid JSON"
                        })
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
        finally:
            await self.ws_manager.unregister(ws)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.ws_manager.clients)}")
        
        return ws
    
    async def _handle_ws_message(self, ws: web.WebSocketResponse, data: dict):
        """处理 WebSocket 消息"""
        msg_type = data.get('type')
        
        if msg_type == 'ping':
            await ws.send_json({"type": "pong"})
        elif msg_type == 'subscribe':
            # 订阅特定事件
            await ws.send_json({
                "type": "subscribed",
                "channels": data.get('channels', [])
            })
    
    def _forward_events(self):
        """在独立线程中转发事件到 WebSocket"""
        import time
        from gridtrader.trader.object import LogData
        
        def event_processor():
            while self._running:
                time.sleep(0.1)  # 避免过度占用 CPU
        
        self._event_thread = Thread(target=event_processor, daemon=True)
        self._event_thread.start()
    
    def _on_log_event(self, event: Event):
        """处理日志事件"""
        asyncio.create_task(self.ws_manager.broadcast({
            "type": "log",
            "data": {
                "msg": event.data.msg,
                "level": event.data.level,
                "gateway": event.data.gateway_name,
                "time": str(event.data.datetime) if hasattr(event.data, 'datetime') else None
            }
        }))
    
    def _on_strategy_event(self, event: Event):
        """处理策略状态事件"""
        asyncio.create_task(self.ws_manager.broadcast({
            "type": "strategy_update",
            "data": event.data
        }))
    
    def _on_order_event(self, event: Event):
        """处理订单事件"""
        order = event.data
        asyncio.create_task(self.ws_manager.broadcast({
            "type": "order_update",
            "data": {
                "vt_orderid": order.vt_orderid,
                "symbol": order.symbol,
                "status": str(order.status),
                "traded": float(order.traded),
                "volume": float(order.volume)
            }
        }))
    
    def _on_trade_event(self, event: Event):
        """处理成交事件"""
        trade = event.data
        asyncio.create_task(self.ws_manager.broadcast({
            "type": "trade",
            "data": {
                "vt_tradeid": trade.vt_tradeid,
                "symbol": trade.symbol,
                "direction": str(trade.direction),
                "volume": float(trade.volume),
                "price": float(trade.price)
            }
        }))
    
    def _on_account_event(self, event: Event):
        """处理账户事件"""
        account = event.data
        asyncio.create_task(self.ws_manager.broadcast({
            "type": "account_update",
            "data": {
                "accountid": account.accountid,
                "balance": float(account.balance),
                "frozen": float(account.frozen)
            }
        }))
    
    def _on_position_event(self, event: Event):
        """处理持仓事件"""
        position = event.data
        asyncio.create_task(self.ws_manager.broadcast({
            "type": "position_update",
            "data": {
                "symbol": position.symbol,
                "direction": str(position.direction),
                "volume": float(position.volume),
                "price": float(position.price) if hasattr(position, 'price') else 0
            }
        }))
    
    def start(self):
        """启动 API 服务器"""
        if self._running:
            logger.warning("API Server is already running")
            return
        
        self._running = True
        
        # 创建 aiohttp 应用
        self.app = web.Application()
        self._setup_routes()
        
        # 创建 runner
        self.runner = web.AppRunner(self.app)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.runner.setup())
        self.site = web.TCPSite(self.runner, self.host, self.port)
        loop.run_until_complete(self.site.start())
        
        logger.info(f"REST API Server started on http://{self.host}:{self.port}")
        
        # 在事件引擎中注册处理器
        self.event_engine.register(EVENT_LOG, self._on_log_event)
        self.event_engine.register(EVENT_CTA_STRATEGY, self._on_strategy_event)
        self.event_engine.register(EVENT_ORDER, self._on_order_event)
        self.event_engine.register(EVENT_TRADE, self._on_trade_event)
        self.event_engine.register(EVENT_ACCOUNT, self._on_account_event)
        self.event_engine.register(EVENT_POSITION, self._on_position_event)
        
        # 在独立线程中运行 asyncio 事件循环
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        self._loop_thread = Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        logger.info("WebSocket manager started")
    
    def stop(self):
        """停止 API 服务器"""
        if not self._running:
            return
        
        self._running = False
        
        # 注销事件处理器
        self.event_engine.unregister(EVENT_LOG, self._on_log_event)
        self.event_engine.unregister(EVENT_CTA_STRATEGY, self._on_strategy_event)
        self.event_engine.unregister(EVENT_ORDER, self._on_order_event)
        self.event_engine.unregister(EVENT_TRADE, self._on_trade_event)
        self.event_engine.unregister(EVENT_ACCOUNT, self._on_account_event)
        self.event_engine.unregister(EVENT_POSITION, self._on_position_event)
        
        # 清理
        if hasattr(self, '_loop_thread'):
            self._loop_thread.join(timeout=2)
        
        if self.runner:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.runner.cleanup())
            except Exception as e:
                logger.error(f"Error stopping API server: {e}")
        
        logger.info("API Server stopped")
