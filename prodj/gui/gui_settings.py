from dataclasses import dataclass

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
  QComboBox,
  QDialog,
  QDialogButtonBox,
  QDoubleSpinBox,
  QFormLayout,
  QSpinBox,
  QVBoxLayout,
)

from prodj.audio.output import AudioOutputUnavailable, list_output_devices


@dataclass
class LtcSettings:
  device: int | None
  output_channel: int
  fps: float
  sample_rate: int
  blocksize: int
  volume: float
  compensation_ms: float
  buffer_ms: float


class SettingsDialog(QDialog):
  def __init__(self, settings: LtcSettings, parent=None):
    super().__init__(parent)
    self.setWindowTitle("Settings")
    self.setFixedSize(520, 360)
    self.devices = []

    self.device = QComboBox(self)
    self.populateDevices(settings.device)
    self.device.currentIndexChanged.connect(self.updateChannelRange)

    self.output_channel = QSpinBox(self)
    self.output_channel.setRange(1, 64)
    self.output_channel.setValue(settings.output_channel + 1)

    self.fps = QComboBox(self)
    self.fps.addItem("23.976 without drop frames", 23.976)
    self.fps.addItem("24", 24)
    self.fps.addItem("25", 25)
    self.fps.addItem("29.97 without drop frames", 29.97)
    self.fps.addItem("30", 30)
    self.fps.setCurrentIndex(2) # 25 fps default. TODO: Make this last state dependent

    fps_index = self.fps.findText(str(settings.fps), Qt.MatchStartsWith)
    if fps_index >= 0:
      self.fps.setCurrentIndex(fps_index)

    self.sample_rate = QComboBox(self)
    self.sample_rate.addItem("Device default", None)
    self.sample_rate.addItem("44.1 kHz", 44100)
    self.sample_rate.addItem("48 kHz", 48000)
    self.sample_rate.addItem("96 kHz", 96000)
    self.sample_rate.addItem("192 kHz", 192000)


    self.blocksize = QSpinBox(self)
    self.blocksize.setRange(64, 8192)
    self.blocksize.setSingleStep(64)
    self.blocksize.setValue(settings.blocksize)

    self.volume = QDoubleSpinBox(self)
    self.volume.setRange(0, 1)
    self.volume.setDecimals(2)
    self.volume.setSingleStep(0.05)
    self.volume.setValue(settings.volume)

    self.compensation_ms = QDoubleSpinBox(self)
    self.compensation_ms.setRange(-1000, 1000)
    self.compensation_ms.setDecimals(1)
    self.compensation_ms.setValue(settings.compensation_ms)

    self.buffer_ms = QDoubleSpinBox(self)
    self.buffer_ms.setRange(10, 1000)
    self.buffer_ms.setDecimals(1)
    self.buffer_ms.setValue(settings.buffer_ms)

    form = QFormLayout()
    form.addRow("Audio output", self.device)
    form.addRow("Output channel", self.output_channel)
    form.addRow("FPS", self.fps)
    form.addRow("Sample rate", self.sample_rate)
    form.addRow("Block size", self.blocksize)
    form.addRow("Volume", self.volume)
    form.addRow("LTC compentation ms", self.compensation_ms)
    form.addRow("Buffer ms", self.buffer_ms)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
    buttons.accepted.connect(self.accept)
    buttons.rejected.connect(self.reject)

    layout = QVBoxLayout(self)
    layout.addLayout(form)
    layout.addStretch(1)
    layout.addWidget(buttons)

    self.setStyleSheet("""
      QDialog { background-color: black; color: white; }
      QLabel { color: white; }
      QComboBox, QSpinBox, QDoubleSpinBox {
        color: white;
        background-color: black;
        border: 1px solid #777;
        padding: 3px;
      }
      QPushButton {
        color: white;
        background-color: black;
        border: 1px solid #777;
        padding: 5px 12px;
      }
    """)
    self.updateChannelRange()

  def populateDevices(self, selected_device):
    self.device.addItem("System default", None)
    try:
      self.devices = list_output_devices()
    except AudioOutputUnavailable as exc:
      self.device.addItem(str(exc), None)
      self.device.setEnabled(False)
      return
    for device in self.devices:
      label = "{}  {}  {}ch  {:.0f} Hz".format(
        device.hostapi,
        device.name,
        device.max_output_channels,
        device.default_samplerate,
      )
      self.device.addItem(label, device.index)
      if selected_device == device.index:
        self.device.setCurrentIndex(self.device.count() - 1)

  def selectedDevice(self):
    index = self.device.currentIndex()
    if index < 0:
      return None
    return self.device.itemData(index)

  def selectedDeviceInfo(self):
    selected = self.selectedDevice()
    return next((device for device in self.devices if device.index == selected), None)

  def updateChannelRange(self):
    device = self.selectedDeviceInfo()
    max_channels = device.max_output_channels if device is not None else 64
    current = min(self.output_channel.value() if hasattr(self, "output_channel") else 1, max_channels)
    if hasattr(self, "output_channel"):
      self.output_channel.setRange(1, max_channels)
      self.output_channel.setValue(current)

  def settings(self):
    return LtcSettings(
      device=self.selectedDevice(),
      output_channel=self.output_channel.value() - 1,
      fps=self.fps.currentData(),
      sample_rate=self.sample_rate.currentData(),
      blocksize=self.blocksize.value(),
      volume=self.volume.value(),
      compensation_ms=self.compensation_ms.value(),
      buffer_ms=self.buffer_ms.value(),
    )
