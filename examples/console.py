from PyQt5 import QtWidgets


class ConsoleView(QtWidgets.QWidget):

    def __init__(self):
        """
        Consoleview combines the terminal and debuglog window
        """
        super().__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)

    def addView(self, view, label):
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(label)
        layout.addWidget(label)
        layout.addWidget(view)
        self.layout.addLayout(layout)
