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
1. monitoring_system: Prometheus
2. pods:
3.   FlaskPod:
4.     components:
5.       FlaskDisplay:
6.         shared_memory: False
7.         component_type_name: FlaskVideoDisplay
8.         component_args:
9.          port: 5000
10.        queues: []
11.        routines:
12.          from_redis:
13.            message_queue: flask_display
14.            redis_read_key: cam
15.            routine_type_name: MessageFromRedis
16.    ip: 192.169.30.4
17.  StreamPod:
18.    components:
19.      Stream:
20.        shared_memory: True
21.        queues:
22.        - video
23.        routines:
24.          capture_frame:
25.            fps: 30
26.            out_queue: video
27.            routine_type_name: ListenToStream
28.            stream_address: pipert/contrib/test.mp4
29.          upload_redis:
30.            max_stream_length: 10
31.            message_queue: video
32.            redis_send_key: cam
33.            routine_type_name: MessageToRedis


To make it more clear, the pods is a list of component objects in each pod.
Each pod running in different container

Line 1: declaring which monitoring system to use (Optional).

Line 2: start of new pods dictionary.

Line 3: start a new pod and setting its name.

Line 4: start of new components dictionary.

Line 5: start a new component and setting its name.

Line 6: Use the shared memory to communicate between components (Optional, Default is False)

Line 7: name of premade component (not a necessary field)

Line 8: starting a new dictionary for the component arguments

Line 9: setting the component arguments

Line 10: start an array of queue names.

Line 11: start a new dictionary of routines.

Line 12: start a new routine and setting its name.

Lines 13-15: setting the routine constructor parameters.

Lines 16: setting the ip of the pod (Optional, The ip network part must be 192.169)

Lines 17-33: create a new pod and reapiting itself

Additional notes:

- To make a premade component you need to add to the component object a new field called component_type_name, for exapmle: `component_type_name: FlaskVideoDisplay`
- You can make a component to use a shared_memory by adding a field called shared_memory, for example: `shared_memory: True`