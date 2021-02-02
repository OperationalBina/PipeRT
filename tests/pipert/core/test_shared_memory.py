import pipert.core.shared_memory as sm


class DummySharedMemoryGenerator(sm.SharedMemoryGenerator):
    def __init__(self):
        super().__init__("dummy_component", max_count=5)


def test_cleanup():
    generator = DummySharedMemoryGenerator()
    generator.get_next_shared_memory()
    generator.get_next_shared_memory()
    generator.cleanup()
    assert generator.shared_memories == {}


def test_get_next_shared_memory():
    generator = DummySharedMemoryGenerator()
    first_memory = generator.get_next_shared_memory()
    second_memory = generator.get_next_shared_memory()
    assert first_memory != second_memory
    assert first_memory == "dummy_component_0"
    assert second_memory == "dummy_component_1"
    generator.cleanup()


def test_max_count():
    generator = DummySharedMemoryGenerator()
    first_memory = generator.get_next_shared_memory()
    for _ in range(generator.max_count - 1):
        generator.get_next_shared_memory()

    assert first_memory == generator.get_next_shared_memory()
    generator.cleanup()


def test_write_and_read_from_memory():
    generator = DummySharedMemoryGenerator()
    memory_name = generator.get_next_shared_memory()
    memory = sm.get_shared_memory_object(memory_name)
    memory.acquire_semaphore()
    memory.write_to_memory(b"AAA")
    memory.release_semaphore()
    memory.acquire_semaphore()
    data = memory.read_from_memory()
    memory.release_semaphore()
    assert data == b"AAA"
    generator.cleanup()
