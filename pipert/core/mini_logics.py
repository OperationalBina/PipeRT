import time
from pipert.core.message_handlers import RedisHandler
from pipert.core.message import message_decode, message_encode
from pipert.core.routine import Routine
from pipert.core import QueueHandler
from pipert.core.sharedMemory import get_shared_memory_object
from pipert.core.sharedMemory import SharedMemoryGenerator


class Listen2Stream(Routine):

    def __init__(self, stream_address, queue, fps=30., use_memory=False,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_address = stream_address
        self.isFile = str(stream_address).endswith("mp4")
        self.stream = None
        self.queue = queue
        self.fps = fps
        self.updated_config = {}
        self.use_memory = use_memory
        self.memory_generator = SharedMemoryGenerator(self.component_name)

    def begin_capture(self):
        self.stream = cv2.VideoCapture(self.stream_address)
        if self.isFile:
            self.fps = self.stream.get(cv2.CAP_PROP_FPS)
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.logger.info("Starting video capture on %s", self.stream_address)

    def change_stream(self):
        if self.stream_address == self.updated_config['stream_address']:
            return
        self.stream_address = self.updated_config['stream_address']
        self.fps = self.updated_config['FPS']
        self.isFile = str(self.stream_address).endswith("mp4")
        self.logger.info("Changing source stream address to %s",
                         self.updated_config['stream_address'])
        self.begin_capture()

    def main_logic(self, *args, **kwargs):
        if self.updated_config:
            self.change_stream()
            self.updated_config = {}

        grabbed, frame = self.stream.read()

        if grabbed:
            start = time.time()
            if self.use_memory:
                row, column, depth = frame.shape
                frame_size = row*column*depth
                memory_name = self.memory_generator.get_next_shared_memory(
                    size=frame_size
                )
                memory = get_shared_memory_object(memory_name)
                memory.acquire_semaphore()
                msg = Message(memory_name, self.stream_address)
            else:
                msg = Message(frame, self.stream_address)
            msg.record_entry(self.component_name, self.logger)
            frame = resize(frame, 640, 480)
            # if the stream is from a webcam, flip the frame
            if self.stream_address == 0:
                frame = cv2.flip(frame, 1)
            try:
                self.queue.get(block=False)
            except Empty:
                pass
            finally:
                if self.use_memory:
                    memory.write_to_memory(cv2.imencode('.png', frame)[1]
                                           .tostring())
                    memory.release_semaphore()
                else:
                    msg.update_payload(frame)
                self.queue.put(msg)
                if self.isFile:
                    wait = time.time() - start
                    time.sleep(max(1 / self.fps - wait, 0))
                time.sleep(0)
                return True

    def setup(self, *args, **kwargs):
        self.begin_capture()

    def cleanup(self, *args, **kwargs):
        self.stream.release()
        self.memory_generator.cleanup()
        del self.stream


# TODO: add Error handling to connection
class Message2Redis(Routine):

    def __init__(self, out_key, url, queue, maxlen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.out_key = out_key
        self.url = url
        self.q_handler = QueueHandler(queue)
        self.maxlen = maxlen
        self.msg_handler = None

    def main_logic(self, *args, **kwargs):
        msg = self.q_handler.non_blocking_get()
        if msg:
            msg.record_exit(self.component_name, self.logger)
            encoded_msg = message_encode(msg)
            self.msg_handler.send(self.out_key, encoded_msg)
            return True
        else:
            return False

    def setup(self, *args, **kwargs):
        self.msg_handler = RedisHandler(self.url, self.maxlen)
        self.msg_handler.connect()

    def cleanup(self, *args, **kwargs):
        self.msg_handler.close()


class MessageFromRedis(Routine):

    def __init__(self, in_key, url, queue, most_recent=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_key = in_key
        self.url = url
        self.q_handler = QueueHandler(queue)
        self.msg_handler = None
        self.most_recent = most_recent
        self.read_method = None
        self.flip = False
        self.negative = False

    def main_logic(self, *args, **kwargs):
        encoded_msg = self.read_method(self.in_key)
        if encoded_msg:
            msg = message_decode(encoded_msg)
            msg.record_entry(self.component_name, self.logger)
            success = self.q_handler.deque_non_blocking_put(msg)
            return success
        else:
            time.sleep(0)
            return None

    def setup(self, *args, **kwargs):
        self.msg_handler = RedisHandler(self.url)
        if self.most_recent:
            self.read_method = self.msg_handler.read_most_recent_msg
        else:
            self.read_method = self.msg_handler.read_next_msg
        self.msg_handler.connect()

    def cleanup(self, *args, **kwargs):
        self.msg_handler.close()
