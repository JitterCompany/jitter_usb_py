from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QWidget



class StatusWidget(QWidget):

    def __init__(self):
        super().__init__()

        layout = QtGui.QHBoxLayout()
        self.name = QtGui.QLabel("Name")
        layout.addWidget(self.name)

        self.status = QtGui.QLabel("Status")
        layout.addWidget(self.status)

        self.setLayout(layout)

        self.device = None

    def select_device(self, device):
        self.device = device
        self.refresh()

    def refresh(self):
        if self.device:
            self.name.setText(self.device.name)
            self.status.setText(self.device.program_state)
            if self.device.program_state == 'active':
                self.status.setStyleSheet("font-weight: bold; color: green");
            elif 'error' in self.device.program_state:
                self.status.setStyleSheet("font-weight: bold; color: red");
            else:
                self.status.setStyleSheet("font-weight: bold; color: black");

        else:
            self.name.setText('No Device')
            self.status.setText('')

    

