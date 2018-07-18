from __future__ import print_function
import unittest
import time
import threading

from support.pyro.support_pyro.support_pyro4.util import CoopPausableThread


class TrackableGenerator(object):

    def __init__(self):
        self.idx = 0

    def __call__(self):
        for i in xrange(10):
            time.sleep(0.1)
            self.idx = i
            yield i


class TestCoopPausableThread(unittest.TestCase):

    def test_stop(self):

        generator = TrackableGenerator()
        coop_thread = CoopPausableThread(target=generator)
        coop_thread.start()
        time.sleep(0.5)
        coop_thread.stop()
        coop_thread.join()
        self.assertTrue(generator.idx == 4)


if __name__ == "__main__":
    unittest.main()
