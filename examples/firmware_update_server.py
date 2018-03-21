#!/usr/bin/env python

import time

from jitter_usb_py.update_server import FirmwareUpdateServer


def run_demo(host, port):
    server = FirmwareUpdateServer((host, port))
    server.start()

    # add some dummy devices
    class DummyDevice:
        def __init__(self, serial_number):
            self.serial_number = serial_number

        def upload_file(self, dst_fname, src_fname, on_complete=None):
            print("Dummy device {}: 'upload' file '{}' as '{}'".format(
                self.serial_number, src_fname, dst_fname))
            on_complete(dst_fname)

        def stop(self, on_complete=None):
            print("Dummy device {}: 'stop'".format(
                self.serial_number))
            if on_complete:
                on_complete()

        def reboot(self, on_complete=None):
            print("Dummy device {}: 'reboot'".format(
                self.serial_number))
            if on_complete:
                on_complete()


    dummies = [DummyDevice("1234-5678-0000"), DummyDevice("3333-4444-5555")]
    server.update_device_list(dummies)
   
    try:
        while True:
            time.sleep(1)
            server.poll()         

    except KeyboardInterrupt:
        print("\rExit")
    
    server.stop()

if __name__ == "__main__":
    run_demo("localhost", 3853)

