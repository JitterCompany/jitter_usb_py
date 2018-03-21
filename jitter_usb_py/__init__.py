"""
Jitter USB Py handles low level USB communication with Jitter USB Devices.

It provides a simple extendable API to interface with devices.
"""

from .USB import USB, default_device_builder
from .callback_queue import CallbackQueue
