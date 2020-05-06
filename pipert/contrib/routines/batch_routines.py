import time
from queue import Queue
from pipert.contrib.routines import MessageFromRedis, MessageToRedis
from pipert.core import QueueHandler, Routine, BatchMechanism, RoutineTypes


class BatchMsgFromRedis(Routine, BatchMechanism):
	routine_type = RoutineTypes.INPUT

	def __init__(self, src_dst_keys, out_que, name, component_name, metrics_collector,
					internal_que_size: int = 1, blocking: bool = False, timeout: float = 0.0):
		"""

		Args:
			src_dst_keys: iterable (which?), each entry has 2 items: src (in) and dst (out)
		"""
		Routine.__init__(self, name=name, component_name=component_name, metrics_collector=metrics_collector)
		self.out_queue = QueueHandler(out_que)
		self._inside_collection = {}
		args = []
		for idx, (in_key, out_key) in enumerate(src_dst_keys):
			p_args = [in_key,  Queue(maxsize=internal_que_size)]
			kw_args = {'name': '_'.join(['slave', name, str(idx)]), 'component_name': component_name,
						'out_key': out_key, 'metrics_collector': metrics_collector}
			args.append((p_args, kw_args))

		BatchMechanism.__init__(self, MessageFromRedis, tuple(args), 'name', blocking, timeout)

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
		pass

	def cleanup(self, *args, **kwargs):
		pass

	@staticmethod
	def get_constructor_parameters():
		pass

	def does_routine_use_queue(self, queue_name):
		pass


class BatchMsgToRedis(Routine, BatchMechanism):
	routine_type = RoutineTypes.OUTPUT

	def __init__(self, src_dst_keys, in_que, maxlen, name, component_name, metrics_collector,
	             internal_que_size: int = 1, blocking: bool = False, timeout: float = 0.0):
		"""

		Args:
			src_dst_keys: iterable (which?), each entry has 2 items: src (in) and dst (out)
		"""
		Routine.__init__(self, name=name, component_name=component_name, metrics_collector=metrics_collector)
		self.in_queue = QueueHandler(in_que)
		self._inside_collection = {}
		args = []
		for idx, (in_key, out_key) in enumerate(src_dst_keys):
			p_args = [out_key,  Queue(maxsize=internal_que_size), maxlen]
			kw_args = {'name': '_'.join(['slave', name, str(idx)]), 'component_name': component_name,
			           'metrics_collector': metrics_collector, 'out_key': out_key}
			args.append((p_args, kw_args))

		BatchMechanism.__init__(self, MessageToRedis, tuple(args), 'out_key', blocking, timeout)

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
		pass

	def cleanup(self, *args, **kwargs):
		pass

	@staticmethod
	def get_constructor_parameters():
		pass

	def does_routine_use_queue(self, queue_name):
		pass

