from multiprocessing.shared_memory import SharedMemory


class MemoryIdGenerator:
    """
    Generates a new id for a unique shared memory each time get_next is
    called. The id's are in the following format:
    "{component_name}_{serial_memory_number}", this helps make a unique
    shared memory each time even with threads so that we won't override
    any existing shared memories that were already created.
    """
    def __init__(self, component_name, max_count):
        self.component_name = component_name
        self.name_count = 0
        self.max_count = max_count

    def get_next(self):
        """
        Generates the next id to use for the shared memory and return
        the name of a shared memory to free if necessary.
        """
        next_name = "{0}_{1}".format(self.component_name, self.name_count)
        name_to_unlink = ""
        self.name_count += 1
        if self.name_count >= self.max_count:
            name_to_unlink = "{0}_{1}".format(self.component_name,
                                              (self.name_count
                                               - self.max_count))

        return next_name, name_to_unlink


def get_shared_memory_object(name):
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
