import wave
import random
import numpy as np


class LTCGenerator():
    def __init__():
        # Audio socket/output?
        # callbacks/ed?
        pass


    def biphase_mark_encode(self,
        bitstream: list[int],
        sample_rate=48000,
        fps=25,
        amplitude=0.8,
        jitter=0.0,
    ):
        """
        Converts a raw bitstream into biphase-mark encoded audio samples. 
    
        Parameters
        ----------
        bitstream : list[int]
            A list of bits to be converted
        sample_rate : int
            The sample rate of the audio sample (default 48000)
        fps : int
            LTC frames per second. Typical values are 25, 30. 
        """
    
        nominal_half_bit_samples = sample_rate / (fps * 80 * 2)
    
        level = 1.0
        samples = []
    
        for bit in bitstream:
            # transition aan begin van bit
            level *= -1.0
    
            if jitter == 0:
                n1 = int(round(nominal_half_bit_samples))
            else:
                # jitter = 1 betekent: vrij extreme timing-rommel
                factor = 1.0 + random.uniform(-0.85, 0.85) * jitter
                n1 = max(1, int(round(nominal_half_bit_samples * factor)))
    
            samples.extend([level] * n1)
    
            # extra transition halverwege bij een 1
            if bit == 1:
                level *= -1.0
    
            if jitter == 0:
                n2 = int(round(nominal_half_bit_samples))
            else:
                factor = 1.0 + random.uniform(-0.85, 0.85) * jitter
                n2 = max(1, int(round(nominal_half_bit_samples * factor)))
    
            samples.extend([level] * n2)
    
        audio = np.array(samples, dtype=np.float32)
        audio *= amplitude
    
        return audio
    
    
    def set_bits(self, bits, start, value, count):
        for i in range(count):
            bits[start + i] = (value >> i) & 1
    
    
    def make_ltc_frame(self, frame_number, fps, *, drop_frame = False):
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
        sync_bits = [int(c) for c in "0011111111111101"]
        bits[64:80] = sync_bits
    
        return bits