Message Handler
===============

Message Handler is an object that managed the connection to the message broker.
For this moment, the only implementation available is Redis Handler,
that managed the connection to the redis server.
It also managed the sending and receiving messages from the components to Redis and back.
In addition, it has two special functions:
    1. read_next_msg: reads the next message right after the message you just read.
    2. read_most_recent_msg: reads only the most recent message, the last one that came in.
Both functions don't read the same message twice.

.. currentmodule:: pipert.core.message_handler

.. autoclass:: MessageHandler
   :members: