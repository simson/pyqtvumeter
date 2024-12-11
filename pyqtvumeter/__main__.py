import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QProgressBar, QComboBox
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QTimer, QIODevice, QSettings
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudioFormat, QAudioInput, QAudio
import pyqtgraph as pg

class AudioMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.audio_input = None
        self.audio_device = None
        self.audio_buffer = None
        self.amplitude_history = [0] * 100  # Store the last 64 amplitude values
        self.settings = QSettings("perso", "AudioMonitor")
        self.initUI()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_audio_level)
        self.timer.start(20)  # Update every 100 ms

    def initUI(self):
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


        self.populate_input_sources()

    def populate_input_sources(self):
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
        if self.audio_input is not None:
            self.audio_input.stop()
            self.audio_buffer.close()

        self.audio_device = self.input_devices[index]
        format = QAudioFormat()
        format.setSampleRate(44100)
        format.setChannelCount(1)
        format.setSampleSize(16)
        format.setCodec("audio/pcm")
        format.setByteOrder(QAudioFormat.LittleEndian)
        format.setSampleType(QAudioFormat.SignedInt)

        if not self.audio_device.isFormatSupported(format):
            print("Default format not supported, trying to use the nearest.")
            format = self.audio_device.nearestFormat(format)

        self.audio_input = QAudioInput(self.audio_device, format)
        self.audio_buffer = AudioBuffer()

        self.audio_input.start(self.audio_buffer)

    def update_audio_level(self):
        if self.audio_buffer is not None:
            audio_data = self.audio_buffer.readAll()
            if not audio_data.isEmpty():
                data = np.frombuffer(audio_data, dtype=np.int16)
                amplitude = int(np.abs(data).max())
                self.progress_bar.setValue(int(amplitude / 32768 * 100))

                self.amplitude_history.pop(0)
                self.amplitude_history.append(amplitude/ 32768 * 100)
                self.graph_plot.setData(self.amplitude_history)



    def closeEvent(self, event):
        if self.audio_input is not None:
            self.audio_input.stop()
            self.audio_buffer.close()
        print(f"Save {self.audio_device.deviceName()} as default")
        self.settings.setValue("default_device", self.audio_device.deviceName())
        event.accept()



class AudioBuffer(QIODevice):
    def __init__(self):
        super().__init__()
        self.buffer = bytearray()
        self.open(QIODevice.ReadWrite)

    def writeData(self, data):
        self.buffer.extend(data)
        return len(data)

    def readData(self, maxlen):
        data = self.buffer[:maxlen]
        self.buffer = self.buffer[maxlen:]
        return bytes(data)


def main():
    app = QApplication(sys.argv)
    ex = AudioMonitor()
    ex.show()
    sys.exit(app.exec_()) 

if __name__ == '__main__':
    main()
