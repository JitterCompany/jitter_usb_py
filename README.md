This is a python library + some example programs to work wit Jitter-USB devices.
    
# Demo programs

* console_app.py: A basic PyQt5 app that communicates with USB devices.

    - Supports multiple connected devices
    - Show a simple command terminal / debug log for one device at a time
    - update server accepting (firmware) file uploads from a separate client program running on the same host
    
    This is a fairly basic application, the main purpose is to give an example of how to build an application around an USB device.
    The terminal console + debug output are the main functionality of this application.
    
    When building a new application, this demo can serve as a guidance. The recommended way is to depend on this repository and import USB into your application, along with gui element you want to re-use such as the console.


* update_server.py: Standalone demo version of the update server

    - allows connections from a separate client
(see firmware_update_client.py for an example)
    - can update multiple devices with one command
    - when running  it standalone, the demo runs with dummy devices:
    you can test it without actual USB devices.
    To try it with real devices, run console_app.py (which runs
            update_server in the background)

* firmware_update_client.py: Example client for the firmware update server.

    Make sure you have an update server running on the same host
    (console_app.py or update_server.py).
    This client will send firmware updates to that running server.
