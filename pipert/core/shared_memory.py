class SharedMemory:
    """
   A wrapper for posix_ipc.SharedMemory, posix_ipc.Semaphore and the correlating mapfile to simplify usage.
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
