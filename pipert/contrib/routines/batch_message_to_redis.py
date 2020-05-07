import time
from queue import Queue
from pipert.contrib.routines import MessageToRedis
from pipert.core import QueueHandler, Routine, BatchMechanism, RoutineTypes


class BatchMessageToRedis(Routine, BatchMechanism):
	routine_type = RoutineTypes.OUTPUT

	def __init__(self, src_dst_keys, in_que, maxlen: int, internal_que_size: int = 1, blocking: bool = False,
					timeout: float = 0.0, *args, **kwargs):
		"""

		Args:
			src_dst_keys: iterable (which?), each entry has 2 items: src (in) and dst (out)
		"""
		Routine.__init__(self, *args, **kwargs)
		self.in_queue = QueueHandler(in_que)
		self._inside_collection = {}
		slave_args = []
		for idx, (in_key, out_key) in enumerate(src_dst_keys):
			p_args = [out_key, Queue(maxsize=internal_que_size), maxlen]
			kw_args = {'name': '_'.join(['slave', self.name, str(idx)]), 'component_name': self.component_name,
			           'metrics_collector': self.metrics_collector}
			slave_args.append((p_args, kw_args))

		BatchMechanism.__init__(self, MessageToRedis, tuple(slave_args), 'out_key', blocking, timeout)

	def main_logic(self, *args, **kwargs):
		msg = self.in_queue.non_blocking_get()
		if msg:
			self._inside_collection = msg

			if self.blocking:
				self.blocking_batched_operation()

			else:
				self.timeout_batched_operation()

			self._inside_collection.clear()

	def _batched_operation(self):
		to_delete = []
		for out_key, data in self._inside_collection.items():
			if self.batch[out_key]['queue'].non_blocking_put(data):
				to_delete.append(out_key)  # mark this key for deletion to avoid sending again

		# delete all keys marked for deletion
		[self._inside_collection.pop(key) for key in to_delete]

	def blocking_batched_operation(self, *args, **kwargs):
		while self._inside_collection.keys():
			self._batched_operation()

	def timeout_batched_operation(self, *args, **kwargs):
		start_time = time.time()
		timeout_reached = False
		while not timeout_reached:
			self._batched_operation()
			if not self._inside_collection.keys():
				break  # to save some time if sent all values already

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
			"in_queue": "Queue",
			"src_dst_keys": "tuple",
			"maxlen": "int",
			"internal_que_size": "int",
			"blocking": "bool",
			"timeout": "float"
		})
		return dicts

	def does_routine_use_queue(self, queue_name):
		return queue_name in [self.in_queue] + [entry['queue'] for entry in self.batch.values()]
