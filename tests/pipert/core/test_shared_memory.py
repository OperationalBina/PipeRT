import pipert.core.shared_memory as sm


class DummySharedMemoryGenerator(sm.SharedMemoryGenerator):
    def __init__(self):
        super().__init__("dummy_component", max_count=5)


def test_get_next_shared_memory():
    generator = DummySharedMemoryGenerator()
    first_name = generator.get_next_shared_memory()
    second_name = generator.get_next_shared_memory()
    assert first_name != second_name
    assert first_name == "dummy_component_0"
    assert second_name == "dummy_component_1"


def test_cleanup():
    generator = DummySharedMemoryGenerator()
    generator.get_next_shared_memory()
    generator.get_next_shared_memory()
    generator.cleanup()
    assert generator.shared_memories == {}


def test_max_count():
    generator = DummySharedMemoryGenerator()
    first_memory = generator.get_next_shared_memory()
    generator.get_next_shared_memory()
    generator.get_next_shared_memory()
    generator.get_next_shared_memory()
    generator.get_next_shared_memory()
    generator.get_next_shared_memory()

    assert first_memory not in generator.shared_memories


def test_write_and_read_from_memory():
    generator = DummySharedMemoryGenerator()
    memory_name = generator.get_next_shared_memory(size=3)
    memory = sm.get_shared_memory_object(memory_name)
    memory.acquire_semaphore()
    memory.write_to_memory(b"AAA")
    assert memory.read_from_memory() == b"AAA"
