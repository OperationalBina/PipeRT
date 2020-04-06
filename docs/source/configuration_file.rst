Configuration file
==================

Configuration file or config file is a file designed to upload to the pipeline 
a pre-made pipeline with all of its components already set with their routines.

There are two ways to generate a config file:
The first is to generate it from a pipeline that you made with the cli using 
the command export_config_file.

The second is to write one on your own. 
Here is an example of how a config file looks like and an explanation on its structure:

.. configuration-block::
    1.   - name: Stream
    2.     queues:
    3.     - video
    4.     routines:
    5.      - fps: 23.976023976023978
    6.       name: capture_frame
    7.       out_queue: video
    8.       routine_type_name: ListenToStream
    9.       stream_address: /home/internet/Desktop/video.mp4
    10.    - max_stream_length: 10
    11.      message_queue: video
    12.      name: upload_redis
    13.      redis_send_key: camera:0
    14.      routine_type_name: MessageToRedis
    15.  - name: Display
    16.    queues:
    17.    - messages
    18.    routines:
    19.    - message_queue: messages
    20.      name: get_frames
    21.      redis_read_key: camera:0
    22.      routine_type_name: MessageFromRedis
    23.    - frame_queue: messages
    24.      name: draw_frames
    25.      routine_type_name: DisplayCv2

To make it more clear, the file is a list of components objects.

Line 1: start of new component object, setting its name value.

Line 2: start an array of queue names of the component

Line 3: the name of the queue inside the component

Line 4: start an array of routine objects, each routine has its constructor parameter names and values

Lines 5-9: key - value of the constructor parameters of the first routine

Lines 10-14: key - value of the constructor parameters of the second routine

Lines 15-25: Start a new component.

Additional notes:

- To make a premade component you need to add to the component object a new field called component_type_name, for exapmle: ``component_type_name: FlaskVideoDisplay``
