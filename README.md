# 币安网格交易机器人（Binance Grid Trader）

一个基于 Python 的币安网格交易程序，支持**币安现货**与**币安 USDT 本位合约**两个市场，内置 4 种网格策略，提供图形化界面（PyQt5）与无界面脚本两种运行方式，可连接**测试网**零成本验证策略逻辑。

---

## ✨ 功能特性

- ✅ 支持币安**现货**与 **USDT 本位合约**行情推送与实盘下单
- ✅ 内置 4 种网格策略：现货中性网格、合约中性网格、合约多空网格、合约只做多网格
- ✅ 图形化界面：行情、委托、成交、持仓、资金、日志一站式监控
- ✅ 无界面脚本模式：读取配置文件自动初始化并启动全部策略，适合服务器挂机
- ✅ 支持**测试网（Testnet）**，新手可先用模拟资金跑通整个流程
- ✅ 策略持仓、均价等运行数据自动保存，重启程序后自动恢复
- ✅ 支持代理（proxy_host / proxy_port），海外服务器也可使用

---

## 📚 内置策略说明

网格策略的基本思路：在设定的价格区间内，将价格等分为 N 个网格，价格每波动一个网格即触发一次买卖，低买高卖赚取波段差价。**网格策略在震荡行情下表现较好；一旦出现单边趋势行情，可能产生较大浮亏，请务必注意风险。**

### 1️⃣ SpotGridStrategy — 现货中性网格

币安现货市场的中性网格：在区间内同时挂买单和卖单，价格下跌买入、上涨卖出，赚取差价。

| 参数 | 说明 |
| --- | --- |
| `upper_price` | 网格区间上限价 |
| `bottom_price` | 网格区间下限价 |
| `grid_number` | 网格数量（步长 = (上限 - 下限) / 网格数） |
| `order_volume` | 每次下单的数量（交易币种数量） |
| `invest_coin` | 投入币种，默认 `USDT` |
| `max_open_orders` | 单边最大挂单数量 |

### 2️⃣ FuturesGridStrategy — 合约中性网格

币安 USDT 本位合约的中性网格，与现货中性网格逻辑一致，通过合约多空双向开平仓实现。

| 参数 | 说明 |
| --- | --- |
| `upper_price` | 网格区间上限价 |
| `bottom_price` | 网格区间下限价 |
| `grid_number` | 网格数量 |
| `order_volume` | 每次下单数量（张数） |
| `max_open_orders` | 单边最大挂单数量 |

### 3️⃣ FuturesGridLongShortStrategy — 合约多空网格

在合约中性网格的基础上，支持**带初始仓位启动**：启动时先持有多头或空头仓位，再在其上方/下方布置网格。

| 参数 | 说明 |
| --- | --- |
| `initial_volume` | 初始仓位数量：**大于 0 表示先做多**，小于 0 表示先做空，0 表示中性（与中性网格相同） |
| `upper_price` | 网格区间上限价 |
| `bottom_price` | 网格区间下限价 |
| `grid_number` | 网格数量 |
| `order_volume` | 每次下单数量（张数） |
| `max_open_orders` | 单边最大挂单数量 |

### 4️⃣ FuturesLongGridStrategy — 合约只做多网格

币安合约**只做多**网格（只开多、只平多），在震荡上行行情中分批建仓、分批止盈，不做空。

| 参数 | 说明 |
| --- | --- |
| `upper_price` | 网格区间上限价 |
| `bottom_price` | 网格区间下限价 |
| `grid_number` | 网格数量 |
| `order_volume` | 每次下单数量（张数） |
| `max_open_orders` | 最大挂单数量 |
| `initial_entry_volume` | 启动时立即建仓的张数，**0 表示不建仓**。大于 0 时按当前价格建仓，并在上方每个网格各挂一张平多单，价格每上涨一格分批止盈 |

---

## 📁 项目结构

```
binance_grid_trader
├── main.py                          # 图形界面入口
├── main_spot_script.py              # 现货脚本模式入口（无界面）
├── main_futures_script.py           # 合约脚本模式入口（无界面）
├── requirements.txt                 # Python 依赖清单
├── gridtrader/
│   ├── api/                         # REST / WebSocket 接口封装
│   ├── event/                       # 事件引擎
│   ├── gateway/binance/             # 币安现货、USDT 本位合约网关
│   ├── trader/
│   │   ├── engine.py                # 主引擎 + 策略引擎
│   │   ├── ui/                      # PyQt5 图形界面
│   │   └── strategies/              # 网格策略实现
│   ├── connect_spot.json            # 现货 API 连接配置（已加入 .gitignore）
│   ├── connect_futures.json         # 合约 API 连接配置（已加入 .gitignore）
│   ├── grid_strategy_setting.json   # 策略参数配置（已加入 .gitignore）
│   ├── grid_strategy_data.json      # 策略运行数据，自动保存（已加入 .gitignore）
│   └── vt_setting.json              # 全局设置（日志开关等）
└── resources/                       # 操作界面截图
```

---

## 🛠 环境要求与安装

- Python 3.x（建议 3.8 及以上）
- 依赖安装：

```bash
pip install -r requirements.txt
```

> 💡 国内用户可加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 加速安装。

---

## 🚀 快速开始（操作流程）

首次使用强烈建议**先在测试网跑通全流程**，确认无误后再考虑实盘。

### 第一步：申请测试网 API Key

| 市场 | 测试网地址 | 说明 |
| --- | --- | --- |
| 现货 | [https://testnet.binance.vision](https://testnet.binance.vision) | 生成 `API Key` + `Private Key`（Ed25519 私钥） |
| 合约 | [https://testnet.binancefuture.com](https://testnet.binancefuture.com) | 生成 `API Key` + `Secret Key` |

> ⚠️ 现货与合约的密钥体系不同：现货使用 **Ed25519 私钥**签名，合约使用 **HMAC Secret**，请分别在对应测试网生成。

### 第二步：填写连接配置

有两种填写方式（任选其一）：

**方式 A：图形界面里填写**（推荐）—— 启动程序后在连接弹窗中填写，保存后会自动写入配置文件。

**方式 B：手动编辑配置文件**

现货 `gridtrader/connect_spot.json`：

```json
{
    "api_key": "你的现货 API Key",
    "private_key": "你的现货 Ed25519 私钥",
    "testnet": true,
    "proxy_host": "",
    "proxy_port": 0
}
```

合约 `gridtrader/connect_futures.json`：

```json
{
    "key": "你的合约 API Key",
    "secret": "你的合约 Secret Key",
    "testnet": true,
    "proxy_host": "",
    "proxy_port": 0
}
```

> 🔒 这两个文件已加入 `.gitignore`，不会被提交到 Git 仓库，请放心填写。

### 第三步：启动程序

```bash
python main.py
```

主界面如下：

![主界面](resources/img_window.png)

### 第四步：连接交易所

点击菜单栏「系统 → 连接 Binance Spot / 连接 Binance Futures」或工具栏对应图标，在弹窗中填写 API 信息（或修改已自动读取的配置），点击连接：

![连接合约](resources/connect_future_usdt.png)

![连接现货](resources/connect_spot.png)

连接成功后，日志区会输出连接日志，行情面板开始推送行情。

### 第五步：添加策略

点击「功能 → 策略引擎」打开策略管理窗口，点击「添加策略」：

1. 选择策略类名（如 `FuturesLongGridStrategy`）
2. 填写 `vt_symbol`，格式为 `交易对.交易所后缀`，例如 `ETHUSDT.BINANCE`
3. 填写策略参数（价格区间、网格数量、下单数量等）

![添加合约网格策略](resources/add_future_grid_strategy.png)

![添加现货网格策略](resources/add_spot_grid_strategy.png)

### 第六步：初始化并启动

在策略列表中选中刚添加的策略，依次点击：

1. **初始化** —— 加载策略配置与历史数据
2. **启动** —— 策略开始接收行情并挂单交易

![启动策略](resources/start_strategy.png)

启动后可在「日志」面板查看策略运行日志，在「委托 / 成交 / 持仓 / 资金」面板实时监控状态。策略的持仓、均价等运行数据会自动保存到 `grid_strategy_data.json`，下次启动自动恢复。

---

## 🤖 脚本模式（无界面，适合服务器挂机）

不想开图形界面时，可使用脚本模式：从 `grid_strategy_setting.json` 读取所有策略配置，自动初始化并启动全部策略。

1. 在脚本顶部填写 API 配置（`main_spot_script.py` 填现货，`main_futures_script.py` 填合约）
2. 编辑 `gridtrader/grid_strategy_setting.json`，配置要运行的策略：

```json
{
    "我的多头网格": {
        "class_name": "FuturesLongGridStrategy",
        "vt_symbol": "ETHUSDT.BINANCE",
        "setting": {
            "upper_price": 2400.0,
            "bottom_price": 2350.0,
            "grid_number": 40,
            "order_volume": 0.05,
            "max_open_orders": 40,
            "initial_entry_volume": 20.0
        }
    }
}
```

3. 运行脚本：

```bash
python main_spot_script.py    # 现货
python main_futures_script.py # 合约
```

脚本会依次完成：连接 API → 初始化策略引擎 → 初始化全部策略 → 启动全部策略，然后常驻运行。

---

## ⚙️ 配置文件说明

| 文件 | 用途 |
| --- | --- |
| `gridtrader/connect_spot.json` | 现货 API 连接配置 |
| `gridtrader/connect_futures.json` | 合约 API 连接配置 |
| `gridtrader/grid_strategy_setting.json` | 策略参数配置（GUI 添加策略时也会写入；脚本模式启动时读取） |
| `gridtrader/grid_strategy_data.json` | 策略运行数据（持仓、均价、成交次数等，程序自动保存与恢复） |
| `gridtrader/vt_setting.json` | 全局设置（日志开关、日志级别等） |

---

## ❓ 常见问题（FAQ）

**Q1：启动策略时报 `Could Not Find The Symbol: xxx, Please Connect the Api First.`**
说明对应交易所尚未连接成功。请先完成 API 连接，确认日志区输出连接成功日志后再启动策略。

**Q2：合约下单报错？**
本程序的合约网关仅支持**单向持仓模式**（One-way Mode）。请在币安合约设置中将持仓模式改为单向。

**Q3：行情不推送 / 连接不上？**
国内网络访问币安可能受限，可在连接配置中填写 `proxy_host` / `proxy_port` 使用代理。

**Q4：现货下单签名报错？**
现货使用 Ed25519 私钥签名，与合约的 HMAC Secret 不同。请确认在现货测试网正确生成了 `Private Key` 并填入 `private_key` 字段。

**Q5：API Key 会不会被提交到 GitHub？**
不会。`connect_*.json`、`grid_strategy_*.json`、`log/` 均已加入 `.gitignore`，Git 不会跟踪这些文件。

**Q6：价格突破网格上下限会怎样？**
网格只在设定区间内挂单。价格突破区间后不再触发新的网格交易，已有持仓不会自动平仓，请自行评估风险并做好止损预案。

---

## ⚠️ 免责声明

- 本项目仅供**学习与测试**用途，不构成任何投资建议。
- 虚拟货币交易风险极高，请先在**测试网**充分验证策略逻辑，并自行承担实盘交易的一切后果。
- 策略代码中可能存在未知 Bug，使用前请务必通读并理解代码。

## 📄 开源协议

本项目采用 [MIT License](LICENSE)。

## 🙏 致谢

- 项目架构基于 [vn.py](https://github.com/vnpy/vnpy)（MIT License，版权归原作者 Xiaoyou Chen）
- 网格策略实现参考 [51bitquant](https://github.com/51bitquant) 的网格交易框架

---

# 老曾的量化团队 — 跨境交易一站式服务平台

> 🔍 **淘宝搜索：`老曾的量化团队`** 即可找到我们

我们是一家位于深圳的团队，长期深耕**交易、投资、跨境**三大方向。无论你是刚入门的新手，还是已经征战市场多年的老兵，这条路上遇到的账户、出金、平台选择、信号源、策略学习等大部分问题，我们都能帮你兜底。欢迎添加微信长期备着，不一定做生意，多个懂行的朋友多条路。

---

## 🎁 添加微信，免费领福利

扫码或搜索微信号添加好友（**记得备注来源 GitHub**，否则不会通过）：

| 微信号 | 备注 |
| --- | --- |
| `zlb08668` | 优先添加 |
| `zlb0868` | 备用 |
| `laozeng111222` | 备用 |

### 添加后你能得到什么？

**① 一支深圳本地团队的长期陪伴**
我们公司在深圳，主营交易、投资、跨境支付与全球资产配置。这条路上的坑我们基本都踩过，从平台挑选、出入金通道，到交易心理与策略迭代，都能给你一些实在建议。加一下，**长期备用，欢迎纯交流**。

**② 一份精心整理的《交易学习大礼包》**（免费赠送）
微信好友即可领取，内容包括但不限于：

- 📘 **聪明钱（Smart Money）理论** —— 机构资金到底在看什么
- 📘 **ICT 订单流理论** —— 解读 K 线背后的真实买卖力量
- 📘 **哈佛心理公开课** —— 交易心态建设的经典素材
- 📘 **K 线形态学合集** —— 实战中真正有效的形态识别

> 资料为团队多年积累整理，市面上零散收费的资源我们帮你打包好了，**绝对有价值**。

---

## 🏢 公司主推业务 — 开户推荐

我们在官网基础返佣之上，**额外提供以下团队福利**。我们的收入来自平台推广奖励，不赚用户一分钱。单个用户返佣虽薄，靠大家支持也能积少成多，感谢一路同行。

### 1️⃣ 黄金外汇平台 — 开户 + 转户（公司主推）

📄 详细文档：[https://docs.qq.com/doc/DWGFXdmtuR2tnT0dF](https://docs.qq.com/doc/DWGFXdmtuR2tnT0dF)

✅ **覆盖 20+ 主流平台**：TMGM、激石 Pepperstone、嘉盛 Forex、爱华 AVATRADE、富拓 FXTM、福汇 FXCM、EXness、XM、GTC、EBC、EC、CMC、IC、D Prime 德璞、BCR、CPT、蓝莓、DBG、ZFX 山海证券、安汇、ATFX、CXM 希盟、DLSM、VT、Wetrade、FPG 等。

✅ **六大独家优势**：

| 序号 | 福利内容 |
| --- | --- |
| 1 | 交易费用全网最低，量大可议 |
| 2 | 达到交易量可进入喊单群，基于价格行为学获取专业交易员做单分析 |
| 3 | 部分平台可申请免隔夜费，转户活动额外奖励 |
| 4 | 信息同步：入金活动、交易奖励实时对接，顺手把羊毛薅到极致 |
| 5 | 对接总部官方人员，长期售后，最高权限，问题优先解决 |
| 6 | 团队信息获取能力强，帮你避开信息差陷阱 |

---

### 2️⃣ 数字加密平台 — 改绑 + 加绑（公司主推）

📄 详细文档：[https://docs.qq.com/doc/DWFhKY3BRZ2NabEhT](https://docs.qq.com/doc/DWFhKY3BRZ2NabEhT)

✅ **三大独家优势**：

| 序号 | 福利内容 |
| --- | --- |
| 1 | 最高返佣 **70%**，全网数一数二的真福利 |
| 2 | 直接对接官方：**BG-50、Gate-70** 可改绑；**BN、OKX** 可加绑，都是主流平台 |
| 3 | 长期售后 + 问题解决 + 信息同步 |

---

### 3️⃣ 境外卡 / 港卡 + 港美股券商

📄 详细文档：[https://docs.qq.com/doc/DWGVYckFic2pPZEtD](https://docs.qq.com/doc/DWGVYckFic2pPZEtD)

> 🏠 **核心卖点：内地身份 + 在家即可办理**

**境外银行**（持续合作中）：
渣打银行、华侨银行、华美银行、星展银行、汇丰银行，其他平台还在拓展。

**港美股券商**（持续合作中）：
复星国际证券、致富证券、盈立证券，其他平台还在拓展。

✅ **三大独家优势**：

| 序号 | 福利内容 |
| --- | --- |
| 1 | 内地身份在家办理，流程简单，渠道福利直达 |
| 2 | 直接对接官方，可靠有保障 |
| 3 | 除一两家银行外，**全面免费！免费！免费！** |

> 💡 **特别说明**：我们赚的不是服务费，而是官方的推荐奖励。所以能免的全部给你免了，放心用。

---

## 🌐 关注我们 — 社交媒体矩阵

想第一时间获取交易机会、市场分析、喊单信号？关注我们的全网账号：

### 📱 视频号 / 公众号
- **老曾的量化世界**
- **老曾的量化交易世界**

### 📺 YouTube
- 账号1：[VeloAlgo](https://www.youtube.com/@VeloAlgo)
- 账号2：[LaoZeng0530](https://www.youtube.com/@LaoZeng0530)

### 📺 Bilibili
- [老曾的量化团队](https://space.bilibili.com/3546820166814537)

### 🌐 团队官网
- [Laozeng123.com](http://Laozeng123.com)

---

## 📌 一句话总结

> **淘宝搜「老曾的量化团队」→ 加微信 → 领资料 + 对接开户 → 长期陪伴**

无论你是想找一支靠谱的团队长期交流，还是想薅到平台开户的全网最优福利，或者想系统学习交易，**我们都在这里**。

加微信请备注 **GitHub**，秒过。

---

*本项目及所有推荐内容不构成任何投资建议。市场有风险，交易需谨慎。*
