import posix_ipc
import mmap


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
        next_name = "{0}_{1}".format(self.component_name, (self.name_count % self.max_count))
        # name_to_unlink = ""
        self.name_count += 1
        # if self.name_count >= self.max_count:
        #     name_to_unlink = "{0}_{1}".format(self.component_name,
        #                                       (self.name_count
        #                                        - self.max_count))
        # return next_name, name_to_unlink
        return next_name


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
        self.mapfile.flush()
        self.mapfile.seek(0)
        self.mapfile.write(b)
        self.size = len(b)

    def read_from_memory(self, size=0):
        """
        Reads what is currently in the shared memory.
        """
        self.mapfile.seek(0)
        file_content = self.mapfile.read(size)

        return file_content

    def free_memory(self):
        """
        cleans what is on the memory and deletes it.
        """
        self.mapfile.close()
        self.memory.close_fd()
        self.semaphore.release()
        self.semaphore.unlink()
        self.memory.unlink()


def get_shared_memory_object(name):
    """
    Returns a SharedMemory object that correlates to the name given.
    Params:
        -name: The name of a shared memory.
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
    Generates a new shared memory each time get_next_shared_memory is called
    and is responsible for cleaning up shared memories if the count that
    exists now exceeds the max or the proccess has ended.
    """
    def __init__(self, component_name, max_count=50, size=5000000):
        self.memory_id_gen = MemoryIdGenerator(component_name, max_count)
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

    def get_next_shared_memory(self, size=5000000):
        # next_name, name_to_unlink = self.memory_id_gen.get_next()
        next_name = self.memory_id_gen.get_next()

        # memory = posix_ipc.SharedMemory(next_name, posix_ipc.O_CREAT,
        #                                 size=size)
        # semaphore = posix_ipc.Semaphore(next_name, posix_ipc.O_CREAT)
        # print(f"Shared Memory:\nfd: {memory.fd}\nmode: {memory.mode}\nname: {memory.name}\nsize: {memory.size}")
        # mapfile = mmap.mmap(memory.fd, memory.size)
        #
        # memory.close_fd()
        #
        # self.shared_memories[next_name] = SharedMemory(memory, semaphore,
        #                                                mapfile)
        #
        # if name_to_unlink:
        #     if name_to_unlink in self.shared_memories:
        #         self._destroy_memory(name_to_unlink)

        # semaphore.release()

        return next_name

    def cleanup(self):
        for _ in range(self.max_count):
            name_to_unlink = self.memory_id_gen.get_next()
            if name_to_unlink:
                if name_to_unlink in self.shared_memories:
                    self._destroy_memory(name_to_unlink)
        # for _ in range(self.max_count):
        #     _, name_to_unlink = self.memory_id_gen.get_next()
        #     if name_to_unlink:
        #         if name_to_unlink in self.shared_memories:
        #             self._destroy_memory(name_to_unlink)

    def _destroy_memory(self, name_to_unlink):
        self.shared_memories[name_to_unlink].free_memory()
        self.shared_memories.pop(name_to_unlink)
