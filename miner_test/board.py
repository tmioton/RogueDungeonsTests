from random import randrange, random
from typing import List, Tuple, Optional, Iterator, Union
from collections import namedtuple
from math import sqrt, tau, ceil
from os import urandom
from sys import byteorder
from enum import Enum

import pyglet
from pyglet.resource import texture as load_image
from transitions import Machine
from opensimplex import OpenSimplex
from vectors import Vector
from cellmath import *
import numpy as np
gl = pyglet.gl

# ****** Globals ******
# **** Types ****
VertexList = pyglet.graphics.vertexdomain.VertexList
Uninitialized = Optional
Number = Union[int, float]
Position = Tuple[Number, Number]
Offset = namedtuple("Offset", "x, y")

# **** Constants ****
eighth = tau / 8
tex_size = 2
size = 16 * tex_size  # px
texture_map = {}


# ****** Load Textures ******
def load_atlas(t: str) -> Iterator[Tuple[str, pyglet.image.TextureRegion]]:
    atlas = pyglet.resource.image("tiles/{}.png".format(t))
    names = pyglet.resource.file("tiles/{}_names.txt".format(t), "r")

    strip = lambda x: str.rstrip(x, "\n")

    for atlas_index, name in enumerate(map(strip, names)):
        mult, rem = divmod(atlas_index, atlas.width // 16)

        left = mult * 16
        top = rem * 16

        texture = atlas.get_region(
            left, top, 16, 16
        )
        yield name, texture


texture_map.update(load_atlas("stone"))
texture_map.update(load_atlas("coal"))
texture_map.update(
    {
        # air textures
        # "bottom_addition": load_image("tiles/wall_02.png"),
        # "bottom_addition_02": load_image("tiles/wall_01.png"),
        "shadow_left": load_image("tiles/shadow_left.png"),
        "shadow_corner": load_image("tiles/shadow_corner.png"),
        "air": load_image("tiles/air.png"),

        # resource textures
        # "full_01": load_image("tiles/coal_01.png"),

        # skirt textures
        "skirt": load_image("tiles/skirt.png"),
        "FACE": load_image("tiles/FACE_BRICK.png"),
        "FACE_CORNER": load_image("tiles/FACE_BRICK_CORNER.png"),
        "FACE_SHADOW": load_image("tiles/FACE_BRICK_SHADOW.png"),

        # miner textures
        # "miner": load_image("tiles/pickaxe.png")
        "miner": load_image("tiles/skeleton.png")
        # "miner": load_image("tiles/green_mage.png")
    }
)

pyglet.gl.glBlendFunc(
    pyglet.gl.GL_SRC_ALPHA,
    pyglet.gl.GL_ONE_MINUS_SRC_ALPHA
)

for key in texture_map.keys():
    texture = texture_map[key]
    gl.glBindTexture(texture.target, texture.id)
    gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
    gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)

    texture.width *= tex_size
    texture.height *= tex_size

floors = pyglet.graphics.Group(order=0)
blocks = pyglet.graphics.Group(order=1)
miners = pyglet.graphics.Group(order=2)
lights = pyglet.graphics.Group(order=3)


class Board:
    """Contains both blocks and miners."""

    ORE_CHANCE = 0.25
    VEIN_SIZE = 5

    def __init__(self, window: pyglet.window.Window, width, height, xoff, yoff, depth=1):
        """Initialize the board."""

        assert depth > 0, "Attempted to created empty board."

        # ****** Board Attributes ******
        self.window = window
        self.width = width
        self.height = height
        self.depth = depth
        self.level = 0
        self.offset = Offset(xoff, yoff)

        # ****** Initialize Board ******
        self.batch = pyglet.graphics.Batch()
        self.blocks: List[List[List[Block]]] = [[[None] * height for _1 in range(width)] for _2 in range(depth)]
        self.skirt: List[pyglet.sprite.Sprite] = [None] * width
        self.miners: List[Miner] = []

        # self.lighting = LightingSystem(
        #     window.width, window.height,
        #     xoff, yoff, (width, height, depth),
        #     batch=self.batch
        # )

        # breaks if the size is decreased too much.
        # needs to be converted to a callback loader.
        self.seed = int.from_bytes(urandom(16), byteorder, signed=False)
        noise = OpenSimplex(seed=self.seed)
        for d in range(depth):
            # generate in 16x16 squares
            # 3 for-loops but only n squared.
            for chunk in range(int(ceil(width / 16) * ceil(height / 16))):
                m, n = map(lambda x: x * 16, divmod(chunk, int(ceil(width / 16))))
                for i in range(n, n + 16):
                    for j in range(m, m + 16):
                        if not 0 <= i < width or not 0 <= j < height:
                            continue

                        pos = i * size + xoff, j * size + yoff
                        block = Block(self, self.batch, pos, (i, j), d, (width, height, depth))
                        if d != self.level:
                            block.disable_rendering()
                        self.set_block(block, i, j, d)

                        # range of OpenSimplex is -1 to 1. To retrieve a
                        # value between 0 and 1 the equation is (x + 1) / 2
                        nval = (noise.noise3(x=i / self.VEIN_SIZE, y=j / self.VEIN_SIZE, z=d / self.VEIN_SIZE) + 1) / 2
                        # nval = random()
                        if nval < self.ORE_CHANCE:
                            block = self.blocks[d][i][j]
                            block.type = 'coal'

                    # disabled for now. Looks kind of weird.
                    # self.skirt[i] = pyglet.sprite.Sprite(
                    #     texture_map["skirt"], i * size + xoff,
                    #     yoff - size * 2, batch=self.batch, group=floors
                    # )

        num_miners = 5
        for i in range(num_miners):
            k, m, d = randrange(width), randrange(height), randrange(depth)
            pos = k * size + xoff, m * size + yoff
            miner = Miner(
                i, self, self.batch, pos, (k, m),
                d, (width, height, depth)
            )
            if d != self.level:
                miner.disable_rendering()
            self.miners.append(miner)

            block = self.get_block(k, m, d)
            block.change_type("air")
            # self.lighting.add_air(k, m, d)

            for p, q in nearby_cells(k, m, 3):
                if not 0 <= p < width or not 0 <= q < height:
                    continue
                block = self.get_block(p, q, d)
                block.visible = True

        for block_row in self.blocks:
            for block_col in block_row:
                for block in block_col:
                    block.update()

    def block_exists(self, i, j, d):
        if 0 <= i < self.width and 0 <= j < self.height:
            return not self.get_block(i, j, d).is_broken()
        return False

    def is_on_edge(self, i, j):
        return i == 0 or i == self.width - 1 or j == 0 or j == self.height - 1

    def get_block(self, i, j, d=0) -> "Block":
        return self.blocks[d][i][j]

    def set_block(self, block: "Block", i, j, d=0):
        self.blocks[d][i][j] = block

    def get_abs_pos(self, x, y) -> Tuple[int, int]:
        return tuple(Vector(x, y) + Vector(*self.offset))

    def change_level(self, delta: int):
        """Change the level from the current by delta steps"""

        # ignore if level is outside of depth
        if not 0 <= self.level + delta < self.depth:
            return

        # disable rendering blocks on previous level
        for bc in self.blocks[self.level]:
            for block in bc:
                block.disable_rendering()

        # disable rendering miners on previous level
        for miner in self.miners:
            if miner.level == self.level:
                miner.disable_rendering()

        # go to new level
        self.level += delta

        # enable rendering blocks on new level
        for bc in self.blocks[self.level]:
            for block in bc:
                block.enable_rendering()

        # enable rendering miners on new level
        for miner in self.miners:
            if miner.level == self.level:
                miner.enable_rendering()

        # self.lighting.change_level(self.level)

    def update(self, dt):
        for miner in self.miners:
            miner.update(dt)

    def draw(self):
        """Dispatch draw calls of each block and miner."""
        self.batch.draw()

        # let's draw a semi-transparent square on top of the board
        # to test the feasability of the lighting system.
        # self.lighting.draw()


class Piece:
    __slots__ = (
        "board", "batch", "x", "y",
        "i", "j", "level", "bound",
        "board_width", "board_height",
        "board_depth", "_rendering"
    )

    def __init__(
            self, board: Board, batch, pos: Tuple[int, int],
            index: Tuple[int, int], depth, bound: Tuple[int, int, int],
    ):
        self.board = board
        self.batch = batch

        self.x, self.y = 0, 0
        self.pos = pos

        self.i, self.j = 0, 0
        self.index = index
        self.level = depth

        self._rendering = True

        self.bound = bound
        self.board_width, self.board_height, self.board_depth = bound

    def __repr__(self):
        return type(self).__name__

    @property
    def pos(self) -> Tuple[int, int]:
        return self.x, self.y

    @pos.setter
    def pos(self, v: Tuple[int, int]):
        self.x, self.y = v

    @property
    def index(self) -> Tuple[int, int]:
        return self.i, self.j

    @index.setter
    def index(self, v: Tuple[int, int]):
        self.i, self.j = v

    def enable_rendering(self):
        self._rendering = True

    def disable_rendering(self):
        self._rendering = False

    def is_good_pair(self, pair):
        k, m = pair
        return 0 <= k < self.board_width and 0 <= m < self.board_height

    def draw(self):
        raise NotImplementedError


class Block(Piece):
    TYPES = ("stone", "air", "coal")
    DEF_HEALTH = 100

    def __init__(
            self, board: Board, batch, pos: Tuple[int, int],
            index: Tuple[int, int], depth: int, bound: Tuple[int, int, int]
    ):
        super(Block, self).__init__(board, batch, pos, index, depth, bound)
        self.rotation = randrange(4)

        self.health = self.DEF_HEALTH
        self.type = "stone"

        self.texture_index = randrange(3) + 1
        # store the name of the texture for lighting purposes.
        self.current_texture = f"STONE_FLOOR_{self.texture_index:0>2}"
        self.sprite = pyglet.sprite.Sprite(
            texture_map[self.current_texture],
            # rocks[self.rotation],
            *pos, batch=batch, group=blocks
        )

        # store the floor under the block with this block rather than the board.
        self.floor_type = "stone"
        self.floor_texture_index = randrange(3) + 1
        self.floor_current_texture = f"STONE_FLOOR_{self.floor_texture_index:0>2}"
        self.floor_sprite = pyglet.sprite.Sprite(
            texture_map[self.floor_current_texture],
            # texture_map["air"],
            *pos, batch=batch, group=floors
        )

        self._rendering = True
        self.visible = False

    def mine(self) -> bool:
        if self.is_broken():
            return True

        if random() < 0.6:
            self.health -= 10

        if self.health > 0:
            return False

        self.change_type("air")
        self.health = self.DEF_HEALTH
        for cell in filter(
                self.is_good_pair,
                nearby_cells(*self.index, 3)
        ):
            # when this block is broken, update the blocks around it.
            i, j = cell

            block = self.board.get_block(i, j, self.level)
            block.visible = True
            block.update()
        return True

    @staticmethod
    def surroundings(octs, exist, broken, func=all):
        check_nots = [not octs[i] for i in broken]
        check_haves = [octs[i] for i in exist]
        return func(check_nots + check_haves)

    def _get_physical_texture(self, octs, block_type) -> str:
        ch = f"{self.texture_index:0>2}"
        if self.surroundings(octs, (0, 1, 3, 5, 6), (4,)):
            return block_type + f"_WALL_N_" + ch
        elif self.surroundings(octs, (1, 3, 5, 6), (0, 4,)):
            return block_type + f"_EXIT_T2_NW_" + ch
        elif self.surroundings(octs, (0, 1, 3, 6), (4, 5)):
            return block_type + f"_EXIT_T2_NE_" + ch
        elif self.surroundings(octs, (1, 3, 6), (0, 4, 5)):
            return block_type + f"_JUNCTION_N_" + ch

        elif self.surroundings(octs, (1, 2, 4, 6, 7), (3,)):
            return block_type + f"_WALL_S_" + ch
        elif self.surroundings(octs, (1, 4, 6, 7), (2, 3)):
            return block_type + f"_EXIT_T2_SW_" + ch
        elif self.surroundings(octs, (1, 2, 4, 6), (3, 7)):
            return block_type + f"_EXIT_T2_SE_" + ch
        elif self.surroundings(octs, (1, 4, 6), (2, 3, 7)):
            return block_type + f"_JUNCTION_S_" + ch

        elif self.surroundings(octs, (3, 4, 5, 6, 7), (1,)):
            return block_type + f"_WALL_W_" + ch
        elif self.surroundings(octs, (3, 4, 5, 6), (1, 7)):
            return block_type + f"_EXIT_T1_NW_" + ch
        elif self.surroundings(octs, (3, 4, 6, 7), (1, 5)):
            return block_type + f"_EXIT_T1_SW_" + ch
        elif self.surroundings(octs, (3, 4, 6), (1, 5, 7)):
            return block_type + f"_JUNCTION_W_" + ch

        elif self.surroundings(octs, (0, 1, 2, 3, 4), (6,)):
            return block_type + f"_WALL_E_" + ch
        elif self.surroundings(octs, (0, 1, 3, 4), (2, 6)):
            return block_type + f"_EXIT_T1_NE_" + ch
        elif self.surroundings(octs, (1, 2, 3, 4), (0, 6)):
            return block_type + f"_EXIT_T1_SE_" + ch
        elif self.surroundings(octs, (1, 3, 4), (0, 2, 6)):
            return block_type + f"_JUNCTION_E_" + ch

        elif self.surroundings(octs, (3, 6, 5), (1, 4)):
            return block_type + "_CORNER_EXTERIOR_NW"
        elif self.surroundings(octs, (0, 1, 3), (4, 6)):
            return block_type + "_CORNER_EXTERIOR_NE"
        elif self.surroundings(octs, (4, 6, 7), (1, 3)):
            return block_type + "_CORNER_EXTERIOR_SW"
        elif self.surroundings(octs, (1, 2, 4), (3, 6)):
            return block_type + "_CORNER_EXTERIOR_SE"

        elif self.surroundings(octs, (3, 6), (1, 4, 5)):
            return block_type + "_HALL_NW"
        elif self.surroundings(octs, (1, 3), (0, 4, 6)):
            return block_type + "_HALL_NE"
        elif self.surroundings(octs, (4, 6), (1, 3, 7)):
            return block_type + "_HALL_SW"
        elif self.surroundings(octs, (1, 4), (2, 3, 6)):
            return block_type + "_HALL_SE"

        elif self.surroundings(octs, (3,), (1, 4, 6)):
            return block_type + "_ENDCAP_N"
        elif self.surroundings(octs, (4,), (1, 3, 6)):
            return block_type + "_ENDCAP_S"
        elif self.surroundings(octs, (6,), (1, 3, 4)):
            return block_type + "_ENDCAP_W"
        elif self.surroundings(octs, (1,), (3, 4, 6)):
            return block_type + "_ENDCAP_E"

        elif self.surroundings(octs, (1, 6), (3, 4)):
            return block_type + "_HALL_HORIZONTAL"
        elif self.surroundings(octs, (3, 4), (1, 6)):
            return block_type + "_HALL_VERTICAL"
        elif self.surroundings(octs, (), (1, 3, 4, 6)):
            return block_type + "_COLUMN_01"

        elif self.surroundings(octs, (0, 1, 3, 4, 5, 6), (2, 7)):
            return block_type + f"_CONNECTOR_N_" + ch
        elif self.surroundings(octs, (0, 1, 3, 4, 5, 6, 7), (2,)):
            return block_type + f"_CORNER_INTERIOR_NW_" + ch
        elif self.surroundings(octs, (1, 3, 4, 5, 6), (0, 2, 7)):
            return block_type + f"_EXIT_T3_NW_" + ch
        elif self.surroundings(octs, (0, 1, 3, 4, 6), (2, 5, 7)):
            return block_type + f"_EXIT_T3_NE_" + ch

        elif self.surroundings(octs, (0, 1, 3, 4, 6, 7), (2, 5)):
            return block_type + f"_JOINT_POS_" + ch

        elif self.surroundings(octs, (1, 2, 3, 4, 6, 7), (0, 5)):
            return block_type + f"_CONNECTOR_S_" + ch
        elif self.surroundings(octs, (0, 1, 2, 3, 4, 6, 7), (5,)):
            return block_type + f"_CORNER_INTERIOR_SE_" + ch
        elif self.surroundings(octs, (1, 3, 4, 6, 7), (0, 2, 5)):
            return block_type + f"_EXIT_T3_SW_" + ch
        elif self.surroundings(octs, (1, 2, 3, 4, 6), (0, 5, 7)):
            return block_type + f"_EXIT_T3_SE_" + ch

        elif self.surroundings(octs, (1, 3, 4, 5, 6, 7), (0, 2)):
            return block_type + f"_CONNECTOR_W_" + ch
        elif self.surroundings(octs, (1, 2, 3, 4, 5, 6, 7), (0,)):
            return block_type + f"_CORNER_INTERIOR_SW_" + ch

        elif self.surroundings(octs, (1, 2, 3, 4, 5, 6), (0, 7)):
            return block_type + f"_JOINT_NEG_" + ch

        elif self.surroundings(octs, (0, 1, 2, 3, 4, 6), (5, 7)):
            return block_type + f"_CONNECTOR_E_" + ch
        elif self.surroundings(octs, (0, 1, 2, 3, 4, 5, 6), (7,)):
            return block_type + f"_CORNER_INTERIOR_NE_" + ch

        else:
            return block_type + f"_FLOOR_" + ch

    def _get_air_texture(self, octs) -> str:
        if self.surroundings(octs, (4,), (1,)):
            return "FACE"
        elif self.surroundings(octs, (4, 1), ()):
            return "FACE_SHADOW"
        elif self.surroundings(octs, (4, ), (2, )):
            return "FACE_CORNER"
        elif self.surroundings(octs, (1,), ()):
            return "shadow_left"
        elif self.surroundings(octs, (2,), (1,)):
            return "shadow_corner"

        # if self.surroundings(octs, (0, 1), ()):
        #     return "shadow_left"
        # elif self.surroundings(octs, (1, ), (0, )):
        #     return "shadow_corner"
        else:
            return "air"

    # noinspection PyUnboundLocalVariable
    def update(self):
        on_edge = self.board.is_on_edge(self.i, self.j)
        if not self.visible and not on_edge:
            self.change_tex(f"STONE_FLOOR_01")
            # if self.type == 'stone':
            #     self.change_tex("STONE_FLOOR_01")
            # elif self.type == 'coal':
            #     self.change_tex("COAL_FLOOR_01")
            return

        octs = [False] * 8
        for k, cell in enumerate(nearby_cells(self.i, self.j, 3)):
            i, j = cell
            val = self.board.block_exists(i, j, self.level)
            octs[k] = val

        if not self.visible and on_edge:
            tex = self._get_physical_texture(octs, "STONE")
        elif self.visible:
            if self.type == "stone":
                tex = self._get_physical_texture(octs, "STONE")
            elif self.type == "air":
                tex = self._get_air_texture(octs)
            elif self.type == 'coal':
                tex = self._get_physical_texture(octs, "COAL")
        else:
            tex = "STONE_FLOOR_01"
        self.change_tex(tex)

    def change_type(self, t: str):
        assert t in self.TYPES, "The only supported types are: " + ", ".join(self.TYPES)

        self.type = t
        self.update()

    def change_floor_type(self, t: str):
        self.floor_type = t

    def change_tex(self, tex: str):
        self.sprite.image = texture_map[tex]
        self.current_texture = tex

    # ****** State Change Methods ******
    # block can be in a state of rendering and a state of hidden.
    def enable_rendering(self):
        """Enable rendering this block's sprite to the screen.
        Does not mean it will be shown.
        Allows blocks from other floors to maintain their
        hidden status when the floor changes.
        """
        self.sprite.visible = True
        if self.is_broken():
            self.floor_sprite.visible = True
        super().enable_rendering()

    def disable_rendering(self):
        """Disable rendering this block's sprite to the screen.
        Allows blocks from other floors to maintain their hidden status when the floor changes."""
        self.sprite.visible = False
        self.floor_sprite.visible = False
        super().disable_rendering()

    # ****** State Checks ******
    def is_rendering(self):
        """Return whether this block is in view."""
        return self._rendering

    def is_broken(self) -> bool:
        """Return whether this block is broken."""
        return self.type == "air"

    def is_stone(self) -> bool:
        return self.type == "stone"

    def is_coal(self) -> bool:
        return self.type == "coal"

    def is_air(self) -> bool:
        return self.type == "air"

    # ****** Draw Method ******
    def draw(self):
        # should not normally be called.
        self.sprite.draw()


def distance(a: "Vector", b: "Vector") -> float:
    x1, y1 = a
    x2, y2 = b

    return sqrt(pow(x2 - x1, 2) + pow(y2 - y1, 2))


class Miner(Piece):
    MOVE_TIME = 1 / 2  # seconds. 1 move / moves per second
    SEARCH_LIMIT = 9
    MINE_RANGE: int = 3

    states = ["standing", "searching", "mining", "moving", "crafting", "placing"]
    transitions = [
        # on <<trigger>> go from <<source>> to <<dest>>
        # [<<trigger>>, <<source>>, <<dest>>]
        ["search", "standing", "searching"],
        ["move", "standing", "moving"],
        ["move", "searching", "moving"],
        ["mine", "searching", "mining"],
        ["mine", "moving", "mining"],
        ["stop", "*", "standing"],
        # ["craft", "standing", "crafting"],
        # ["place", "standing", "placing"]
    ]

    def __init__(
            self, name: int, board: Board, batch: pyglet.graphics.Batch,
            pos: Position, index: Position, depth: int,
            bound: Tuple[int, int, int]
    ):
        super(Miner, self).__init__(board, batch, pos, index, depth, bound)

        self.name = name  # debug variable

        self.block: Uninitialized[Block] = None
        self.target_block: Uninitialized[Block] = None
        x, y = pos
        self.sprite = pyglet.sprite.Sprite(
            texture_map["miner"], x, y, batch=batch, group=miners
        )

        self.move_time: float = 0.
        self.target_index: Uninitialized[Tuple[int, int]] = None

        self.angle = tau * random()  # a velocity vector to filter directions.
        self.search_field = 3

        self.machine = Machine(
            model=self, states=self.states,
            transitions=self.transitions,
            initial="standing"
        )

    def enable_rendering(self):
        self.sprite.visible = True
        super().enable_rendering()

    def disable_rendering(self):
        self.sprite.visible = False
        super().disable_rendering()

    # ****** State Handlers ******
    def handle_moving(self, dt):
        i, j = self.index
        if self.target_index is None:
            # if there is no target block, move randomly
            self.target_index = i + randrange(-1, 2), j + randrange(-1, 2)

        if not self.in_range(*self.target_index):
            # if it's not in range, move closer.
            spos = Vector(*self.index)
            dpos = Vector(*self.target_index)
            angle = spos.angle(dpos)

            index = next_cell(*self.index, angle)
            will_reach = False
        else:
            index = self.target_index
            will_reach = True

        if self.board.block_exists(*index, self.level):
            self.block = self.board.get_block(*index, self.level)
            self.mine()
            return

        cont = self.stumble(*index, dt)
        if not cont:
            self.move_time = 0.
            if will_reach:
                self.target_index = None
            self.stop()
        return

    def handle_mining(self, dt):
        broken = self.block.mine()
        if broken:
            self.block = None
            self.stop()
        return

    def handle_standing(self, dt):
        if random() < 0.6:
            self.search()
        elif random() < 0.2:
            self.move()
        return

    def handle_searching(self, dt):
        block = self.target_block
        if block is None or block.is_broken():
            block = self.best_block()

        if block is None:
            # move randomly
            self.move()
            return
        self.block = block

        index = block.index
        p, q = index
        if not self.in_range(p, q):
            # move towards the block
            # target_index should be the position right before the block,
            # not the block's index.
            spos = Vector(p, q)
            dpos = Vector(*self.index)
            angle = spos.angle(dpos)

            index = next_cell(p, q, angle)
            self.target_index = index
            self.move()
        else:
            self.mine()
        return

    def update(self, dt):
        """
        standing -> searching
        searching -> moving
        searching -> mining
        moving -> standing
        mining -> standing
        """
        handler_name = "handle" + "_" + self.state
        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            handler(dt)
        else:
            raise Exception(f"No handler for state {self.state}")

    def best_block(self) -> Optional[Block]:
        stored: Optional[Block] = None
        for k, cell in enumerate(filter(
                self.is_good_pair, nearby_cells(*self.index, 5, angle=random() * tau)
        )):
            i, j = cell

            block = self.board.get_block(i, j, self.level)
            if not block.visible:
                continue

            if block.is_stone():
                if stored is None:
                    stored = block
                else:
                    continue

            if block.is_coal():
                return block
        else:
            return stored

    def in_range(
            self, p: Optional[int] = None,
            q: Optional[int] = None, *,
            rng: Optional[int] = None
    ):
        i, j = self.index

        if p is None and q is None:
            return False

        if rng is None:
            rng = self.MINE_RANGE

        half = rng // 2
        if p is not None:
            if i - half > p:
                return False
            if i + half < p:
                return False

        if q is not None:
            if j - half > q:
                return False
            if j + half < q:
                return False
        return True

    def stumble(self, i, j, dt):
        abs_pos = self.board.get_abs_pos
        k, m = self.index

        # check if it is a valid position
        if not 0 <= i < self.board_width:
            return False

        if not 0 <= j < self.board_height:
            return False

        if not self.board.get_block(i, j, self.level).is_broken():
            return False

        self.move_time += dt

        x, y = self.pos
        cpos = Vector(x, y)                                      # current pos
        spos = Vector(*abs_pos(k * size, m * size))              # start position
        dpos = Vector(*abs_pos(i * size, j * size))  # destination pos
        p, q = dpos

        total_dist = distance(spos, dpos)
        angle = spos.angle(dpos)

        required_dist = (self.move_time * total_dist) / self.MOVE_TIME
        move = required_dist - distance(cpos, spos)

        mpos = Vector(*from_polar(move, angle))
        cpos += mpos
        x, y = cpos
        self.sprite.update(x, y)
        self.pos = x, y

        # how to tell if the destination has been reached?
        # if ((j > 0 and y >= q) or (j < 0 and y <= q) or (not j))
        x_satisfied = (i > k and x >= p) or (i < k and x <= p) or i == k
        y_satisfied = (j > m and y >= q) or (j < m and y <= q) or j == m
        if x_satisfied and y_satisfied:
            self.index = i, j
            self.pos = p, q
            self.sprite.update(p, q)
            return False
        return True

    def teleport(self, i, j):
        k, m = self.index

        if not 0 <= k + i < self.board_width:
            return

        if not 0 <= m + j < self.board_height:
            return

        if not self.board.get_block(k + i, m + j, self.level).is_broken():
            return

        self.index = k + i, m + j

        x, y = self.pos
        pos = x + i * size, y + j * size
        self.sprite.update(*pos)
        self.pos = pos

    def draw(self):
        # should not normally be called.
        self.sprite.draw()


class Item(Enum):
    COAL = 1
    TORCH = 2
