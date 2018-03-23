import traceback
import time
from threading import Thread

from .usbthread import USBThread
from .device import Device
from .device_list import DeviceList
from .update_server import FirmwareUpdateServer


POLL_INTERVAL_FAST_SEC = 0.1
POLL_INTERVAL_SLOW_SEC = 1.5


def default_device_builder(*args, **kwargs):
    """ Default device builder: builds a Device instance when called """
    return Device(*args, **kwargs)


def _differ_lists(l1, l2):
    """ Compare two lists of objects

    Parameters
    ----------
    l1, l2: lists

    Returns:
        True if different
    """
    is_different = False
    l2_copy = list(l2)
    for dev in l1:
        if not dev in l2_copy:
            is_different = True
            break
        else:
            l2_copy.remove(dev)

    return is_different or l2_copy


class USB:
    """
    pass in a custom device_creator_func, for example if you want to
    use a custom Device subclass or add Device init code
    """

    def __init__(self, USB_VID, USB_PID,
                 device_creator_func,
                 firmware_update_server_enable=True,
                 firmware_update_server_host='localhost',
                 firmware_update_server_port=3853):

        self._usb_thread = USBThread()

        # inject _usb_thread as parameter each time a Device is created
        def _device_creator_with_thread(*args, **kwargs):
            return device_creator_func(*args, **kwargs,
                                       usb_thread=self._usb_thread)

        self._device_list = DeviceList(USB_VID, USB_PID,
                                       _device_creator_with_thread)

        if firmware_update_server_enable:
            self._update_server = FirmwareUpdateServer(
                (firmware_update_server_host, firmware_update_server_port), [])
            self._update_server.start()
        else:
            self._update_server = None


        self._running = True
        self._event_thread = Thread(target=self._run)
        self._event_thread.deamon = True
        self._event_thread.start()

    def quit(self):
        self._running = False
        start_quit = time.time()

        while self._running is not None:
            if time.time() - start_quit > 4:
                print("\rUSB: thread crashed, force quit")
                break

        if self._update_server:
            self._update_server.stop()

        self._device_list.quit()
        self._usb_thread.quit()

        # remove all devices
        for dev in self.list_devices():
            dev.remove()


    def list_devices(self, prev_list=None):
        """
        get a list of all devices

        Parameters
        ----------
        prev_list: list of devices, optional
            If a (previous) list of devices is passed
            to this function, change detection will be performed
            and an extra return value will indicate whether the
            device list differs from the list returned

        Returns
        -------
        device_list: list of devices
            All devices currently connected
        changed: boolean, optional
            True if device_list differs from prev_list.
            Only returned if prev_list is not None
        """
        new_list = self._device_list.all()

        if prev_list is not None:
            return (new_list, _differ_lists(prev_list, new_list))

        return new_list

    # This runs in a separate thread
    def _run(self):
        last_slow = time.time()
        try:
            while self._running:
                self._poll()
                time.sleep(POLL_INTERVAL_FAST_SEC)

                if time.time() - last_slow > POLL_INTERVAL_SLOW_SEC:
                    last_slow = time.time()
                    self._slow_poll()

        except Exception:
            print(traceback.format_exc())
            print("USB: caught exception, stopping thread")

        # end of thread
        self._running = None

    def _poll(self):
        self._update_devicelist()

        if self._update_server:
            self._update_server.poll()

        while self._usb_thread.complete_control_task():
            pass
        while self._usb_thread.complete_write_task():
            pass
        while self._usb_thread.complete_read_task():
            pass


    def _slow_poll(self):
        for dev in self.list_devices():
            dev.update_metadata()


    def _update_devicelist(self):
        """ update list of devices: returns ([obsolete_list], [new_list]) """

        obsolete, new = self._device_list.update()
        if obsolete or new:
            if self._update_server:
                self._update_server.update_device_list(self.list_devices())
        return (obsolete, new)
