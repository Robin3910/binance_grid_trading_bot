"""
Basic widgets for Binance Grid Trader.
"""

from typing import Any, Dict
from tzlocal import get_localzone
from PyQt5 import QtCore, QtGui, QtWidgets
from gridtrader.event import Event, EventEngine
from ..constant import Direction
from ..engine import MainEngine
from gridtrader.event import (
    EVENT_LOG,
    EVENT_CTA_STRATEGY,
    EVENT_ORDER
)
from ..utility import load_json, save_json

COLOR_LONG = QtGui.QColor("red")
COLOR_SHORT = QtGui.QColor("green")
COLOR_BID = QtGui.QColor(255, 174, 201)
COLOR_ASK = QtGui.QColor(160, 255, 160)
COLOR_BLACK = QtGui.QColor("black")

from ..engine import CtaEngine


DISPLAY_NAMES = {
    "strategy_name": "策略名称",
    "vt_symbol": "交易对",
    "class_name": "策略类型",
    "author": "作者",
    "upper_price": "价格上限",
    "bottom_price": "价格下限",
    "grid_number": "网格数量",
    "order_volume": "每格数量",
    "max_open_orders": "最大挂单数",
    "invest_coin": "投资币种",
    "inited": "已初始化",
    "trading": "交易中",
    "pos": "持仓",
    "time": "时间",
    "msg": "内容",
    "gateway_name": "接口",
    "symbol": "交易对",
    "type": "类型",
    "direction": "方向",
    "offset": "开平",
    "price": "价格",
    "volume": "委托数量",
    "traded": "已成交",
    "status": "状态",
    "datetime": "时间",
    "key": "API 密钥",
    "secret": "API 私钥",
    "proxy_host": "代理地址",
    "proxy_port": "代理端口",
    "futures_type": "合约类型",
    "futures_types": "合约类型",
}

ENUM_DISPLAY_NAMES = {
    "Long": "多",
    "Short": "空",
    "Net": "净",
    "OPEN": "开仓",
    "CLOSE": "平仓",
    "CLOSETODAY": "平今",
    "CLOSEYESTERDAY": "平昨",
    "SUBMITTING": "提交中",
    "NOTTRADED": "未成交",
    "PARTTRADED": "部分成交",
    "ALLTRADED": "全部成交",
    "CANCELLED": "已撤销",
    "REJECTED": "已拒绝",
    "LIMIT": "限价",
    "TAKER": "市价吃单",
    "MAKER": "挂单",
    "STOP": "止损市价",
    "STOP_LIMIT": "止损限价",
}


def get_display_name(name: str) -> str:
    return DISPLAY_NAMES.get(name, name)


class BaseCell(QtWidgets.QTableWidgetItem):
    """
    General cell used in tablewidgets.
    """

    def __init__(self, content: Any, data: Any):
        """"""
        super(BaseCell, self).__init__()
        self.setTextAlignment(QtCore.Qt.AlignCenter)
        self.set_content(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        Set text content.
        """
        self.setText(str(content))
        self._data = data

    def get_data(self) -> Any:
        """
        Get data object.
        """
        return self._data


class EnumCell(BaseCell):
    """
    Cell used for showing enum data.
    """

    def __init__(self, content: str, data: Any):
        """"""
        super(EnumCell, self).__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        Set text using enum.constant.value.
        """
        if content:
            super(EnumCell, self).set_content(
                ENUM_DISPLAY_NAMES.get(content.value, content.value), data
            )


class DirectionCell(EnumCell):
    """
    Cell used for showing direction data.
    """

    def __init__(self, content: str, data: Any):
        """"""
        super(DirectionCell, self).__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        Cell color is set according to direction.
        """
        super(DirectionCell, self).set_content(content, data)

        if content is Direction.SHORT:
            self.setForeground(COLOR_SHORT)
        else:
            self.setForeground(COLOR_LONG)


class TimeCell(BaseCell):
    """
    Cell used for showing time string from datetime object.
    """

    local_tz = get_localzone()

    def __init__(self, content: Any, data: Any):
        """"""
        super(TimeCell, self).__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """"""
        if content is None:
            return

        content = content.astimezone(self.local_tz)
        timestamp = content.strftime("%H:%M:%S")

        millisecond = int(content.microsecond / 1000)
        if millisecond:
            timestamp = f"{timestamp}.{millisecond}"

        self.setText(timestamp)
        self._data = data


class MsgCell(BaseCell):
    """
    Cell used for showing msg data.
    """

    def __init__(self, content: str, data: Any):
        """"""
        super(MsgCell, self).__init__(content, data)
        self.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)


class BaseMonitor(QtWidgets.QTableWidget):
    """
    Monitor data update in Binance Grid Trader.
    """

    event_type: str = ""
    data_key: str = ""
    sorting: bool = False
    headers: Dict[str, dict] = {}

    signal: QtCore.pyqtSignal = QtCore.pyqtSignal(Event)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super(BaseMonitor, self).__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine
        self.cells: Dict[str, dict] = {}

        self.init_ui()
        self.register_event()

    def init_ui(self) -> None:
        """"""
        self.init_table()
        self.init_menu()

    def init_table(self) -> None:
        """
        Initialize table.
        """
        self.setColumnCount(len(self.headers))

        labels = [d["display"] for d in self.headers.values()]
        self.setHorizontalHeaderLabels(labels)

        self.verticalHeader().setVisible(False)
        self.setEditTriggers(self.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(self.sorting)

    def init_menu(self) -> None:
        """
        Create right click menu.
        """
        self.menu = QtWidgets.QMenu(self)

        resize_action = QtWidgets.QAction("调整列宽", self)
        resize_action.triggered.connect(self.resize_columns)
        self.menu.addAction(resize_action)

    def register_event(self) -> None:
        """
        Register event handler into event engine.
        """
        if self.event_type:
            self.signal.connect(self.process_event)
            self.event_engine.register(self.event_type, self.signal.emit)

    def process_event(self, event: Event) -> None:
        """
        Process new data from event and update into table.
        """
        # Disable sorting to prevent unwanted error.
        if self.sorting:
            self.setSortingEnabled(False)

        # Update data into table.
        data = event.data

        if not self.data_key:
            self.insert_new_row(data)
        else:
            key = data.__getattribute__(self.data_key)

            if key in self.cells:
                self.update_old_row(data)
            else:
                self.insert_new_row(data)

        # Enable sorting
        if self.sorting:
            self.setSortingEnabled(True)

    def insert_new_row(self, data: Any):
        """
        Insert a new row at the top of table.
        """
        self.insertRow(0)

        row_cells = {}
        for column, header in enumerate(self.headers.keys()):
            setting = self.headers[header]

            content = data.__getattribute__(header)
            cell = setting["cell"](content, data)
            self.setItem(0, column, cell)

            if setting["update"]:
                row_cells[header] = cell

        if self.data_key:
            key = data.__getattribute__(self.data_key)
            self.cells[key] = row_cells

    def update_old_row(self, data: Any) -> None:
        """
        Update an old row in table.
        """
        key = data.__getattribute__(self.data_key)
        row_cells = self.cells[key]

        for header, cell in row_cells.items():
            content = data.__getattribute__(header)
            cell.set_content(content, data)

    def resize_columns(self) -> None:
        """
        Resize all columns according to contents.
        """
        self.horizontalHeader().resizeSections(QtWidgets.QHeaderView.ResizeToContents)


    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """
        Show menu with right click.
        """
        self.menu.popup(QtGui.QCursor.pos())


class LogMonitor(BaseMonitor):
    """
    Monitor for log data.
    """

    event_type = EVENT_LOG
    data_key = ""
    sorting = False

    headers = {
        "time": {"display": "时间", "cell": TimeCell, "update": False},
        "msg": {"display": "内容", "cell": MsgCell, "update": False},
        "gateway_name": {"display": "接口", "cell": BaseCell, "update": False},
    }


class ActiveOrderMonitor(BaseMonitor):
    """
    Monitor for order data.
    """

    event_type = EVENT_ORDER
    data_key = "vt_orderid"
    sorting = True

    headers: Dict[str, dict] = {
        "symbol": {"display": "交易对", "cell": BaseCell, "update": False},
        "type": {"display": "类型", "cell": EnumCell, "update": False},
        "direction": {"display": "方向", "cell": DirectionCell, "update": False},
        "offset": {"display": "开平", "cell": EnumCell, "update": False},
        "price": {"display": "价格", "cell": BaseCell, "update": False},
        "volume": {"display": "委托数量", "cell": BaseCell, "update": True},
        "traded": {"display": "已成交", "cell": BaseCell, "update": True},
        "status": {"display": "状态", "cell": EnumCell, "update": True},
        "datetime": {"display": "时间", "cell": TimeCell, "update": True},
        "gateway_name": {"display": "接口", "cell": BaseCell, "update": False},
    }

    def init_ui(self):
        """
        Connect signal.
        """
        super(ActiveOrderMonitor, self).init_ui()

        self.setToolTip("双击撤销委托")
        self.itemDoubleClicked.connect(self.cancel_order)

    def cancel_order(self, cell: BaseCell) -> None:
        """
        Cancel order if cell double clicked.
        """
        order = cell.get_data()
        req = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    def process_event(self, event) -> None:
        """
        Hides the row if order is not active.
        """
        super(ActiveOrderMonitor, self).process_event(event)

        order = event.data
        row_cells = self.cells[order.vt_orderid]
        row = self.row(row_cells["volume"])

        if order.is_active():
            self.showRow(row)
        else:
            self.hideRow(row)


class CtaManager(QtWidgets.QWidget):
    """"""

    signal_log = QtCore.pyqtSignal(Event)
    signal_strategy = QtCore.pyqtSignal(Event)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        super(CtaManager, self).__init__()

        self.main_engine = main_engine
        self.event_engine = event_engine
        self.cta_engine = main_engine.get_engine('strategy')

        self.managers = {}

        self.init_ui()
        self.register_event()
        self.cta_engine.init_engine()
        self.update_class_combo()

    def init_ui(self):
        """"""
        self.setWindowTitle("币安网格策略")

        # Create widgets
        self.class_combo = QtWidgets.QComboBox()

        add_button = QtWidgets.QPushButton("添加策略")
        add_button.clicked.connect(self.add_strategy)

        init_button = QtWidgets.QPushButton("初始化全部策略")
        init_button.clicked.connect(self.cta_engine.init_all_strategies)

        start_button = QtWidgets.QPushButton("启动全部策略")
        start_button.clicked.connect(self.cta_engine.start_all_strategies)

        stop_button = QtWidgets.QPushButton("停止全部策略")
        stop_button.clicked.connect(self.cta_engine.stop_all_strategies)

        clear_button = QtWidgets.QPushButton("清空日志")
        clear_button.clicked.connect(self.clear_log)

        self.scroll_layout = QtWidgets.QVBoxLayout()
        self.scroll_layout.addStretch()

        scroll_widget = QtWidgets.QWidget()
        scroll_widget.setLayout(self.scroll_layout)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_widget)

        # Set layout
        hbox1 = QtWidgets.QHBoxLayout()
        hbox1.addWidget(self.class_combo)
        hbox1.addWidget(add_button)
        hbox1.addStretch()
        hbox1.addWidget(init_button)
        hbox1.addWidget(start_button)
        hbox1.addWidget(stop_button)
        hbox1.addWidget(clear_button)

        grid = QtWidgets.QGridLayout()
        grid.addWidget(scroll_area, 0, 0, 2, 1)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(hbox1)
        vbox.addLayout(grid)

        self.setLayout(vbox)

    def update_class_combo(self):
        """"""
        self.class_combo.addItems(
            self.cta_engine.get_all_strategy_class_names()
        )

    def register_event(self):
        """"""
        self.signal_strategy.connect(self.process_strategy_event)

        self.event_engine.register(
            EVENT_CTA_STRATEGY, self.signal_strategy.emit
        )

    def process_strategy_event(self, event):
        """
        Update strategy status onto its monitor.
        """
        data = event.data
        strategy_name = data["strategy_name"]

        if strategy_name in self.managers:
            manager = self.managers[strategy_name]
            manager.update_data(data)
        else:
            manager = StrategyManager(self, self.cta_engine, data)
            self.scroll_layout.insertWidget(0, manager)
            self.managers[strategy_name] = manager

    def remove_strategy(self, strategy_name):
        """"""
        manager = self.managers.pop(strategy_name)
        manager.deleteLater()

    def add_strategy(self):
        """"""
        class_name = str(self.class_combo.currentText())
        if not class_name:
            return

        parameters = self.cta_engine.get_strategy_class_parameters(class_name)
        editor = SettingEditor(parameters, class_name=class_name)
        n = editor.exec_()

        if n == editor.Accepted:
            setting = editor.get_setting()
            vt_symbol: str = setting.pop("vt_symbol")
            strategy_name = setting.pop("strategy_name")

            if not vt_symbol.__contains__('.BINANCE'):
                vt_symbol += '.BINANCE'

            self.cta_engine.add_strategy(
                class_name, strategy_name, vt_symbol, setting
            )

    def clear_log(self):
        """"""
        if self.log_monitor:
            self.log_monitor.setRowCount(0)


class StrategyManager(QtWidgets.QFrame):
    """
    Manager for a strategy
    """

    def __init__(
            self, cta_manager: CtaManager, cta_engine: CtaEngine, data: dict
    ):
        """"""
        super(StrategyManager, self).__init__()

        self.cta_manager = cta_manager
        self.cta_engine = cta_engine

        self.strategy_name = data["strategy_name"]
        self._data = data

        self.init_ui()

    def init_ui(self):
        """"""
        self.setFixedHeight(300)
        self.setFrameShape(self.Box)
        self.setLineWidth(1)

        self.init_button = QtWidgets.QPushButton("初始化")
        self.init_button.clicked.connect(self.init_strategy)

        self.start_button = QtWidgets.QPushButton("启动")
        self.start_button.clicked.connect(self.start_strategy)
        self.start_button.setEnabled(False)

        self.stop_button = QtWidgets.QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_strategy)
        self.stop_button.setEnabled(False)

        self.edit_button = QtWidgets.QPushButton("编辑")
        self.edit_button.clicked.connect(self.edit_strategy)

        self.remove_button = QtWidgets.QPushButton("删除")
        self.remove_button.clicked.connect(self.remove_strategy)

        strategy_name = self._data["strategy_name"]
        vt_symbol = self._data["vt_symbol"]
        class_name = self._data["class_name"]
        author = self._data["author"]

        label_text = (
            f"{strategy_name}  -  {vt_symbol}  ({class_name})"
        )
        label = QtWidgets.QLabel(label_text)
        label.setAlignment(QtCore.Qt.AlignCenter)

        self.parameters_monitor = DataMonitor(self._data["parameters"])
        self.variables_monitor = DataMonitor(self._data["variables"])

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.init_button)
        hbox.addWidget(self.start_button)
        hbox.addWidget(self.stop_button)
        hbox.addWidget(self.edit_button)
        hbox.addWidget(self.remove_button)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(label)
        vbox.addLayout(hbox)
        vbox.addWidget(self.parameters_monitor)
        vbox.addWidget(self.variables_monitor)
        self.setLayout(vbox)

    def update_data(self, data: dict):
        """"""
        self._data = data

        self.parameters_monitor.update_data(data["parameters"])
        self.variables_monitor.update_data(data["variables"])

        # Update button status
        variables = data["variables"]
        inited = variables["inited"]
        trading = variables["trading"]

        if not inited:
            return

        self.init_button.setEnabled(False)

        if trading:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.remove_button.setEnabled(False)
            self.edit_button.setEnabled(False)
        else:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.remove_button.setEnabled(True)
            self.edit_button.setEnabled(True)

    def init_strategy(self):
        """"""
        self.cta_engine.init_strategy(self.strategy_name)

    def start_strategy(self):
        """"""
        self.cta_engine.start_strategy(self.strategy_name)

    def stop_strategy(self):
        """"""
        self.cta_engine.stop_strategy(self.strategy_name)

    def edit_strategy(self):
        """"""
        strategy_name = self._data["strategy_name"]

        parameters = self.cta_engine.get_strategy_parameters(strategy_name)
        editor = SettingEditor(parameters, strategy_name=strategy_name)
        n = editor.exec_()

        if n == editor.Accepted:
            setting = editor.get_setting()
            self.cta_engine.edit_strategy(strategy_name, setting)

    def remove_strategy(self):
        """"""
        result = self.cta_engine.remove_strategy(self.strategy_name)

        # Only remove strategy gui manager if it has been removed from engine
        if result:
            self.cta_manager.remove_strategy(self.strategy_name)


class DataMonitor(QtWidgets.QTableWidget):
    """
    Table monitor for parameters and variables.
    """

    def __init__(self, data: dict):
        """"""
        super(DataMonitor, self).__init__()

        self._data = data
        self.cells = {}

        self.init_ui()

    def init_ui(self):
        """"""
        labels = [get_display_name(name) for name in self._data.keys()]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)

        self.setRowCount(1)
        self.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(self.NoEditTriggers)

        for column, name in enumerate(self._data.keys()):
            value = self._data[name]

            cell = QtWidgets.QTableWidgetItem(str(value))
            cell.setTextAlignment(QtCore.Qt.AlignCenter)

            self.setItem(0, column, cell)
            self.cells[name] = cell

    def update_data(self, data: dict):
        """"""
        for name, value in data.items():
            cell = self.cells[name]
            cell.setText(str(value))


class SettingEditor(QtWidgets.QDialog):
    """
    For creating new strategy and editing strategy parameters.

    弹窗底部会实时计算并展示：
        - 预计最大投入 USDT = 参考价格 × 最大挂单数量 × 每格数量
        - 预计每格 USDT = 参考价格 × 每格数量
        - 每格利润 = (每格价差 / 参考价格) × 100%

    其中：
        参考价格 = (价格上限 + 价格下限) / 2
        每格价差 = (价格上限 - 价格下限) / 网格数量
    """

    # 在 SettingEditor 中需要参与计算的参数名
    COMPUTE_PARAM_NAMES = {"upper_price", "bottom_price", "grid_number", "order_volume", "max_open_orders"}

    # 计算结果展示标签映射
    COMPUTE_RESULT_LABELS = {
        "ref_price": "交易对参考价格",
        "max_invest": "预计最大投入 (USDT)",
        "per_grid_usdt": "预计每格 (USDT)",
        "per_grid_profit": "每格利润",
    }

    def __init__(
            self, parameters: dict, strategy_name: str = "", class_name: str = ""
    ):
        """"""
        super(SettingEditor, self).__init__()

        self.parameters = parameters
        self.strategy_name = strategy_name
        self.class_name = class_name

        self.edits = {}
        # 存放只读的计算结果展示控件（QLabel）
        self.compute_labels = {}

        self.init_ui()
        # 初始化后立刻触发一次计算，让用户一打开就能看到结果
        self.update_compute_result()

    def init_ui(self):
        """"""
        form = QtWidgets.QFormLayout()

        # Add vt_symbol and name edit if add new strategy
        if self.class_name:
            self.setWindowTitle(f"添加策略：{self.class_name}")
            button_text = "确认"
            parameters = {"strategy_name": "", "vt_symbol": ""}
            parameters.update(self.parameters)
        else:
            self.setWindowTitle(f"编辑参数：{self.strategy_name}")
            button_text = "确认"
            parameters = self.parameters

        for name, value in parameters.items():
            type_ = type(value)

            edit = QtWidgets.QLineEdit(str(value))
            if type_ is int:
                validator = QtGui.QIntValidator()
                edit.setValidator(validator)
            elif type_ is float:
                validator = QtGui.QDoubleValidator()
                edit.setValidator(validator)

            form.addRow(f"{get_display_name(name)} {type_}", edit)

            self.edits[name] = (edit, type_)

            # 只要是会参与计算的参数，绑定 textChanged 信号，触发实时计算
            if name in self.COMPUTE_PARAM_NAMES:
                edit.textChanged.connect(self.update_compute_result)

        # ---- 实时计算结果展示区 ----
        for key, display_name in self.COMPUTE_RESULT_LABELS.items():
            label = QtWidgets.QLabel("-")
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            label.setStyleSheet("color: #1a73e8;")
            self.compute_labels[key] = label
            form.addRow(f"{display_name}", label)

        button = QtWidgets.QPushButton(button_text)
        button.clicked.connect(self.accept)
        form.addRow(button)

        widget = QtWidgets.QWidget()
        widget.setLayout(form)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(scroll)
        self.setLayout(vbox)

    def update_compute_result(self):
        """
        当任意相关输入框变化时，实时刷新底部四个计算字段。
        任何一个字段为空或非法时，所有结果都置为 '-'。
        """
        def get_float(name: str) -> float:
            edit, _ = self.edits[name]
            text = edit.text().strip()
            if not text:
                raise ValueError(f"{name} empty")
            return float(text)

        try:
            upper_price = get_float("upper_price")
            bottom_price = get_float("bottom_price")
            grid_number = get_float("grid_number")
            order_volume = get_float("order_volume")
            max_open_orders = get_float("max_open_orders")

            # 防御性校验
            if upper_price <= 0 or bottom_price <= 0 or grid_number <= 0 or order_volume <= 0:
                raise ValueError("non-positive")

            ref_price = (upper_price + bottom_price) / 2.0
            max_invest = ref_price * max_open_orders * order_volume
            per_grid_usdt = ref_price * order_volume
            step_price = (upper_price - bottom_price) / grid_number
            per_grid_profit_pct = step_price / ref_price * 100.0

            self.compute_labels["ref_price"].setText(f"{ref_price:.6f}")
            self.compute_labels["max_invest"].setText(f"{max_invest:.6f}")
            self.compute_labels["per_grid_usdt"].setText(f"{per_grid_usdt:.6f}")
            self.compute_labels["per_grid_profit"].setText(f"{per_grid_profit_pct:.4f}%")
        except Exception:
            for label in self.compute_labels.values():
                label.setText("-")

    def get_setting(self):
        """"""
        setting = {}

        if self.class_name:
            setting["class_name"] = self.class_name

        for name, tp in self.edits.items():
            edit, type_ = tp
            value_text = edit.text()

            if type_ == bool:
                if value_text == "True":
                    value = True
                else:
                    value = False
            else:
                value = type_(value_text)

            setting[name] = value

        return setting


class ConnectDialog(QtWidgets.QDialog):
    """
    Start connection of a certain gateway.
    """

    def __init__(self, main_engine: MainEngine, gateway_name: str):
        """"""
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.gateway_name: str = gateway_name
        self.filename: str = f"connect_{gateway_name.lower()}.json"

        self.widgets: Dict[str, QtWidgets.QWidget] = {}

        self.init_ui()

    def init_ui(self) -> None:
        """"""
        self.setWindowTitle(f"连接 {self.gateway_name}")

        # Default setting provides field name, field data type and field default value.
        default_setting = self.main_engine.get_default_setting(
            self.gateway_name)

        # Saved setting provides field data used last time.
        loaded_setting = load_json(self.filename)

        # Initialize line edits and form layout based on setting.
        form = QtWidgets.QFormLayout()

        for field_name, field_value in default_setting.items():
            field_type = type(field_value)

            if field_type == list:
                widget = QtWidgets.QComboBox()
                widget.addItems(field_value)

                if field_name in loaded_setting:
                    saved_value = loaded_setting[field_name]
                    ix = widget.findText(saved_value)
                    widget.setCurrentIndex(ix)
            else:
                widget = QtWidgets.QLineEdit(str(field_value))

                if field_name in loaded_setting:
                    saved_value = loaded_setting[field_name]
                    widget.setText(str(saved_value))

            form.addRow(
                f"{get_display_name(field_name)} <{field_type.__name__}>", widget
            )
            self.widgets[field_name] = (widget, field_type)

        button = QtWidgets.QPushButton("确认")
        button.clicked.connect(self.connect)
        form.addRow(button)

        self.setLayout(form)

    def connect(self) -> None:
        """
        Get setting value from line edits and connect the gateway.
        """
        setting = {}
        for field_name, tp in self.widgets.items():
            widget, field_type = tp
            if field_type == list:
                field_value = str(widget.currentText())
            else:
                field_value = field_type(widget.text())
            setting[field_name] = field_value

        save_json(self.filename, setting)

        self.main_engine.connect(setting, self.gateway_name)

        self.accept()

