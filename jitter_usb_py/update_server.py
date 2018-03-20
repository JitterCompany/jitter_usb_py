#!/usr/bin/env python

import threading
import socket
import socketserver
import time
import queue

def list_to_str(l):
    ret = ""
    for i in l:
        ret+= str(i) + ","
    
    if len(ret):
        ret = ret[:-1]

    return ret

def encode(string):
    return bytes(string, 'ascii')

def decode(bytestr):
    return str(bytestr, 'ascii')



class FirmwareTask:

    def __init__(self, device, fw_files):
        """ Init FirmwareTask: fw_files is a {'dst_name': 'src_fname'} dict"""
        self._device = device
        self._fw_files = fw_files

        self._result = None

    def execute(self):
        """ Perform a firmware update from main/USB thread"""
       
        if not self._device:
            print("WARNING: dummy mode!")
            self._result = False
            return

        print("updating device {}: prepare for update".format(
            self._device.serial_number))

        self._device.stop()

        for dst_fname, src_fname in self._fw_files.items():
            self._device.upload_file(dst_fname, src_fname,
                    on_complete=self._on_upload_cb)
            
        self._device.reboot(on_complete=self._on_reboot_cb)

    def _on_upload_cb(self, fname):
        print("updating device {}: file {} uploaded".format(
            self._device.serial_number, fname))

    def _on_reboot_cb(self):
        print("updating device {}: reboot done!".format(
            self._device.serial_number))
        self._result =True
        

    def wait(self, timeout_sec=5):
        """ Wait untill the task is done, returns False on timeout"""
        interval = 0.1
        while (timeout_sec > 0) and (self._result is None):
            time.sleep(interval)
            timeout_sec-= interval

        return self._result



class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        
        print("\n==== Firmware Update Request ====")
        devices = [d.serial_number for d in self.server.get_device_list()]
        header = "devices=" + list_to_str(devices)
        self.request.sendall(encode(header))

        data = decode(self.request.recv(1024*1024)).split("\n")

        response = self._process_client_command(data)
        self.request.sendall(encode(response))
        print("=" * 33)
   
    def _process_client_command(self, data):

        FILE_PREFIX = 'file:'
        # received params
        to_update = []
        fw_files = {}
            
        # parse commands from client
        for line in data:
            tokens = line.split('=')
            if len(tokens) < 2:
                continue
            key = tokens[0]
            value = line[len(key):].strip('=')
            
            # fw_*[.bin]=<src_filename> uploads <src_filename> as fw_*.bin 
            if key.startswith('fw_'):
                dst_name = key
                if not dst_name.endswith('.bin'):
                    dst_name+= '.bin'
                fw_files[dst_name] = value

            # file:<src_fname>=<src_fname> uploads <src_fname> as <dst_fname>
            elif key.startswith(FILE_PREFIX):
                dst_name = key[len(FILE_PREFIX):]
                fw_files[dst_name] = value

            # update_devices=<csv_devicelist> updates all devices in the list 
            elif key == 'update_devices':
                to_update = [v.strip() for v in value.split(',')]

            else:
                print("API WARNING: unknown key '{}'".format(key))
        
        updated = []
        for dev_id in to_update:
            if self._do_firmware_upgrade(dev_id, fw_files):
                updated.append(dev_id)
            else:
                print("updating device {}: fail or timeout".format(dev_id))

        response = "updated=" + list_to_str(updated)

        return response

    def _find_device(self, dev_id):
        devices = self.server.get_device_list()
        for dev in devices:
            if dev.serial_number == dev_id:
                return dev
        return None

    def _do_firmware_upgrade(self, dev_id, fw_files):
        dst_names = [dst for dst in fw_files]
        print("Update {} {}".format(dev_id, dst_names))
        
        device = self._find_device(dev_id)
        if device is None:
            return False

        task = FirmwareTask(device, fw_files)
        self.server.update_tasks.put(task)
        return task.wait(timeout_sec=10)


class FirmwareUpdateServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    def __init__(self, addr, device_list=[]):
        super().__init__(addr, ThreadedTCPRequestHandler)
        self._device_list = device_list
        self.update_tasks = queue.Queue()

    def update_device_list(self, new_device_list):
        """ Keep the list of available devices up to date """
        print("FirmwareUpdateServer: new device list:",
                [dev.serial_number for dev in new_device_list])
        self._device_list = new_device_list

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

    def start(self):
        ip, port = self.server_address

        server_thread = threading.Thread(target=self.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        print("Firmware Update Server ready at {}:{}".format(ip,port))

    def stop(self):
        self.shutdown()
        self.server_close()
        print("Firmware Update Server stopped")

    def poll(self):
        try:
            t = self.update_tasks.get(block=False)
            if t:
                t.execute()
        except queue.Empty:
            pass

    def get_device_list(self):
        return self._device_list



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

