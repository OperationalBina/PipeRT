import posix_ipc
import mmap


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
        next_name = f"{self.component_name}_{(self.name_count % self.max_count)}"
        self.name_count += 1

        return next_name


class SharedMemory:
    """
    A wrapper for posix_ipc.SharedMemory, posix_ipc.Semaphore and the correlating mapfile to simply usage.
    """
    def __init__(self, memory, semaphore, mapfile):
        self.memory = memory
        self.semaphore = semaphore
        self.mapfile = mapfile

    def release_semaphore(self):
        self.semaphore.release()

    def acquire_semaphore(self):
        self.semaphore.acquire()

    def write_to_memory(self, byte_code):
        """
        Writes a given byte code to the shared memory.
        Args:
            byte_code: A byte string that's to be written to the shared memory.

        """
        self.mapfile.flush()
        self.mapfile.seek(0)
        self.mapfile.write(byte_code)

    def read_from_memory(self, size=0):
        """
        Reads a segment from the shared memory according to size.
        Args:
            size: The amount of bytes that are to be read.

        Returns: The byte string stored in the memory.

        """
        self.mapfile.seek(0)
        file_content = self.mapfile.read(size)

        return file_content

    def free_memory(self):
        """
        Cleans what is on the memory and deletes it.
        """
        self.mapfile.close()
        self.memory.close_fd()
        self.semaphore.release()
        self.semaphore.unlink()
        self.memory.unlink()


def get_shared_memory_object(name):
    """
    Get a SharedMemory object that correlates to the name given.

    Args:
        name: The name of a shared memory.

    Returns: A SharedMemory object.

    """
    try:
        memory = posix_ipc.SharedMemory(name)
        semaphore = posix_ipc.Semaphore(name)
    except posix_ipc.ExistentialError:
        return None
    except Exception:
        return None

    mapfile = mmap.mmap(memory.fd, memory.size)

    memory.close_fd()

    semaphore.release()

    return SharedMemory(memory, semaphore, mapfile)


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

    def get_next_shared_memory(self):
        """
        Iterates over the existing memories in a cycle.

        Returns: The next shared memory that's available to use.

        """
        return self.memory_id_gen.get_next()

    def cleanup(self):
        """
        Cleans all of the allocated shared memories to free up the ram.

        """
        for _ in range(self.max_count):
            name_to_unlink = self.memory_id_gen.get_next()
            if name_to_unlink:
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
