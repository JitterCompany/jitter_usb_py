from usbthread import USBThread
from device import Device
from device_list import DeviceList
from update_server import FirmwareUpdateServer


def default_device_builder(*args, **kwargs):
    """ Default device builder: builds a Device instance when called """
    return Device(*args, **kwargs)
    

class USB:

    # pass in a custom device_creator_func if you want to
    # use a custom Device subclass

    # TODO: remove protocol_ep, read_timeout params? they are only used for
    # the default device_builder
    def __init__(self, USB_VID, USB_PID,
            device_creator_func,
            firmware_update_server_enable=True,
            firmware_update_server_host='localhost',
            firmware_update_server_port=3853):
        
        self._usb_thread = USBThread()

        # inject _usb_thread as parameter each time a Device is created
        def device_creator_with_thread(*args, **kwargs):
            return device_creator_func(*args, **kwargs,
                    usb_thread=self._usb_thread)

        self._device_list = DeviceList(USB_VID, USB_PID,
                device_creator_with_thread)

        if firmware_update_server_enable:
            self._update_server = FirmwareUpdateServer(
                    (firmware_update_server_host, firmware_update_server_port),
                    [])
            self._update_server.start()
        else:
            self._update_server = None


    def quit(self):
        if self._update_server:
            self._update_server.stop()
        self._usb_thread.quit()


    def list_devices(self):
        """ get a list of all devices """
        return self._device_list.all()

    
    # TODO from own thread
    def poll(self):
        self._update_devicelist()

        if self._update_server:
            self._update_server.poll()

        while self._usb_thread.complete_control_task():
            pass
        while self._usb_thread.complete_write_task():
            pass
        while self._usb_thread.complete_read_task():
            pass


    def _update_devicelist(self):
        """ update list of devices: returns ([obsolete_list], [new_list]) """

        obsolete, new = self._device_list.update()
        if len(obsolete) or len(new):
            if self._update_server:
                self._update_server.update_device_list(self.list_devices())
        return (obsolete, new)

