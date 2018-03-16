from pyqtgraph.Qt import QtGui
from collections import defaultdict, deque
from functools import partial


class DebugLog:

    def __init__(self):
        """ DebugLogController manages the debug output from devices """
        self.view = DebugLogView(self)
        self.data = defaultdict(partial(deque, maxlen=200))
        self.selectedKey = None

    def select_device(self, dev):
        """ Notify debuglog of the currently selected device """
        if dev:
            self.selectedKey = dev.serial_number
        else: 
            self.selectedKey = None

        self.update()

    def add(self, device, line):
        """ Add log output for device """
        self.data[device.serial_number].append(line + '\n')
        self.update()
        prefix = device.name if device.name else device.serial_number
        try:
            print(prefix + ": " +  line)
        except UnicodeEncodeError:
            line = ':'.join(hex(ord(x))[2:] for x in line)
            print(prefix + " (binary): " +  line)

    def update(self):
        """ Rerender console text view. """
        if self.selectedKey:
            self.view.set_text(''.join(self.data[self.selectedKey]))

    def clear(self):
        """ Clear current device context """
        if self.selectedKey:
            self.data[self.selectedKey].clear()
            self.update()

class DebugLogView(QtGui.QWidget):

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        l = self.layout()
        self.setLayout(l)
        self.text = ''

    def layout(self):
        layout = QtGui.QVBoxLayout()
        self.textview = QtGui.QTextEdit()
        self.textview.setReadOnly(True)
        layout.addWidget(self.textview)

        inputlayout = QtGui.QHBoxLayout()
        inputlayout.addStretch(1)
        clearbtn = QtGui.QPushButton("Clear")
        clearbtn.setShortcut('META+L')
        clearbtn.clicked.connect(self.controller.clear)
        inputlayout.addWidget(clearbtn)
        layout.addLayout(inputlayout)

        return layout

    def set_text(self, text):
        if self.text != text:
            self.text = text;
            self.textview.setPlainText(text)
            self.textview.moveCursor(QtGui.QTextCursor.End)

