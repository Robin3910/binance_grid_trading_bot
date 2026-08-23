from ..engine import CtaEngine, EVENT_TIMER

from gridtrader.trader.object import Status
from typing import Union, Optional
from gridtrader.trader.utility import floor_to
from gridtrader.trader.object import OrderData, TickData, TradeData, ContractData, Direction, Offset
from .template import CtaTemplate
from gridtrader.trader.utility import GridPositionCalculator


class FuturesLongGridStrategy(CtaTemplate):
    """
    币安合约只做多网格（只开多，只平多）。
    基于中性网格策略改造而来：只保留 long_orders_dict，移除所有做空分支。

    功能增强：支持"启动时按指定量立即建仓"。
    - 参数 initial_entry_volume：建仓量（张数）。0 表示不建仓（与原策略行为一致）。
    - 启动时如果当前价格在第 k 格（k = round((price - bottom)/step)），
      建仓后会在第 k+1, k+2, ..., k+initial_entry_volume 个网格上各挂一张 sell 平多单，
      这样当价格逐步上涨时，会按"每跨一格平一仓"的节奏分批止盈。

    免责声明: 本策略仅供测试参考，本人不负有任何责任。使用前请熟悉代码。测试其中的bugs, 请清楚里面的功能后再使用。
    币安邀请链接: https://www.binancezh.pro/cn/futures/ref/51bitquant
    合约邀请码：51bitquant


    Disclaimer:
    Invest in Crypto currency is high risk. Take care of yourself. I am not responsible for your investment.
    Binance Referral Link: https://www.binancezh.pro/cn/futures/ref/51bitquant

    """
    author = "51bitquant"

    # parameters
    upper_price = 0.0  # The grid strategy high/upper price 执行策略的最高价.
    bottom_price = 0.0  # The grid strategy low/bottom price 执行策略的最低价.
    grid_number = 100  # grid number 网格的数量.
    order_volume = 0.05  # order volume  每次下单的数量.
    max_open_orders = 5  # max open price  一边订单的数量.
    initial_entry_volume = 0.0  # 启动时立即建仓量（张数），0 = 不建仓.

    # variables
    avg_price = 0.0  # current average price for the position  持仓的均价
    step_price = 0.0  # price step between two grid 网格的间隔
    trade_times = 0  # trade times
    initial_entry_filled = False  # whether initial entry order has been submitted
    initial_entry_grid = 0  # grid index where initial entry was placed
    realized_pnl = 0.0  # 已实现盈亏（仅归属本策略的成交）
    float_pnl = 0.0  # 浮动盈亏
    total_commission = 0.0  # 累计手续费（折算 USDT）
    total_pnl = 0.0  # 合计 = realized_pnl + float_pnl - total_commission

    parameters = [
        "upper_price",
        "bottom_price",
        "grid_number",
        "order_volume",
        "max_open_orders",
        "initial_entry_volume",
    ]

    variables = [
        "avg_price",
        "step_price",
        "trade_times",
        "initial_entry_filled",
        "initial_entry_grid",
        "realized_pnl",
        "float_pnl",
        "total_commission",
        "total_pnl",
    ]

    def __init__(self, cta_engine: CtaEngine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.long_orders_dict = {}  # long orders dict {'orderid': price}
        self.sell_orders_dict = {}  # sell (close long) orders dict {'orderid': price}
        self.initial_entry_order_ids = set()  # order ids of the initial entry order(s)
        self.initial_entry_profit_placed = False  # whether profit-taking sells have been placed

        self.tick: Union[TickData, None] = None
        self.contract_data: Optional[ContractData] = None

        self.pos_calculator = GridPositionCalculator()
        self.timer_count = 0

        # ---- 多策略盈亏归属 ----
        # 记录本策略所有下过的 vt_orderid，用于 on_trade 里过滤
        self.my_order_ids: set = set()
        # 合约面值（USDT 永续合约通常 trade.price * trade.volume * contract_size = 名义额）
        self.contract_size: float = 0.0

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("Init Strategy")

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("Start Strategy")
        self.contract_data = self.cta_engine.main_engine.get_contract(self.vt_symbol)

        if not self.contract_data:
            self.write_log(f"Could Not Find The Symbol:{self.vt_symbol}, Please Connect the Api First.")
            self.inited = False
        else:
            self.inited = True
            self.contract_size = float(self.contract_data.size or 0)

        self.pos_calculator.pos = self.pos
        self.pos_calculator.avg_price = self.avg_price

        self.cta_engine.event_engine.register(EVENT_TIMER, self.process_timer)

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("Stop Strategy")
        self.cta_engine.event_engine.unregister(EVENT_TIMER, self.process_timer)

    def process_timer(self, event):
        self.timer_count += 1
        if self.timer_count >= 10:
            self.timer_count = 0

            # remove the lowest price buy order to keep the max open order count
            if len(self.long_orders_dict.keys()) > self.max_open_orders:

                vt = list(self.long_orders_dict.keys())[0]
                lowest_price = self.long_orders_dict[vt]
                cancel_order_id = None

                for orderid in self.long_orders_dict.keys():
                    order_price = self.long_orders_dict[orderid]
                    if lowest_price >= order_price:
                        cancel_order_id = orderid
                        lowest_price = order_price

                if cancel_order_id:
                    self.cancel_order(cancel_order_id)

            self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """

        if tick and tick.bid_price_1 > 0 and self.contract_data:
            self.tick = tick

            if self.upper_price - self.bottom_price <= 0:
                return

            step_price = (self.upper_price - self.bottom_price) / self.grid_number

            self.step_price = float(floor_to(step_price, self.contract_data.pricetick))

            # 启动时若启用首单建仓，则按指定量立即建仓
            if not self.initial_entry_filled:
                self._place_initial_entry()
                self.initial_entry_filled = True

            mid_count = round((float(self.tick.bid_price_1) - self.bottom_price) / self.step_price)

            if len(self.long_orders_dict.keys()) == 0:

                for i in range(self.max_open_orders):
                    price = self.bottom_price + (mid_count - i - 1) * self.step_price
                    if price < self.bottom_price:
                        return

                    orders_ids = self.buy(price, self.order_volume)
                    for orderid in orders_ids:
                        self.long_orders_dict[orderid] = price

    def _place_initial_entry(self) -> None:
        """
        启动时按 initial_entry_volume 指定的量立即建仓（限价单，价格=当前 bid）。
        记录返回的 orderid 到 initial_entry_order_ids，on_order 会用它识别是否为首单成交。
        """
        if self.initial_entry_volume <= 0:
            return

        current_price = float(self.tick.bid_price_1)
        self.initial_entry_grid = round(
            (current_price - self.bottom_price) / self.step_price
        )
        self.write_log(
            f"Initial entry: price={current_price}, "
            f"grid={self.initial_entry_grid}, "
            f"volume={self.initial_entry_volume}"
        )
        orders_ids = self.buy(current_price, self.initial_entry_volume)
        for orderid in orders_ids:
            self.initial_entry_order_ids.add(orderid)

    def _place_initial_take_profit_orders(self, base_grid: int, volume: float) -> None:
        """
        建仓成交后，在 base_grid+1, +2, ..., +volume 个网格各挂一张 sell 平多单。
        每张单量 = order_volume；最后一格若不够按 order_volume，则按剩余量下单。
        """
        if volume <= 0:
            return
        remaining = float(volume)
        count = int(volume)
        for offset in range(1, count + 1):
            sell_price = self.bottom_price + (base_grid + offset) * self.step_price
            if sell_price > self.upper_price:
                break
            v = self.order_volume if remaining > self.order_volume else remaining
            remaining -= v
            orders_ids = self.sell(sell_price, v)
            for orderid in orders_ids:
                self.sell_orders_dict[orderid] = sell_price

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        # 凡是本策略自己下过的单（被引擎回报回来的），都登记到归属集合
        # 这样 on_trade 里就能用 orderid 精确过滤归属
        self.my_order_ids.add(order.vt_orderid)

        is_initial_entry = order.vt_orderid in self.initial_entry_order_ids

        if order.vt_orderid not in (list(self.sell_orders_dict.keys()) + list(self.long_orders_dict.keys())):
            # 只关心已登记的网格单/平多单 + 首单建仓单；其它忽略
            if not is_initial_entry:
                return

        self.pos_calculator.update_position(order)
        self.avg_price = self.pos_calculator.avg_price

        if order.status == Status.ALLTRADED:

            if is_initial_entry:
                # 首单建仓成交 -> 在上方 N 个网格各挂一张 sell 平多单
                self.initial_entry_order_ids.discard(order.vt_orderid)
                if not self.initial_entry_profit_placed:
                    self.initial_entry_profit_placed = True
                    self._place_initial_take_profit_orders(
                        self.initial_entry_grid, self.initial_entry_volume
                    )
                self.put_event()
                return

            if order.vt_orderid in self.long_orders_dict.keys():
                del self.long_orders_dict[order.vt_orderid]

                self.trade_times += 1

                # 开多成交 -> 在上方一个网格挂一个卖单（平多）
                sell_price = float(order.price) + float(self.step_price)

                if sell_price <= self.upper_price:
                    orders_ids = self.sell(sell_price, self.order_volume)

                    for orderid in orders_ids:
                        self.sell_orders_dict[orderid] = sell_price

                # 若仍未挂满买单，补一张更低的买单
                if len(self.long_orders_dict.keys()) < self.max_open_orders:
                    count = len(self.long_orders_dict.keys()) + 1
                    long_price = float(order.price) - float(self.step_price) * count
                    if long_price >= self.bottom_price:
                        orders_ids = self.buy(long_price, self.order_volume)
                        for orderid in orders_ids:
                            self.long_orders_dict[orderid] = long_price

            elif order.vt_orderid in self.sell_orders_dict.keys():
                # 平多成交 -> 在下方一个网格补一张买单
                del self.sell_orders_dict[order.vt_orderid]

                self.trade_times += 1
                long_price = float(order.price) - float(self.step_price)
                if long_price >= self.bottom_price:
                    orders_ids = self.buy(long_price, self.order_volume)
                    for orderid in orders_ids:
                        self.long_orders_dict[orderid] = long_price

                # 若买单仍未挂满，向上挂平多单（即使价格已成交也能补到更高的网格上）
                if len(self.sell_orders_dict.keys()) < self.max_open_orders:
                    count = len(self.sell_orders_dict.keys()) + 1
                    sell_price = float(order.price) + float(self.step_price) * count

                    if sell_price <= self.upper_price:
                        orders_ids = self.sell(sell_price, self.order_volume)
                        for orderid in orders_ids:
                            self.sell_orders_dict[orderid] = sell_price

        if not order.is_active():
            if is_initial_entry:
                self.initial_entry_order_ids.discard(order.vt_orderid)
            elif order.vt_orderid in self.long_orders_dict.keys():
                del self.long_orders_dict[order.vt_orderid]

            elif order.vt_orderid in self.sell_orders_dict.keys():

                del self.sell_orders_dict[order.vt_orderid]

        self.put_event()

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.

        多策略归属：只用本策略下过的订单产生的成交来累计 realized_pnl / commission。
        浮动盈亏用最新 tick 算。
        """
        if trade.vt_orderid not in self.my_order_ids:
            return

        # 1) 已实现盈亏：只在平仓那一笔算
        #    只做多网格里：
        #      - 平多 = direction SHORT & offset CLOSE  → 盈利 = (卖价 - 均价) * 量 * 面值
        if trade.offset == Offset.CLOSE and self.avg_price > 0 and self.contract_size > 0:
            if trade.direction == Direction.SHORT:
                pnl = (float(trade.price) - float(self.avg_price)) * float(trade.volume) * self.contract_size
                self.realized_pnl += pnl
            elif trade.direction == Direction.LONG:
                pnl = (float(self.avg_price) - float(trade.price)) * float(trade.volume) * self.contract_size
                self.realized_pnl += pnl

        # 2) 累计手续费：开仓/平仓每笔都收
        commission = float(trade.commission or 0)
        if commission > 0 and trade.commission_asset and trade.commission_asset != "USDT":
            # 手续费扣的是标的币（如 BTC/BNB），按成交价折算 USDT
            commission = commission * float(trade.price)
        self.total_commission += commission

        # 3) 浮动盈亏：用最新 tick + 当前持仓均价
        if self.tick and self.pos and self.avg_price > 0 and self.contract_size > 0:
            if self.pos > 0:
                self.float_pnl = (float(self.tick.bid_price_1) - float(self.avg_price)) * self.pos * self.contract_size
            elif self.pos < 0:
                self.float_pnl = (float(self.avg_price) - float(self.tick.ask_price_1)) * abs(self.pos) * self.contract_size
            else:
                self.float_pnl = 0.0
        else:
            self.float_pnl = 0.0

        # 4) 合计 = 已实现 + 浮动 - 累计手续费
        self.total_pnl = self.realized_pnl + self.float_pnl - self.total_commission

        self.put_event()