"""
Web Dashboard Application for Grid Trader

提供基于 Flask 的 Web 界面来控制 Grid Trader 服务
"""

import logging
import os
from pathlib import Path
from threading import Thread

from flask import Flask, render_template, jsonify, request, redirect, url_for

logger = logging.getLogger("GridTrader.WebDashboard")


class WebDashboard:
    """
    Web 仪表盘应用
    
    提供 HTML 界面来管理策略、查看账户和持仓
    """
    
    def __init__(
        self,
        main_engine,
        event_engine,
        host: str = "0.0.0.0",
        port: int = 8080
    ):
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.host = host
        self.port = port
        
        base_dir = Path(__file__).parent
        template_dir = base_dir / 'templates'
        static_dir = base_dir / 'static'
        
        self.app = Flask(
            __name__,
            template_folder=str(template_dir),
            static_folder=str(static_dir)
        )
        
        self._setup_routes()
        self._running = False
        self._server_thread = None
        self._recent_logs = []

    def _get_recent_logs(self, limit: int = 50):
        """获取最近的日志"""
        return self._recent_logs[-limit:]

    def _setup_routes(self):
        """设置路由"""
        app = self.app
        
        @app.route('/')
        def index():
            """首页 - 重定向到仪表盘"""
            return redirect(url_for('dashboard'))
        
        @app.route('/dashboard')
        def dashboard():
            """仪表盘页面"""
            return render_template('dashboard.html')
        
        @app.route('/api/status')
        def api_status():
            """获取服务状态"""
            cta_engine = self.main_engine.get_engine('strategy')
            strategies = []
            for name, strategy in cta_engine.strategies.items():
                data = strategy.get_data()
                strategies.append(data)

            accounts = []
            for acc in self.main_engine.get_all_accounts():
                accounts.append({
                    'accountid': acc.accountid,
                    'gateway': acc.gateway_name,
                    'balance': acc.balance,
                    'frozen': acc.frozen
                })

            positions = []
            for pos in self.main_engine.get_all_positions():
                positions.append({
                    'symbol': pos.symbol,
                    'gateway': pos.gateway_name,
                    'direction': str(pos.direction),
                    'volume': pos.volume,
                    'price': getattr(pos, 'price', 0)
                })

            return jsonify({
                'strategies': strategies,
                'accounts': accounts,
                'positions': positions
            })
        
        @app.route('/api/strategies')
        def api_list_strategies():
            """获取策略列表"""
            cta_engine = self.main_engine.get_engine('strategy')
            strategies = []
            for name, strategy in cta_engine.strategies.items():
                strategies.append(strategy.get_data())
            return jsonify({'strategies': strategies})
        
        @app.route('/api/strategies', methods=['POST'])
        def api_add_strategy():
            """添加策略"""
            data = request.json
            cta_engine = self.main_engine.get_engine('strategy')
            
            class_name = data.get('class_name')
            strategy_name = data.get('strategy_name')
            vt_symbol = data.get('vt_symbol')
            setting = data.get('setting', {})
            
            if '.BINANCE' not in vt_symbol:
                vt_symbol = vt_symbol + '.BINANCE'
            
            cta_engine.add_strategy(class_name, strategy_name, vt_symbol, setting)
            
            return jsonify({'success': True, 'strategy_name': strategy_name})
        
        @app.route('/api/strategies/<strategy_name>/init', methods=['POST'])
        def api_init_strategy(strategy_name):
            """初始化策略"""
            cta_engine = self.main_engine.get_engine('strategy')
            cta_engine.init_strategy(strategy_name)
            return jsonify({'success': True})
        
        @app.route('/api/strategies/<strategy_name>/start', methods=['POST'])
        def api_start_strategy(strategy_name):
            """启动策略"""
            cta_engine = self.main_engine.get_engine('strategy')
            cta_engine.start_strategy(strategy_name)
            return jsonify({'success': True})
        
        @app.route('/api/strategies/<strategy_name>/stop', methods=['POST'])
        def api_stop_strategy(strategy_name):
            """停止策略"""
            cta_engine = self.main_engine.get_engine('strategy')
            cta_engine.stop_strategy(strategy_name)
            return jsonify({'success': True})
        
        @app.route('/api/strategies/<strategy_name>', methods=['DELETE'])
        def api_remove_strategy(strategy_name):
            """删除策略"""
            cta_engine = self.main_engine.get_engine('strategy')
            result = cta_engine.remove_strategy(strategy_name)
            return jsonify({'success': result})
        
        @app.route('/api/strategies/<strategy_name>', methods=['PUT'])
        def api_edit_strategy(strategy_name):
            """修改策略参数"""
            data = request.json
            cta_engine = self.main_engine.get_engine('strategy')
            cta_engine.edit_strategy(strategy_name, data.get('setting', {}))
            return jsonify({'success': True})
        
        @app.route('/api/strategy-classes')
        def api_strategy_classes():
            """获取策略类型"""
            cta_engine = self.main_engine.get_engine('strategy')
            classes = cta_engine.get_all_strategy_class_names()
            result = []
            for class_name in classes:
                params = cta_engine.get_strategy_class_parameters(class_name)
                result.append({
                    'class_name': class_name,
                    'parameters': params
                })
            return jsonify({'classes': result})
        
        @app.route('/api/accounts')
        def api_accounts():
            """获取账户"""
            accounts = self.main_engine.get_all_accounts()
            return jsonify({
                'accounts': [
                    {
                        'accountid': acc.accountid,
                        'gateway': acc.gateway_name,
                        'balance': acc.balance,
                        'frozen': acc.frozen
                    }
                    for acc in accounts
                ]
            })
        
        @app.route('/api/gateways')
        def api_gateways():
            """获取所有网关及其默认设置"""
            gateways = []
            for name in self.main_engine.get_all_gateway_names():
                gateway = self.main_engine.get_gateway(name)
                default_setting = self.main_engine.get_default_setting(name)
                gateways.append({
                    'name': name,
                    'connected': gateway.connected if hasattr(gateway, 'connected') else False,
                    'default_setting': default_setting or {}
                })
            return jsonify({'gateways': gateways})
        
        @app.route('/api/gateways/<gateway_name>/connect', methods=['POST'])
        def api_connect_gateway(gateway_name):
            """连接网关"""
            data = request.json
            self.main_engine.connect(data, gateway_name)
            return jsonify({'success': True, 'gateway': gateway_name})
        
        @app.route('/api/positions')
        def api_positions():
            """获取持仓"""
            positions = self.main_engine.get_all_positions()
            return jsonify({
                'positions': [
                    {
                        'symbol': pos.symbol,
                        'gateway': pos.gateway_name,
                        'direction': str(pos.direction),
                        'volume': pos.volume,
                        'price': getattr(pos, 'price', 0)
                    }
                    for pos in positions
                ]
            })
        
        @app.route('/api/orders')
        def api_orders():
            """获取活动订单"""
            orders = self.main_engine.get_all_active_orders()
            return jsonify({
                'orders': [
                    {
                        'vt_orderid': order.vt_orderid,
                        'symbol': order.symbol,
                        'gateway': order.gateway_name,
                        'direction': str(order.direction),
                        'price': float(order.price),
                        'volume': float(order.volume),
                        'traded': float(order.traded),
                        'status': str(order.status)
                    }
                    for order in orders
                ]
            })

        @app.route('/api/orders/<vt_orderid>/cancel', methods=['POST'])
        def api_cancel_order(vt_orderid):
            """撤销订单"""
            order = self.main_engine.get_active_order(vt_orderid)
            if not order:
                return jsonify({'success': False, 'message': 'Order not found'})
            req = order.create_cancel_request()
            self.main_engine.cancel_order(req, order.gateway_name)
            return jsonify({'success': True})

        @app.route('/api/logs')
        def api_logs():
            """获取日志"""
            limit = request.args.get('limit', 50, type=int)
            limit = min(limit, 200)

            # 从 LogEngine 获取日志
            log_engine = self.main_engine.get_engine('log')
            logs = []
            if log_engine:
                logs = log_engine.get_recent_logs(limit)
            else:
                logs = self._get_recent_logs(limit)

            return jsonify({'logs': logs})
    
    def start(self):
        """启动 Web 服务"""
        if self._running:
            logger.warning("Web Dashboard is already running")
            return
        
        self._running = True
        
        def run_server():
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        
        self._server_thread = Thread(target=run_server, daemon=True)
        self._server_thread.start()
        
        logger.info(f"Web Dashboard started on http://{self.host}:{self.port}")
    
    def stop(self):
        """停止 Web 服务"""
        if not self._running:
            return
        
        self._running = False
        logger.info("Web Dashboard stopped")
