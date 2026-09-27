import random
import sys
import pygame as pg
pg.init()

# --- CONFIGURATION ---
COLS, ROWS = 10, 20
CELL = 40
MARGIN = 20
SIDEBAR = 170
WIN_W = MARGIN * 2 + COLS * CELL + SIDEBAR
WIN_H = MARGIN * 2 + ROWS * CELL
FPS = 60
LOCK_DELAY = 0.5        #Soft-lock таймер

# --- SETTINGS ---
DEFAULT_SETTINGS = {
    'das': 0.13,     # Delayed Auto Shift
    'arr': 0.03,     # Auto Repeat Rate
    'soft_drop_rate': 0.04,     #Скорость софтдропа
    'queue_size': 5,    #Размер сумки
    'hold_enabled': True,   #Функция холда
    'ghost_enabled': True,  #Функция гост-подсветки
    'effects_enabled': True, #Эфекты
}

DEFAULT_KEY_BINDINGS = {
    'move_left':  [pg.K_LEFT, pg.K_a],  #Лево
    'move_right': [pg.K_RIGHT, pg.K_d],  #Право
    'soft_drop':  [pg.K_DOWN, pg.K_s],  #Вниз
    'hard_drop':  [pg.K_SPACE],  #БАМ
    'rotate_cw':  [pg.K_UP, pg.K_w],  #По часовой
    'rotate_ccw': [pg.K_z, pg.K_LCTRL],  #Против часовой
    'hold':       [pg.K_LSHIFT, pg.K_c],  #Холд
    'pause':      [pg.K_p],  #Пауза
    'restart':    [pg.K_r],  #Рестарт
}

# --- ASSETS ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRID = (51, 51, 51)  #Сетка

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
    return [list(row) for row in zip(*matrix)][::-1] #Тройной вызов функции был вайбовее •⩊•


# --- GAME LOGIC ---   (Движок)
class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.matrix = [row[:] for row in SHAPES[kind]]
        self.x = COLS // 2 - len(self.matrix[0]) // 2
        self.y = 0

    # --- COLLISION DETECT ---
    def is_colliding(self, grid, dx=0, dy=0, matrix=None):
        matrix = self.matrix if matrix is None else matrix
        for r, row in enumerate(matrix):
            for c, val in enumerate(row):
                if not val:
                    continue
                x = self.x + c + dx
                y = self.y + r + dy
                if x < 0 or x >= COLS or y >= ROWS:
                    return True
                if y >= 0 and grid[y][x]:
                    return True
        return False


class Game:
    def __init__(self, settings):
        self.settings = settings
        self.reset()

    def reset(self):
        self.grid = [[0] * COLS for _ in range(ROWS)]
        self.bag = []
        self.next_queue = []
        self._refill_queue()
        self.hold_kind = None
        self.can_hold = True
        self.piece = self.spawn()
        self.drop_timer = 0
        self.lock_timer = 0
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.paused = False
        self.flash = 0.0

    # --- QUEUE HANDLING ---  (Сумка фигур типа SRS)
    def _refill_queue(self):  #Вспомогательный метод заполнения queue
        while len(self.next_queue) < self.settings['queue_size']:
            if not self.bag:
                self.bag = list(SHAPES)
                random.shuffle(self.bag)
            self.next_queue.append(self.bag.pop())

    def pull(self):
        if not self.bag:
            self.bag = list(SHAPES)
            random.shuffle(self.bag)
        return self.bag.pop()

    def spawn(self):
        if self.next_queue:
            kind = self.next_queue.pop(0)
        else:
            kind = self.pull()
        self._refill_queue()
        piece = Piece(kind)
        if piece.is_colliding(self.grid):
            self.game_over = True
        return piece

    @property
    def next_kind(self):
        return self.next_queue[0] if self.next_queue else 'I'  #Нахуй не надо, но я оставил чтобы багов-хуягов не было

    @property
    def drop_interval(self):
        return max(0.05, 0.8 * (0.85 ** (self.level - 1)))  #В секундах блять

    def move(self, dx):
        if self.game_over or self.paused:
            return False
        if not self.piece.is_colliding(self.grid, dx=dx):
            self.piece.x += dx
            self.lock_timer = 0
            return True
        return False

    def rotate(self, direction=1):
        if self.game_over or self.paused:
            return False
        if self.piece.kind == 'O':
            return False
        p = self.piece.matrix
        new_p = rotate_cw(p) if direction > 0 else rotate_ccw(p)
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)):
            if not self.piece.is_colliding(self.grid, dx=dx, dy=dy, matrix=new_p):
                self.piece.matrix = new_p
                self.piece.x += dx
                self.piece.y += dy
                self.lock_timer = 0
                return True
        return False

    def soft_drop(self):
        if self.game_over or self.paused:
            return
        if not self.piece.is_colliding(self.grid, dy=1):
            self.piece.y += 1
            self.score += 1
            self.drop_timer = 0

    def hard_drop(self):
        if self.game_over or self.paused:
            return
        cells = 0
        while not self.piece.is_colliding(self.grid, dy=1):
            self.piece.y += 1
            cells += 1
        self.score += 2 * cells
        self.lock_piece()
        self.lock_timer = 0

    # --- HOLD ---  #Механика холда
    def hold(self):
        if self.game_over or self.paused:
            return False
        if not self.settings['hold_enabled']:
            return False
        if not self.can_hold:
            return False
        if self.hold_kind is None:
            self.hold_kind = self.piece.kind
            self.piece = self.spawn()
        else:
            held = self.hold_kind
            self.hold_kind = self.piece.kind
            new_piece = Piece(held)
            if new_piece.is_colliding(self.grid):
                self.game_over = True
            self.piece = new_piece
        self.can_hold = False  #Сброс флага допустимости холда
        self.drop_timer = 0
        self.lock_timer = 0
        return True

    def update(self, dt):  #Тик обновления игры (В секундах блять, не забывай)
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt * 4.0)

        if self.game_over or self.paused:
            return
        if self.piece.is_colliding(self.grid, dy=1):
            self.lock_timer += dt
            if self.lock_timer >= LOCK_DELAY:
                self.lock_piece()
            return

        self.lock_timer = 0
        self.drop_timer += dt
        if self.drop_timer >= self.drop_interval:
            self.drop_timer -= self.drop_interval
            self.piece.y += 1

    def lock_piece(self):  #Лок фигуры на месте
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
        if cleared:
            self.flash = 1.0

        self.can_hold = True  #Ресет холда
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
        # table = {1: 100, 2: 300, 3: 500, 4: 800} "Кол-во линий: Очки"
        score_table = [100, 300, 500, 800]
        self.score += score_table[cleared - 1] * self.level
        self.lines += cleared
        self.level = 1 + self.lines // 10

    def ghost_y(self):
        dy = 0
        while not self.piece.is_colliding(self.grid, dy=dy + 1):
            dy += 1
        return self.piece.y + dy


# --- INPUT STATE ---  (DAS/ARR)
class InputState:

    def __init__(self):
        self.reset()

    def reset(self):
        self.left_held = False
        self.left_timer = 0.0
        self.left_das_done = False
        self.right_held = False
        self.right_timer = 0.0
        self.right_das_done = False
        self.soft_held = False
        self.soft_timer = 0.0
        self.last_dir = None

    # --- key down handlers ---
    def press_left(self, game, settings):
        self.left_held = True
        self.left_timer = 0.0
        self.left_das_done = False
        self.last_dir = 'left'
        game.move(-1)

    def press_right(self, game, settings):
        self.right_held = True
        self.right_timer = 0.0
        self.right_das_done = False
        self.last_dir = 'right'
        game.move(1)

    def press_soft(self, game, settings):
        self.soft_held = True
        self.soft_timer = 0.0
        game.soft_drop()

    def release_left(self):
        self.left_held = False
        self.left_timer = 0.0
        self.left_das_done = False

    def release_right(self):
        self.right_held = False
        self.right_timer = 0.0
        self.right_das_done = False

    def release_soft(self):
        self.soft_held = False
        self.soft_timer = 0.0

    # --- PER-FRAME UPDATE ---
    def update(self, dt, game, settings):
        #При зажатии вправо и влево - приоритет на последнюю нажатую
        if self.left_held and self.right_held:
            if self.last_dir == 'left':
                self.right_held = False
                self.right_timer = 0.0
                self.right_das_done = False
            elif self.last_dir == 'right':
                self.left_held = False
                self.left_timer = 0.0
                self.left_das_done = False

        self.left_timer, self.left_das_done = self._shift(
            dt, self.left_held, self.left_timer, self.left_das_done,
            -1, game, settings)
        self.right_timer, self.right_das_done = self._shift(
            dt, self.right_held, self.right_timer, self.right_das_done,
            1, game, settings)

        #На софтдроп не распространяется DAS
        if self.soft_held:
            rate = max(0.005, settings['soft_drop_rate'])
            self.soft_timer += dt
            #Чтобы не лагало
            steps = 0
            while self.soft_timer >= rate and steps < 30:
                self.soft_timer -= rate
                game.soft_drop()
                steps += 1

    def _shift(self, dt, held, timer, das_done, direction, game, settings):
        if not held:
            return timer, das_done
        timer += dt
        if not das_done:
            if timer >= settings['das']:
                das_done = True
                timer -= settings['das']
                if settings['arr'] <= 0:
                    while not game.piece.is_colliding(game.grid, dx=direction):
                        game.piece.x += direction
                    timer = 0.0
                    game.lock_timer = 0
        else:
            if settings['arr'] <= 0:
                return timer, das_done
            steps = 0
            while timer >= settings['arr'] and steps < 30:
                timer -= settings['arr']
                if not game.move(direction):
                    break
                steps += 1
        return timer, das_done


# --- RENDERING ---  (Отрисовка)
def cell_rect(x, y):
        return pg.Rect(MARGIN + x * CELL, MARGIN + y * CELL, CELL, CELL)


def draw_block(surf, x, y, color, filled=True):
    rect = cell_rect(x, y)
    if filled:
        pg.draw.rect(surf, color, rect)
        pg.draw.rect(surf, BLACK, rect, 2)
    else:
        pg.draw.rect(surf, color, rect, 2)


#Нахуй не надо, но оставил
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


# --- CENTERED PIECE PREVIEW ---  (Новый метод отображения)
def draw_piece_preview(surf, kind, cx, cy, cell_size):
    p = SHAPES[kind]
    cells = [(r, c) for r, row in enumerate(p) for c, v in enumerate(row) if v]
    if not cells:
        return
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    w = max(cols) - min(cols) + 1  #Ширина фигуры в клетках
    h = max(rows) - min(rows) + 1  #Высота фигуры в клетках
    ox = cx - (w * cell_size) // 2
    oy = cy - (h * cell_size) // 2
    for r, c in cells:
        rect = pg.Rect(ox + (c - min(cols)) * cell_size,
                       oy + (r - min(rows)) * cell_size,
                       cell_size, cell_size)
        pg.draw.rect(surf, COLORS[p[r][c]], rect)
        pg.draw.rect(surf, BLACK, rect, 2)

#Отрисовка интерфейса
def draw(screen, game, font, big, settings):
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
    if not game.game_over:
        if settings['ghost_enabled']:
            gy = game.ghost_y()
            for r, row in enumerate(game.piece.matrix):
                for c, val in enumerate(row):
                    if not val:
                        continue
                    if gy != game.piece.y:
                        draw_block(screen, game.piece.x + c, gy + r,
                                   COLORS[val], filled=False)
        for r, row in enumerate(game.piece.matrix):
            for c, val in enumerate(row):
                if not val:
                    continue
                draw_block(screen, game.piece.x + c, game.piece.y + r, COLORS[val])

    pg.draw.rect(screen, GRID, board, 2)

    # --- SIDEBAR ---
    x = MARGIN + COLS * CELL + 20  #Левая граница сайдбара
    cx = MARGIN + COLS * CELL + SIDEBAR // 2  #Центр сайдбара
    #Заголовок
    screen.blit(big.render('DMTRIS', True, WHITE), (x, 15))

    # --- HOLD BOX ---
    screen.blit(font.render('HOLD', True, WHITE), (x, 68))
    if game.hold_kind:
        if game.can_hold or not game.settings['hold_enabled']:
            draw_piece_preview(screen, game.hold_kind, cx, 112, 18)
        else:
            tmp = pg.Surface((SIDEBAR, 60), pg.SRCALPHA)
            draw_piece_preview(tmp, game.hold_kind, SIDEBAR // 2, 30, 18)
            tmp.set_alpha(90)
            screen.blit(tmp, (x - 20, 82))

# --- QUEUE --- (Очередб фигур)
    screen.blit(font.render('NEXT', True, WHITE), (x, 150))
    qsize = settings['queue_size']
    qy = 185
    for i, kind in enumerate(game.next_queue[:qsize]):
        size = 16 if i > 0 else 20
        spacing = 48 if i > 0 else 56
        draw_piece_preview(screen, kind, cx, qy, size)
        qy += spacing

    #Статистика
    stat_y = WIN_H - 100
    for i, text in enumerate((f'SCORE: {game.score}',
                              f'LINES: {game.lines}',
                              f'LEVEL: {game.level}')):
        screen.blit(font.render(text, True, WHITE), (x, stat_y + i * 26))

    #Эффекты
    if settings['effects_enabled'] and game.flash > 0:
        overlay = pg.Surface((COLS * CELL, ROWS * CELL), pg.SRCALPHA)
        a = int(120 * game.flash)
        overlay.fill((255, 255, 255, a))
        screen.blit(overlay, (MARGIN, MARGIN))

    #Оверлеи состояний
    if game.paused:
        msg = big.render('PAUSE', True, WHITE)
        screen.blit(msg, (MARGIN + COLS * CELL // 2 - msg.get_width() // 2,
                          MARGIN + ROWS * CELL // 2 - 20))
    if game.game_over:
        msg = big.render('GAME OVER', True, (255, 90, 90))
        screen.blit(msg, (MARGIN + 20, MARGIN + ROWS * CELL // 2 - 40))
        hint = font.render('R - restart', True, WHITE)
        screen.blit(hint, (MARGIN + 60, MARGIN + ROWS * CELL // 2 + 10))

    #Tab для настроек
    tip = font.render('TAB - settings', True, (140, 140, 160))
    screen.blit(tip, (x, WIN_H - 24))


# --- SETTINGS MENU ---  (Настройки)
class SettingsMenu:

    def __init__(self, settings, key_bindings):
        self.settings = settings.copy() #Копия для редакта
        self.key_bindings = key_bindings
        self.open = False
        self.selected = 0
        self.rebinding = None
        self.message = ''    #Статусбар внизу

        #Список пунктов меню
        self.items = [
            {'key': 'das',             'label': 'DAS (s)',        'type': 'float',
             'min': 0.0,  'max': 0.30, 'step': 0.01},
            {'key': 'arr',             'label': 'ARR (s)',        'type': 'float',
             'min': 0.0,  'max': 0.20, 'step': 0.005},
            {'key': 'soft_drop_rate',  'label': 'Soft Drop Rate', 'type': 'float',
             'min': 0.01, 'max': 0.20, 'step': 0.005},
            {'key': 'queue_size',      'label': 'Queue Size',     'type': 'int',
             'min': 1,    'max': 8,    'step': 1},
            {'key': 'hold_enabled',    'label': 'Hold',           'type': 'bool'},
            {'key': 'ghost_enabled',   'label': 'Ghost Piece',    'type': 'bool'},
            {'key': 'effects_enabled', 'label': 'Effects',        'type': 'bool'},
            {'key': None,              'label': 'Key Bindings',   'type': 'header'},
        ]

        #Пункты для каждой кнопки управления
        for action in DEFAULT_KEY_BINDINGS:
            self.items.append({'key': action, 'label': action, 'type': 'key'})
        self._move(1)

    #Тогл меню
    def toggle(self):
        self.open = not self.open
        self.rebinding = None
        self.message = ''

    def _navigable(self, idx):
        return self.items[idx]['type'] != 'header'

    def _move(self, direction):
        n = len(self.items)
        i = self.selected
        for _ in range(n):
            i = (i + direction) % n
            if self._navigable(i):
                self.selected = i
                return
        self.selected = 0

    def handle_key(self, key):
        #Обработка ввода внутри меню
        if self.rebinding is not None:
            if key == pg.K_ESCAPE:
                self.rebinding = None
                self.message = 'Rebind cancelled'
                return
            self.key_bindings[self.rebinding] = [key]
            self.message = f"Bound {self.rebinding} -> {pg.key.name(key)}"
            self.rebinding = None
            return

        #Закрытие
        if key in (pg.K_TAB, pg.K_ESCAPE):
            self.open = False
            return

        #Навигация
        if key in (pg.K_UP, pg.K_w):
            self._move(-1)
        elif key in (pg.K_DOWN, pg.K_s):
            self._move(1)
        #Изменение
        elif key in (pg.K_LEFT, pg.K_a):
            self._adjust(-1)
        elif key in (pg.K_RIGHT, pg.K_d):
            self._adjust(1)
        #Подтверждение
        elif key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
            item = self.items[self.selected]
            #Режим переназначения
            if item['type'] == 'key':
                self.rebinding = item['key']
                self.message = f"Press a key for {item['label']} (Esc to cancel)"
            #Булевые флаги
            elif item['type'] == 'bool':
                self.settings[item['key']] = not self.settings[item['key']]
            #Числовые значения
            elif item['type'] in ('float', 'int'):
                self._adjust(1)

    #Изменение выбранного параметра
    def _adjust(self, direction):
        item = self.items[self.selected]
        t = item['type']
        if t == 'float':
            v = self.settings[item['key']] + direction * item['step']
            v = max(item['min'], min(item['max'], v))
            self.settings[item['key']] = round(v, 3)
        elif t == 'int':
            v = self.settings[item['key']] + direction * item['step']
            v = max(item['min'], min(item['max'], v))
            self.settings[item['key']] = int(v)
        elif t == 'bool':
            self.settings[item['key']] = not self.settings[item['key']]

    #Меню поверх игрового поля
    def draw(self, screen, font, big):
        overlay = pg.Surface((WIN_W, WIN_H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        screen.blit(overlay, (0, 0))

        title = big.render('SETTINGS', True, WHITE)
        screen.blit(title, (WIN_W // 2 - title.get_width() // 2, 18))

        y = 72
        for i, item in enumerate(self.items):
            t = item['type']
            if t == 'header':
                text = font.render(f'— {item["label"]} —', True, (200, 200, 120))
                screen.blit(text, (60, y))
                y += 26
                continue

            selected = (i == self.selected)
            color = (255, 240, 100) if selected else WHITE

            #Форматирование отображаемого значения
            if t == 'float':
                val = f"{self.settings[item['key']]:.3f}"
            elif t == 'int':
                val = str(self.settings[item['key']])
            elif t == 'bool':
                val = 'ON' if self.settings[item['key']] else 'OFF'
            elif t == 'key':
                if self.rebinding == item['key']:
                    val = '<press...>'
                else:
                    keys = self.key_bindings.get(item['key'], [])
                    val = ', '.join(pg.key.name(k) for k in keys) if keys else '(none)'
            else:
                val = ''

            prefix = '▶ ' if selected else '  '
            text = font.render(f'{prefix}{item["label"]}: {val}', True, color)
            screen.blit(text, (50, y))
            y += 26
        #Статусная строка
        if self.message:
            msg = font.render(self.message, True, (180, 220, 180))
            screen.blit(msg, (50, y + 6))


# --- INPUT ---  (Функции инпута)
def handle_key_down(game, input_state, key, settings, key_bindings):
    if key == pg.K_ESCAPE:
        pg.quit()
        sys.exit()
    if key == pg.K_TAB:
        return 'open_settings'

    if game.game_over:
        if key in key_bindings['restart']:
            game.reset()
            input_state.reset()
        return

    if key in key_bindings['pause']:
        game.paused = not game.paused
        return

    if game.paused:
        return

    if key in key_bindings['move_left']:
        input_state.press_left(game, settings)
    elif key in key_bindings['move_right']:
        input_state.press_right(game, settings)
    elif key in key_bindings['soft_drop']:
        input_state.press_soft(game, settings)
    elif key in key_bindings['hard_drop']:
        game.hard_drop()
    elif key in key_bindings['restart']:
        game.reset()
        input_state.reset()
    elif key in key_bindings['hold']:
        game.hold()
    elif key in key_bindings['rotate_cw']:
        game.rotate(1)
    elif key in key_bindings['rotate_ccw']:
        game.rotate(-1)


def handle_key_up(game, input_state, key, key_bindings):
    if key in key_bindings['move_left']:
        input_state.release_left()
    elif key in key_bindings['move_right']:
        input_state.release_right()
    elif key in key_bindings['soft_drop']:
        input_state.release_soft()


# --- MAIN ---
def main():
    pg.init()
    screen = pg.display.set_mode((WIN_W, WIN_H))
    pg.display.set_caption('DMTRIS')

    #Шрифты системные, без импорта внешних пока что
    font = pg.font.SysFont('consolas,dejavusanmono,monospace', 20)
    big = pg.font.SysFont('consolas,dejavusanmono,monospace', 34, bold=True)
    small = pg.font.SysFont('consolas,dejavusanmono,monospace', 16)
    clock = pg.time.Clock()

    #Копии дефолтных настроек и биндов
    key_bindings = {k: list(v) for k, v in DEFAULT_KEY_BINDINGS.items()}

    #Создание игровых объектов
    input_state = InputState()
    menu = SettingsMenu(DEFAULT_SETTINGS, key_bindings)
    game = Game(menu.settings)

    while True:
        dt = clock.tick(FPS) / 1000.0
        #Обработка событий
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            if event.type == pg.KEYDOWN:
                if menu.open:
                    menu.handle_key(event.key)
                else:
                    action = handle_key_down(game, input_state, event.key, menu.settings, key_bindings)
                    if action == 'open_settings':
                        menu.toggle()
                        input_state.reset()
                        game.paused = False   # close pause when opening menu
            if event.type == pg.KEYUP:
                if not menu.open:
                    handle_key_up(game, input_state, event.key, key_bindings)

        #Фриз игры при открытии меню
        if not menu.open:
            game.update(dt)
            input_state.update(dt, game, menu.settings)
        else:
            #Эффекты продолжают угасать
            if game.flash > 0:
                game.flash = max(0.0, game.flash - dt * 4.0)

        #Основной рендеринг
        draw(screen, game, font, big, menu.settings)
        if menu.open:
            menu.draw(screen, font, big)
        pg.display.flip()


if __name__ == ('__main__'):
    main()

