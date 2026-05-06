import logging
import time

import numpy as np
from prodj.timecode import ClockSource

POSITION_DISCONTINUITY_SECONDS = 0.25
LATENCY_LOG_INTERVAL = 2.0


class LTCStreamGenerator():
    def __init__(self, 
                 clock_source: ClockSource, 
                 fps: int = 25, 
                 sample_rate: int = 48000, 
                 volume: float = 0.8,
                 latency_compensation_ms: float = 0):
        self.clock_source = clock_source
        self.fps = fps
        self.sample_rate = sample_rate
        self.volume = volume
        self.latency_compensation_ms = latency_compensation_ms
        self._frame_cache = {}
        self._sample_cursor = None
        self._sample_rate = sample_rate
        self._bmc_level = 1.0
        self._current_frame_number = None
        self._current_frame_audio = None
        self._current_frame_offset = 0
        self._current_frame_end_level = 1.0
        self._last_latency_log = 0

    def samples_per_ltc_frame(self, sample_rate=None):
        sample_rate = sample_rate or self.sample_rate
        return int(round(sample_rate / self.fps))

    def render_ltc_frame(self, frame_number, sample_rate=None, start_level=1.0):
        sample_rate = sample_rate or self.sample_rate
        cache_key = (int(frame_number), sample_rate, self.fps, self.volume, start_level)
        if cache_key not in self._frame_cache:
            raw_frame = self.gen_ltc_frame(int(frame_number), self.fps)
            self._frame_cache[cache_key] = self.biphase_mark_encode(
                raw_frame,
                sample_rate,
                self.fps,
                self.volume,
                start_level=start_level,
                return_final_level=True,
            )
        return self._frame_cache[cache_key]

    def biphase_mark_encode(self,
        bitstream: list[int],
        sample_rate=48000,
        fps=25,
        amplitude=0.8,
        start_level=1.0,
        return_final_level=False,
    ):
        """
        Converts a raw bitstream into biphase-mark encoded audio (samples). 
    
        Parameters
        ----------
        bitstream : list[int]
            A list of bits to be converted
        sample_rate : int
            The sample rate of the audio sample (default 48000)
        fps : int
            LTC frames per second. Typical values are 25, 29.97, 30. 
        """
    
        nominal_half_bit_samples = sample_rate / (fps * 80 * 2)
    
        level = start_level
        samples = []
    
        for bit in bitstream:
            # transition aan begin van bit
            level *= -1.0
    
            n1 = int(round(nominal_half_bit_samples))
            samples.extend([level] * n1)
    
            # extra transition halverwege bij een 1
            if bit == 1:
                level *= -1.0
            n2 = int(round(nominal_half_bit_samples))
    
            samples.extend([level] * n2)
    
        audio = np.array(samples, dtype=np.float32)
        audio *= amplitude

        if return_final_level:
            return audio, level
        return audio

    def reset_stream(self, start_sample, sample_rate):
        self._sample_cursor = float(max(0, start_sample))
        self._sample_rate = sample_rate
        self._bmc_level = 1.0
        self._current_frame_number = None
        self._current_frame_audio = None
        self._current_frame_end_level = 1.0
        self._current_frame_offset = 0

    def load_frame(self, frame_number, sample_rate):
        if self._current_frame_number == frame_number and self._current_frame_audio is not None:
            return
        self._current_frame_number = frame_number
        self._current_frame_audio, self._current_frame_end_level = self.render_ltc_frame(
            frame_number,
            sample_rate,
            start_level=1.0,
        )

    def output_latency_ms(self, device_info):
        if device_info is None:
            return None
        current_time = getattr(device_info, "currentTime", None)
        output_time = getattr(device_info, "outputBufferDacTime", None)
        if current_time is None or output_time is None:
            return None
        return (output_time - current_time) * 1000

    def log_latency(self, frames_requested, sample_rate, device_info, clock_offset_samples):
        now = time.monotonic()
        if now - self._last_latency_log < LATENCY_LOG_INTERVAL:
            return
        self._last_latency_log = now
        output_latency_ms = self.output_latency_ms(device_info)
        block_ms = frames_requested / sample_rate * 1000
        clock_offset_ms = clock_offset_samples / sample_rate * 1000
        if output_latency_ms is None:
            logging.info(
                "LTC latency: clock offset %.1f ms, compensation %.1f ms, audio block %.1f ms",
                clock_offset_ms,
                self.latency_compensation_ms,
                block_ms,
            )
        else:
            logging.info(
                "LTC latency: clock offset %.1f ms, compensation %.1f ms, device/DAC %.1f ms, audio block %.1f ms",
                clock_offset_ms,
                self.latency_compensation_ms,
                output_latency_ms,
                block_ms,
            )
    
    
    def set_bits(self, bits, start, value, count):
        for i in range(count):
            bits[start + i] = (value >> i) & 1
    
    
    def gen_ltc_frame(self, frame_number, fps, *, drop_frame = False):
        """"Generates a raw LTC frame. 
        
            Parameters
            ----------
            frame_number : int
                The frame number. The time is calculated from this value
            fps : int
                The LTC frame rate. 
            drop_frame : bool
                Set the drop frame 
        """
        fps_int = int(round(fps))
    
        frames = frame_number % fps_int
        total_seconds = frame_number // fps_int
        seconds = total_seconds % 60
        minutes = (total_seconds // 60) % 60
        hours = (total_seconds // 3600) % 24
    
        bits = [0] * 80
        # Frames
        self.set_bits(bits, 0, frames % 10, 4)       # frame units, bits 0-3
        self.set_bits(bits, 8, frames // 10, 2)      # frame tens, bits 8-9
        bits[10] = 1 if drop_frame else 0       # drop-frame flag
        bits[11] = 0                            # color-frame flag
    
        # Seconds
        self.set_bits(bits, 16, seconds % 10, 4)     # seconds units, bits 16-19
        self.set_bits(bits, 24, seconds // 10, 3)    # seconds tens, bits 24-26
        bits[27] = 0                            # biphase correction / flag bit
    
        # Minutes
        self.set_bits(bits, 32, minutes % 10, 4)     # minutes units, bits 32-35
        self.set_bits(bits, 40, minutes // 10, 3)    # minutes tens, bits 40-42
        bits[43] = 0                            # binary group flag
    
        # Hours
        self.set_bits(bits, 48, hours % 10, 4)       # hours units, bits 48-51
        self.set_bits(bits, 56, hours // 10, 2)      # hours tens, bits 56-57
        bits[58] = 0                            # binary group flag
        bits[59] = 0                            # binary group flag
    
        # Sync word, bits 64-79, LSB-first
        if bits[:64].count(0) % 2:
            bits[27] = 1

        sync_bits = [int(c) for c in "0011111111111101"]
        bits[64:80] = sync_bits
    
        return bits
    
    def render(self, frames_requested, sample_rate, device_info=None):
        sample_rate = sample_rate or self.sample_rate

        transport_position = self.clock_source.get_transport_position()

        if transport_position is None:
            self._sample_cursor = None
            self._current_frame_audio = None
            return np.zeros(frames_requested, dtype=np.float32)

        transport_rate = self.clock_source.get_transport_rate()
        if transport_rate <= 0:
            self._sample_cursor = None
            self._current_frame_audio = None
            return np.zeros(frames_requested, dtype=np.float32)

        samples_per_frame = self.samples_per_ltc_frame(sample_rate)
        compensation_samples = sample_rate * (self.latency_compensation_ms / 1000) * transport_rate
        measured_sample = transport_position * samples_per_frame + compensation_samples
        clock_offset_samples = 0
        if self._sample_cursor is None or sample_rate != self._sample_rate:
            self.reset_stream(int(round(measured_sample)), sample_rate)
        else:
            correction = measured_sample - self._sample_cursor
            clock_offset_samples = correction
            discontinuity_threshold = samples_per_frame * self.fps * POSITION_DISCONTINUITY_SECONDS
            if abs(correction) > discontinuity_threshold:
                logging.info(
                    "LTC discontinuity %.1f ms, resetting output stream position",
                    correction / sample_rate * 1000,
                )
                self.reset_stream(int(round(measured_sample)), sample_rate)
                clock_offset_samples = 0

        self.log_latency(frames_requested, sample_rate, device_info, clock_offset_samples)

        output = np.zeros(frames_requested, dtype=np.float32)

        for index in range(frames_requested):
            source_sample = int(self._sample_cursor)
            frame_number = source_sample // samples_per_frame
            frame_offset = source_sample % samples_per_frame
            self.load_frame(frame_number, sample_rate)
            output[index] = self._current_frame_audio[min(frame_offset, len(self._current_frame_audio) - 1)]
            self._sample_cursor += transport_rate

        return output
