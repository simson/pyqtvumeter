import sys
import signal
import numpy as np
import argparse
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWidgets import QLabel, QProgressBar, QComboBox, QPushButton
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtCore import QTimer, QIODevice, QSettings
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudioFormat, QAudioInput, QAudio
import pyqtgraph as pg

class AudioMonitor(QMainWindow):
    def __init__(self, start_in_tray=False, audio_source=None, color="white"):
        """MainWindow initializator"""
        super().__init__()
        self.audio_input = None
        self.audio_device = None
        self.audio_buffer = None
        self.amplitude_history = [0] * 100  # Store the last 64 amplitude values
        self.settings = QSettings("perso", "AudioMonitor")

        self.color = QColor(color)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_audio_level)
        self.timer.start(20)  # Update every 20 ms

        self.input_devices = []

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_bar_icon(self.amplitude_history))
        self.tray_icon.activated.connect(self.restore_from_tray)

        self.tray_menu = QMenu(self)
        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.restore_from_tray_context)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        self.tray_menu.addAction(restore_action)
        self.tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(self.tray_menu)


        self.initUI()

        self.populate_input_sources()

        if audio_source:
            index = self.combo_box.findText(audio_source)
            if index != -1:
                self.combo_box.setCurrentIndex(index)

        if start_in_tray:
            self.minimize_to_tray()
        else:
            self.show()


    def initUI(self):
        """Initialize the UI (widget creation)"""
        self.setWindowTitle('Audio Signal Monitor')
        self.setGeometry(100, 100, 300, 200)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.label = QLabel('Select Audio Input Source:', self)
        self.layout.addWidget(self.label)

        self.combo_box = QComboBox(self)
        self.layout.addWidget(self.combo_box)
        self.combo_box.currentIndexChanged.connect(self.change_input_source)

        self.progress_label = QLabel('Audio Signal Amplitude:', self)
        self.layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar(self)
        self.layout.addWidget(self.progress_bar)

        self.graph_widget = pg.PlotWidget()
        self.layout.addWidget(self.graph_widget)
        self.graph_plot = self.graph_widget.plot()
        # Disable dynamic resizing
        self.graph_widget.setXRange(0, 100)
        self.graph_widget.setYRange(0, 100)

        self.minimize_button = QPushButton("Minimize to Tray", self)
        self.minimize_button.clicked.connect(self.minimize_to_tray)
        self.layout.addWidget(self.minimize_button)


    def populate_input_sources(self):
        """Filler of the combobox with all audio device available"""
        self.input_devices = QAudioDeviceInfo.availableDevices(QAudio.AudioInput)
        for device in self.input_devices:
            self.combo_box.addItem(device.deviceName())

        # Load the saved default device
        default_device_name = self.settings.value("default_device", "")
        if default_device_name:
            index = self.combo_box.findText(default_device_name)
            if index != -1:
                self.combo_box.setCurrentIndex(index)

    def change_input_source(self, index):
        """Handler of input source selection"""
        if self.audio_input is not None:
            self.audio_input.stop()
            self.audio_buffer.close()

        self.audio_device = self.input_devices[index]
        audio_format = QAudioFormat()
        audio_format.setSampleRate(44100)
        audio_format.setChannelCount(1)
        audio_format.setSampleSize(16)
        audio_format.setCodec("audio/pcm")
        audio_format.setByteOrder(QAudioFormat.LittleEndian)
        audio_format.setSampleType(QAudioFormat.SignedInt)

        if not self.audio_device.isFormatSupported(audio_format):
            print("Default format not supported, trying to use the nearest.")
            audio_format = self.audio_device.nearestFormat(audio_format)

        self.audio_input = QAudioInput(self.audio_device, audio_format)
        self.audio_buffer = AudioBuffer()

        self.audio_input.start(self.audio_buffer)

    def update_audio_level(self):
        """Handler of new data"""
        if self.audio_buffer is not None:
            audio_data = self.audio_buffer.readAll()
            if not audio_data.isEmpty():
                data = np.frombuffer(audio_data, dtype=np.int16)
                amplitude = int(np.abs(data).max())
                self.progress_bar.setValue(int(amplitude / 32768 * 100))

                self.amplitude_history.pop(0)
                self.amplitude_history.append(amplitude/ 32768 * 100)
                self.graph_plot.setData(self.amplitude_history)

                # Update the tray icon with the latest amplitude history
                self.update_tray_icon()

    def create_bar_icon(self, values, size=64):
        """Generate an icon representing the Audio level"""
        # Create a QPixmap object with the specified size
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("transparent"))

        # Create a QPainter object to draw on the QPixmap
        painter = QPainter(pixmap)

        painter.setPen(self.color)
        painter.setBrush(self.color)

        bar_width = size / len(values)
        for i, value in enumerate(values):
            bar_height = int(value / 100 * size)
            painter.drawRect(int(i * bar_width), size - bar_height, int(bar_width), bar_height)

        painter.end()

        # Convert QPixmap to QIcon
        return QIcon(pixmap)

    def update_tray_icon(self):
        """Handler Update tray icon"""
        # Create a bar icon with the latest amplitude history
        icon = self.create_bar_icon(self.amplitude_history)
        self.tray_icon.setIcon(icon)

    def minimize_to_tray(self):
        """Handler to minize to tray"""
        self.hide()
        self.tray_icon.show()

    def restore_from_tray(self, reason):
        """Handler on restore (Click on tray)"""
        if reason == QSystemTrayIcon.Trigger:
            self.show()
            self.tray_icon.hide()

    def restore_from_tray_context(self, reason):
        """Handler on restore context"""
        self.restore_from_tray(QSystemTrayIcon.Trigger)

    def closeEvent(self, event):
        """On close event handler stop all captures and save last settings"""
        if self.audio_input is not None:
            self.audio_input.stop()
            self.audio_buffer.close()
        print(f"Save {self.audio_device.deviceName()} as default")
        self.settings.setValue("default_device", self.audio_device.deviceName())
        event.accept()



class AudioBuffer(QIODevice):
    """Class representing the AudioBuffer"""

    def __init__(self):
        """Constructor of AudioBuffer"""
        super().__init__()
        self.buffer = bytearray()
        self.open(QIODevice.ReadWrite)

    def writeData(self, data):
        """Append data to audio buffer"""
        self.buffer.extend(data)
        return len(data)

    def readData(self, maxlen):
        """return maxlen data from Audio Bufer"""
        data = self.buffer[:maxlen]
        self.buffer = self.buffer[maxlen:]
        return bytes(data)


def list_audio_sources():
    """List all available audio sources"""
    input_devices = QAudioDeviceInfo.availableDevices(QAudio.AudioInput)
    for device in input_devices:
        print(device.deviceName())

def main():
    """Run the main application"""
    parser = argparse.ArgumentParser(description="Audio Signal Monitor")
    parser.add_argument("--tray", action="store_true", help="Start directly in tray icon")
    parser.add_argument("--color", type=str, help="Color for tray icon barplot", default="white")
    parser.add_argument("--source", type=str, help="Select audio source from command line")
    parser.add_argument("--list-sources", action="store_true", help="List available audio sources")

    args = parser.parse_args()

    if args.list_sources:
        list_audio_sources()
        sys.exit(0)

    app = QApplication(sys.argv)
    ex = AudioMonitor(start_in_tray=args.tray, audio_source=args.source)
    ex = AudioMonitor(start_in_tray=args.tray, audio_source=args.source, color=args.color)

    # Handle SIGINT (Ctrl+C) to gracefully exit the application
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
