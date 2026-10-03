import wave
import struct
import math
import random
import os

def write_wave(filename, duration, sample_fn, sample_rate=44100):
    num_samples = int(duration * sample_rate)
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with wave.open(filename, 'wb') as w:
        w.setnchannels(1)  # Mono
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        for i in range(num_samples):
            t = i / sample_rate
            value = sample_fn(t, duration)
            # Clip value
            value = max(-1.0, min(1.0, value))
            packed = struct.pack('<h', int(value * 32767))
            w.writeframesraw(packed)

def hover_sample(t, duration):
    freq = 800 + 400 * (t / duration)
    vol = math.exp(-25 * t)
    return math.sin(2 * math.pi * freq * t) * vol * 0.35

def select_sample(t, duration):
    if t < 0.07:
        freq = 700
    else:
        freq = 1100
    vol = math.exp(-12 * t)
    return math.sin(2 * math.pi * freq * t) * vol * 0.5

def hit_sample(t, duration):
    freq = 160 * math.exp(-8 * t)
    noise = random.uniform(-1.0, 1.0)
    vol = math.exp(-5 * t)
    return (0.35 * math.sin(2 * math.pi * freq * t) + 0.65 * noise) * vol * 0.6

def dodge_sample(t, duration):
    freq = 900 - 700 * math.sin(math.pi * t / duration)
    vol = math.sin(math.pi * t / duration) * math.exp(-4 * t)
    return math.sin(2 * math.pi * freq * t) * vol * 0.6

def alert_sample(t, duration):
    freq = 980 if (int(t * 16) % 2 == 0) else 580
    vol = math.sin(math.pi * t / duration)
    val = 0.35 if math.sin(2 * math.pi * freq * t) > 0 else -0.35
    return val * vol * 0.45

def ice_shatter_sample(t, duration):
    freq = 2400.0 * math.exp(-12 * t) + 1200.0 * math.sin(2 * math.pi * 3200 * t)
    noise = random.uniform(-0.8, 0.8)
    vol = math.exp(-18 * t)
    return (0.4 * math.sin(2 * math.pi * freq * t) + 0.6 * noise) * vol * 0.55

def whoosh_sample(t, duration):
    envelope = math.sin(math.pi * (t / duration)) ** 2
    freq = 180 + 750 * math.sin(math.pi * (t / duration))
    noise = random.uniform(-1.0, 1.0)
    sine = math.sin(2 * math.pi * freq * t)
    return (0.35 * sine + 0.65 * noise) * envelope * 0.75

if __name__ == '__main__':
    base_dir = os.path.join("assets", "sounds")
    write_wave(os.path.join(base_dir, "hover.wav"), 0.08, hover_sample)
    write_wave(os.path.join(base_dir, "select.wav"), 0.18, select_sample)
    write_wave(os.path.join(base_dir, "hit.wav"), 0.45, hit_sample)
    write_wave(os.path.join(base_dir, "dodge.wav"), 0.28, dodge_sample)
    write_wave(os.path.join(base_dir, "alert.wav"), 0.35, alert_sample)
    write_wave(os.path.join(base_dir, "ice_shatter.wav"), 0.15, ice_shatter_sample)
    write_wave(os.path.join(base_dir, "whoosh.wav"), 0.70, whoosh_sample)
    print("Sound assets generated successfully inside assets/sounds/.")
