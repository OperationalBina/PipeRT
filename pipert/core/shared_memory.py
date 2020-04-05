import mmap
import posix_ipc


class SharedMemory:
    def __init__(self, memory, semaphore, mapfile):
        self.memory = memory
        self.semaphore = semaphore
        self.mapfile = mapfile

    def release_semaphore(self):
        self.semaphore.release()

    def acquire_semaphore(self):
        self.semaphore.acquire()

    def write_to_memory(self, b):
        """
        writes the frame given to it to the shared memory object.
        Params:
            -b: A frame converted to byte code.
        """
        self.mapfile.seek(0)
        self.mapfile.write(b)

    def read_from_memory(self):
        """
        Reads what is currently in the shared memory.
        """
        self.mapfile.seek(0)
        file_content = self.mapfile.read(self.mapfile.size())

        return file_content

    def free_memory(self):
        """
        cleans what is on the memory and deletes it.
        """
        self.mapfile.close()
        self.memory.unlink()
        self.semaphore.release()
        self.semaphore.unlink()


def get_shared_memory_object(name):
    """
    Returns a SharedMemory object that correlates to the name given.
    Params:
        -name: The name of a shared memory.
    """
    memory = posix_ipc.SharedMemory(name, posix_ipc.O_CREAT)
    semaphore = posix_ipc.Semaphore(name, posix_ipc.O_CREAT)
    mapfile = mmap.mmap(memory.fd, memory.size)

    memory.close_fd()

    semaphore.release()

    return SharedMemory(memory, semaphore, mapfile)


class SharedMemoryGenerator:
    """
    Generates a new shared memory each time get_next_shared_memory is called
    and is responsible for cleaning up shared memories if the count that
    exists now exceeds the max or the proccess has ended.
    """
    def __init__(self, component_name, max_count=5):
        self.memory_id_gen = MemoryIdGenerator(component_name, max_count)
        self.max_count = max_count
        self.shared_memories = {}

    def get_next_shared_memory(self, size=5000000):
        next_name, name_to_unlink = self.memory_id_gen.get_next()

        memory = posix_ipc.SharedMemory(next_name, posix_ipc.O_CREAT,
                                        size=size)
        semaphore = posix_ipc.Semaphore(next_name, posix_ipc.O_CREAT)
        mapfile = mmap.mmap(memory.fd, memory.size)

        memory.close_fd()

        self.shared_memories[next_name] = SharedMemory(memory, semaphore,
                                                       mapfile)

        if name_to_unlink:
            if name_to_unlink in self.shared_memories:
                self._destroy_memory(name_to_unlink)

        semaphore.release()

        return next_name

    def cleanup(self):
        for _ in range(self.max_count):
            _, name_to_unlink = self.memory_id_gen.get_next()
            if name_to_unlink:
                if name_to_unlink in self.shared_memories:
                    self._destroy_memory(name_to_unlink)

    def _destroy_memory(self, name_to_unlink):
        self.shared_memories[name_to_unlink].free_memory()
        self.shared_memories.pop(name_to_unlink)
