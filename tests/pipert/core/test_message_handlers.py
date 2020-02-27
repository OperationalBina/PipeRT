import pytest
from pipert.core.message_handlers import RedisHandler
from urllib.parse import urlparse

key = "test"

# TODO - replace the redis url to os.environ.get('REDIS_URL') ????
@pytest.fixture(scope="function")
def redis_handler():
    redis_handler = RedisHandler(urlparse("redis://127.0.0.1:6379"))
    redis_handler.connect()
    yield redis_handler
    redis_handler.conn.delete(key)
    redis_handler.close()


# tests if the method read the last message if it didn't read before
def test_redis_read_next_msg_reads_last_message(redis_handler):
    redis_handler.send("AAA", key)
    redis_handler.send("BBB", key)
    msg = redis_handler.read_next_msg(key)

    assert msg.decode() == "BBB"


def test_redis_read_next_msg(redis_handler):
    redis_handler.send("AAA", key)
    assert redis_handler.read_next_msg(key).decode() == "AAA"
    redis_handler.send("BBB", key)
    redis_handler.send("CCC", key)
    assert redis_handler.read_next_msg(key).decode() == "BBB"


def test_redis_read_next_msg_cannot_read_the_same_message(redis_handler):
    redis_handler.send("AAA", key)
    assert redis_handler.read_next_msg(key).decode() == "AAA"

    assert redis_handler.read_next_msg(key) is None


def test_redis_read_most_recent_message(redis_handler):
    redis_handler.send("AAA", key)
    redis_handler.send("BBB", key)
    assert redis_handler.read_most_recent_msg(key).decode() == "BBB"


def test_redis_read_most_recent_message_cannot_read_the_same_message(redis_handler):
    redis_handler.send("AAA", key)
    assert redis_handler.read_most_recent_msg(key).decode() == "AAA"
    assert redis_handler.read_most_recent_msg(key) is None
