# A Redis gear for orchestrating realtime video analytics
import redisAI
import numpy as np
# from time import time
from PIL import Image

# Globals for downsampling
_mspf = 1000 / 10.0      # Msecs per frame (initialized with 10.0 FPS)
_next_ts = 0             # Next timestamp to sample a frame
#
# class SimpleMovingAverage(object):
#     ''' Simple moving average '''
#     def __init__(self, value=0.0, count=7):
#         '''
#         @value - the initialization value
#         @count - the count of samples to keep
#         '''
#         self.count = int(count)
#         self.current = float(value)
#         self.samples = [self.current] * self.count
#
#     def __str__(self):
#         return str(round(self.current, 3))
#
#     def add(self, value):
#         ''' Adds the next value to the average '''
#         v = float(value)
#         self.samples.insert(0, v)
#         o = self.samples.pop()
#         self.current = self.current + (v-o)/self.count

# class Profiler(object):
#     ''' Mini profiler '''
#     names = []  # Steps names in order
#     data = {}   # ... and data
#     last = None
#     def __init__(self):
#         pass
#
#     def __str__(self):
#         s = ''
#         for name in self.names:
#             s = '{}{}:{}, '.format(s, name, self.data[name])
#         return(s[:-2])
#
#     def __delta(self):
#         ''' Returns the time delta between invocations '''
#         now = time()*1000       # Transform to milliseconds
#         if self.last is None:
#             self.last = now
#         value = now - self.last
#         self.last = now
#         return value
#
#     def start(self):
#         ''' Starts the profiler '''
#         self.last = time()*1000
#
#     def add(self, name):
#         ''' Adds/updates a step's duration '''
#         value = self.__delta()
#         if name not in self.data:
#             self.names.append(name)
#             self.data[name] = SimpleMovingAverage(value=value)
#         else:
#             self.data[name].add(value)
#
#     def assign(self, name, value):
#         ''' Assigns a step with a value '''
#         if name not in self.data:
#             self.names.append(name)
#             self.data[name] = SimpleMovingAverage(value=value)
#         else:
#             self.data[name].add(value)
#
#     def get(self, name):
#         ''' Gets a step's value '''
#         return self.data[name].current

'''
The profiler is used first and foremost for keeping track of the total (average) time it takes to process
a frame - the information is required for setting the FPS dynamically. As a side benefit, it also provides
per step metrics.
'''
# prf = Profiler()

# def downsampleStream(x):
#     ''' Drops input frames to match FPS '''
#     global _mspf, _next_ts
#     execute('TS.INCRBY', 'camera:0:in_fps', 1, 'RESET', 1)  # Store the input fps count
#     ts, _ = map(int, str(x['streamId']).split('-'))         # Extract the timestamp part from the message ID
#     sample_it = _next_ts <= ts
#     if sample_it:                                           # Drop frames until the next timestamp is in the present/past
#         _next_ts = ts + _mspf
#     return sample_it


def runCanny(x):
    ''' Runs the model on an input image from the stream '''
    global prf
    IMG_SIZE = 416     # Model's input image size

    # log('read')

    # Read the image from the stream's message
    buf = io.BytesIO(x['image'])
    pil_image = Image.open(buf)
    image = np.array(pil_image).transpose((2, 0, 1)) / 255.

    # log('resize')
    # Resize, normalize and tensorize the image for the model (number of images, width, height, channels)
    # log('tensor')
    img_ba = bytearray(image.tobytes())
    image_tensor = redisAI.createTensorFromBlob('FLOAT', [1, 480, 640, 3], img_ba)

    # log('model')
    # Create the RedisAI model runner and run it
    modelRunner = redisAI.createModelRunner('canny:model')
    redisAI.modelRunnerAddInput(modelRunner, 'input', image_tensor)
    redisAI.modelRunnerAddOutput(modelRunner, 'output')
    model_replies = redisAI.modelRunnerRun(modelRunner)
    # model_output = model_replies[0]
    shape = redisAI.tensorGetDims(model_replies)
    buf = redisAI.tensorGetDataAsBlob(model_replies)
    edges = np.frombuffer(buf, dtype=np.float32).reshape(shape)

    # log('script')
    # The model's output is processed with a PyTorch script for non maxima suppression
    # scriptRunner = redisAI.createScriptRunner('yolo:script', 'boxes_from_tf')
    # redisAI.scriptRunnerAddInput(scriptRunner, model_output)
    # redisAI.scriptRunnerAddOutput(scriptRunner)
    # script_reply = redisAI.scriptRunnerRun(scriptRunner)
    # prf.add('script')

    # log('boxes')
    # The script outputs bounding boxes
    # shape = redisAI.tensorGetDims(script_reply)
    # buf = redisAI.tensorGetDataAsBlob(script_reply)
    # boxes = np.frombuffer(buf, dtype=np.float32).reshape(shape)

    # Iterate boxes to extract the people
    # ratio = float(IMG_SIZE) / max(pil_image.width, pil_image.height)  # ratio = old / new
    # pad_x = (IMG_SIZE - pil_image.width * ratio) / 2                  # Width padding
    # pad_y = (IMG_SIZE - pil_image.height * ratio) / 2                 # Height padding
    # boxes_out = []
    # people_count = 0
    # for box in boxes[0]:
    #     if box[4] == 0.0:  # Remove zero-confidence detections
    #         continue
    #     if box[-1] != 14:  # Ignore detections that aren't people
    #         continue
    #     people_count += 1
    #
    #     # Descale bounding box coordinates back to original image size
    #     x1 = (IMG_SIZE * (box[0] - 0.5 * box[2]) - pad_x) / ratio
    #     y1 = (IMG_SIZE * (box[1] - 0.5 * box[3]) - pad_y) / ratio
    #     x2 = (IMG_SIZE * (box[0] + 0.5 * box[2]) - pad_x) / ratio
    #     y2 = (IMG_SIZE * (box[1] + 0.5 * box[3]) - pad_y) / ratio
    #
    #     # Store boxes as a flat list
    #     boxes_out += [x1,y1,x2,y2]
    # prf.add('boxes')

    return x['streamId'], edges


def storeResults(x):
    ''' Stores the results in Redis Stream and TimeSeries data structures '''
    global _mspf, prf
    ref_id, edges = x[0], int(x[1])
    ref_msec = int(str(ref_id).split('-')[0])

    # Store the output in its own stream
    res_id = execute('XADD', 'camera:0:yolo', 'MAXLEN', '~', 1000, '*', 'ref', ref_id, 'edges', edges)


# Create and register a gear that for each message in the stream
gb = GearsBuilder('StreamReader')
# gb.filter(downsampleStream)  # Filter out high frame rate
gb.map(runCanny)              # Run the model
gb.map(storeResults)         # Store the results
gb.register('camera:0')