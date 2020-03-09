import queue
import multiprocessing as mp
from typing import Union
import time


class QueueHandler:

    def __init__(self, q):
        self.q: Union[queue.Queue, mp.Queue] = q

    def get(self, block=True, timeout=None):
        """
        Works just like the `get` method of `queue.Queue`

        Returns:
            item from the queue
        """
        return self.q.get(block, timeout)

    def timeout_get(self, timeout):
        """
        If timeout is reached, forces a context switch using `time.sleep(0)`
        and then returns `None`
        Args:
            timeout: number of seconds until timeout

        Returns:
            item from the queue
        """
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            time.sleep(0)
            return None

    def non_blocking_get(self):
        """
        If the queue is empty, forces a context switch using `time.sleep(0)`
        and then returns `None`
        """
        try:
            return self.q.get(block=False)
        except queue.Empty:
            time.sleep(0)
            return None

    def put(self, item, block=True, timeout=None):
        """
        Works just like the `put` method of `queue.Queue`
        """
        self.q.put(item, block, timeout)

    def timeout_put(self, item, timeout):
        """
        If timeout is reached returns `False`, else puts item in queue
        and returns `True`
        Args:
            item: item to put in queue
            timeout: number of seconds until timeout

        Returns:
            True if successful, False if not
        """
        try:
            self.q.put(item, timeout=timeout)
            return True
        except queue.Full:
            return False

    def non_blocking_put(self, item):
        """
        If queue is full, returns `False`, else puts item in queue
        and returns `True`
        Args:
            item: item to put in queue

        Returns:
            True if successful, False if not
        """
        try:
            self.q.put(item, block=False)
            return True
        except queue.Full:
            return False

    def deque_timeout_put(self, item, timeout):
        """
        If timeout is reached, it tries to take an item from the queue and then
        puts the item in the queue.
        Args:
            item: item to put in queue
            timeout: number of seconds until timeout

        Returns:
            True if successful, False if had to deque an item
        """
        try:
            self.q.put(item, timeout=timeout)
            return True
        except queue.Full:
            try:
                _ = self.q.get(block=False)
                dropped = True
            except queue.Empty:
                dropped = False
            # TODO - could crash due to a race condition, could be solved with a lock
            self.q.put(item, block=False)
            return dropped

    def deque_non_blocking_put(self, item):
        """
        If queue is full, it tries to take an item from the queue and then
        puts the item in the queue.
        Args:
            item: item to put in queue

        Returns:
            True if successful, False if had to deque an item
        """
        try:
            self.q.put(item, block=False)
            return True
        except queue.Full:
            try:
                _ = self.q.get(block=False)
                dropped = True
            except queue.Empty:
                dropped = False
            # TODO - could crash due to a race condition, could be solved with a lock
            self.q.put(item, block=False)
            return dropped
