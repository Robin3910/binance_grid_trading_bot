"""
REST API Handlers for Grid Trader Strategy Management
"""

import json
from typing import Dict, Any, List
from aiohttp import web

from gridtrader.event import Event, EVENT_LOG
from gridtrader.event.engine import EventEngine


class StrategyHandler:
    """策略管理 API 处理器"""
    
    def __init__(self, main_engine, cta_engine):
        self.main_engine = main_engine
        self.cta_engine = cta_engine
    
    async def list_strategies(self, request: web.Request) -> web.Response:
        """
        GET /api/strategies
        获取所有策略列表
        """
        strategies = []
        for name, strategy in self.cta_engine.strategies.items():
            strategies.append(strategy.get_data())
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {"strategies": strategies}
        })
    
    async def get_strategy(self, request: web.Request) -> web.Response:
        """
        GET /api/strategies/{strategy_name}
        获取指定策略详情
        """
        strategy_name = request.match_info['strategy_name']
        
        if strategy_name not in self.cta_engine.strategies:
            return web.json_response({
                "code": 404,
                "message": f"Strategy '{strategy_name}' not found"
            }, status=404)
        
        strategy = self.cta_engine.strategies[strategy_name]
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": strategy.get_data()
        })
    
    async def add_strategy(self, request: web.Request) -> web.Response:
        """
        POST /api/strategies
        添加新策略
        Body: {
            "class_name": "FuturesGridStrategy",
            "strategy_name": "my_strategy",
            "vt_symbol": "BTCUSDT.BINANCE",
            "setting": {...}
        }
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                "code": 400,
                "message": "Invalid JSON body"
            }, status=400)
        
        # 验证必需字段
        required = ['class_name', 'strategy_name', 'vt_symbol']
        for field in required:
            if field not in data:
                return web.json_response({
                    "code": 400,
                    "message": f"Missing required field: {field}"
                }, status=400)
        
        class_name = data['class_name']
        strategy_name = data['strategy_name']
        vt_symbol = data['vt_symbol']
        setting = data.get('setting', {})
        
        # 检查策略是否已存在
        if strategy_name in self.cta_engine.strategies:
            return web.json_response({
                "code": 409,
                "message": f"Strategy '{strategy_name}' already exists"
            }, status=409)
        
        # 确保 vt_symbol 格式正确
        if '.BINANCE' not in vt_symbol:
            vt_symbol = vt_symbol + '.BINANCE'
        
        # 添加策略
        self.cta_engine.add_strategy(class_name, strategy_name, vt_symbol, setting)
        
        return web.json_response({
            "code": 0,
            "message": "Strategy added successfully",
            "data": {"strategy_name": strategy_name}
        })
    
    async def init_strategy(self, request: web.Request) -> web.Response:
        """
        POST /api/strategies/{strategy_name}/init
        初始化策略
        """
        strategy_name = request.match_info['strategy_name']
        
        if strategy_name not in self.cta_engine.strategies:
            return web.json_response({
                "code": 404,
                "message": f"Strategy '{strategy_name}' not found"
            }, status=404)
        
        self.cta_engine.init_strategy(strategy_name)
        
        return web.json_response({
            "code": 0,
            "message": "Strategy initialized",
            "data": {"strategy_name": strategy_name}
        })
    
    async def start_strategy(self, request: web.Request) -> web.Response:
        """
        POST /api/strategies/{strategy_name}/start
        启动策略
        """
        strategy_name = request.match_info['strategy_name']
        
        if strategy_name not in self.cta_engine.strategies:
            return web.json_response({
                "code": 404,
                "message": f"Strategy '{strategy_name}' not found"
            }, status=404)
        
        strategy = self.cta_engine.strategies[strategy_name]
        
        if not strategy.inited:
            return web.json_response({
                "code": 400,
                "message": "Strategy must be initialized before starting"
            }, status=400)
        
        if strategy.trading:
            return web.json_response({
                "code": 400,
                "message": "Strategy is already trading"
            }, status=400)
        
        self.cta_engine.start_strategy(strategy_name)
        
        return web.json_response({
            "code": 0,
            "message": "Strategy started",
            "data": {"strategy_name": strategy_name}
        })
    
    async def stop_strategy(self, request: web.Request) -> web.Response:
        """
        POST /api/strategies/{strategy_name}/stop
        停止策略
        """
        strategy_name = request.match_info['strategy_name']
        
        if strategy_name not in self.cta_engine.strategies:
            return web.json_response({
                "code": 404,
                "message": f"Strategy '{strategy_name}' not found"
            }, status=404)
        
        strategy = self.cta_engine.strategies[strategy_name]
        
        if not strategy.trading:
            return web.json_response({
                "code": 400,
                "message": "Strategy is not trading"
            }, status=400)
        
        self.cta_engine.stop_strategy(strategy_name)
        
        return web.json_response({
            "code": 0,
            "message": "Strategy stopped",
            "data": {"strategy_name": strategy_name}
        })
    
    async def edit_strategy(self, request: web.Request) -> web.Response:
        """
        PUT /api/strategies/{strategy_name}
        修改策略参数
        """
        strategy_name = request.match_info['strategy_name']
        
        if strategy_name not in self.cta_engine.strategies:
            return web.json_response({
                "code": 404,
                "message": f"Strategy '{strategy_name}' not found"
            }, status=404)
        
        strategy = self.cta_engine.strategies[strategy_name]
        
        if strategy.trading:
            return web.json_response({
                "code": 400,
                "message": "Cannot edit strategy while trading"
            }, status=400)
        
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                "code": 400,
                "message": "Invalid JSON body"
            }, status=400)
        
        if 'setting' not in data:
            return web.json_response({
                "code": 400,
                "message": "Missing 'setting' field"
            }, status=400)
        
        self.cta_engine.edit_strategy(strategy_name, data['setting'])
        
        return web.json_response({
            "code": 0,
            "message": "Strategy updated",
            "data": {"strategy_name": strategy_name}
        })
    
    async def remove_strategy(self, request: web.Request) -> web.Response:
        """
        DELETE /api/strategies/{strategy_name}
        删除策略
        """
        strategy_name = request.match_info['strategy_name']
        
        if strategy_name not in self.cta_engine.strategies:
            return web.json_response({
                "code": 404,
                "message": f"Strategy '{strategy_name}' not found"
            }, status=404)
        
        strategy = self.cta_engine.strategies[strategy_name]
        
        if strategy.trading:
            return web.json_response({
                "code": 400,
                "message": "Cannot remove strategy while trading. Stop it first."
            }, status=400)
        
        result = self.cta_engine.remove_strategy(strategy_name)
        
        if result:
            return web.json_response({
                "code": 0,
                "message": "Strategy removed",
                "data": {"strategy_name": strategy_name}
            })
        else:
            return web.json_response({
                "code": 500,
                "message": "Failed to remove strategy"
            }, status=500)
    
    async def get_strategy_classes(self, request: web.Request) -> web.Response:
        """
        GET /api/strategy-classes
        获取可用的策略类型列表
        """
        classes = self.cta_engine.get_all_strategy_class_names()
        
        result = []
        for class_name in classes:
            params = self.cta_engine.get_strategy_class_parameters(class_name)
            result.append({
                "class_name": class_name,
                "parameters": params
            })
        
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {"classes": result}
        })


class AccountHandler:
    """账户信息 API 处理器"""
    
    def __init__(self, main_engine):
        self.main_engine = main_engine
    
    async def get_accounts(self, request: web.Request) -> web.Response:
        """
        GET /api/accounts
        获取所有账户信息
        """
        accounts = self.main_engine.get_all_accounts()
        account_list = []
        
        for account in accounts:
            account_list.append({
                "vt_accountid": account.vt_accountid,
                "accountid": account.accountid,
                "gateway_name": account.gateway_name,
                "balance": account.balance,
                "frozen": account.frozen,
                "available": account.available if hasattr(account, 'available') else account.balance - account.frozen
            })
        
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {"accounts": account_list}
        })
    
    async def get_positions(self, request: web.Request) -> web.Response:
        """
        GET /api/positions
        获取所有持仓信息
        """
        positions = self.main_engine.get_all_positions()
        position_list = []
        
        for position in positions:
            position_list.append({
                "vt_positionid": position.vt_positionid,
                "symbol": position.symbol,
                "gateway_name": position.gateway_name,
                "direction": str(position.direction),
                "volume": position.volume,
                "price": position.price,
                "pnl": position.pnl if hasattr(position, 'pnl') else 0,
                "yfee": position.yfee if hasattr(position, 'yfee') else 0
            })
        
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {"positions": position_list}
        })
    
    async def get_orders(self, request: web.Request) -> web.Response:
        """
        GET /api/orders
        获取活动订单
        """
        vt_symbol = request.query.get('symbol', '')
        orders = self.main_engine.get_all_active_orders(vt_symbol)
        
        order_list = []
        for order in orders:
            order_list.append({
                "vt_orderid": order.vt_orderid,
                "symbol": order.symbol,
                "gateway_name": order.gateway_name,
                "direction": str(order.direction),
                "offset": str(order.offset),
                "type": str(order.type),
                "price": float(order.price),
                "volume": float(order.volume),
                "traded": float(order.traded),
                "status": str(order.status),
                "datetime": order.datetime.isoformat() if order.datetime else None
            })
        
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {"orders": order_list}
        })


class LogHandler:
    """日志 API 处理器"""
    
    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine
        self.logs: List[Dict] = []
        self.max_logs = 1000
    
    async def get_logs(self, request: web.Request) -> web.Response:
        """
        GET /api/logs
        获取最近的日志
        """
        limit = int(request.query.get('limit', 100))
        limit = min(limit, 500)
        
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {
                "logs": self.logs[-limit:]
            }
        })
    
    def add_log(self, log_data: Any):
        """添加日志到缓冲区"""
        log_entry = {
            "time": log_data.gateway_name if hasattr(log_data, 'gateway_name') else 'system',
            "msg": log_data.msg,
            "level": log_data.level if hasattr(log_data, 'level') else 20,
            "timestamp": str(log_data.datetime) if hasattr(log_data, 'datetime') and log_data.datetime else None
        }
        self.logs.append(log_entry)
        
        # 限制日志数量
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]


class GatewayHandler:
    """网关管理 API 处理器"""
    
    def __init__(self, main_engine):
        self.main_engine = main_engine
    
    async def connect_gateway(self, request: web.Request) -> web.Response:
        """
        POST /api/gateways/{gateway_name}/connect
        连接网关
        """
        gateway_name = request.match_info['gateway_name']
        
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                "code": 400,
                "message": "Invalid JSON body"
            }, status=400)
        
        self.main_engine.connect(data, gateway_name)
        
        return web.json_response({
            "code": 0,
            "message": f"Connecting to {gateway_name}...",
            "data": {"gateway_name": gateway_name}
        })
    
    async def get_gateway_status(self, request: web.Request) -> web.Response:
        """
        GET /api/gateways/{gateway_name}/status
        获取网关状态
        """
        gateway_name = request.match_info['gateway_name']
        gateway = self.main_engine.get_gateway(gateway_name)
        
        if not gateway:
            return web.json_response({
                "code": 404,
                "message": f"Gateway '{gateway_name}' not found"
            }, status=404)
        
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {
                "gateway_name": gateway.gateway_name,
                "connected": gateway.connected if hasattr(gateway, 'connected') else False
            }
        })


class SystemHandler:
    """系统 API 处理器"""
    
    def __init__(self, main_engine):
        self.main_engine = main_engine
    
    async def health_check(self, request: web.Request) -> web.Response:
        """
        GET /api/health
        健康检查
        """
        return web.json_response({
            "code": 0,
            "message": "healthy",
            "data": {
                "status": "running",
                "strategies_count": len(self.main_engine.get_engine('strategy').strategies),
                "gateways": list(self.main_engine.gateways.keys())
            }
        })
    
    async def get_strategy_classes(self, request: web.Request) -> web.Response:
        """
        GET /api/strategy-classes
        获取所有策略类型
        """
        cta_engine = self.main_engine.get_engine('strategy')
        classes = cta_engine.get_all_strategy_class_names()
        
        result = []
        for class_name in classes:
            params = cta_engine.get_strategy_class_parameters(class_name)
            result.append({
                "class_name": class_name,
                "parameters": params
            })
        
        return web.json_response({
            "code": 0,
            "message": "success",
            "data": {"classes": result}
        })
