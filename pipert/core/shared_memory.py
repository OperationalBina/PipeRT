import mmap
import posix_ipc


class MemoryIdGenerator:
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
        self.mapfile.seek(0)
        self.mapfile.write(b)

    def read_from_memory(self):
        self.mapfile.seek(0)
        file_content = self.mapfile.read(self.mapfile.size())

        return file_content

    def free_memory(self):
        self.mapfile.close()
        self.memory.unlink()
        self.semaphore.release()
        self.semaphore.unlink()


def get_shared_memory_object(name):
    memory = posix_ipc.SharedMemory(name, posix_ipc.O_CREAT,
                                    size=5000000)
    semaphore = posix_ipc.Semaphore(name, posix_ipc.O_CREAT)
    mapfile = mmap.mmap(memory.fd, memory.size)

    memory.close_fd()

    semaphore.release()

    return SharedMemory(memory, semaphore, mapfile)


class SharedMemoryGenerator:
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
                self.shared_memories[name_to_unlink].free_memory()

        semaphore.release()

        return next_name

    def cleanup(self):
        for _ in range(self.max_count):
            _, name_to_unlink = self.memory_id_gen.get_next()
            if name_to_unlink:
                if name_to_unlink in self.shared_memories:
                    self.shared_memories[name_to_unlink].free_memory()
