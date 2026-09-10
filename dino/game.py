"""Chrome's T-Rex runner as a vectorized NumPy game: n games advance one 60 FPS frame per step."""

import numpy as np

WIDTH, SPEED, MAX_SPEED, ACCEL = 600, 6.0, 13.0, 0.001
DINO_X, DINO_W, DINO_H, DUCK_W, DUCK_H = 50, 44, 47, 59, 25
JUMP_V, GRAVITY, DROP, PAD = 10.0, 0.6, 3.0, 4  # PAD forgives near misses, like Chrome's hitboxes
SLOTS = 4  # obstacles tracked per game, enough to keep spawns off-screen

# Obstacle kinds, ordered by the speed that unlocks them: small cacti x1-3, large cacti x1-3, low/mid/high birds
KIND_W = np.array([17, 34, 51, 25, 50, 75, 46, 46, 46])
KIND_LOW = np.array([0, 0, 0, 0, 0, 0, 0, 25, 50])  # height of the bottom edge above ground
KIND_HIGH = KIND_LOW + [35, 35, 35, 50, 50, 50, 40, 40, 40]
KIND_MIN_SPEED = np.array([0, 0, 0, 0, 7, 7, 8.5, 8.5, 8.5])
KIND_MIN_GAP = np.array([72, 72, 72, 72, 72, 72, 90, 90, 90])

# Discrete state: timing of the next obstacle, its kind, speed band, dino height band, rising
STATE_SHAPE = (60, len(KIND_W), 4, 9, 2)
N_STATES, N_ACTIONS = int(np.prod(STATE_SHAPE)), 3  # actions: run, jump, duck


class Dino:
    def __init__(self, n, max_start_speed=SPEED, seed=None):
        self.rng = np.random.default_rng(seed)
        self.max_start_speed = max_start_speed
        self.speed, self.dist, self.y, self.vy = np.zeros((4, n))
        self.duck = np.zeros(n, bool)
        self.ox, self.kind = np.zeros((n, SLOTS)), np.zeros((n, SLOTS), int)
        self.reset(np.arange(n))

    def reset(self, rows):
        self.speed[rows] = self.rng.uniform(SPEED, self.max_start_speed, len(rows))
        self.dist[rows] = self.y[rows] = self.vy[rows] = 0
        x = np.full(len(rows), float(WIDTH))
        for j in range(SLOTS):
            self.ox[rows, j], self.kind[rows, j] = x, self._new_kind(rows)
            x = x + self._spacing(rows, self.kind[rows, j])

    def step(self, action):
        """Advance one frame and return which games crashed (those are reset)."""
        grounded = self.y == 0
        self.duck = grounded & (action == 2)
        drop = np.where((action == 2) & (self.vy < 0), DROP, 1)  # ducking while falling lands sooner
        self.vy = np.where(grounded & (action == 1), JUMP_V, self.vy - GRAVITY * drop)
        self.y = np.maximum(self.y + self.vy, 0)
        self.vy *= self.y > 0

        self.ox -= self.speed[:, None]
        self.dist += self.speed
        self.speed = np.minimum(self.speed + ACCEL, MAX_SPEED)

        # Recycle obstacles that left the screen to the back of the queue
        rows, cols = np.nonzero(self.ox + KIND_W[self.kind] < 0)
        last = self.ox[rows].argmax(1)
        self.ox[rows, cols] = self.ox[rows, last] + self._spacing(rows, self.kind[rows, last])
        self.kind[rows, cols] = self._new_kind(rows)

        x, k = self.next_obstacle()
        right = DINO_X + np.where(self.duck, DUCK_W, DINO_W)
        top = self.y + np.where(self.duck, DUCK_H, DINO_H)
        crashed = (x < right - PAD) & (x + KIND_W[k] > DINO_X + PAD)
        crashed &= (KIND_LOW[k] < top - PAD) & (KIND_HIGH[k] > self.y + PAD)
        self.reset(np.flatnonzero(crashed))
        return crashed

    def next_obstacle(self):
        """Position and kind of the nearest obstacle the dino hasn't cleared yet."""
        i = np.where(self.ox + KIND_W[self.kind] > DINO_X, self.ox, np.inf).argmin(1)
        rows = np.arange(len(i))
        return self.ox[rows, i], self.kind[rows, i]

    def state(self):
        """Discrete state index of each game."""
        x, k = self.next_obstacle()
        # Frames until the obstacle is reached or, once overlapping, minus the frames until it is cleared
        ahead = x - DINO_X - DINO_W
        frames = np.clip(np.where(ahead > 0, ahead, -(ahead + KIND_W[k] + DINO_W)) // self.speed, -20, 39) + 20
        band = (self.speed - SPEED) // 2
        height = np.minimum(self.y // 10, 8)
        index = (frames.astype(int), k, band.astype(int), height.astype(int), self.vy > 0)
        return np.ravel_multi_index(index, STATE_SHAPE)

    def _new_kind(self, rows):
        """Random kind among those unlocked at each game's speed."""
        unlocked = (KIND_MIN_SPEED <= self.speed[rows, None]).sum(1)
        return (self.rng.random(len(rows)) * unlocked).astype(int)

    def _spacing(self, rows, kind):
        """Distance from an obstacle's left edge to the next one's, using Chrome's gap rule."""
        gap = KIND_W[kind] * self.speed[rows] + KIND_MIN_GAP[kind]
        return KIND_W[kind] + gap * self.rng.uniform(1, 1.5, len(rows))
