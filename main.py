import logging
import sys

from PyQt6.QtWidgets import QApplication

from dis_radio.config import DEFAULT_CONFIG_PATH, load
from dis_radio.gui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def main() -> None:
    config = load(DEFAULT_CONFIG_PATH)
    app = QApplication(sys.argv)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
