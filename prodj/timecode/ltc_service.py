import logging

from prodj.audio.output import OutputConfig, SoundDeviceOutput
from prodj.timecode import ClockSource
from prodj.timecode.linear.encode import LTCStreamGenerator


class LTCService:
  def __init__(
      self,
      prodj,
      player_number,
      output_config=None,
      output_channel=0,
      fps=25,
      volume=0.8,
      latency_compensation_ms=0):
    self.prodj = prodj
    self.player_number = player_number
    self.output_config = output_config or OutputConfig()
    self.output_channel = output_channel
    self.fps = fps
    self.volume = volume
    self.latency_compensation_ms = latency_compensation_ms
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
      self.generator.render,
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

  def start(self):
    logging.info(
      "Starting LTC output for player %d at %.3f fps on device %s with %.1f ms compensation",
      self.player_number,
      self.fps,
      self.output_config.device,
      self.latency_compensation_ms,
    )
    self.output.start()

  def stop(self):
    self.output.stop()
