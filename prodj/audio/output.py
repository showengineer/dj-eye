import logging
from threading import Lock
from dataclasses import dataclass

import numpy as np


class AudioOutputUnavailable(RuntimeError):
  pass


def import_sounddevice():
  try:
    import sounddevice as sd
  except ImportError as exc:
    raise AudioOutputUnavailable(
      "sounddevice is not installed. Run `pipenv install` to install Pipfile dependencies."
    ) from exc
  return sd


@dataclass
class AudioDevice:
  index: int
  name: str
  hostapi: str
  max_output_channels: int
  default_samplerate: float


@dataclass
class HostApi:
  index: int
  name: str


@dataclass
class OutputConfig:
  device: int | None = None
  sample_rate: int | None = 48000
  channels: int = 1
  blocksize: int = 512
  latency: str | float | None = None
  dtype: str = "float32"


def list_output_devices():
  sd = import_sounddevice()
  hostapis = sd.query_hostapis()
  devices = []
  for index, device in enumerate(sd.query_devices()):
    if device["max_output_channels"] <= 0:
      continue
    hostapi = hostapis[device["hostapi"]]["name"]
    devices.append(AudioDevice(
      index=index,
      name=device["name"],
      hostapi=hostapi,
      max_output_channels=device["max_output_channels"],
      default_samplerate=device["default_samplerate"],
    ))
  return devices


def list_hostapis():
  sd = import_sounddevice()
  return [
    HostApi(index=index, name=hostapi["name"])
    for index, hostapi in enumerate(sd.query_hostapis())
  ]


def format_output_devices(devices=None):
  if devices is None:
    devices = list_output_devices()
  lines = []
  for device in devices:
    lines.append(
      f"{device.index:>3}  {device.hostapi:<18}  "
      f"{device.max_output_channels:>2}ch  "
      f"{device.default_samplerate:>8.1f} Hz  {device.name}"
    )
  return "\n".join(lines)


def format_hostapis(hostapis=None):
  if hostapis is None:
    hostapis = list_hostapis()
  return "\n".join(f"{hostapi.index:>3}  {hostapi.name}" for hostapi in hostapis)


def find_output_devices(hostapi=None, name=None):
  devices = list_output_devices()
  if hostapi is not None:
    hostapi = hostapi.lower()
    devices = [device for device in devices if hostapi in device.hostapi.lower()]
  if name is not None:
    name = name.lower()
    devices = [device for device in devices if name in device.name.lower()]
  return devices


def validate_output_device(device, channels=1, sample_rate=48000, dtype="float32"):
  sd = import_sounddevice()
  sd.check_output_settings(
    device=device,
    channels=channels,
    samplerate=sample_rate,
    dtype=dtype,
  )


def play_buffer(audio, sample_rate=48000, device=None, channels=1):
  sd = import_sounddevice()
  audio = np.asarray(audio, dtype=np.float32)
  if audio.ndim == 1 and channels > 1:
    output = np.zeros((len(audio), channels), dtype=np.float32)
    output[:, 0] = audio
  elif audio.ndim == 1:
    output = audio
  else:
    output = audio
  sd.play(output, samplerate=sample_rate, device=device, blocking=True)


def route_mono_to_output(audio, frames, channels, output_channel=0):
  audio = np.asarray(audio, dtype=np.float32)
  out = np.zeros((frames, channels), dtype=np.float32)
  count = min(frames, len(audio))
  out[:count, output_channel] = audio[:count]
  return out


class MonoRingBuffer:
  def __init__(self, capacity_frames):
    self.capacity = capacity_frames
    self.buffer = np.zeros(capacity_frames, dtype=np.float32)
    self.read_pos = 0
    self.write_pos = 0
    self.size = 0
    self.underruns = 0
    self.overruns = 0
    self.lock = Lock()

  def available_read(self):
    with self.lock:
      return self.size

  def available_write(self):
    with self.lock:
      return self.capacity - self.size

  def clear(self):
    with self.lock:
      self.read_pos = 0
      self.write_pos = 0
      self.size = 0

  def write(self, audio):
    audio = np.asarray(audio, dtype=np.float32)
    written = 0
    with self.lock:
      count = min(len(audio), self.capacity - self.size)
      if count < len(audio):
        self.overruns += 1
      while written < count:
        chunk = min(count - written, self.capacity - self.write_pos)
        self.buffer[self.write_pos:self.write_pos + chunk] = audio[written:written + chunk]
        self.write_pos = (self.write_pos + chunk) % self.capacity
        self.size += chunk
        written += chunk
    return written

  def read(self, frames):
    output = np.zeros(frames, dtype=np.float32)
    read = 0
    with self.lock:
      count = min(frames, self.size)
      if count < frames:
        self.underruns += 1
      while read < count:
        chunk = min(count - read, self.capacity - self.read_pos)
        output[read:read + chunk] = self.buffer[self.read_pos:self.read_pos + chunk]
        self.read_pos = (self.read_pos + chunk) % self.capacity
        self.size -= chunk
        read += chunk
    return output

  def consume_counters(self):
    with self.lock:
      underruns = self.underruns
      overruns = self.overruns
      self.underruns = 0
      self.overruns = 0
    return underruns, overruns


class SoundDeviceOutput:
  def __init__(self, callback, config=None, output_channel=0):
    self.sd = import_sounddevice()
    self.callback = callback
    self.config = config or OutputConfig()
    self.output_channel = output_channel
    self.stream = None
    self.status_count = 0
    self.stream_latency_ms = None
    self.device_output_latency_ms = None

  def start(self):
    if self.stream is not None:
      return
    validate_output_device(
      self.config.device,
      channels=self.config.channels,
      sample_rate=self.config.sample_rate,
      dtype=self.config.dtype,
    )
    self.stream = self.sd.OutputStream(
      device=self.config.device,
      samplerate=self.config.sample_rate,
      channels=self.config.channels,
      blocksize=self.config.blocksize,
      latency=self.config.latency,
      dtype=self.config.dtype,
      callback=self._callback,
    )
    self.stream.start()
    block_ms = self.config.blocksize / self.config.sample_rate * 1000
    latency = self.stream.latency
    latency_ms = latency * 1000 if isinstance(latency, (int, float)) else latency
    self.stream_latency_ms = latency_ms if isinstance(latency_ms, (int, float)) else None
    logging.info(
      "Started sounddevice output stream on device %s, latency %s ms, block %.1f ms",
      self.config.device,
      latency_ms,
      block_ms,
    )

  def stop(self):
    if self.stream is None:
      return
    self.stream.stop()
    self.stream.close()
    self.stream = None
    self.device_output_latency_ms = None
    logging.info("Stopped sounddevice output stream")

  def _callback(self, outdata, frames, device_info, status):
    if status:
      self.status_count += 1
    current_time = getattr(device_info, "currentTime", None)
    output_time = getattr(device_info, "outputBufferDacTime", None)
    if current_time is not None and output_time is not None:
      self.device_output_latency_ms = (output_time - current_time) * 1000
    audio = self.callback(frames, self.config.sample_rate, device_info)
    audio = np.asarray(audio, dtype=np.float32)
    outdata.fill(0)
    count = min(frames, len(audio))
    outdata[:count, self.output_channel] = audio[:count]

  def consume_status_count(self):
    status_count = self.status_count
    self.status_count = 0
    return status_count

  def __enter__(self):
    self.start()
    return self

  def __exit__(self, exc_type, exc, tb):
    self.stop()
