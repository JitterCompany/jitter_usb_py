from PyQt5 import QtGui


class ConsoleView(QtGui.QWidget):

    def __init__(self):
        """
        Consoleview combines the terminal and debuglog window
        """
        super().__init__()
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)

    def addView(self, view, label):
        layout = QtGui.QVBoxLayout()
        label = QtGui.QLabel(label)
        layout.addWidget(label)
        layout.addWidget(view)
        self.layout.addLayout(layout)
