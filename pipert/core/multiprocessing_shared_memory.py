from pipert.core.shared_memory import MemoryIdGenerator
from multiprocessing.shared_memory import SharedMemory


def get_mp_shared_memory_object(name):
    """
    Returns a SharedMemory object that correlates to the name given.
    Params:
        -name: The name of a shared memory.
    """
    try:
        memory = SharedMemory(name=name)
    except FileNotFoundError:
        memory = None

    return memory


class MpSharedMemoryGenerator:
    """
    Generates a new shared memory each time get_next_shared_memory is called
    and is responsible for cleaning up shared memories if the count that
    exists now exceeds the max or the proccess has ended.
    """
    def __init__(self, component_name, max_count=5):
        self.memory_id_gen = MemoryIdGenerator(component_name, max_count)
        self.max_count = max_count
        self.shared_memories = {}

    def get_next_shared_memory(self, size=500000):
        next_name, name_to_unlink = self.memory_id_gen.get_next()

        memory = SharedMemory(name=next_name, create=True, size=size)

        self.shared_memories[next_name] = memory

        if name_to_unlink:
            if name_to_unlink in self.shared_memories:
                self._destroy_memory(name_to_unlink)

        return memory

    def cleanup(self):
        for _ in range(self.max_count):
            _, name_to_unlink = self.memory_id_gen.get_next()
            if name_to_unlink:
                if name_to_unlink in self.shared_memories:
                    self._destroy_memory(name_to_unlink)

    def _destroy_memory(self, name_to_unlink):
        self.shared_memories[name_to_unlink].close()
        self.shared_memories[name_to_unlink].unlink()
        self.shared_memories.pop(name_to_unlink)
