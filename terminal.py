from collections import deque
from pyqtgraph.Qt import QtGui

class Terminal:

    def __init__(self, send_cmd_func):
        """ TerminalController handles text rendering and command 
            dispatching. 
        """
        self._send_cmd_func = send_cmd_func
        self.terminal_list = deque(maxlen=40)
        self.view = TerminalView(self)

    def send_cmd(self, cmd):
        """ Send current command and show command 
            in text view.
        """

        # allow typing of '^z' to send ctrl-Z char
        cmd = cmd.replace("^z",'\x1A')
        self._send_cmd_func(cmd + '\0')
        self.add('>> ' + cmd + '\n');
        
    def update(self):
        """ Rerender terminal text view. """
        self.view.set_text(''.join(self.terminal_list))

    def add(self, line):
        """ Add one line of text to the terminal text view """
        self.terminal_list.append(line)
        self.update()


    def clear(self):
        """ Clear terminal window of text. """
        self.terminal_list.clear()
        self.update()

class TerminalView(QtGui.QWidget):

    def __init__(self, controller):
        """ TerminalView is a QWidget to display and enter 
            terminal commands
        """
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
        self.inputfield = QtGui.QLineEdit()
        inputlayout.addWidget(self.inputfield)
        sendbtn = QtGui.QPushButton("Enter")
        sendbtn.setShortcut('return')
        sendbtn.clicked.connect(
                lambda x: self.controller.send_cmd(self.inputfield.text()))
        inputlayout.addWidget(sendbtn)

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

