"""Application entry point: `python -m ghost_ai` or the `ghost-ai` script."""

from __future__ import annotations

import logging
import sys

from . import APP_NAME, __version__
from .config import AppConfig, data_dir, setup_logging

log = logging.getLogger("ghost_ai")


def build_context():
    from .engine.service import AutomationService
    from .i18n import set_language
    from .storage.db import Store
    from .ui.context import AppContext

    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    log_file = setup_logging(root / "logs")
    config = AppConfig.load(root / "config.json")
    store = Store(root / "ghost.db")
    if store.get("language") is None:
        from PySide6.QtCore import QLocale
        store.set("language", "hr" if QLocale.system().name().startswith("hr") else "en")
    set_language(store.get("language", "en"))
    service = AutomationService(store, str(root), settle_seconds=config.settle_seconds)
    log.info("%s %s starting, data in %s", APP_NAME, __version__, root)
    return AppContext(service=service, store=store, config=config, data_dir=root, log_file=log_file)


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("GHOST AI")

    from .ui.main_window import MainWindow, app_icon

    app.setWindowIcon(app_icon())
    ctx = build_context()
    ctx.service.start_watching()
    win = MainWindow(ctx)
    win.show()
    if not ctx.setting("onboarded", False):
        from .ui.onboarding import Onboarding
        Onboarding(ctx, win).exec()
    code = app.exec()
    ctx.service.stop_watching()
    ctx.store.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
