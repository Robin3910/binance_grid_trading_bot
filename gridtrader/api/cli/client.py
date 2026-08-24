"""
Grid Trader CLI Client

命令行客户端，用于通过 SSH 控制 Grid Trader 服务

Usage:
    gridtrader-cli --server http://localhost:8765 list
    gridtrader-cli --server http://localhost:8765 add --class FuturesGridStrategy ...
    gridtrader-cli --server http://localhost:8765 start MyStrategy
    gridtrader-cli --server http://localhost:8765 stop MyStrategy
"""

import argparse
import json
import sys
import os
from typing import Optional

import requests
from requests.exceptions import ConnectionError, Timeout

# 默认服务器地址
DEFAULT_SERVER = os.environ.get('GRIDTRADER_SERVER', 'http://localhost:8765')


class GridTraderCLI:
    """Grid Trader 命令行客户端"""
    
    def __init__(self, server_url: str = DEFAULT_SERVER, timeout: int = 30):
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[dict]:
        """发送 HTTP 请求"""
        url = f"{self.server_url}{endpoint}"
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except ConnectionError:
            print(f"Error: Cannot connect to {self.server_url}")
            print("Make sure the GridTrader service is running.")
            return None
        except requests.exceptions.Timeout:
            print(f"Error: Request timeout ({self.timeout}s)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return None
    
    def list_strategies(self):
        """列出所有策略"""
        result = self._request('GET', '/api/strategies')
        if not result:
            return False
        
        strategies = result.get('data', {}).get('strategies', [])
        
        if not strategies:
            print("No strategies found.")
            return True
        
        print(f"\n{'Strategy Name':<25} {'Symbol':<18} {'Class':<30} {'Status':<12}")
        print("-" * 90)
        
        for s in strategies:
            status = "🟢 Trading" if s['variables']['trading'] else "🔴 Stopped"
            inited = "✓" if s['variables']['inited'] else "✗"
            print(f"{s['strategy_name']:<25} {s['vt_symbol']:<18} {s['class_name']:<30} {status:<12} [init:{inited}]")
        
        print(f"\nTotal: {len(strategies)} strategies")
        return True
    
    def get_strategy(self, strategy_name: str):
        """获取策略详情"""
        result = self._request('GET', f'/api/strategies/{strategy_name}')
        if not result:
            return False
        
        data = result.get('data', {})
        
        print(f"\n{'='*50}")
        print(f"Strategy: {data['strategy_name']}")
        print(f"{'='*50}")
        print(f"Class:    {data['class_name']}")
        print(f"Symbol:   {data['vt_symbol']}")
        print(f"Status:   {'Trading' if data['variables']['trading'] else 'Stopped'}")
        print(f"Inited:   {'Yes' if data['variables']['inited'] else 'No'}")
        print(f"Position: {data['variables']['pos']}")
        print("\nParameters:")
        for k, v in data['parameters'].items():
            print(f"  {k}: {v}")
        print("\nVariables:")
        for k, v in data['variables'].items():
            print(f"  {k}: {v}")
        
        return True
    
    def add_strategy(self, class_name: str, strategy_name: str, vt_symbol: str, **params):
        """添加策略"""
        payload = {
            "class_name": class_name,
            "strategy_name": strategy_name,
            "vt_symbol": vt_symbol,
            "setting": params
        }
        
        result = self._request('POST', '/api/strategies', json=payload)
        if not result:
            return False
        
        print(f"✓ Strategy '{strategy_name}' added successfully")
        return True
    
    def init_strategy(self, strategy_name: str):
        """初始化策略"""
        result = self._request('POST', f'/api/strategies/{strategy_name}/init')
        if not result:
            return False
        
        print(f"✓ Strategy '{strategy_name}' initialization started")
        return True
    
    def start_strategy(self, strategy_name: str):
        """启动策略"""
        result = self._request('POST', f'/api/strategies/{strategy_name}/start')
        if not result:
            return False
        
        print(f"✓ Strategy '{strategy_name}' started")
        return True
    
    def stop_strategy(self, strategy_name: str):
        """停止策略"""
        result = self._request('POST', f'/api/strategies/{strategy_name}/stop')
        if not result:
            return False
        
        print(f"✓ Strategy '{strategy_name}' stopped")
        return True
    
    def edit_strategy(self, strategy_name: str, **params):
        """编辑策略参数"""
        payload = {"setting": params}
        result = self._request('PUT', f'/api/strategies/{strategy_name}', json=payload)
        if not result:
            return False
        
        print(f"✓ Strategy '{strategy_name}' updated")
        return True
    
    def remove_strategy(self, strategy_name: str):
        """删除策略"""
        result = self._request('DELETE', f'/api/strategies/{strategy_name}')
        if not result:
            return False
        
        print(f"✓ Strategy '{strategy_name}' removed")
        return True
    
    def get_accounts(self):
        """获取账户信息"""
        result = self._request('GET', '/api/accounts')
        if not result:
            return False
        
        accounts = result.get('data', {}).get('accounts', [])
        
        if not accounts:
            print("No accounts found.")
            return True
        
        print(f"\n{'Account ID':<20} {'Gateway':<12} {'Balance':<15} {'Frozen':<15} {'Available':<15}")
        print("-" * 80)
        
        for acc in accounts:
            print(f"{acc['accountid']:<20} {acc['gateway_name']:<12} "
                  f"{acc['balance']:<15.4f} {acc['frozen']:<15.4f} {acc.get('available', 0):<15.4f}")
        
        return True
    
    def get_positions(self):
        """获取持仓信息"""
        result = self._request('GET', '/api/positions')
        if not result:
            return False
        
        positions = result.get('data', {}).get('positions', [])
        
        if not positions:
            print("No positions found.")
            return True
        
        print(f"\n{'Symbol':<15} {'Direction':<10} {'Volume':<12} {'Price':<12} {'P&L':<15}")
        print("-" * 70)
        
        for pos in positions:
            direction = "Long" if "LONG" in str(pos['direction']).upper() else "Short"
            pnl = pos.get('pnl', 0)
            pnl_str = f"{pnl:+.4f}" if pnl else "N/A"
            print(f"{pos['symbol']:<15} {direction:<10} {pos['volume']:<12.4f} "
                  f"{pos.get('price', 0):<12.4f} {pnl_str:<15}")
        
        return True
    
    def get_orders(self, symbol: str = None):
        """获取活动订单"""
        endpoint = '/api/orders'
        if symbol:
            endpoint += f'?symbol={symbol}'
        
        result = self._request('GET', endpoint)
        if not result:
            return False
        
        orders = result.get('data', {}).get('orders', [])
        
        if not orders:
            print("No active orders found.")
            return True
        
        print(f"\n{'Order ID':<25} {'Symbol':<12} {'Type':<10} {'Direction':<10} "
              f"{'Price':<12} {'Volume':<10} {'Traded':<10} {'Status':<12}")
        print("-" * 110)
        
        for order in orders:
            direction = "Long" if "LONG" in str(order['direction']).upper() else "Short"
            print(f"{order['vt_orderid']:<25} {order['symbol']:<12} {order['type']:<10} "
                  f"{direction:<10} {order['price']:<12.4f} {order['volume']:<10.4f} "
                  f"{order['traded']:<10.4f} {order['status']:<12}")
        
        print(f"\nTotal: {len(orders)} active orders")
        return True
    
    def get_logs(self, limit: int = 50):
        """获取日志"""
        result = self._request('GET', f'/api/logs?limit={limit}')
        if not result:
            return False
        
        logs = result.get('data', {}).get('logs', [])
        
        if not logs:
            print("No logs found.")
            return True
        
        for log in reversed(logs[-limit:]):
            level_name = {10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR'}.get(log.get('level', 20), 'INFO')
            print(f"[{level_name}] {log.get('msg', '')}")
        
        return True
    
    def health_check(self):
        """健康检查"""
        result = self._request('GET', '/api/health')
        if not result:
            return False
        
        data = result.get('data', {})
        print(f"\n{'='*40}")
        print(f"GridTrader Service Status")
        print(f"{'='*40}")
        print(f"Status:         {data.get('status', 'unknown')}")
        print(f"Strategies:     {data.get('strategies_count', 0)}")
        print(f"Gateways:       {', '.join(data.get('gateways', []))}")
        print(f"Server URL:     {self.server_url}")
        print(f"{'='*40}")
        
        return True
    
    def list_strategy_classes(self):
        """列出可用的策略类型"""
        result = self._request('GET', '/api/strategy-classes')
        if not result:
            return False
        
        classes = result.get('data', {}).get('classes', [])
        
        print("\nAvailable Strategy Classes:")
        print("-" * 60)
        
        for cls in classes:
            print(f"\n{cls['class_name']}:")
            for k, v in cls.get('parameters', {}).items():
                print(f"  {k}: {v}")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='GridTrader CLI Client',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all strategies
  gridtrader-cli list
  
  # Get strategy details
  gridtrader-cli get MyStrategy
  
  # Add a new strategy
  gridtrader-cli add --class FuturesGridStrategy --name BTCGrid --symbol BTCUSDT \\
      --upper_price 70000 --bottom_price 60000 --grid_number 10 --order_volume 0.01
  
  # Start/Stop strategy
  gridtrader-cli start BTCGrid
  gridtrader-cli stop BTCGrid
  
  # Get account info
  gridtrader-cli accounts
  gridtrader-cli positions
  gridtrader-cli orders
  
  # Health check
  gridtrader-cli health
        """
    )
    
    parser.add_argument(
        '--server', '-s',
        type=str,
        default=DEFAULT_SERVER,
        help=f'GridTrader server URL (default: {DEFAULT_SERVER})'
    )
    
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # list command
    subparsers.add_parser('list', help='List all strategies')
    subparsers.add_parser('health', help='Health check')
    subparsers.add_parser('accounts', help='List all accounts')
    subparsers.add_parser('positions', help='List all positions')
    subparsers.add_parser('classes', help='List available strategy classes')
    
    # logs command
    logs_parser = subparsers.add_parser('logs', help='Get recent logs')
    logs_parser.add_argument('--limit', '-n', type=int, default=50, help='Number of logs to show')
    
    # orders command
    orders_parser = subparsers.add_parser('orders', help='List active orders')
    orders_parser.add_argument('--symbol', type=str, help='Filter by symbol')
    
    # get command
    get_parser = subparsers.add_parser('get', help='Get strategy details')
    get_parser.add_argument('strategy_name', type=str, help='Strategy name')
    
    # init command
    init_parser = subparsers.add_parser('init', help='Initialize strategy')
    init_parser.add_argument('strategy_name', type=str, help='Strategy name')
    
    # start command
    start_parser = subparsers.add_parser('start', help='Start strategy')
    start_parser.add_argument('strategy_name', type=str, help='Strategy name')
    
    # stop command
    stop_parser = subparsers.add_parser('stop', help='Stop strategy')
    stop_parser.add_argument('strategy_name', type=str, help='Strategy name')
    
    # remove command
    remove_parser = subparsers.add_parser('remove', help='Remove strategy')
    remove_parser.add_argument('strategy_name', type=str, help='Strategy name')
    
    # add command
    add_parser = subparsers.add_parser('add', help='Add new strategy')
    add_parser.add_argument('--class', dest='class_name', type=str, required=True, help='Strategy class name')
    add_parser.add_argument('--name', type=str, required=True, help='Strategy name')
    add_parser.add_argument('--symbol', type=str, required=True, help='Trading symbol (e.g., BTCUSDT)')
    add_parser.add_argument('--upper-price', type=float, help='Upper price limit')
    add_parser.add_argument('--bottom-price', type=float, help='Bottom price limit')
    add_parser.add_argument('--grid-number', type=int, help='Number of grids')
    add_parser.add_argument('--order-volume', type=float, help='Volume per grid')
    add_parser.add_argument('--max-open-orders', type=int, help='Max open orders')
    add_parser.add_argument('--invest-coin', type=str, help='Investment coin')
    
    # edit command
    edit_parser = subparsers.add_parser('edit', help='Edit strategy parameters')
    edit_parser.add_argument('strategy_name', type=str, help='Strategy name')
    edit_parser.add_argument('--upper-price', type=float, help='Upper price limit')
    edit_parser.add_argument('--bottom-price', type=float, help='Bottom price limit')
    edit_parser.add_argument('--grid-number', type=int, help='Number of grids')
    edit_parser.add_argument('--order-volume', type=float, help='Volume per grid')
    edit_parser.add_argument('--max-open-orders', type=int, help='Max open orders')
    
    args = parser.parse_args()
    
    # 创建客户端
    cli = GridTraderCLI(server_url=args.server, timeout=args.timeout)
    
    # 执行命令
    if args.command == 'list':
        success = cli.list_strategies()
    elif args.command == 'health':
        success = cli.health_check()
    elif args.command == 'accounts':
        success = cli.get_accounts()
    elif args.command == 'positions':
        success = cli.get_positions()
    elif args.command == 'orders':
        success = cli.get_orders(args.symbol if hasattr(args, 'symbol') else None)
    elif args.command == 'logs':
        success = cli.get_logs(args.limit)
    elif args.command == 'classes':
        success = cli.list_strategy_classes()
    elif args.command == 'get':
        success = cli.get_strategy(args.strategy_name)
    elif args.command == 'init':
        success = cli.init_strategy(args.strategy_name)
    elif args.command == 'start':
        success = cli.start_strategy(args.strategy_name)
    elif args.command == 'stop':
        success = cli.stop_strategy(args.strategy_name)
    elif args.command == 'remove':
        success = cli.remove_strategy(args.strategy_name)
    elif args.command == 'add':
        params = {}
        if args.upper_price is not None:
            params['upper_price'] = args.upper_price
        if args.bottom_price is not None:
            params['bottom_price'] = args.bottom_price
        if args.grid_number is not None:
            params['grid_number'] = args.grid_number
        if args.order_volume is not None:
            params['order_volume'] = args.order_volume
        if args.max_open_orders is not None:
            params['max_open_orders'] = args.max_open_orders
        if args.invest_coin is not None:
            params['invest_coin'] = args.invest_coin
        
        success = cli.add_strategy(args.class_name, args.name, args.symbol, **params)
    elif args.command == 'edit':
        params = {}
        if args.upper_price is not None:
            params['upper_price'] = args.upper_price
        if args.bottom_price is not None:
            params['bottom_price'] = args.bottom_price
        if args.grid_number is not None:
            params['grid_number'] = args.grid_number
        if args.order_volume is not None:
            params['order_volume'] = args.order_volume
        if args.max_open_orders is not None:
            params['max_open_orders'] = args.max_open_orders
        
        success = cli.edit_strategy(args.strategy_name, **params)
    else:
        parser.print_help()
        sys.exit(0)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
