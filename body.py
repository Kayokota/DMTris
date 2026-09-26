import random
import sys
import pygame as pg

# --- CONFIG ---
COLS, ROWS = 10, 20
CELL = 30
MARGIN = 20
SIDEBAR = 170
WIN_W = MARGIN * 2 + COLS * CELL + SIDEBAR
WIN_H = MARGIN * 2 + ROWS * CELL
FPS = 60
LOCK_DELAY = 0.5        #Soft-lock таймер, ага - тот самый, когда фигурка падает, но ещё не закрепиласб, нахуя ты это читаешь??)))) Долбаёб

# --- ASSETS ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRID = (51, 51, 51)

COLORS = {
    0: BLACK,
    1: (000, 240, 241), # I
    2: (000, 000, 241), # J
    3: (240, 245, 000), # L
    4: (241, 240, 000), # O
    5: (000, 240, 000), # S
    6: (160, 000, 240), # Z
    7: (242, 000, 000), # T
}


SHAPES = {
    'I': [[0, 0, 0, 0],
          [1, 1, 1, 1],
          [0, 0, 0, 0],
          [0, 0, 0, 0]],
    'J': [[2, 0, 0],
          [2, 2, 2],
          [0, 0, 0]],
    'L': [[0, 0, 3],
          [3, 3, 3],
          [0, 0, 0]],
    'O': [[4, 4],
         [4, 4]],
    'S': [[0, 5, 5],
          [5, 5, 0],
          [0, 0, 0]],
    'T': [[0, 6, 0],
          [6, 6, 6],
          [0, 0, 0]],
    'Z': [[7, 7, 0],
          [0, 7, 7],
          [0, 0, 0]],
}


# --- MATRIX MATH ---
def rotate_cw(matrix):
    return [list(row) for row in zip(*matrix[::-1])]

def rotate_ccw(matrix):
    return rotate_cw(rotate_cw(rotate_cw(matrix)))



# --- COLLISION DETECT ---
def col(grid, piece, dx=0, dy=0, matrix=None):
    p = piece.matrix if matrix is None else matrix
    for r, row in enumerate(p):
        for c, val in enumerate(row):
            if not val:
                continue
            x = piece.x + c + dx
            y = piece.y + r + dy
            if x < 0 or x >= COLS or y >= ROWS:
                return True
            if y >= 0 and grid[y][x]:
                return True
    return False


# --- GAME LOGIC ---
class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.matrix = [row[:] for row in SHAPES[kind]]
        self.x = COLS // 2 - len(self.matrix[0]) // 2
        self.y = 0

class Game:
    def __init__(self):
        self.paused = None
        self.game_over = None
        self.level = None
        self.lines = None
        self.score = None
        self.lock_timer = None
        self.drop_timer = None
        self.piece = None
        self.next_kind = None
        self.bag = None
        self.grid = None
        self.reset()

    def reset(self):
        self.grid = [[0] * COLS for _ in range(ROWS)]
        self.bag = []
        self.next_kind = self.pull()
        self.piece = self.spawn()
        self.drop_timer = 0
        self.lock_timer = 0
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.paused = False

    def pull(self):
        if not self.bag:
            self.bag = list(SHAPES)
            random.shuffle(self.bag)
        return self.bag.pop()

    def spawn(self):
        piece = Piece(self.next_kind)
        self.next_kind = self.pull()
        if col(self.grid, piece):
            self.game_over = True
        return piece

    @property
    def drop_interval(self):
        return max(0.05, 0.8 * (0.85 ** (self.level - 1)))

    def move(self, dx):
        if self.game_over or self.paused:
            return
        if not col(self.grid, self.piece, dx=dx):
            self.piece.x += dx
            self.lock_timer = 0

    def rotate(self, direction=1):
        if self.game_over or self.paused:
            return
        if self.piece.kind == 'O':
            return
        p = self.piece.matrix
        new_p = rotate_cw(p) if direction > 0 else rotate_ccw(p)
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)):
            if not col(self.grid, self.piece, dx=dx, dy=dy, matrix=new_p):
                self.piece.matrix = new_p
                self.piece.x += dx
                self.piece.y += dy
                self.lock_timer = 0
                return

    def soft_drop(self):
        if self.game_over or self.paused:
            return
        if not col(self.grid, self.piece, dy=1):
            self.piece.y += 1
            self.score += 1
            self.drop_timer = 0

    def hard_drop(self):
        if self.game_over or self.paused:
            return
        cells = 0
        while not col(self.grid, self.piece, dy=1):
            self.piece.y += 1
            cells += 1
        self.score += 2 * cells
        self.lock_piece()
        self.lock_timer = 0

    def update(self, dt):
        if self.game_over or self.paused:
            return
        if col(self.grid, self.piece, dy=1):
            self.lock_timer += dt
            if self.lock_timer >= LOCK_DELAY:
                self.lock_piece()
            return

        self.lock_timer = 0
        self.drop_timer += dt
        if self.drop_timer >= self.drop_interval:
            self.drop_timer -= self.drop_interval
            self.piece.y += 1

    def lock_piece(self):
        for r, row in enumerate(self.piece.matrix):
            for c, val in enumerate(row):
                if not val:
                    continue
                y, x = self.piece.y + r, self.piece.x + c
                if y < 0:
                    self.game_over = True
                    return
                self.grid[y][x] = val

        cleared = self.clear_lines()
        self.apply_score(cleared)

        self.piece = self.spawn()
        self.drop_timer = 0
        self.lock_timer = 0

    def clear_lines(self):
        full = [r for r in range(ROWS) if all(self.grid[r])]

        for r in full:
            del self.grid[r]
            self.grid.insert(0, [0] * COLS)
        return len(full)

    def apply_score(self, cleared):
        if not cleared:
            return
        table = {1: 100, 2: 300, 3: 500, 4: 800}
        self.score += table[cleared] * self.level
        self.lines += cleared
        self.level = 1 + self.lines // 10

    def ghost_y(self):
        dy = 0
        while not col(self.grid, self.piece, dy=dy + 1):
            dy += 1
        return self.piece.y + dy



# --- RENDER ---
def cell_rect(x, y):
        return pg.Rect(MARGIN + x * CELL, MARGIN + y * CELL, CELL, CELL)


def draw_block(surf, x, y, color, filled=True):
    rect = cell_rect(x, y)
    if filled:
        pg.draw.rect(surf, color, rect)
        pg.draw.rect(surf, BLACK, rect, 2)
    else:
        pg.draw.rect(surf, color, rect, 2)


def draw_next(surf, kind):
    p = SHAPES[kind]
    cells = [(r, c) for r, row in enumerate(p) for c, v in enumerate(row) if v]
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    w = max(cols) - min(cols) + 1
    size = int(CELL * 0.7)
    ox = MARGIN + COLS * CELL + (SIDEBAR - w * size) // 2
    oy = 120
    for r, c in cells:
        rect = pg.Rect(ox + (c - min(cols)) * size,
                       oy + (r - min(rows)) * size, size, size)
        pg.draw.rect(surf, COLORS[p[r][c]], rect)
        pg.draw.rect(surf, BLACK, rect, 2)

def draw(screen, game, font, big):
    screen.fill(BLACK)

    board = pg.Rect(MARGIN, MARGIN, COLS * CELL, ROWS * CELL)
    pg.draw.rect(screen, (22, 22, 30), board)

    #Отрисовка сетки линий поверх фона
    for c in range(1, COLS):
        pg.draw.line(screen, GRID, (MARGIN + c * CELL, MARGIN),
                     (MARGIN + c * CELL, MARGIN + ROWS * CELL))

    #Блоки поля
    for r in range(1, ROWS):
        pg.draw.line(screen, GRID, (MARGIN, MARGIN + r * CELL),
                     (MARGIN + COLS * CELL, MARGIN + r * CELL))

    for r in range(ROWS):
        for c in range(COLS):
            if game.grid[r][c]:
                draw_block(screen, c, r, COLORS[game.grid[r][c]])

#Фигура и её тень
    gy = game.ghost_y()
    for r, row in enumerate(game.piece.matrix):
        for c, val in enumerate(row):
            if not val:
                continue
            color = COLORS[val]
            if game.piece.y + r != gy + r or gy != game.piece.y:
                draw_block(screen, game.piece.x + c, gy + r, color, filled=False)
            draw_block(screen, game.piece.x + c, game.piece.y + r, color)

    pg.draw.rect(screen, GRID, board, 2)

#UI сайдбара
    x = MARGIN + COLS * CELL + 20
    screen.blit(big.render('DMTRIS', True, WHITE), (x, 30))
    for i, text in enumerate((f'SCORE: {game.score}',
                                    f'LINES: {game.lines}',
                                    f'LEVEL: {game.level}')):
        screen.blit(font.render(text, True, WHITE), (x, 200 + i * 28))
    screen.blit(font.render('NEXT', True, WHITE), (x, 90))
    draw_next(screen, game.next_kind)

#Оверлеи состояний
    if game.paused:
        screen.blit(big.render('PAUSE', True, WHITE),
                    (MARGIN + 40, MARGIN + ROWS * CELL // 2))
    if game.game_over:
        msg = big.render('GAME OVER', True, (255, 90, 90))
        screen.blit(msg, (MARGIN + 20, MARGIN + ROWS * CELL // 2 - 40))
        hint = font.render('R - restart', True, WHITE)
        screen.blit(hint, (MARGIN + 60, MARGIN + ROWS * CELL // 2 + 10))


# --- INPUT ---
def handle_key(game, key):
    if key == pg.K_ESCAPE:
        pg.quit()
        sys.exit()
    if key == pg.K_r:
        game.reset()
        return
    if key == pg.K_p and not game.game_over:
        game.paused = not game.paused
        return
    if key in (pg.K_LEFT, pg.K_a):
        game.move(-1)
    elif key in (pg.K_RIGHT, pg.K_d):
        game.move(1)
    elif key in (pg.K_DOWN, pg.K_s):
        game.soft_drop()
    elif key == pg.K_SPACE:
        game.hard_drop()
    elif key in (pg.K_UP, pg.K_x, pg.K_w):
        game.rotate(+1)
    elif key in (pg.K_z, pg.K_LCTRL):
        game.rotate(-1)


# --- MAIN ---
def main():
    pg.init()
    screen = pg.display.set_mode((WIN_W, WIN_H))
    pg.display.set_caption('DMTRIS')

    #Шрифты системные, без импорта внешних пока что
    font = pg.font.SysFont('consolas,dejavusanmono,monospace', 20)
    big = pg.font.SysFont('consolas,dejavusanmono,monospace', 34, bold=True)
    clock = pg.time.Clock()
    game = Game()

    while True:
        dt = clock.tick(FPS) / 1000.0
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            if event.type == pg.KEYDOWN:
                handle_key(game, event.key)

        game.update(dt)
        draw(screen, game, font, big)
        pg.display.flip()


if __name__ == ('__main__'):
    main()




