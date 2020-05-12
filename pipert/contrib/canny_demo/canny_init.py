# RedisEdge realtime video analytics initialization script
import argparse
from urllib.parse import urlparse
import redisai as rai
import ml2rt

if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--device', help='CPU or GPU', type=str, default='CPU')
    parser.add_argument('-i', '--camera_id', help='Input video stream key camera ID', type=str, default='0')
    parser.add_argument('-p', '--camera_prefix', help='Input video stream key prefix', type=str, default='camera')
    parser.add_argument('-u', '--url', help='RedisEdge URL', type=str, default='redis://127.0.0.1:6379')
    args = parser.parse_args()

    # Set up some vars
    # input_stream_key = '{}:{}'.format(args.camera_prefix, args.camera_id)  # Input video stream key name
    # initialized_key = '{}:initialized'.format(input_stream_key)

    device = rai.Device.gpu
    pt_model_path = 'canny.pt'
    # script_path = '../models/pytorch/imagenet/data_processing_script.txt'

    # Set up Redis connection
    url = urlparse(args.url)
    # conn = redis.Redis(host=url.hostname, port=url.port)
    conn = rai.Client(host=url.hostname, port=url.port)

    if not conn.ping():
        raise Exception('Redis unavailable')


    # Load the RedisAI model
    print('Loading model - ', end='')
    pt_model = ml2rt.load_model(pt_model_path)
    # script = ml2rt.load_script(script_path)
    out1 = conn.modelset('canny_model', rai.Backend.torch, device, pt_model)
    # out2 = conn.scriptset('canny_script', device, script)

    # Load the gear
    print('Loading gear - ', end='')
    with open('canny_gear.py', 'rb') as f:
        gear = f.read()
        res = conn.execute_command('RG.PYEXECUTE', gear)
        print(res)
