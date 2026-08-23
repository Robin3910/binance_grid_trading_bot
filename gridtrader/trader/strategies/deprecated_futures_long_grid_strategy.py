# 已废弃


from mimetypes import init
from typing import Dict, Optional, Union

from gridtrader.trader.engine import CtaEngine, EVENT_TIMER
from gridtrader.trader.object import ContractData, OrderData, Status, TickData, TradeData
from gridtrader.trader.utility import floor_to

from .template import CtaTemplate


class FuturesLongGridStrategy(CtaTemplate):
    """USDT perpetual grid strategy that opens and closes long positions only."""

    author = "51bitquant"

    upper_price = 0.0
    bottom_price = 0.0
    grid_number = 100
    order_volume = 0.05
    max_open_orders = 5
    initial_entry_enabled = True

    avg_price = 0.0
    step_price = 0.0
    trade_times = 0
    initial_entry_submitted = False
    grid_initialized = False
    initial_entry_grid = 0
    initial_entry_volume = 0.0

    parameters = [
        "upper_price",
        "bottom_price",
        "grid_number",
        "order_volume",
        "max_open_orders",
        "initial_entry_enabled",
    ]
    variables = [
        "avg_price",
        "step_price",
        "trade_times",
        "initial_entry_submitted",
        "grid_initialized",
        "initial_entry_grid",
        "initial_entry_volume",
    ]

    def __init__(
        self,
        cta_engine: CtaEngine,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.buy_orders: Dict[str, float] = {}
        self.buy_order_volumes: Dict[str, float] = {}
        self.initial_buy_order_ids = set()
        self.sell_orders: Dict[str, float] = {}
        self.sell_order_volumes: Dict[str, float] = {}
        self.initial_sell_order_ids = set()
        self.tick: Optional[TickData] = None
        self.contract_data: Optional[ContractData] = None
        self.timer_count = 0

    def on_init(self) -> None:
        self.write_log("Init long-only futures grid strategy")

    def on_start(self) -> None:
        self.write_log("Start long-only futures grid strategy")
        self.write_log(f"Parameters: upper={self.upper_price}, bottom={self.bottom_price}, grid_number={self.grid_number}, order_volume={self.order_volume}, max_open_orders={self.max_open_orders}, initial_entry_enabled={self.initial_entry_enabled}")
        self.write_log(f"Current state: inited={self.inited}, trading={self.trading}")

        self.contract_data = self.cta_engine.main_engine.get_contract(self.vt_symbol)
        if not self.contract_data:
            self.write_log(
                f"Could Not Find The Symbol:{self.vt_symbol}, Please Connect the Api First."
            )
            self.inited = False
            self.cta_engine.event_engine.register(EVENT_TIMER, self.process_timer)
            return

        self.inited = True

        self.cta_engine.event_engine.register(EVENT_TIMER, self.process_timer)
        self.write_log(f"Strategy on_start completed. contract: {self.vt_symbol}, pricetick={self.contract_data.pricetick}. trading will be set to True by engine after this method returns")

    def on_stop(self) -> None:
        self.write_log("Stop long-only futures grid strategy")
        self.cta_engine.event_engine.unregister(EVENT_TIMER, self.process_timer)

    def process_timer(self, event) -> None:
        self.timer_count += 1

        # Try to lazily load contract data if it is still missing.
        if not self.contract_data:
            self.contract_data = self.cta_engine.main_engine.get_contract(self.vt_symbol)
            if self.contract_data:
                self.write_log(f"Contract data loaded via timer: {self.vt_symbol}, pricetick={self.contract_data.pricetick}")

        if self.timer_count < 10:
            return

        self.timer_count = 0
        self.cancel_excess_buy_orders()
        self.put_event()

    def on_tick(self, tick: TickData) -> None:
        if not tick or tick.bid_price_1 <= 0:
            if not self.grid_initialized:
                self.write_log(f"Tick validation failed: tick exists={tick is not None}, bid_price_1={tick.bid_price_1 if tick else 'N/A'}")
            return

        if self.inited == False:
            self.write_log("策略未启动")
            return

        if not self.contract_data:
            self.contract_data = self.cta_engine.main_engine.get_contract(self.vt_symbol)
            if not self.contract_data:
                if not self.grid_initialized:
                    self.write_log(f"Waiting for contract data for {self.vt_symbol}")
                return
            self.write_log(f"Contract data loaded late: {self.vt_symbol}, pricetick={self.contract_data.pricetick}")

        if self.upper_price <= self.bottom_price or self.grid_number <= 0:
            self.write_log(f"Parameter validation failed: upper_price={self.upper_price}, bottom_price={self.bottom_price}, grid_number={self.grid_number}")
            return

        step_price = (self.upper_price - self.bottom_price) / self.grid_number
        self.step_price = float(floor_to(step_price, self.contract_data.pricetick))
        if self.step_price <= 0:
            self.write_log(f"Grid step calculation failed: calculated step={step_price}, rounded step={self.step_price}, pricetick={self.contract_data.pricetick}")
            return

        if not self.grid_initialized:
            self.write_log(f"First valid tick received: bid_price_1={tick.bid_price_1}, step_price={self.step_price}")

        self.tick = tick
        if not self.initial_entry_submitted:
            self.place_initial_entry_order()
            self.initial_entry_submitted = True

        if not self.grid_initialized:
            self.place_initial_buy_orders()
            self.grid_initialized = True

    def place_initial_entry_order(self) -> None:
        if not self.initial_entry_enabled:
            self.write_log("Initial entry disabled by configuration")
            return

        current_price = float(self.tick.bid_price_1)
        current_grid = round((current_price - self.bottom_price) / self.step_price)
        current_grid = max(0, min(self.grid_number, current_grid))
        initial_position_count = self.grid_number - current_grid
        
        self.write_log(f"Initial entry calculation: current_price={current_price}, current_grid={current_grid}, initial_position_count={initial_position_count}")
        
        if initial_position_count <= 0:
            self.write_log("Initial entry skipped because price is at or above the upper grid")
            return

        self.initial_entry_grid = current_grid
        self.initial_entry_volume = initial_position_count * self.order_volume
        self.write_log(f"Placing initial entry order: price={current_price}, volume={self.initial_entry_volume}")
        self.place_buy_order(current_price, self.initial_entry_volume, initial=True)

    def place_initial_buy_orders(self) -> None:
        mid_count = round((float(self.tick.bid_price_1) - self.bottom_price) / self.step_price)
        self.write_log(f"Placing initial grid buy orders: current_price={self.tick.bid_price_1}, mid_count={mid_count}, max_open_orders={self.max_open_orders}")
        
        placed_count = 0
        for index in range(self.max_open_orders):
            price = self.bottom_price + (mid_count - index - 1) * self.step_price
            if price < self.bottom_price:
                self.write_log(f"Grid order #{index+1} skipped: calculated price {price} is below bottom_price {self.bottom_price}")
                break
            self.write_log(f"Placing grid buy order #{index+1}: price={price}, volume={self.order_volume}")
            self.place_buy_order(price)
            placed_count += 1
        
        self.write_log(f"Placed {placed_count} initial grid buy orders")

    def place_buy_order(
        self, price: float, volume: Optional[float] = None, initial: bool = False
    ) -> None:
        if price < self.bottom_price or price > self.upper_price:
            self.write_log(f"Buy order rejected: price {price} is outside range [{self.bottom_price}, {self.upper_price}]")
            return

        volume = volume or self.order_volume
        if volume <= 0:
            self.write_log(f"Buy order rejected: volume {volume} is not positive")
            return

        self.write_log(f"Sending buy order: price={price}, volume={volume}, initial={initial}")
        order_ids = self.buy(price, volume)
        
        if not order_ids:
            self.write_log(f"Buy order failed: no order IDs returned from exchange")
            return
        
        for order_id in order_ids:
            self.buy_orders[order_id] = price
            self.buy_order_volumes[order_id] = volume
            if initial:
                self.initial_buy_order_ids.add(order_id)
            self.write_log(f"Buy order placed successfully: order_id={order_id}, price={price}, volume={volume}")

    def place_sell_order(
        self, price: float, volume: Optional[float] = None, initial: bool = False
    ) -> None:
        if price > self.upper_price:
            self.write_log(f"Sell order rejected: price {price} is above upper_price {self.upper_price}")
            return

        volume = volume or self.order_volume
        if volume <= 0:
            self.write_log(f"Sell order rejected: volume {volume} is not positive")
            return

        self.write_log(f"Sending sell order: price={price}, volume={volume}, initial={initial}")
        order_ids = self.sell(price, volume)
        
        if not order_ids:
            self.write_log(f"Sell order failed: no order IDs returned from exchange")
            return
        
        for order_id in order_ids:
            self.sell_orders[order_id] = price
            self.sell_order_volumes[order_id] = volume
            if initial:
                self.initial_sell_order_ids.add(order_id)
            self.write_log(f"Sell order placed successfully: order_id={order_id}, price={price}, volume={volume}")

    def place_initial_profit_orders(self) -> None:
        first_profit_grid = self.initial_entry_grid + 1
        for grid_index in range(first_profit_grid, self.grid_number + 1):
            price = self.bottom_price + grid_index * self.step_price
            self.place_sell_order(price, self.order_volume, initial=True)

    def cancel_excess_buy_orders(self) -> None:
        while len(self.buy_orders) > self.max_open_orders > 0:
            order_id = min(self.buy_orders, key=self.buy_orders.get)
            self.cancel_order(order_id)

    def on_order(self, order: OrderData) -> None:
        is_buy_order = order.vt_orderid in self.buy_orders
        is_sell_order = order.vt_orderid in self.sell_orders
        if not is_buy_order and not is_sell_order:
            return

        if order.status == Status.ALLTRADED:
            if is_buy_order:
                volume = self.buy_order_volumes.pop(order.vt_orderid, self.order_volume)
                is_initial_entry = order.vt_orderid in self.initial_buy_order_ids
                self.initial_buy_order_ids.discard(order.vt_orderid)
                del self.buy_orders[order.vt_orderid]
                self.trade_times += 1
                if is_initial_entry:
                    self.place_initial_profit_orders()
                else:
                    self.place_sell_order(float(order.price) + self.step_price, volume)

            elif is_sell_order:
                volume = self.sell_order_volumes.pop(order.vt_orderid, self.order_volume)
                is_initial_profit = order.vt_orderid in self.initial_sell_order_ids
                self.initial_sell_order_ids.discard(order.vt_orderid)
                del self.sell_orders[order.vt_orderid]
                self.trade_times += 1
                if not is_initial_profit:
                    self.place_buy_order(float(order.price) - self.step_price, volume)

        elif not order.is_active():
            if is_buy_order:
                del self.buy_orders[order.vt_orderid]
                self.buy_order_volumes.pop(order.vt_orderid, None)
                self.initial_buy_order_ids.discard(order.vt_orderid)
            elif is_sell_order:
                del self.sell_orders[order.vt_orderid]
                self.sell_order_volumes.pop(order.vt_orderid, None)
                self.initial_sell_order_ids.discard(order.vt_orderid)

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        if trade.direction.value == "Long":
            self.avg_price = float(trade.price)
        self.put_event()
