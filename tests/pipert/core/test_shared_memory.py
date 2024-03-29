import pipert.core.shared_memory_generator as sm
from pipert.core.shared_memory_generator import get_shared_memory_object


class DummySharedMemoryGenerator(sm.SharedMemoryGenerator):
    def __init__(self):
        super().__init__("dummy_component", max_count=5)
        self.create_memories()


def test_cleanup():
    generator = DummySharedMemoryGenerator()
    generator.cleanup()
    assert generator.shared_memories == {}


def test_get_next_shared_memory():
    generator = DummySharedMemoryGenerator()
    first_memory = generator.get_next_shared_memory_name()
    second_memory = generator.get_next_shared_memory_name()
    assert first_memory == "dummy_component_0"
    assert second_memory == "dummy_component_1"
    generator.cleanup()


def test_max_count():
    generator = DummySharedMemoryGenerator()
    first_memory = generator.get_next_shared_memory_name()
    for _ in range(generator.max_count - 1):
        generator.get_next_shared_memory_name()

    assert first_memory == generator.get_next_shared_memory_name()
    generator.cleanup()


def test_write_and_read_from_memory():
    generator = DummySharedMemoryGenerator()
    memory_name = generator.get_next_shared_memory_name()
    memory = get_shared_memory_object(memory_name)
    memory.acquire_semaphore()
    memory.write_to_memory(b"AAA")
    message_size = len(b"AAA")
    memory.release_semaphore()
    memory.acquire_semaphore()
    data = memory.read_from_memory(message_size)
    memory.release_semaphore()
    assert data == b"AAA"
    generator.cleanup()
