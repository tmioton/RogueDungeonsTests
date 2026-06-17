import argparse
import pyglet
from pyglet.window import key
from miner_test.board import Board, size, texture_map

# ****** Globals ******
resolution = {"width": 1536, "height": 1136}
window = pyglet.window.Window(**resolution, caption="MinerTest", vsync=True)
width, height = window.width, window.height
assert not width % 16, "Width must be a multiple of 16"
assert not height % 16, "Height must be a multiple of 16"


# ****** Game Objects ******
reserved_space = 42  # * @size px
board_size = (width // size, (height - reserved_space) // size)
print(board_size)
# board_size = (128, 128)
bwidth, bheight = board_size

xoff = 0
yoff = reserved_space

board = Board(window, *board_size, xoff, yoff, 1)
pyglet.gl.glViewport(xoff, yoff, bwidth, bheight)
fps = pyglet.window.FPSDisplay(window)


@window.event
def on_draw():
    window.clear()
    board.draw()
    fps.draw()


@window.event
def on_key_press(symbol, modifiers):
    if symbol == key.MINUS:
        # print("going up")
        board.change_level(-1)
    elif symbol == key.EQUAL:
        # print("going down")
        board.change_level(1)
    elif symbol == key.F12:
        pyglet.image.get_buffer_manager().get_color_buffer().save('screenshot.png')
        print("Screenshot saved to screenshot.png")


def update(dt):
    # print("New frame:")
    board.update(dt)


def auto_close(dt):
    pyglet.image.get_buffer_manager().get_color_buffer().save('screenshot.png')
    print("Screenshot saved to screenshot.png")
    pyglet.app.exit()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto-close', action='store_true', help='Automatically close the program and take a screenshot after 1 second')
    args = parser.parse_args()

    if args.auto_close:
        pyglet.clock.schedule_once(auto_close, 1.0)
    pyglet.clock.schedule_interval(update, 1/60)
    pyglet.app.run()
