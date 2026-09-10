"""Train a tabular Q-learning agent on thousands of dino games in parallel."""

import time
from pathlib import Path

import numpy as np

from game import MAX_SPEED, N_ACTIONS, N_STATES, Dino

GAMES, STEPS, ALPHA, GAMMA, COST = 4096, 20_000, 0.3, 0.97, 0.01

rng = np.random.default_rng(0)
env = Dino(GAMES, max_start_speed=MAX_SPEED, seed=0)  # random start speeds cover the whole game early on
# Rewards are never positive, so untried actions look best and get explored without epsilon-greedy
q = np.zeros((N_STATES, N_ACTIONS), np.float32)
s, crashes, start = env.state(), 0, time.time()
for t in range(1, STEPS + 1):
    a = q[s].argmax(1)
    crashed = env.step(a)
    s_next = env.state()
    # Crashing costs 1, and ducking on the ground a little so the agent only ducks when it must.
    # Duplicate (s, a) pairs keep the last write, i.e. one sampled update each.
    reward = np.where(crashed, -1, -COST * env.duck)
    q[s, a] += ALPHA * (reward + GAMMA * q[s_next].max(1) * ~crashed - q[s, a])
    s, crashes = s_next, crashes + crashed.sum()
    if t % 100 == 0:  # restart a few games so good agents keep practicing every speed
        env.reset(rng.choice(GAMES, GAMES // 50, replace=False))
        s = env.state()
    if t % 1000 == 0:
        print(f"step {t:>6} | {GAMES * 1000 / max(crashes, 1):>8.0f} frames/crash | {time.time() - start:.0f}s")
        crashes = 0

model = Path(__file__).with_name("model.npz")
np.savez(model, q=q, frames=GAMES * STEPS, seconds=time.time() - start)
