Message
=======

A message is an object that was created to wrap the data from the components and add to it
more necessary information for the developer to keep track of the data.
With the messages, the components can send the data to the database they use and receive data as well.
For this moment, all the components use Redis message broker.

Every message contains:
1. unique id
2. payload - a frame or prediction to send or receive from the message broker.
3. history - a documentation of when data came in and out of the component.

Payloads:
We have 2 payloads - frame and prediction.
Each payload has an encoding and decoding functions.
These functions in the prediction payload do nothing, but in the frame payload,
the encoding compressing the frame in .jpg form and the decoding does the opposite function.

Before sending the message, we need to pickle it - turn it into bytes.
Redis only gets information in bytes and that is the reason we need to encode the message,
and when we receive a message, decode it.

.. currentmodule:: pipert.core.message

.. autoclass:: Message
   :members:
