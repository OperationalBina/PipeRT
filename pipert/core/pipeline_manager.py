import zerorpc
import re
from pipert.core.component import BaseComponent
from pipert.core.errors import QueueDoesNotExist
from pipert.core.routine import Routine
from os import listdir
from os.path import isfile, join
import json


class PipelineManager:

    def __init__(self, endpoint="tcp://0.0.0.0:4001"):
        """
        Args:
            endpoint: the endpoint the PipelineManager's zerorpc server will listen
            in.
        """
        super().__init__()
        self.components = {}
        self.endpoint_port_counter = 4002
        self.zrpc = zerorpc.Server(self)
        self.zrpc.bind(endpoint)
        self.ROUTINES_FOLDER_PATH = "../contrib/routines"
        self.zrpc.run()

    def create_component(self, component_name):
        if self._does_component_exist(component_name):
            print("Component name '" + component_name + "' already exist")
            return False
        else:
            self.components[component_name] = \
                BaseComponent(name=component_name,
                              endpoint="tcp://0.0.0.0:{0:0=4d}"
                              .format(self.endpoint_port_counter))
            print("Component " + component_name + " has been created")
            self.endpoint_port_counter += 1
            return True

    def remove_component(self, component_name):
        if not self._does_component_exist(component_name):
            print("Component name '" + component_name + "' doesn't exist")
            return False
        else:
            if not self.components[component_name].stop_event.is_set():
                self.components[component_name].stop_run()
            del self.components[component_name]
            return True

    def add_routine_to_component(self, component_name, routine_name, **routine_kwargs):
        if not self._does_component_exist(component_name):
            print("The component '" + component_name + " doesn't exist")
            return False
        routine_object = self._get_routine_object_by_name(routine_name)

        if routine_object is None:
            print("The routine '" + routine_name + " doesn't exist")
            return False

        try:
            # replace all queue names with the queue objects of the component
            for key, value in routine_kwargs.items():
                if 'queue' in key.lower():
                    routine_kwargs[key] = self.components[component_name].get_queue(queue_name=value)

            self.components[component_name].register_routine(routine_object(**routine_kwargs).as_thread())
            return True
        except QueueDoesNotExist as e:
            print(e.msg)
        except Exception as e:
            print(e.__traceback__)
        return False

    def remove_routine_from_component(self, component_name, routine_name):
        pass

    def create_queue_to_component(self, component_name, queue_name, queue_size=1):
        if not self._does_component_exist(component_name):
            print("The component " + component_name + " doesn't exist")
            return False
        if self.components[component_name].does_queue_exist(queue_name):
            print("The queue name " + queue_name + " already exist")
            return False

        self.components[component_name].create_queue(queue_name=queue_name, queue_size=queue_size)
        return True

    def remove_queue_from_component(self, component_name, queue_name):
        if not self._does_component_exist(component_name):
            print("The component " + component_name + " doesn't exist")
            return False
        if not self.components[component_name].does_queue_exist(queue_name):
            print("The queue name " + queue_name + " doesn't exist")
            return False

        return self.components[component_name].delete_queue(queue_name=queue_name)

    def run_component(self, component_name):
        if not self._does_component_exist(component_name):
            print("The component " + component_name + " doesn't exist")
            return False
        elif not self.components[component_name].stop_event.is_set():
            print("The component already running")
            return False
        else:
            self.components[component_name].run()
            return True

    def stop_component(self, component_name):
        if not self._does_component_exist(component_name):
            print("The component " + component_name + " doesn't exist")
            return False
        elif self.components[component_name].stop_event.is_set():
            print("The component is not running running")
            return False
        else:
            self.components[component_name].stop_run()
            return True

    def run_all_components(self):
        for component in self.components.values():
            if component.stop_event.is_set():
                print("Started")
                print(component)
                component.run()
        return True

    def stop_all_components(self):
        for component in self.components.values():
            if not component.stop_event.is_set():
                print("Stopped")
                print(component)
                print(component.stop_run())
        return True

    def get_all_routines(self):
        routine_file_names = [f for f in
                              listdir(self.ROUTINES_FOLDER_PATH)
                              if isfile(join(self.ROUTINES_FOLDER_PATH, f))]

        routine_file_names = [file_name[:-3] for file_name in routine_file_names]
        routine_file_names = [file_name[0].upper() +
                              re.sub(r'_\w',
                                     self._remove_string_with_underscore,
                                     file_name)[1:]
                              for file_name in routine_file_names]
        return routine_file_names

    @staticmethod
    def _remove_string_with_underscore(match):
        return match.group(0).upper()[1]

    @staticmethod
    def _add_underscore_before_uppercase(match):
        return '_' + match.group(0).lower()

    def get_routine_params(self, routine_name):
        routine_object = self._get_routine_object_by_name(routine_name)
        params = routine_object.get_constructor_parameters()
        params = json.dumps(params)
        return params

    def _get_routine_object_by_name(self, routine_name: str) -> Routine:
        path = self.ROUTINES_FOLDER_PATH.replace('/', '.') + "." + \
               re.sub(r'[A-Z]',
                      self._add_underscore_before_uppercase,
                      routine_name)[1:]
        absolute_path = "pipert." + path[3:] + "." + routine_name
        path = absolute_path.split('.')
        module = ".".join(path[:-1])
        try:
            m = __import__(module)
            for comp in path[1:]:
                m = getattr(m, comp)
            return m
        except ModuleNotFoundError:
            return None

    def _does_component_exist(self, component_name):
        return component_name in self.components

    def set_up_components(self):
        self.create_component("Stream")
        self.create_component("Display")
        self.create_queue_to_component("Stream", "video")
        self.create_queue_to_component("Display", "messages")
        # self.add_routine_to_component(component_name="Stream",
        #                               routine_name="ListenToStream",
        #                               stream_address="/home/internet/Desktop/video.mp4",
        #                               out_queue="video",
        #                               fps=30,
        #                               name="capture_frame")
        # self.add_routine_to_component(component_name="Stream",
        #                               routine_name="MessageToRedis",
        #                               redis_send_key="camera:0",
        #                               url="redis://127.0.0.1:6379",
        #                               message_queue="video",
        #                               max_stream_length=10,
        #                               name="upload_redis")
        self.add_routine_to_component(component_name="Display",
                                      routine_name="MessageFromRedis",
                                      redis_read_key="camera:0",
                                      url="redis://127.0.0.1:6379",
                                      message_queue="messages",
                                      name="get_frames")
        self.add_routine_to_component(component_name="Display",
                                      routine_name="DisplayCv2",
                                      frame_queue="messages",
                                      name="draw_frames")


PipelineManager()