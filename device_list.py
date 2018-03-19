import threading
import queue
import time

import usb.core
import usb.util

from device import Device

#NOTE: hotplug support is avaliable in pyusb jitter-1.1
if usb.__version__.startswith('jitter'):
    import usb.hotplug as hotplug
else:
    try:
        import usb.hotplug as hotplug
    except:
        print('\033[93m' + "WARNING: no hotplug support!")
        print('\033[93m' + "WARNING: this requires pyusb > jitter-1.1"
                + ", see JitterCompany/pyusb.git")
        print('\033[0m')
    hotplug = None

def _device_in_list(dev, usb_dev_list):
    for d in usb_dev_list:
        if (dev.bus == d.bus
                and dev.address == d.address
                and dev.idVendor == d.idVendor
                and dev.idProduct == d.idProduct):
            return True
    return False

class DeviceList:

    def __init__(self, vendor_id, product_id, device_creator_func):
        
        self._device_create = device_creator_func
        self._devices = []
        self._usb_VID = vendor_id
        self._usb_PID = product_id

        self.hotplugEventQueue = queue.Queue() 
        
        if hotplug is not None:
            event_mask = (hotplug.LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED
                    | hotplug.LIBUSB_HOTPLUG_EVENT_DEVICE_LEFT)
            flags = hotplug.LIBUSB_HOTPLUG_NO_FLAGS
            dev_class = hotplug.LIBUSB_HOTPLUG_MATCH_ANY

            # NOTE: we MUST keep a reference to hotplug_handle to avoid segfaults
            # in pyusb
            self.hotplug_handle = hotplug.register_callback(event_mask, flags,
                    self._usb_VID, self._usb_PID, dev_class, self._hotplug_cb, 0)
            self.hotplug_iterator = hotplug.loop()

        self.usbEventThread = threading.Thread(target=self._usb_handle_events)
        self.usbEventThread.daemon = True
        self.usbEventThread.start()

        self.first_time = True

    def _has_changed(self):
        """ Returns True if device list has changed """
        
        if not self.first_time:
            if self.hotplugEventQueue.empty():
                return False

        self.first_time = False
        
        # empty event queue
        while not self.hotplugEventQueue.empty():
            try:
                self.hotplugEventQueue.get(False)
            except queue.Empty:
                continue

        return True

    def all(self):
        """ Returns all devices. Call update() first to update the list """
        return self._devices

    def update(self):
        """ returns (obsolete[], new[]) devices since last update """
        obsolete = []
        new = []

        if not self._has_changed():
            return (obsolete, new)

        prev_devices = self._devices
        found_usb_devices = list(self._find_devices())
        self._devices = []

        # close obsolete devices
        for dev in prev_devices:
            if not _device_in_list(dev.usb, found_usb_devices):
                # obsolete: close

                print("==== RM device: ====")
                print(str(dev));
                obsolete.append(dev)
                dev.remove()
            else:
                # still active: keep
                self._devices.append(dev)
      
        # configure new devices
        for usb_dev in found_usb_devices:
            if not _device_in_list(usb_dev, [d.usb for d in prev_devices]):
                # new: add

                # create new device with usb_dev as argument
                dev = self._device_create(usb_device=usb_dev)

                print("==== NEW device: ====")
                print(str(dev))
                new.append(dev)
                self._devices.append(dev)
                dev.set_configuration()
        
        return (obsolete, new)

    def _usb_handle_events(self):

        # hotplug support: submit real hotplug events when they happen
        if hotplug is not None:
            while True:
                #hotplugging
                next(self.hotplug_iterator)
                time.sleep(0.1)

        # no hotplug support: emulate it by submitting fake hotplug events
        # every n seconds. This should cause the high-level logic
        # to check for changed devices.
        else:
            while True:
                self.hotplugEventQueue.put(None)
                time.sleep(2.0)


    def _hotplug_cb(self, usb_device, event, dummy_ctx):
        print("==== Hotplug ====", usb_device._str(), event)

        self.hotplugEventQueue.put(event)
        return 0

    def _find_devices(self):
        return usb.core.find(idVendor=self._usb_VID, idProduct=self._usb_PID, 
                find_all=True)

