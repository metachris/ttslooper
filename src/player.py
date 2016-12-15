"""
MediaPlayer plays the music files with omxplayer, and reacts to mouse-inputs
"""
import os
import sys
# import time
# import subprocess
# import signal
import termios
# from random import shuffle
from threading import Thread  #, Event
from Queue import Queue

# from mouseinput import wait_mouse_click, MouseClickThread
from logutils import setup_logger

# from fb import FrameBuffer
# from fbitool import FBI
# fbi = FBI()

# pylint: disable=C0103
logger = setup_logger()

DIR_SCRIPT = os.path.dirname(os.path.realpath(__file__))

CMD_QUIT = object()
CMD_UP = object()
CMD_DOWN = object()
CMD_INTO = object()
CMD_BACK = object()


# def showimage(fn):
#     fn_full = "%s/images/%s" % (DIR_SCRIPT, fn)
#     fbi.show_image(fn_full)


def tts(text):
    """ Text to speech (todo) """
    logger.info("tts: %s", text)


def find_dirs(path):
    """ Return all subdirectories of a given path """
    dirs = [d for d in next(os.walk(path))[1] if not d.startswith(".")]
    return dirs


class KeyboardPoller(Thread):
    """
    Background thread which reads keyboard input and calls the bound callbacks.
    """
    binds = {}

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True

    def bind(self, key, cb):
        """ Bind a callback to a specific key (string or ord-int) """
        if isinstance(key, int):
            self.binds[key] = cb
        else:
            self.binds[ord(key)] = cb

    def _wait_key(self):
        fd = sys.stdin.fileno()

        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        try:
            result = sys.stdin.read(1)
        except IOError:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

        return result

    def run(self):
        while True:
            ch = self._wait_key()
            #logger.info("key: %s", ord(ch))
            if ord(ch) in self.binds:
                self.binds[ord(ch)]()

            # Quit thread on "q"
            if ch == "q":
                return


class TTSMediaPlayer(object):
    """
    Starts at specified root directory.
    Commands are "up", "down", "into", "back".
    Uses TTS to speak the current directory, and then starts playing files.
    """
    command_queue = None  # FIFO Queue
    player_thread = None
    basepath = None

    path_selection_pos = -1
    paths_next_possible = []
    path_next = None

    def __init__(self, basepath):
        self.command_queue = Queue()
        self.basepath = os.path.abspath(basepath)
        self.path_selection = self.basepath
        logger.info("Starting with basepath %s", self.basepath)
        #self.fb = FrameBuffer()

    def start_playback(self):
        """ Main entry point """
        self.switch_to_path(self.basepath)
        self.play_path(self.basepath)

        #logger.info("threads started. waiting for commands...")
        while True:
            cmd = self.command_queue.get(True)
            if cmd == CMD_QUIT:
                break
            elif cmd == CMD_UP:
                self.cmd_up()
            elif cmd == CMD_DOWN:
                self.cmd_down()
            elif cmd == CMD_INTO:
                self.cmd_into()
            elif cmd == CMD_BACK:
                self.cmd_back()

    def shutdown(self):
        """ Shutdown method. Exit main loop. """
        logger.info("shutdown")
        self.command_queue.put(CMD_QUIT)

    def play_path(self, path):
        """ Play files in a specific path """
        logger.info("play_path: %s", path)
        path_ext = path[len(self.basepath)+1:].strip()
        if not path_ext or path_ext == "/":
            path_tts = "root"
        else:
            path_tts = path_ext
        tts("Playing %s" % path_tts)

    def play_selected(self):
        """ Start playing from the currently selected path """
        logger.info("play_selected")
        if self.path_selection_pos != -1:
            p = self.select_path_pos(self.path_selection_pos)
            self.switch_to_path(p)
        self.play_path(self.path_selection)

    def switch_to_path(self, path):
        """ Actually switch to this directory, but don't start playing yet """
        self.path_selection = path
        self.path_selection_pos = -1
        self.paths_next_possible = find_dirs(path)
        logger.debug("next possible paths: %s", str(self.paths_next_possible))

    def select_path_pos(self, n):
        """ Select one of the current subdirectories """
        self.path_selection_pos = n
        p = self.paths_next_possible[n]
        #logger.info("select_path_pos: %s = %s", n, os.path.join(self.path_selection, p))
        tts(p)
        return os.path.join(self.path_selection, p)

    def cmd_up(self):
        #logger.info("cmd: up")
        pos = self.path_selection_pos - 1
        if pos < 0:
            pos = len(self.paths_next_possible) - 1
        self.select_path_pos(pos)

    def cmd_down(self):
        #logger.info("cmd: down")
        pos = (self.path_selection_pos + 1) % len(self.paths_next_possible)
        self.select_path_pos(pos)

    def cmd_into(self):
        #logger.info("cmd: into")
        if self.path_selection_pos == -1:
            logger.warn("cannot go into directory without a selection")
            return

        tts("current directory is %s" % self.paths_next_possible[self.path_selection_pos])
        path = os.path.join(self.path_selection, self.paths_next_possible[self.path_selection_pos])
        self.switch_to_path(path)

    def cmd_back(self):
        #logger.info("cmd: back")
        path_next = os.path.abspath(os.path.join(self.path_selection, ".."))
        if len(path_next) < len(self.basepath):
            logger.warn("cannot go beyond basepath (next path would be %s)" % path_next)
            return

        path_tts = path_next[len(self.basepath)+1:].strip()
        if not path_tts:
            path_tts = "root"
        tts("current directory is %s" % path_tts)

        self.switch_to_path(path_next)


if __name__ == "__main__":
    path = "." if len(sys.argv) < 2 else sys.argv[1]
    player = TTSMediaPlayer(path)

    kbd_poller = KeyboardPoller()
    kbd_poller.bind("w", player.cmd_up)
    kbd_poller.bind("a", player.cmd_back)
    kbd_poller.bind("s", player.cmd_down)
    kbd_poller.bind("d", player.cmd_into)
    kbd_poller.bind("q", player.shutdown)
    kbd_poller.bind(10, player.play_selected)  # enter
    kbd_poller.start()

    try:
        player.start_playback()
    except:
        player.shutdown()
    finally:
        print "bye"

