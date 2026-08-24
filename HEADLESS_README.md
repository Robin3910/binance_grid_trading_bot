# Binance Grid Trader - Headless Service

Linux 服务器部署方案，支持通过 REST API、CLI 和 Web 界面管理策略。

## 功能特性

- **REST API** - 完整的策略管理接口
- **WebSocket** - 实时事件推送
- **Web Dashboard** - 浏览器控制面板
- **CLI 工具** - 命令行管理工具
- **systemd** - 开机自启服务

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制配置模板并编辑：

```bash
cp config/headless.yaml.example config/headless.yaml
```

编辑 `config/headless.yaml`，填入你的 Binance API Key：

```yaml
binance:
  spot:
    api_key: "your_spot_api_key"
    private_key: "your_spot_private_key"
  futures:
    key: "your_futures_key"
    secret: "your_futures_secret"
```

或者使用环境变量：

```bash
export BINANCE_SPOT_API_KEY="your_key"
export BINANCE_SPOT_PRIVATE_KEY="your_secret"
export BINANCE_FUTURES_KEY="your_key"
export BINANCE_FUTURES_SECRET="your_secret"
```

### 3. 启动服务

```bash
# 直接运行
python main_headless.py

# 或指定配置
python main_headless.py --config config/headless.yaml --api-port 8765 --web-port 8080
```

### 4. 访问

- **Web Dashboard**: http://localhost:8080
- **REST API**: http://localhost:8765

## CLI 使用

### 安装 CLI 工具

```bash
pip install -e .
```

### 命令示例

```bash
# 列出所有策略
gridtrader-cli list

# 查看策略详情
gridtrader-cli get MyStrategy

# 添加策略
gridtrader-cli add --class FuturesGridStrategy --name BTCGrid --symbol BTCUSDT \
    --upper-price 70000 --bottom-price 60000 --grid-number 10 --order-volume 0.01

# 启动/停止策略
gridtrader-cli start BTCGrid
gridtrader-cli stop BTCGrid

# 查看账户和持仓
gridtrader-cli accounts
gridtrader-cli positions
gridtrader-cli orders

# 健康检查
gridtrader-cli health
```

## REST API

### 策略管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/strategies` | 获取所有策略 |
| POST | `/api/strategies` | 添加新策略 |
| GET | `/api/strategies/{name}` | 获取策略详情 |
| PUT | `/api/strategies/{name}` | 修改策略参数 |
| DELETE | `/api/strategies/{name}` | 删除策略 |
| POST | `/api/strategies/{name}/init` | 初始化策略 |
| POST | `/api/strategies/{name}/start` | 启动策略 |
| POST | `/api/strategies/{name}/stop` | 停止策略 |

### 账户信息

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/accounts` | 获取账户信息 |
| GET | `/api/positions` | 获取持仓信息 |
| GET | `/api/orders` | 获取活动订单 |

### WebSocket

连接 `ws://localhost:8765/ws`，接收实时推送：

- `log` - 日志事件
- `strategy_update` - 策略状态更新
- `order_update` - 订单更新
- `trade` - 成交事件
- `account_update` - 账户更新
- `position_update` - 持仓更新

## Linux 服务器部署

### systemd 服务安装

```bash
# 以 root 身份运行
sudo cp deploy/gridtrader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gridtrader
sudo systemctl start gridtrader

# 查看状态
sudo systemctl status gridtrader
```

### 使用部署脚本

```bash
# 安装
sudo ./deploy/deploy.sh --install

# 启动/停止/重启
sudo ./deploy/deploy.sh --start
sudo ./deploy/deploy.sh --stop
sudo ./deploy/deploy.sh --restart

# 查看日志
sudo ./deploy/deploy.sh --logs
```

## 目录结构

```
binance_grid_trader/
├── main_headless.py           # 无头服务入口
├── config/
│   └── headless.yaml.example  # 配置模板
├── gridtrader/
│   ├── api/
│   │   ├── rest/             # REST API
│   │   │   ├── server.py
│   │   │   └── handlers.py
│   │   └── cli/              # CLI 客户端
│   │       └── client.py
│   └── web/                  # Web 界面
│       ├── app.py
│       ├── templates/
│       └── static/
└── deploy/
    ├── gridtrader.service     # systemd 服务
    └── deploy.sh             # 部署脚本
```

## API 响应格式

```json
{
    "code": 0,
    "message": "success",
    "data": { ... }
}
```

错误响应：

```json
{
    "code": 404,
    "message": "Strategy 'xxx' not found"
}
```

## 安全建议

1. **使用环境变量存储 API Key**，不要硬编码在配置文件中
2. **配置防火墙**，只允许必要的端口访问
3. **启用 HTTPS**（通过 nginx 反向代理）
4. **限制 API 访问**（使用 API Key 或 IP 白名单）

### Nginx HTTPS 反向代理配置示例

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
