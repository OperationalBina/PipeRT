from torch.multiprocessing import Event
import os
import signal


class BaseComponent:

    def __init__(self, output_dict, input_dict):
        super().__init__()
        self.output_dict = output_dict
        self.input_dict = input_dict
        self.stop_event = Event()

    def _start(self):
        raise NotImplementedError

    def _inner_stop(self):
        raise NotImplementedError

    def stop_run(self):
        """
        used by zerorpc to stop all child processes and threads, and then stop
        the zerorpc server itself, terminating the run
        :return:
        """
        self.stop_event.set()
        self._inner_stop()
        os.kill(os.getpid(), signal.SIGTERM)
