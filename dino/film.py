"""Film the trained agent playing one game, showing the moves it makes, and save it as a GIF."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from game import DINO_H, DINO_W, DINO_X, DUCK_W, KIND_HIGH, WIDTH, Dino

HERE = Path(__file__).parent
START, FRAMES, EVERY, SEED = 5400, 1200, 2, 0  # film 20s from 90s in (60 FPS), keeping every 2nd frame
HEIGHT, GROUND, HORIZON_Y = 150, 140, 127  # canvas height, ground and horizon strip, as in Chrome
SKY, SAND, SOIL, DINO, CACTUS, BIRD, TEXT = (
    (225, 245, 254), (255, 236, 179), (161, 136, 127), (67, 160, 71), (0, 105, 92), (216, 67, 21), (55, 71, 79)
)
PALETTE = Image.new("P", (1, 1))
PALETTE.putpalette([c for color in (SKY, SAND, SOIL, DINO, CACTUS, BIRD, TEXT) for c in color])
FONT = ImageFont.load_default_imagefont()

# Chromium's offline sprite sheet, reduced to ink masks so each sprite can be painted in any color
SHEET = Image.open(HERE / "sprite.png").point(lambda v: 255 * (v == 83))


def sprite(x, w, h, y=2):
    return SHEET.crop((x, y, x + w, y + h))


RUN = [sprite(936, DINO_W, DINO_H), sprite(980, DINO_W, DINO_H)]
DUCK = [sprite(1112, DUCK_W, DINO_H), sprite(1171, DUCK_W, DINO_H)]  # drawn at full height, like Chrome
JUMP = sprite(848, DINO_W, DINO_H)
CACTI = [(228, 17, 35), (245, 34, 35), (279, 51, 35), (332, 25, 50), (357, 50, 50), (407, 75, 50)]
OBSTACLES = [sprite(x, w, h) for x, w, h in CACTI]
BIRDS, HORIZON = [sprite(134, 46, 40), sprite(180, 46, 40)], sprite(2, 1200, 12, y=54)
DIGITS = [sprite(655 + 10 * d, 10, 13) for d in range(10)]


def draw(env, t, action, caption):
    im = Image.new("RGB", (WIDTH, HEIGHT), SKY)
    pen = ImageDraw.Draw(im)
    pen.rectangle((0, HORIZON_Y + 5, WIDTH, HEIGHT), SAND)
    scroll = int(env.dist[0]) % HORIZON.width
    for x in (-scroll, HORIZON.width - scroll):
        im.paste(SOIL, (x, HORIZON_Y), HORIZON)

    for x, k in zip(env.ox[0], env.kind[0]):
        bird = k >= len(OBSTACLES)
        im.paste(BIRD if bird else CACTUS, (int(x), GROUND - KIND_HIGH[k]), BIRDS[t // 10 % 2] if bird else OBSTACLES[k])

    dino = JUMP if env.y[0] > 0 else (DUCK if env.duck[0] else RUN)[t // 5 % 2]
    im.paste(DINO, (DINO_X, GROUND - DINO_H - int(env.y[0])), dino)

    # The agent's move: ducking (or dropping) if it chose to, else jumping while airborne, else running
    move = 2 if action == 2 else int(env.y[0] > 0)
    for i, name in enumerate(("RUN", "JUMP", "DUCK")):
        pen.text((220 + 40 * i, 8), name, DINO if i == move else TEXT, FONT)

    for i, d in enumerate(f"{int(env.dist[0] * 0.025):05d}"):  # Chrome's score
        im.paste(TEXT, (534 + 11 * i, 6), DIGITS[int(d)])
    pen.text((WIDTH - 6 - pen.textlength(caption, FONT), 24), caption, TEXT, FONT)
    return im.quantize(palette=PALETTE, dither=Image.Dither.NONE)


model = np.load(HERE / "model.npz")
q, caption = model["q"], f"Q-learning: {model['frames'] / 1e6:.0f}M frames in {model['seconds']:.0f}s"
env, frames = Dino(1, seed=SEED), []
for t in range(START + FRAMES):
    action = q[env.state()].argmax(1)
    if env.step(action)[0]:
        raise SystemExit(f"The agent crashed at frame {t}, try another SEED")
    if t >= START and t % EVERY == 0:
        frames.append(draw(env, t, action[0], caption))
frames[0].save(HERE / "dino.gif", save_all=True, append_images=frames[1:], duration=EVERY * 1000 // 60, loop=0)
