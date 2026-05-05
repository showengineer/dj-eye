import wave
import random
import numpy as np


def set_bits(bits, start, value, count):
    for i in range(count):
        bits[start + i] = (value >> i) & 1


def make_ltc_frame(frame_number, fps, *, drop_frame = False):
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
    set_bits(bits, 0, frames % 10, 4)       # frame units, bits 0-3
    set_bits(bits, 8, frames // 10, 2)      # frame tens, bits 8-9
    bits[10] = 1 if drop_frame else 0       # drop-frame flag
    bits[11] = 0                            # color-frame flag

    # Seconds
    set_bits(bits, 16, seconds % 10, 4)     # seconds units, bits 16-19
    set_bits(bits, 24, seconds // 10, 3)    # seconds tens, bits 24-26
    bits[27] = 0                            # biphase correction / flag bit

    # Minutes
    set_bits(bits, 32, minutes % 10, 4)     # minutes units, bits 32-35
    set_bits(bits, 40, minutes // 10, 3)    # minutes tens, bits 40-42
    bits[43] = 0                            # binary group flag

    # Hours
    set_bits(bits, 48, hours % 10, 4)       # hours units, bits 48-51
    set_bits(bits, 56, hours // 10, 2)      # hours tens, bits 56-57
    bits[58] = 0                            # binary group flag
    bits[59] = 0                            # binary group flag

    # User bits blijven hier allemaal 0:
    # 4-7, 12-15, 20-23, 28-31,
    # 36-39, 44-47, 52-55, 60-63

    # Sync word, bits 64-79, LSB-first
    sync_bits = [int(c) for c in "0011111111111101"]
    bits[64:80] = sync_bits

    return bits


def make_ltc_bitstream(
    fps=25,
    duration=10,
    start_hour=0,
    start_minute=0,
    start_second=0,
    start_frame=0,
):
    fps_int = int(round(fps))

    start_frame_number = (
        ((start_hour * 3600) + (start_minute * 60) + start_second)
        * fps_int
        + start_frame
    )

    frame_count = int(duration * int(round(fps)))
    bitstream = []

    for i in range(frame_count):
        bitstream.extend(make_ltc_frame(start_frame_number + i, fps))

    return bitstream


def biphase_mark_encode(
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


def write_wav(filename, audio, sample_rate=48000):
    audio_i16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)

    with wave.open(filename, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(audio_i16.tobytes())


def generate_ltc(
    output_file="ltc.wav",
    fps=25,
    duration=10,
    sample_rate=48000,
    start_hour=0,
    start_minute=0,
    start_second=0,
    start_frame=0,
    jitter=0.0,
):
    bitstream = make_ltc_bitstream(
        fps=fps,
        duration=duration,
        start_hour=start_hour,
        start_minute=start_minute,
        start_second=start_second,
        start_frame=start_frame,
    )

    audio = biphase_mark_encode(
        bitstream,
        sample_rate=sample_rate,
        fps=fps,
        amplitude=0.8,
        jitter=jitter,
    )

    write_wav(output_file, audio, sample_rate)

    print(f"Wrote {output_file}")


if __name__ == "__main__":
    generate_ltc(
        output_file="ltc.wav",
        fps=30,
        duration=10,
        sample_rate=48000,
        start_hour=0,
        start_minute=0,
        start_second=0,
        start_frame=0,
        jitter=0.0,
    )