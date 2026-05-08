"""Broker factory — detects OS and presents valid broker options."""
from __future__ import annotations
import platform

import questionary

from .base_broker import BaseBroker


def select_broker() -> BaseBroker:
    is_windows = platform.system() == "Windows"

    choices = [
        questionary.Choice("Paper Trade  (simulated, no setup required)", value="paper"),
        questionary.Choice("MT5 via Wine  (real XM account on Mac via Whisky + file bridge)", value="mt5_file"),
    ]
    if is_windows:
        choices.append(
            questionary.Choice("MT5 Direct  (real XM account, native Windows MT5)", value="mt5_direct")
        )

    broker_key = questionary.select(
        "Select broker:",
        choices=choices,
    ).ask()

    if broker_key is None:
        raise KeyboardInterrupt

    if broker_key == "paper":
        from .paper_broker import PaperBroker
        return PaperBroker()
    elif broker_key == "mt5_file":
        from .mt5_file_broker import MT5FileBroker
        return MT5FileBroker()
    else:
        from .mt5_direct_broker import MT5DirectBroker
        return MT5DirectBroker()
