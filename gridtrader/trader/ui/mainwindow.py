"""
Implements main window of Grid Trader.
"""

from functools import partial
from typing import Callable, Dict, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

import gridtrader
from gridtrader.event import EventEngine
from .widget import (
    ActiveOrderMonitor,
    LogMonitor,
    ConnectDialog
)

from ..engine import MainEngine
from ..utility import get_icon_path, load_json, TRADER_DIR
from .widget import  CtaManager


class MainWindow(QtWidgets.QMainWindow):
    """
    Main window of Grid Trader.
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super(MainWindow, self).__init__()
        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine

        self.window_title: str = f"币安网格交易器 {gridtrader.__version__} [{TRADER_DIR}]"

        self.widgets: Dict[str, QtWidgets.QWidget] = {}
        self.init_ui()
        self.init_menu()
        self.auto_connect()

    def init_ui(self) -> None:
        """"""
        self.setWindowTitle(self.window_title)

        """"""
        cta_widget, dock = self.create_dock(CtaManager, '策略管理', QtCore.Qt.LeftDockWidgetArea)

        self.create_dock(
            ActiveOrderMonitor, "活动委托", QtCore.Qt.RightDockWidgetArea
        )

        log_monitor, dock2 = self.create_dock(
            LogMonitor, "日志", QtCore.Qt.RightDockWidgetArea
        )

        cta_widget.log_monitor = log_monitor

    def init_menu(self) -> None:
        """"""
        bar = self.menuBar()

        # System menu
        sys_menu = bar.addMenu("配置币安 API")

        gateway_names = self.main_engine.get_all_gateway_names()
        for name in gateway_names:
            func = partial(self.connect, name)
            self.add_menu_action(sys_menu, f"连接 {name}", "connect.ico", func)

    def add_menu_action(
            self,
            menu: QtWidgets.QMenu,
            action_name: str,
            icon_name: str,
            func: Callable,
    ) -> None:
        """"""
        icon = QtGui.QIcon(get_icon_path(__file__, icon_name))

        action = QtWidgets.QAction(action_name, self)
        action.triggered.connect(func)
        action.setIcon(icon)

        menu.addAction(action)

    def create_dock(
            self,
            widget_class: QtWidgets.QWidget,
            name: str,
            area: int
    ) -> Tuple[QtWidgets.QWidget, QtWidgets.QDockWidget]:
        """
        Initialize a dock widget.
        """
        widget = widget_class(self.main_engine, self.event_engine)

        dock = QtWidgets.QDockWidget(name)
        dock.setWidget(widget)
        dock.setObjectName(name)
        dock.setFeatures(dock.NoDockWidgetFeatures)
        self.addDockWidget(area, dock)
        return widget, dock

    def connect(self, gateway_name: str) -> None:
        """
        Open connect dialog for gateway connection.
        """
        dialog = ConnectDialog(self.main_engine, gateway_name)
        dialog.exec_()

    def auto_connect(self) -> None:
        """
        Auto connect gateways with previously saved API settings.
        """
        setting_filename_map: Dict[str, Tuple[str, ...]] = {
            "Spot": ("api_key", "private_key"),
            "Futures": ("key", "secret"),
        }

        for gateway_name, required_fields in setting_filename_map.items():
            filename = f"connect_{gateway_name.lower()}.json"
            setting = load_json(filename)

            if not setting:
                continue

            if not all(str(setting.get(field, "")).strip() for field in required_fields):
                self.main_engine.write_log(
                    f"{gateway_name} 接口未配置完整的 API 信息,跳过自动连接。"
                )
                continue

            self.main_engine.write_log(f"自动连接 {gateway_name} 接口...")
            self.main_engine.connect(setting, gateway_name)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Call main engine close function before exit.
        """
        reply = QtWidgets.QMessageBox.question(
            self,
            "退出确认",
            "确定要退出吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply == QtWidgets.QMessageBox.Yes:
            for widget in self.widgets.values():
                widget.close()

            self.main_engine.close()

            event.accept()
        else:
            event.ignore()

    def open_widget(self, widget_class: QtWidgets.QWidget, name: str) -> None:
        """
        Open contract manager.
        """
        widget = self.widgets.get(name, None)
        if not widget:
            widget = widget_class(self.main_engine, self.event_engine)
            self.widgets[name] = widget

        if isinstance(widget, QtWidgets.QDialog):
            widget.exec_()
        else:
            widget.show()
