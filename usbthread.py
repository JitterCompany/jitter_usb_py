import queue
import time
import threading
import traceback

import usb.core
import usb.backend.libusb1 as libusb
import usb.util as util

import error

liveThread = None

class USBTask:

    def __init__(self, ep, timeout, device, on_complete, on_fail, repeat,
            max_retries=3):
        self.ep = ep
        self.timeout = timeout
        self.device = device
        self.on_complete = on_complete
        self.on_fail = on_fail
        self.repeat = repeat
        self.retries = max_retries  # only has effect if on sync queue

    def __lt__(self, other):
        return self.priority < other.priority

    def complete(self, value):
        if self.on_complete:
            self.on_complete(value)

    def fail(self):
        if self.on_fail:
            self.on_fail(self)


class USBControlTask(USBTask):

    def __init__(self, device, request, ep=0, dir='out', value=0, index=0,
            data=None, length=None, timeout=10,
            on_complete=None, on_fail=None, max_retries=3):
        super().__init__(ep, timeout, device, on_complete, on_fail=on_fail,
                max_retries=max_retries, repeat=False)
        self.request = request
        self.data = data
        self.value = value
        self.index = index
        self.dir = dir
        self.length = length

class USBReadTask(USBTask):

    def __init__(self, device, ep, length, timeout=10,
            on_complete=None, on_fail=None, repeat=False):
        super().__init__(ep, timeout, device, on_complete, on_fail=on_fail,
                repeat=repeat)
        self.length = length
        self.data = []

class USBWriteTask(USBTask):

    def __init__(self, device, ep, data, timeout=10,
            on_complete=None, on_fail=None, max_retries=3):
        super().__init__(ep, timeout, device, on_complete, on_fail=on_fail,
                max_retries=max_retries, repeat=False)
        self.data = data
        self.length = len(data)

class repeatTasks:

    def __init__(self):
        self.tasks = []

    def should_repeat(self, task):
        """ Check if the given task should be repeated """
        if not task.repeat:
            return False

        index = self.find(task.device, task.ep)
        if index is None:
            task.repeat = False
        return task.repeat

    def add(self, task):
        """ Mark all tasks with task.device+task.ep as repeating """
        task.repeat = True

        if self.find(task.device, task.ep) is None:
            self.tasks.append(task)

    def cancel(self, device, ep):
        """ Stop repeating all tasks for this device+ep """
        index = self.find(device, ep)
        if index is not None:
            del self.tasks[index]

    def find(self, device, ep):
        for index, task in enumerate(self.tasks):
            if task.device == device and task.ep == ep:
                return index
        return None


class USBThread:

    def __init__(self):
        self.writeQueue = queue.Queue()
        self.priorityWriteQueue = queue.Queue()
        self.readQueue = queue.Queue()
        self.controlQueue = queue.Queue()
        self.readCompleteQueue = queue.Queue()
        self.writeCompleteQueue = queue.Queue()
        self.controlCompleteQueue = queue.Queue()
        self.repeatReader = repeatTasks()

        # Heterogeneous queue to mix different types of tasks that 
        # need executed synchronously
        self.syncQueue = queue.Queue()
       
        self._running = True

        timerThread = threading.Thread(target=self.poll)
        timerThread.deamon = True
        timerThread.start();

# DEPRECATED for now. if you need this kind of functionality,
# it should be implemented in Device, to avoid clearing writes to other
# devices..
#
#    def clear_writes(self):
#        self.priorityWriteQueue.queue.clear()
#        self.writeQueue.queue.clear()

    def _complete_task(self, queue):
        if not queue.empty():
            task = queue.get()
            task.complete(task.length)
            return task
        else:
            return

    def complete_read_task(self):
        return self._complete_task(self.readCompleteQueue)

    def complete_read_queue_length(self):
        return self.readCompleteQueue.qsize()

    def complete_write_task(self):
        return self._complete_task(self.writeCompleteQueue)

    def complete_control_task(self):
        queue = self.controlCompleteQueue
        if not queue.empty():
            task = queue.get()
            task.complete(task.data)
            return task
        else:
            return


    def cancel_autoreads(self, device, ep_list):
        for ep in ep_list:
            self.repeatReader.cancel(device, ep)
    

    def addReadTask(self, task, new_repeat=False):
        self.readQueue.put(task)
        if new_repeat:
            self.repeatReader.add(task)


    def addWriteTask(self, task, sync=False):
        if sync:
            self.addSyncronousTask(task)
        else:
            self.writeQueue.put(task)

    def addControlTask(self, task, sync=False):
        if task.device is None:
            return

        if sync:
            self.addSyncronousTask(task)
        else:
            self.controlQueue.put(task)

    def addSyncronousTask(self, task):
        self.syncQueue.put(task)
    
    def quit(self):
        self._running = False

    def poll(self):
        while(self._running):
            self._handleControlTask()
            self._handleWriteTask()
            self._handleReadTask()
            self._handleReadTask()
            self._handleReadTask()
            self._handleSyncTasks()
            time.sleep(0.001)

        self.writeQueue.queue.clear()
        self.priorityWriteQueue.queue.clear()
        self.readQueue.queue.clear()
        self.controlQueue.queue.clear()
        self.readCompleteQueue.queue.clear()
        self.writeCompleteQueue.queue.clear()
        self.controlCompleteQueue.queue.clear()
        self.syncQueue.queue.clear()


    def submit_control_request(self, task):
        bmRequestType = util.build_request_type(
                    util.CTRL_OUT if task.dir == 'out' else util.CTRL_IN,
                    util.CTRL_TYPE_VENDOR,
                    util.CTRL_RECIPIENT_DEVICE)
        ret = task.device.usb.ctrl_transfer(
            bmRequestType = bmRequestType,
            bRequest = task.request,
            wValue = task.value,
            wIndex = task.index,
            data_or_wLength = task.length if task.length else task.data)
        if ret:
            task.data = ret
        
        if task.on_complete:
            self.controlCompleteQueue.put(task)
            

    def _handleSyncTasks(self):
        #handle all sync tasks in queue

        retryTask = None
        while True:
            try:
                if retryTask and retryTask.retries:
                    retryTask.retries-= 1
                    task = retryTask
                    retryTask = None
                    time.sleep(0.1)

                else:
                    # get next task
                    task = self.syncQueue.get(block=False)

                if (isinstance(task, USBControlTask)):
                    self.submit_control_request(task)
                elif (isinstance(task, USBWriteTask)):
                    l = 0
                    while l != len(task.data):
                        task.data = task.data[l:]
                        l = task.device.usb.write(task.ep,
                                task.data, task.timeout)
                else:
                    print('Only Write and Control tasks are supported')
                    task.fail()
                    
            except queue.Empty:
                break

            except usb.core.USBError as err:
                if err.backend_error_code == libusb.LIBUSB_ERROR_TIMEOUT:
                    print("Warning: USB Timeout, retrying task")
                    retryTask = task

                elif err.backend_error_code == libusb.LIBUSB_ERROR_PIPE:
                    if not task.retries:
                        if not task.on_fail:
                            print("Warning: USB stall, dropping task:")
                        task.fail()
                    else:
                        # only print the warning if no failure handler exists
                        if not task.on_fail:
                            print("Warning: USB stall, retrying task "
                            "(retries left:{})".format(task.retries))
                        retryTask = task


                elif err.backend_error_code == libusb.LIBUSB_ERROR_IO:
                    print("Warning: USB IO error: not retrying task")
                    task.fail()

                elif err.backend_error_code == libusb.LIBUSB_ERROR_NO_DEVICE:
                    error.print_error("No Such Device:" + str(task.device))
                    task.fail()

                else:
                    print("Warning: unknown USB IO error code",
                            err.backend_error_code)
                    print(traceback.format_exc())
                    task.fail()


            except Exception:
                error.print_error(traceback.format_exc())
                task.fail()
            
            for i in range(10):
                self._handleReadTask()
            
            

   
    def _handleReadTask(self):
        try:
            task = self.readQueue.get(block=False)

            task.data = task.device.usb.read(task.ep | 0x80,
                    task.length, task.timeout)
            if task:
 #               print("read task for ep:", task.ep)
                self.readCompleteQueue.put(task)
            
            if self.repeatReader.should_repeat(task):

                # Note: copy task to avoid re-using the buffer
                self.addReadTask(USBReadTask(task.device, task.ep,
                    task.length, timeout=task.timeout,
                    on_complete=task.on_complete, repeat=task.repeat))

        except queue.Empty:
            pass
        except usb.core.USBError as err:
            if (err.backend_error_code == libusb.LIBUSB_ERROR_TIMEOUT
                    or err.backend_error_code == libusb.LIBUSB_ERROR_IO):

                if task.repeat:
                    
                    # Note: copy task to avoid re-using the buffer
                    self.addReadTask(USBReadTask(task.device, task.ep,
                        task.length, timeout=task.timeout,
                        on_complete=task.on_complete, repeat=task.repeat))

                if err.backend_error_code == libusb.LIBUSB_ERROR_IO:
                    print("Warning: USB IO error on read")
                    task.fail()

            elif err.backend_error_code == libusb.LIBUSB_ERROR_NO_DEVICE:
                error.print_error("No Such Device:" + str(task.device))
                task.fail()
            else:
                error.print_error("(unexpected) " + traceback.format_exc())
                task.fail()

        except Exception:
            error.print_error(traceback.format_exc())
            task.fail()

    def _handleControlTask(self):
        try:
            task = self.controlQueue.get(block=False)
            self.submit_control_request(task)
            
        except queue.Empty:
            pass
        except usb.core.USBError as err:
            if err.backend_error_code == libusb.LIBUSB_ERROR_TIMEOUT:
                print("Warning: USB Timeout, retrying task")
                self.controlQueue.put(task)

            elif err.backend_error_code == libusb.LIBUSB_ERROR_PIPE:
                if not task.retries:
                    if not task.on_fail:
                        print("Warning: USB stall, dropping task:")
                    task.fail()
                else:
                    # only print the warning if no failure handler exists
                    if not task.on_fail:
                        print("Warning: USB stall, retrying ctrl task "
                        "(retries left:{})".format(task.retries))
                    task.retries-= 1
                    self.controlQueue.put(task)


            elif err.backend_error_code == libusb.LIBUSB_ERROR_IO:
                print("Warning: USB IO error on control transfer: not retrying")
                task.fail()

            elif err.backend_error_code == libusb.LIBUSB_ERROR_NO_DEVICE:
                error.print_error("No Such Device:" + str(task.device))
                task.fail()
            else:
                print(traceback.format_exc())
                task.fail()
        except Exception:
            print(traceback.format_exc())
            task.fail()


    def _handleWriteTask(self):
        q = self.writeQueue
        if not self.priorityWriteQueue.empty():
            q = self.priorityWriteQueue
        try:
            task = q.get(block=False)


            l = task.device.usb.write(task.ep, task.data, task.timeout)
            if l == len(task.data):
                self.writeCompleteQueue.put(task)
            else:
                task.data = task.data[l:]
                self.priorityWriteQueue.put(task)

        except queue.Empty:
            pass
        except usb.core.USBError as err:
            if err.backend_error_code == libusb.LIBUSB_ERROR_TIMEOUT:
                print("Warning: USB Timeout, retrying task")
                self.priorityWriteQueue.put(task)

            elif err.backend_error_code == libusb.LIBUSB_ERROR_IO:
                print("Warning: USB IO error on write: not retrying")
                task.fail()

            elif err.backend_error_code == libusb.LIBUSB_ERROR_NO_DEVICE:
                error.print_error("No Such Device:" + str(task.device))
                task.fail()
            else:
                print(traceback.format_exc())
                task.fail()
        except Exception:
            print(traceback.format_exc())
            task.fail()

