import posix_ipc
import mmap
from pipert.core.shared_memory import SharedMemory


class MemoryIdIterator:
    """
    Iterates over a set amount of id's. The id's are in the following format:
    "{component_name}_{serial_memory_number}".
    """
    def __init__(self, component_name, max_count):
        self.component_name = component_name
        self.name_count = 0
        self.max_count = max_count

    def get_next(self):
        """
        Get the next shared memory name.

        Returns: Next available shared memory name.
        """
        current_memory_id = (self.name_count % self.max_count)
        next_name = f"{self.component_name}_{current_memory_id}"
        self.name_count += 1

        return next_name


class SharedMemoryGenerator:
    """
    Generates a set 'max_count' amount of shared memories to be used.
    """
    def __init__(self, component_name, max_count=50, size=5000000):
        self.memory_id_gen = MemoryIdIterator(component_name, max_count)
        self.max_count = max_count
        self.shared_memories = {}
        for _ in range(self.max_count):
            next_name = self.memory_id_gen.get_next()
            memory = posix_ipc.SharedMemory(next_name, posix_ipc.O_CREAT,
                                            size=size)
            semaphore = posix_ipc.Semaphore(next_name, posix_ipc.O_CREAT)
            mapfile = mmap.mmap(memory.fd, memory.size)
            memory.close_fd()

            semaphore.release()
            self.shared_memories[next_name] = SharedMemory(memory, semaphore,
                                                           mapfile)

    def get_next_shared_memory_name(self):
        return self.memory_id_gen.get_next()

    def get_shared_memory_object(self, name):
        try:
            return self.shared_memories[name]
        except KeyError:
            return None

    def cleanup(self):
        """
        Cleans all of the allocated shared memories to free up the ram.

        """
        for _ in range(self.max_count):
            name_to_unlink = self.memory_id_gen.get_next()
            if name_to_unlink in self.shared_memories:
                self._destroy_memory(name_to_unlink)

    def _destroy_memory(self, memory_to_destroy):
        """
        Destroys a specified shared memory.

        Args:
            memory_to_destroy: The name of the existing shared memory.

        """
        self.shared_memories[memory_to_destroy].free_memory()
        self.shared_memories.pop(memory_to_destroy)
