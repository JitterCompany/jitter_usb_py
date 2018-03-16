from PyQt5 import QtCore, QtGui, QtWidgets


class MainView(QtWidgets.QMainWindow):
    
    def closeEvent(self, e):
        self._app.quit()
        e.accept()

    def __init__(self, app, consoleWidget, title):
        super().__init__()
        exitShortcut = QtGui.QShortcut("CTRL+Q", self)
        exitShortcut.activated.connect(self.close)

        self._app = app
        self.setWindowTitle(title)
        self.resize(1600,900)

        # Statusbar
        self.statusBar().showMessage('')

        self.setCentralWidget(consoleWidget)

        self.center()

        self.raise_()
        self.activateWindow()

    def create_tool_bar(self, status):
        self._toolbar = self.addToolBar('Toolbar')
        self._status = status 
        self._toolbar.addWidget(self._status)
        
        empty = QtGui.QWidget()
        empty.setSizePolicy(
                QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Preferred)
        self._toolbar.addWidget(empty)

        self._device_picker = QtGui.QComboBox()
        label = QtGui.QLabel('Geselecteerde Apparaat: ')
        self._toolbar.addWidget(label)
        self._device_picker.setSizeAdjustPolicy(
                QtGui.QComboBox.AdjustToContents)
        self._device_picker.currentIndexChanged.connect(
                self._app.select_device_at)
        self._toolbar.addWidget(self._device_picker)


    def set_devices(self, devices):
        prevCount = self._device_picker.count;
        prevIndex = self._device_picker.currentIndex()
        prevText = self._device_picker.currentText()

        self._device_picker.blockSignals(True)
        self._device_picker.clear()
        newIndex = 0
        for i,dev in enumerate(devices):
            if dev.name:
                text = dev.name + ' [ ' + dev.serial_number + ']'
            else:
                text = ' ' + dev.serial_number + ' '

            self._device_picker.addItem(text)
            if text == prevText:
                newIndex = i
        self._device_picker.setCurrentIndex(newIndex)
        self._device_picker.blockSignals(False)
        
        if len(devices):
            if ((prevIndex < 0) or (prevCount != self._device_picker.count)):
                self._device_picker.setCurrentIndex(0)
                self._app.select_device_at(0)
            else:
                pass
                # keep current device
        else:
            self._device_picker.setCurrentIndex(-1)
            self._app.select_device_at(-1)

    def center(self):
        frameGm = self.frameGeometry()
        screen = QtGui.QApplication.desktop().screenNumber(
                QtGui.QApplication.desktop().cursor().pos())
        centerPoint = QtGui.QApplication.desktop().screenGeometry(
                screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

