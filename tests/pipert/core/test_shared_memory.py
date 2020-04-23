import pipert.core.multiprocessing_shared_memory as sm


class DummySharedMemoryGenerator(sm.MpSharedMemoryGenerator):
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
    assert first_memory.name == "dummy_component_0"
    assert second_memory.name == "dummy_component_1"
    generator.cleanup()


def test_max_count():
    generator = DummySharedMemoryGenerator()
    first_memory = generator.get_next_shared_memory()
    for _ in range(5):
        generator.get_next_shared_memory()

    assert first_memory.name not in generator.shared_memories
    generator.cleanup()


def test_write_and_read_from_memory():
    generator = DummySharedMemoryGenerator()
    memory_name = generator.get_next_shared_memory(size=3).name
    memory = sm.get_shared_memory_object(memory_name)
    memory.buf[:] = b"AAA"
    assert bytes(memory.buf) == b"AAA"
    generator.cleanup()
