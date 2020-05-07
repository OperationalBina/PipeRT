import time
from queue import Queue
from pipert.contrib.routines import MessageFromRedis
from pipert.core import QueueHandler, Routine, BatchMechanism, RoutineTypes


class BatchMessageFromRedis(Routine, BatchMechanism):
	routine_type = RoutineTypes.INPUT

	def __init__(self, src_dst_keys, out_que, internal_que_size: int = 1, blocking: bool = False, timeout: float = 0.0,
	             *args, **kwargs):
		"""

		Args:
			src_dst_keys: iterable (which?), each entry has 2 items: src (in) and dst (out)
		"""
		Routine.__init__(self, *args, **kwargs)
		self.out_queue = QueueHandler(out_que)
		self._inside_collection = {}
		slave_args = []
		for idx, (in_key, out_key) in enumerate(src_dst_keys):
			p_args = [in_key, Queue(maxsize=internal_que_size)]
			kw_args = {'name': '_'.join(['slave', self.name, str(idx)]), 'component_name': self.component_name,
			           'out_key': out_key, 'metrics_collector': self.metrics_collector}
			slave_args.append((p_args, kw_args))

		BatchMechanism.__init__(self, MessageFromRedis, tuple(slave_args), 'name', blocking, timeout)

	def main_logic(self, *args, **kwargs):
		if self.blocking:
			self.blocking_batched_operation()

		else:  # Running with timeout=0 will still perform one check cycle
			self.timeout_batched_operation()

		# when done collecting
		self.out_queue.deque_non_blocking_put(tuple(self._inside_collection.values()))
		self._inside_collection.clear()

	def _batched_operation(self):
		for name, entry in self.batch.items():
			msg = entry['queue'].non_blocking_get()
			if msg:
				msg.out_key = entry['slave'].out_key
				self._inside_collection[name] = msg

	def blocking_batched_operation(self):
		while len(self.batch.keys()) != len(self._inside_collection.keys()):
			self._batched_operation()

	def timeout_batched_operation(self):
		start_time = time.time()
		timeout_reached = False
		while not timeout_reached:
			self._batched_operation()
			if len(self.batch.keys()) == len(self._inside_collection.keys()):
				break  # to save some time if got all values already

			timeout_reached = (time.time() - start_time) >= self.timeout

	def setup(self, *args, **kwargs):
		for entry in self.batch.values():
			entry['slave'].stop_event = self.stop_event

			# ------- For shared memory
			# if self.use_memory:
			# 	entry['slave'].use_memory = self.use_memory
			# 	entry['slave'].generator = self.generator

			entry['slave'].start()

	def cleanup(self, *args, **kwargs):
		for entry in self.batch.values():
			entry['slave'].runner.join()

	@staticmethod
	def get_constructor_parameters():
		dicts = Routine.get_constructor_parameters()
		dicts.update({
			"out_queue": "Queue",
			"src_dst_keys": "tuple",
			"internal_que_size": "int",
			"blocking": "bool",
			"timeout": "float"
		})
		return dicts

	def does_routine_use_queue(self, queue_name):
		return queue_name in [self.out_queue] + [entry['queue'] for entry in self.batch.values()]
