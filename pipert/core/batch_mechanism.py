from abc import ABC, abstractmethod
from pipert.core import QueueHandler, BaseComponent, Routine


class BatchMechanism(ABC):
	"""
	args: tuple: ([p_arg, kw_arg],  [p_arg, kw_arg]... )
				A tuple of lists, each list contains:
					- positional arguments (list)
					- keyword arguments (dict)
	"""

	def __init__(self, batch_class: type, args: tuple, batch_key: str, blocking: bool = False, timeout: float = 0.0):
		self.batch = {}
		for p_args, kw_args in args:
			slave = batch_class(*p_args, **kw_args).as_thread()
			self.batch[slave.__getattribute__(batch_key)] = {'queue': QueueHandler(slave.message_queue), 'slave': slave}

		timeout = max(timeout, 0)
		if blocking and timeout > 0:
			raise AttributeError("Either one of 'blocking' or 'timeout' may be active at one time, "
									"but not both together.")

		self.blocking = blocking
		self.timeout = timeout

	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		if not issubclass(cls, (Routine, BaseComponent)):
			raise TypeError(f'{cls} inherits from {__class__} and therefore must '
							f'inherit from either {Routine} or {BaseComponent}')

	@abstractmethod
	def blocking_batched_operation(self, *args, **kwargs):
		raise NotImplementedError

	@abstractmethod
	def timeout_batched_operation(self, *args, **kwargs):
		raise NotImplementedError
