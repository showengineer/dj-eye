import logging
import threading
import time

from prodj.audio.output import MonoRingBuffer, OutputConfig, SoundDeviceOutput
from prodj.timecode import ClockSource
from prodj.timecode.linear.encode import LTCStreamGenerator

LTC_BUFFER_SECONDS = 0.500
LTC_TARGET_BUFFER_MS = 120
LTC_PRODUCER_LOG_INTERVAL = 2.0


class LTCService:
  def __init__(
      self,
      prodj,
      player_number,
      output_config=None,
      output_channel=0,
      fps=25,
      volume=0.8,
      latency_compensation_ms=0,
      target_buffer_ms=LTC_TARGET_BUFFER_MS):
    self.prodj = prodj
    self.player_number = player_number
    self.output_config = output_config or OutputConfig()
    self.output_channel = output_channel
    self.fps = fps
    self.volume = volume
    self.latency_compensation_ms = latency_compensation_ms
    self.target_buffer_ms = target_buffer_ms
    self.sample_rate = self.output_config.sample_rate
    capacity_seconds = max(LTC_BUFFER_SECONDS, target_buffer_ms / 1000 * 2)
    self.buffer = MonoRingBuffer(int(self.sample_rate * capacity_seconds))
    self.target_buffer_frames = int(self.sample_rate * target_buffer_ms / 1000)
    self.producer_blocksize = max(self.output_config.blocksize, 512)
    self.producer_thread = None
    self.running = False
    self.silent = True
    self.last_producer_log = 0
    self.clock_source = ClockSource(
      self.get_transport_frame_position,
      self.get_transport_rate,
    )
    self.generator = LTCStreamGenerator(
      self.clock_source,
      fps=fps,
      sample_rate=self.output_config.sample_rate,
      volume=volume,
      latency_compensation_ms=latency_compensation_ms,
    )
    self.output = SoundDeviceOutput(
      self.read_audio,
      config=self.output_config,
      output_channel=output_channel,
    )

  def get_transport_frame_position(self):
    client = self.prodj.cl.getClient(self.player_number)
    if client is None:
      return None
    if client.getTransportRate() == 0:
      return None
    return client.getTransportFramePosition(self.fps)

  def get_transport_rate(self):
    client = self.prodj.cl.getClient(self.player_number)
    if client is None:
      return 0
    return client.getTransportRate()

  def read_audio(self, frames, sample_rate, device_info=None):
    return self.buffer.read(frames)

  def produce_audio_once(self):
    if self.clock_source.get_transport_rate() <= 0:
      self.silent = True
      self.generator.render(self.producer_blocksize, self.sample_rate)
      self.buffer.clear()
      self.buffer.consume_counters()
      return False

    self.silent = False
    queued_frames = self.buffer.available_read()
    if queued_frames >= self.target_buffer_frames:
      return False

    frames = min(self.producer_blocksize, self.target_buffer_frames - queued_frames)
    queued_ms = queued_frames / self.sample_rate * 1000
    self.generator.latency_compensation_ms = self.latency_compensation_ms + queued_ms
    audio = self.generator.render(frames, self.sample_rate)
    self.buffer.write(audio)
    return True

  def prefill_buffer(self, timeout=0.200):
    deadline = time.monotonic() + timeout
    minimum_frames = min(self.output_config.blocksize, self.target_buffer_frames)
    while self.buffer.available_read() < minimum_frames and time.monotonic() < deadline:
      if not self.produce_audio_once():
        break

  def producer_loop(self):
    logging.info(
      "Started LTC producer thread, target buffer %.1f ms",
      self.target_buffer_frames / self.sample_rate * 1000,
    )
    while self.running:
      if self.produce_audio_once():
        self.log_producer_status()
      else:
        time.sleep(self.producer_blocksize / self.sample_rate)
        self.log_producer_status()
    logging.info("Stopped LTC producer thread")

  def log_producer_status(self):
    now = time.monotonic()
    if now - self.last_producer_log < LTC_PRODUCER_LOG_INTERVAL:
      return
    self.last_producer_log = now
    underruns, overruns = self.buffer.consume_counters()
    status_count = self.output.consume_status_count()
    queued_ms = self.buffer.available_read() / self.sample_rate * 1000
    if self.silent:
      underruns = 0
    if underruns or overruns or status_count:
      logging.warning(
        "LTC buffer status: queued %.1f ms, underruns %d, overruns %d, audio status flags %d",
        queued_ms,
        underruns,
        overruns,
        status_count,
      )
    else:
      logging.debug("LTC buffer status: queued %.1f ms", queued_ms)

  def start(self):
    if self.running:
      return
    logging.info(
      "Starting LTC output for player %s at %.3f fps on device %s with %.1f ms compensation, %.1f ms buffer",
      self.player_number,
      self.fps,
      self.output_config.device,
      self.latency_compensation_ms,
      self.target_buffer_ms,
    )
    self.running = True
    self.silent = True
    self.prefill_buffer()
    self.output.start()
    self.producer_thread = threading.Thread(target=self.producer_loop, name="LTCProducer", daemon=True)
    self.producer_thread.start()

  def stop(self):
    if not self.running and self.output.stream is None:
      return
    self.running = False
    if self.producer_thread is not None:
      self.producer_thread.join(timeout=1)
      self.producer_thread = None
    self.output.stop()
    self.buffer.clear()
    self.silent = True
