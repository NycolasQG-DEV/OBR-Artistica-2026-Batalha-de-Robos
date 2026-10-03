import os
import math
from PIL import Image, ImageDraw, ImageFilter

assets_dir = r"c:\Users\Instrutor\Desktop\files (1)\Main Python Game\assets\textures"
os.makedirs(assets_dir, exist_ok=True)

def create_catcher_texture(w=512, h=160):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Base jaw metallic body
    pad = 12
    jaw_box = [pad, pad + 20, w - pad, h - pad]
    
    # Outer dark titanium chassis with rounded corners
    draw.rounded_rectangle(jaw_box, radius=24, fill=(18, 22, 34, 240), outline=(255, 120, 0, 255), width=4)

    # Inner glowing magma core
    core_box = [pad + 12, pad + 32, w - pad - 12, h - pad - 12]
    draw.rounded_rectangle(core_box, radius=16, fill=(255, 60, 0, 210), outline=(255, 200, 0, 220), width=3)

    # Cybernetic mechanical teeth along top edge
    num_teeth = 9
    tooth_w = (w - pad * 4) / num_teeth
    for i in range(num_teeth):
        tx = pad * 2 + i * tooth_w
        ty_top = pad - 4
        ty_bot = pad + 34
        pts = [(tx, ty_bot), (tx + tooth_w * 0.5, ty_top), (tx + tooth_w, ty_bot)]
        draw.polygon(pts, fill=(255, 230, 160, 255), outline=(255, 100, 0, 255))

    # Side thrusters / energy vents
    draw.ellipse([pad - 4, h/2 - 16, pad + 24, h/2 + 16], fill=(0, 240, 255, 220), outline=(255, 255, 255, 255), width=2)
    draw.ellipse([w - pad - 24, h/2 - 16, w - pad + 4, h/2 + 16], fill=(0, 240, 255, 220), outline=(255, 255, 255, 255), width=2)

    # Glow filter
    blur = img.filter(ImageFilter.GaussianBlur(radius=1.0))
    return Image.alpha_composite(blur, img)

def create_hud_badge_texture(w=384, h=128):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Carbon fiber style translucent frame
    frame_box = [10, 10, w - 10, h - 10]
    draw.rounded_rectangle(frame_box, radius=20, fill=(10, 14, 26, 230), outline=(255, 140, 0, 240), width=4)

    # Inner glowing border
    inner_box = [18, 18, w - 18, h - 18]
    draw.rounded_rectangle(inner_box, radius=14, fill=(30, 10, 5, 140), outline=(255, 80, 0, 160), width=2)

    # Left accent meteor icon indicator circle
    draw.ellipse([26, h/2 - 28, 82, h/2 + 28], fill=(255, 80, 0, 240), outline=(255, 220, 0, 255), width=3)
    draw.ellipse([38, h/2 - 16, 70, h/2 + 16], fill=(255, 220, 140, 255))

    return img

catcher_img = create_catcher_texture(512, 160)
catcher_path = os.path.join(assets_dir, "meteor_stomp_catcher.png")
catcher_img.save(catcher_path, "PNG")

badge_img = create_hud_badge_texture(384, 128)
badge_path = os.path.join(assets_dir, "meteor_stomp_hud_badge.png")
badge_img.save(badge_path, "PNG")

print(f"HUD TEXTURES GENERATED SUCCESSFULLY AT: {catcher_path} AND {badge_path}")
