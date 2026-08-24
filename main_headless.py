"""
Binance Grid Trader - Headless Service Entry Point

Linux 服务器无头服务入口，支持:
- REST API 控制
- WebSocket 实时推送
- CLI 工具控制

Usage:
    python main_headless.py --config config/headless.yaml
    python main_headless.py --api-port 8765 --ws-port 8766
"""

import argparse
import logging
import signal
import sys
import os
from pathlib import Path

from gridtrader.event import EventEngine
from gridtrader.trader.engine import MainEngine
from gridtrader.trader.setting import SETTINGS
from gridtrader.api.rest.server import ApiServer
from gridtrader.web.app import WebDashboard

logger = logging.getLogger("GridTrader.Headless")


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    import yaml
    
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {}
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def setup_logging(config: dict):
    """配置日志"""
    log_config = config.get('logging', {})
    
    SETTINGS["log.active"] = True
    SETTINGS["log.level"] = getattr(logging, log_config.get('level', 'INFO'))
    SETTINGS["log.console"] = log_config.get('console', True)
    SETTINGS["log.file"] = log_config.get('file', True)


def setup_directories(config: dict):
    """创建必要的目录"""
    dirs = ['logs', 'data']
    for d in dirs:
        Path(d).mkdir(exist_ok=True)


class HeadlessRunner:
    """Grid Trader 无头服务运行器"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.event_engine: EventEngine = None
        self.main_engine: MainEngine = None
        self.api_server: ApiServer = None
        self.web_dashboard: WebDashboard = None
        self.running = False
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理终止信号"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)
    
    def _load_connection_settings(self) -> dict:
        """加载交易所连接配置"""
        binance_config = self.config.get('binance', {})
        settings = {}
        
        # Spot 配置
        spot = binance_config.get('spot', {})
        settings['spot'] = {
            "api_key": os.environ.get('BINANCE_SPOT_API_KEY', spot.get('api_key', '')),
            "private_key": os.environ.get('BINANCE_SPOT_PRIVATE_KEY', spot.get('private_key', '')),
            "testnet": spot.get('testnet', False),
            "proxy_host": spot.get('proxy_host', ''),
            "proxy_port": spot.get('proxy_port', 0)
        }
        
        # Futures 配置
        futures = binance_config.get('futures', {})
        settings['futures'] = {
            "key": os.environ.get('BINANCE_FUTURES_KEY', futures.get('key', '')),
            "secret": os.environ.get('BINANCE_FUTURES_SECRET', futures.get('secret', '')),
            "testnet": futures.get('testnet', False),
            "proxy_host": futures.get('proxy_host', ''),
            "proxy_port": futures.get('proxy_port', 0)
        }
        
        return settings
    
    def start(self):
        """启动服务"""
        logger.info("=" * 50)
        logger.info("Binance Grid Trader - Headless Service")
        logger.info("=" * 50)
        
        # 创建事件引擎
        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)
        
        # 连接交易所
        connection_settings = self._load_connection_settings()
        
        if connection_settings['spot'].get('api_key'):
            logger.info("Connecting to Binance Spot...")
            self.main_engine.connect(connection_settings['spot'], "Spot")
        
        if connection_settings['futures'].get('key'):
            logger.info("Connecting to Binance Futures...")
            self.main_engine.connect(connection_settings['futures'], "Futures")
        
        # 初始化策略引擎
        cta_engine = self.main_engine.get_engine('strategy')
        cta_engine.init_engine()
        logger.info("Strategy engine initialized")
        
        # 获取服务配置
        server_config = self.config.get('server', {})
        api_port = server_config.get('api_port', 8765)
        ws_port = server_config.get('ws_port', 8766)
        web_port = server_config.get('web_port', 8080)
        enable_web = server_config.get('enable_web', True)
        
        # 启动 API 服务
        logger.info(f"Starting REST API server on port {api_port}...")
        self.api_server = ApiServer(
            self.main_engine,
            self.event_engine,
            port=api_port,
            ws_port=ws_port
        )
        self.api_server.start()
        
        # 启动 Web 仪表盘 (可选)
        if enable_web:
            logger.info(f"Starting Web Dashboard on port {web_port}...")
            self.web_dashboard = WebDashboard(
                self.main_engine,
                self.event_engine,
                port=web_port
            )
            self.web_dashboard.start()
        
        # 策略全局配置
        strategy_config = self.config.get('strategy', {})
        if strategy_config.get('auto_init', False):
            logger.info("Auto initializing all strategies...")
            cta_engine.init_all_strategies()
        
        if strategy_config.get('auto_start', False):
            logger.info("Auto starting all strategies...")
            cta_engine.start_all_strategies()
        
        self.running = True
        
        logger.info("=" * 50)
        logger.info(f"GridTrader Headless Service Started Successfully!")
        logger.info(f"REST API:  http://0.0.0.0:{api_port}")
        logger.info(f"WebSocket: ws://0.0.0.0:{ws_port}")
        if enable_web:
            logger.info(f"Web UI:    http://0.0.0.0:{web_port}")
        logger.info("=" * 50)
        
        # 保持运行
        try:
            while self.running:
                signal.pause()
        except AttributeError:
            # Windows 不支持 signal.pause()
            import time
            while self.running:
                time.sleep(1)
    
    def shutdown(self):
        """关闭服务"""
        logger.info("Shutting down GridTrader Headless Service...")
        self.running = False
        
        # 停止所有策略
        cta_engine = self.main_engine.get_engine('strategy')
        if cta_engine:
            cta_engine.stop_all_strategies()
        
        # 停止 API 服务
        if self.api_server:
            self.api_server.stop()
        
        # 停止 Web 服务
        if self.web_dashboard:
            self.web_dashboard.stop()
        
        # 关闭引擎
        if self.main_engine:
            self.main_engine.close()
        
        logger.info("Shutdown complete")


def main():
    parser = argparse.ArgumentParser(
        description='Binance Grid Trader - Headless Service',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config/headless.yaml',
        help='Path to config file (default: config/headless.yaml)'
    )
    
    parser.add_argument(
        '--api-port',
        type=int,
        help='REST API server port (overrides config)'
    )
    
    parser.add_argument(
        '--ws-port',
        type=int,
        help='WebSocket server port (overrides config)'
    )
    
    parser.add_argument(
        '--web-port',
        type=int,
        help='Web Dashboard port (overrides config)'
    )
    
    parser.add_argument(
        '--no-web',
        action='store_true',
        help='Disable web dashboard'
    )
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 命令行参数覆盖配置
    if args.api_port:
        config.setdefault('server', {})['api_port'] = args.api_port
    if args.ws_port:
        config.setdefault('server', {})['ws_port'] = args.ws_port
    if args.web_port:
        config.setdefault('server', {})['web_port'] = args.web_port
    if args.no_web:
        config.setdefault('server', {})['enable_web'] = False
    
    # 设置日志
    setup_logging(config)
    setup_directories(config)
    
    # 启动服务
    runner = HeadlessRunner(config)
    runner.start()


if __name__ == "__main__":
    main()
