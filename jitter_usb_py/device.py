import hashlib
import traceback
from collections import namedtuple

from .usbthread import USBReadTask, USBWriteTask, USBControlTask
from .default_commands import *

def parse(data):
    if data and len(data):
        return ''.join([chr(c) for c in data])
    return ''

def _hash_serial(serial):
    raw = hashlib.sha1(bytes(serial, 'utf-8')).hexdigest()[:12]
    return raw[:4] + '-' + raw[4:8] + '-' + raw[8:]

VENDOR_REQUEST = namedtuple('VendorRequest', ['req', 'cb'])


def _noparams_callback(original_func):
    if not original_func:
        return None

    def wrapper(*args, **kwargs):
        return original_func()
    return wrapper

def _data_callback(original_func):
    if not original_func:
        return None

    def wrapper(*args, **kwargs):
        return original_func(args[0].data)
    return wrapper

class Device:

    def __init__(self, usb_device, usb_thread,
            protocol_ep, read_timeout):
        self._configured = False
        self.usb = usb_device
        self._usb_thread = usb_thread
        self._protocol_ep=protocol_ep
        self._read_timeout = read_timeout

        self.full_serial_number = self.usb.serial_number
        self.serial_number = _hash_serial(self.usb.serial_number)

        # these are publicly accessible via self.<propertyname>
        # and are auto-updated by USB vendor-requests.
        self._properties  = {
                'init_done':            False,
        }
        self._on_change = {}
        self._auto_vendor_requests = []
        self._before_init = []

        self._add_vendor_request(GET_NAME,                'name'),
        self._add_vendor_request(GET_FIRMWARE_VERSION,    'fw_version'),
        self._add_vendor_request(GET_BOOTLOADER_VERSION,  'bootloader_version'),
        self._add_vendor_request(GET_HARDWARE_VERSION,    'hardware_version'),
        self._add_vendor_request(GET_BATTERY_VOLTAGE,     'battery_voltage'),
        self._add_vendor_request(GET_PROGRAM_STATE,       'program_state'),
        self.update_metadata()
        self._on_text = None

    def __getattr__(self, key):
        """ getter: allows external access to self._properties """

        if not key in self._properties:
            raise AttributeError()
        return self._properties[key]

    def _set(self, key, value):
        if not key in self._properties:
            raise AttributeError()
        prev = self._properties[key]
        self._properties[key] = value
        if key in self._on_change and not value == prev:
            for func in self._on_change[key]:
                func(self, key, value)




    def _add_vendor_request(self, req_id, property_name,
            before_init=True, transform=None):
        """
        define a public property, whose value is the result from
        the usb vendor-request with id 'req_id'.

        Example: dev._add_vendor_request(GET_NAME, 'name')
        dev.name is auto-updated (async) with the result from GET_NAME
        """

        # make sure the property exists
        if not property_name in self._properties:
            self._properties[property_name] = ''

        # parse as string by default
        if not transform:
            transform = parse

        # wrap _set() with the right attribute name
        def wrapped_set(data):
            self._set(property_name, transform(data))

        self._auto_vendor_requests.append(VENDOR_REQUEST(req_id, wrapped_set))
        if before_init:
            self._before_init.append(req_id)



    def _handle_protocol_data(self, task):
        if not self._on_text or not len(task.data):
            return

        text = ''.join([chr(c) for c in task.data])
        lines = text.split('\n')
        if self._on_text:
            for l in lines:
                if l:
                    self._on_text(self, l)


    def _blacklist_vendor_request(self, request_id):
        for req in self._auto_vendor_requests:
            if req.req == request_id:
                self._auto_vendor_requests.remove(req)
        if request_id in self._before_init:
            self._before_init.remove(request_id)



    #### public low-level API ####

    def set_configuration(self):
        """Marks this Device as 'configured': the Device is ready for use"""
        if not self._configured:
            try:
                self.usb.set_configuration()
                self._configured = True
                self.read(self._protocol_ep, 512, self._read_timeout,
                        repeat=True,
                        on_complete=self._handle_protocol_data)
            except:
                print(traceback.format_exc())


    def remove(self):
        """Marks this Device as 'removed': the Device cannot be used anymore"""

        # usbthread will stop processing events & cleanup libusb stuff
        self._usb_thread.remove_device(self)

        # set a flag indicating this device is no longer configured
        self._configured = False


    def read(self, ep, length, timeout=10, on_complete=None,
            repeat=False, sync=False):

        task = USBReadTask(self, ep, length, timeout=timeout,
            on_complete=on_complete, repeat=repeat)
        self._usb_thread.addReadTask(task, new_repeat=repeat)
        return task


    def cancel_autoreads(self, ep_list):
        self._usb_thread.cancel_autoreads(self, ep_list)


    def write(self, ep, data, timeout=10, on_complete=None, on_fail=None,
            sync=False):
        task = USBWriteTask(self, ep, data, timeout=timeout,
            on_complete=on_complete, on_fail=on_fail)
        self._usb_thread.addWriteTask(task, sync)
        return task


    def control_request(self, request, ep=0, dir='out',
            value=0, index=0,
            data=None, length=None, timeout=10,
            on_complete=None, on_fail=None,
            max_retries=3, sync=False):

        task = USBControlTask(self, request, ep=ep, dir=dir,
                value=value, index=index,
                data=data, length=length, timeout=timeout,
                on_complete=on_complete, on_fail=on_fail,
                max_retries=max_retries)
        self._usb_thread.addControlTask(task, sync)


    def vendor_request(self, request):

        def fail_cb(task):
            self._blacklist_vendor_request(task.request)

        def _data_callback(original_func):

            def wrapper(*args, **kwargs):

                # set _init_done=True when all vendor requests have been
                # called at least once (or blacklisted)
                if not self.init_done and request.req in self._before_init:
                    self._before_init.remove(request.req)
                    if not self._before_init:
                        self._set('init_done', True)
                
                return original_func(args[0].data)
            return wrapper


        self.control_request(request.req,
            dir="in", length=64,
            on_complete=_data_callback(request.cb), on_fail=fail_cb,
            max_retries=2, sync=True)


    def update_metadata(self):
        for req in self._auto_vendor_requests:
            self.vendor_request(req)




    #### public high-level API ####

    def send_terminal_command(self, cmd):
        self.control_request(TERMINAL_CMD, data=cmd)

    def on_change(self, property_name, cb):
        """
        cb(Device, 'property', <new_value>) is called
        whenever the selected property has changed.

        Example: dev.on_change('battery_voltage', myfunc).

        As soon as battery_voltage changes (e.g. from 0 to 5000),
        the callback is called: myfunc(dev, 'battery_voltage', 5000)
        """
        if not property_name in self._on_change:
            self._on_change[property_name] = []
        self._on_change[property_name].append(cb)


    def on_text(self, cb):
        """ cb(Device, line) is called for each line of incoming text """
        self._on_text = cb

    def stop(self, on_complete=None):
        """ Send a stop command. Optional callback has no params """
        self.control_request(GENERAL_CMD, value=CMD_STOP,
                sync=True, on_complete=_noparams_callback(on_complete))

    def start(self, on_complete=None):
        """ Send a start command. Optional callback has no params """
        self.control_request(GENERAL_CMD, value=CMD_START,
                sync=True, on_complete=_noparams_callback(on_complete))

    def reboot(self, on_complete=None):
        """ Reboot the device. Optional callback has no params """
        self.control_request(GENERAL_CMD, value=CMD_REBOOT,
                sync=True, on_complete=_noparams_callback(on_complete))

    def upload_file(self, dst_filename, src_filename, on_complete=None):
        """ Upload a file to device. Optional callback receives filename """

        with open(src_filename, 'rb') as f:
            data = f.read()

        if on_complete:
            def wrapped_cb(_):
                on_complete(dst_filename)
            onCOmplete = wrapped_cb
        self._upload_data(dst_filename, data, on_complete=on_complete)

    def _upload_data(self, dst_filename, binary_data, on_complete=None):

        l = len(binary_data)
        task = self.control_request(UPLOAD_FILE,
            value=l & 0xFFFF,           # low 16 bits of size
            index= (l >> 16) & 0xFFFF,  # high 16 bits of size
            data=dst_filename, timeout=1000,
            sync=True)
        self.write(self._protocol_ep, binary_data, 60000, sync=True,
                on_complete=on_complete)


    def __str__(self):
        return '{}'.format(self.serial_number)

