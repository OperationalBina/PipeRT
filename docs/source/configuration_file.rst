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
1.     components:
2.       FlaskDisplay:
3.          component_type_name: FlaskVideoDisplay
4.          queues:
5.          - messages
6.          routines:
7.            create_image:
8.              in_queue: messages
9.              out_queue: flask_display
10.             routine_type_name: VisLogic
11.           get_frames_and_pred:
12.             image_meta_queue: messages
13.             redis_read_image_key: cam
14.             redis_read_meta_key: camera:1
15.             routine_type_name: MetaAndFrameFromRedis
16.       Stream:
17.         queues:
18.         - video
19.         routines:
20.           capture_frame:
21.             fps: 23.976023976023978
22.             out_queue: video
23.             routine_type_name: ListenToStream
24.             stream_address: pipert/contrib/test.mp4
25.           upload_redis:
26.             max_stream_length: 10
27.             message_queue: video
28.             redis_send_key: camera:0
29.             routine_type_name: MessageToRedis

To make it more clear, the file is a list of component objects.

Line 1: start of new components dictionary.

Line 2: start a new component and setting its name.

Line 3: name of premade component (not a necessary field)

Line 4: start an array of queue names.

Line 5: name of the queues.

Line 6: start a new dictionary of routines.

Line 7: start a new routine and setting its name.

Lines 8-10: setting the routine constructor parameters.

Lines 11-15: create a new routine.

Lines 16-29: create a new component and reapiting itself

Additional notes:

- To make a premade component you need to add to the component object a new field called component_type_name, for exapmle: ``component_type_name: FlaskVideoDisplay`