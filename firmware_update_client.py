#!/usr/bin/env python

import time
import select
import socket
import sys
import os.path

SERVER_IP = "localhost"
SERVER_PORT = 3853

def list_to_str(l, sep=','):
    ret = ""
    for i in l:
        ret+= str(i) + sep
    
    if len(ret):
        ret = ret[:-1]

    return ret

def parse_list(l):
    ret = []
    for v in l.split(','):
        val = v.strip()
        if len(val):
            ret.append(val)

    return ret

def encode(string):
    return bytes(string, 'ascii')

def decode(bytestr):
    return str(bytestr, 'ascii')

def print_devices(devices):
    for dev in devices:
        print("\t{}".format(dev))
    print('')

class Update:

    def __init__(self, firmware_file_m0, firmware_file_m4):
        self.devices = []
        self.updated = []
        self.firmware_file_m0 = firmware_file_m0
        self.firmware_file_m4 = firmware_file_m4

    def parse_incoming(self, socket, timeout_sec=10):

        ready = select.select([socket], [], [], timeout_sec)
        timeout = True
        if ready[0]:
            response = decode(socket.recv(1024*1024))
            if len(response):
                timeout = False

                for line in response.split("\n"):
                    tokens = line.split('=')
                    if len(tokens) < 2:
                        continue
                    key = tokens[0]
                    value = line[len(key):].strip('=')

                    if key == 'devices':
                        self.devices = parse_list(value)

                    if key == 'updated':
                        self.updated = parse_list(value)

        if timeout:
            print("ERROR: timeout")
            return False
        return True


    def ui_select_devices(self):
        """ UI: show devices / select which devices to update """

        to_update = self.devices
        print("")
        if not len(self.devices):
            print("ERROR: No device(s) available for update!")
            return []

        elif len(self.devices) == 1:
            print("Updating device {}".format(self.devices[0]))

        else:
            print("Device(s) available for update:")
            print_devices(self.devices)
            
            # TODO maybe a way to select which ones to update
            # and / or ENTER to update all?
        
        # always update all devices for now
        return to_update
   

    def ui_result(self):
        """ UI: show the result(s) of the update(s)"""
        failed = []
        for dev in self.devices:
            if not dev in self.updated:
                failed.append(dev)
        
        if len(failed):
            print("ERROR: Failed to update these devices:")
            print_devices(failed)

        elif len(self.devices):
            print("SUCCESS: All devices updated")

        else:
            print("ERROR: No device(s) available for update!")

        # TODO these could be tried again if the user selects it
        self.devices = failed

    def upload(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                # connect and get device list
                sock.connect((SERVER_IP, SERVER_PORT))
                if not self.parse_incoming(sock, 2):
                    return
                
                # select which devices to update
                to_update = self.ui_select_devices()
                if not len(to_update):
                    return
                
                # send update commands
                commands = []
                commands.append("update_devices=" + list_to_str(to_update))
                commands.append("fw_m0=" + self.firmware_file_m0)
                commands.append("fw_m4=" + self.firmware_file_m4)
                sock.sendall(encode(list_to_str(commands, '\n')))
                
                # get list of updated devices
                if not self.parse_incoming(sock, 10):
                    return

                self.ui_result()

            except ConnectionRefusedError:
                print("ERROR: USB server not running!")


def print_usage(progname):
    print("\nUsage: {} /path/to/m0.bin /path/to/m4.bin".format(progname))
    print("\tEach argument should be the path to a valid binary")
    print("\tto upload to the m0 and m4 core\n")

def main(args):

    if not len(args) >= 3:
        print("ERROR: expected at least 2 arguments")
        return print_usage(args[0])
    
    files = args[1:3]
    for f in files:
        if not os.path.isfile(f):
            print("ERROR: {} is not a file".format(f))
            return print_usage(args[0])


    update = Update(files[0], files[1])
    update.upload()

if __name__ == "__main__":
    main(sys.argv)

