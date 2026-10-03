import os
import math
from PIL import Image, ImageDraw, ImageFilter

assets_dir = r"c:\Users\Instrutor\Desktop\files (1)\Main Python Game\assets\textures"
os.makedirs(assets_dir, exist_ok=True)

def create_fireball_sprite(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2.0, size / 2.0
    
    # Radii
    r_outer = size * 0.45
    r_mid = size * 0.30
    r_core = size * 0.15
    
    # Outer fire halo
    for r in range(int(r_outer), 0, -2):
        alpha = int(255 * (1.0 - (r / r_outer) ** 1.5) * 0.6)
        color = (255, int(40 + 120 * (1 - r/r_outer)), 0, alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # Mid flaming body
    for r in range(int(r_mid), 0, -2):
        alpha = int(255 * (1.0 - (r / r_mid) ** 2.0) * 0.85)
        color = (255, int(120 + 110 * (1 - r/r_mid)), 0, alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # Core bright white/yellow center
    for r in range(int(r_core), 0, -1):
        alpha = int(255 * (1.0 - (r / r_core) ** 2.5))
        color = (255, 255, int(180 + 75 * (1 - r/r_core)), alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # Add flame tendrils/sparks
    import random
    random.seed(42)
    for _ in range(60):
        angle = random.uniform(0, math.pi * 2)
        dist = random.uniform(r_core, r_outer * 0.95)
        px = cx + dist * math.cos(angle)
        py = cy + dist * math.sin(angle)
        pr = random.uniform(3, 12)
        alpha = random.randint(120, 240)
        col = (255, random.randint(80, 220), 0, alpha)
        draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=col)

    # Soft blur
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    return img

fb_img = create_fireball_sprite(256)
fb_path = os.path.join(assets_dir, "fireball.png")
fb_img.save(fb_path, "PNG")

fb_sprite_path = os.path.join(assets_dir, "fireball_sprite.png")
fb_img.save(fb_sprite_path, "PNG")

print(f"FIREBALL SPRITES GENERATED SUCCESSFULLY AT: {fb_path}")
