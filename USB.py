from usbthread import USBThread
from device import Device, make_device_builder
from device_list import DeviceList
from update_server import FirmwareUpdateServer


class USB:

    # pass in a custom device_creator_func if you want to
    # use a custom Device subclass
    def __init__(self, USB_VID, USB_PID,
            device_creator_func=None,
            protocol_ep=5,
            firmware_update_server_enable=True,
            firmware_update_server_host='localhost',
            firmware_update_server_port=3853):
        
        self._usb_thread = USBThread()

        if device_creator_func is None:
            device_creator_func = make_device_builder(self._usb_thread,
                    protocol_ep)
        self._device_list = DeviceList(USB_VID, USB_PID, device_creator_func)

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


    def update_devicelist(self):
        """ update list of devices: returns ([obsolete_list], [new_list]) """

        obsolete, new = self._device_list.update()
        if len(obsolete) or len(new):
            if self._update_server:
                self._update_server.update_device_list(self.list_devices())
        return (obsolete, new)


    def list_devices(self):
        """ get a list of all devices """
        return self._device_list.all()

    
    def complete_read_task(self):
        return self._usb_thread.complete_read_task()


    def complete_read_queue_length(self):
        return self._usb_thread.complete_read_queue_length()


    def poll(self):
        if self._update_server:
            self._update_server.poll()

        while self._usb_thread.complete_control_task():
            pass
        while self._usb_thread.complete_write_task():
            pass

