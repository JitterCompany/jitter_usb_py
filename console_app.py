#!/usr/bin/env python

import os
import signal
import sys

from PyQt5.QtWidgets import QApplication
from PyQt5 import QtGui, QtCore

from console_app_gui import MainView

from status_widget import StatusWidget
from terminal import Terminal
from debuglog import DebugLog
from console import ConsoleView
from USB import USB, default_device_builder


#### Settings ####
USB_VID                 = 0x3853
USB_PID                 = 0x0021

PROTOCOL_EP             = 5
READ_TIMEOUT            = 1
POLL_INTERVAL_MS        = 10
POLL_INTERVAL_SLOW_MS   = 1000
TERMINAL_PREFIX         = "Info: terminal:"



class ConsoleApp:

    def __init__(self):
        self._running = True
        self._status = StatusWidget()
        self._terminal = Terminal(self._terminal_cmd_to_current_device)
        self._console = ConsoleView()
        self._debuglog = DebugLog()
        self._USB = USB(USB_VID, USB_PID,
                device_creator_func=self._device_builder,
                firmware_update_server_enable=True)

        self._console.addView(self._terminal.view, 'Terminal')
        self._console.addView(self._debuglog.view, 'Log')
        self._view = MainView(self, self._console, 'USB Console')
        self._view.show()
        self._view.create_tool_bar(self._status)

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._timer_poll)
        self._timer.start(POLL_INTERVAL_MS)

        self._slow_timer = QtCore.QTimer()
        self._slow_timer.timeout.connect(self._slow_timer_poll)
        self._slow_timer.start(POLL_INTERVAL_SLOW_MS)

        self._selected_device = None


    def _device_builder(self, *args, **kwargs):
        """ USB calls this function each time a new Device is constructed """
        device = default_device_builder(*args, **kwargs,
                protocol_ep=PROTOCOL_EP, read_timeout=READ_TIMEOUT)

        # subscribe on text output
        device.on_text(self._process_line)
        return device


    def _timer_poll(self):
        """ Frequently complete control+read tasks """
        
        # TODO this will move to its own thread...
        self._USB.poll()


    def _slow_timer_poll(self):
        if not self._selected_device in self._USB.list_devices():
            self.select_device_at(0)

        self._update_views()


    def _update_views(self):
        devices = self._USB.list_devices()
        self._view.set_devices(devices)

        self._status.refresh()


    def quit(self, signal=None, frame=None):
        if not self._running:
            return
        self._running = False

        if signal is not None:
            self._view.close()
        self._USB.quit()
        print("Bye")




    #### GUI <--> USB glue logic: ####

    def _process_line(self, dev, line):
        if not line:
            return

        if line.startswith(TERMINAL_PREFIX):
            self._terminal.add(line[len(TERMINAL_PREFIX):]+'\n')
            return
        else:
            self._debuglog.add(dev, line)


    def _terminal_cmd_to_current_device(self, cmd):
        if not self._selected_device:
            print("failed to send command: no selected_device")
            return
        self._selected_device.send_terminal_command(cmd)


    def select_device_at(self, index):
        devices = self._USB.list_devices()
        if (0 <= index < len(devices)):
            self._selected_device = devices[index]
            print("Selecting device", self._selected_device.serial_number)

        elif self._selected_device:
            self._selected_device = None
            print("No selected device")

        self._status.select_device(self._selected_device)
        self._debuglog.select_device(self._selected_device)




def main():
    app = QApplication([])
    app.setWindowIcon(QtGui.QIcon('assets/blue-icon.png'))
    c = ConsoleApp()

    signal.signal(signal.SIGINT, c.quit)

    if (sys.flags.interactive != 1):
        sys.exit(app.exec_())


if __name__ == '__main__':
    main()

