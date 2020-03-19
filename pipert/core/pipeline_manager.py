# import os
import sys
from flask import Flask, jsonify, request
import zerorpc
import re
from pipert.core.component import BaseComponent
from pipert.core.errors import QueueDoesNotExist
from pipert.core.routine import Routine
from os import listdir
from os.path import isfile, join


class PipelineManager:

    def __init__(self, endpoint="tcp://0.0.0.0:4001", open_zerorpc=True):
        """
        Args:
            endpoint: the endpoint the PipelineManager's
             zerorpc server will listen in.
        """
        super().__init__()
        self.components = {}
        self.zrpc = zerorpc.Server(self)
        self.zrpc.bind(endpoint)
        self.ROUTINES_FOLDER_PATH = "../contrib/routines"
        self.COMPONENTS_FOLDER_PATH = "../contrib/components"
        if open_zerorpc:
            self.zrpc.run()

    def create_component(self, component_name):
        if self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} already exist"
            )
        else:
            self.components[component_name] = \
                BaseComponent(name=component_name)
            return self._create_response(
                True,
                f"Component {component_name} has been created"
            )

    def create_premade_component(self, component_name, component_type_name):
        if self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} already exist"
            )
        else:
            component_object = \
                self._get_component_object_by_name(component_type_name)
            if component_name is None:
                return self._create_response(
                    False,
                    f"The component type {component_type_name} doesn't exist"
                )
            self.components[component_name] = \
                component_object(name=component_name)
            return self._create_response(
                True,
                f"Component {component_name} has been created"
            )

    def remove_component(self, component_name):
        if not self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} doesn't exist"
            )
        else:
            if self._does_component_running(self.components[component_name]):
                self.components[component_name].stop_run()
            del self.components[component_name]
            return self._create_response(
                True,
                f"Component {component_name} has been removed"
            )

    def add_routine_to_component(self, component_name,
                                 routine_type_name, **routine_kwargs):
        if not self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} doesn't exist"
            )
        if self._does_component_running(self.components[component_name]):
            return self._create_response(
                False,
                "You can't add a routine while your component is running"
            )

        if self.components[component_name]\
                .does_routine_name_exist(routine_kwargs["name"]):
            return self._create_response(
                False,
                f"Routine with the name {routine_kwargs['name']}"
                f" already exist in this component"
            )

        routine_object = self._get_routine_object_by_name(routine_type_name)

        if routine_object is None:
            return self._create_response(
                False,
                f"The routine type '{routine_type_name}' doesn't exist"
            )

        try:
            # replace all queue names with the queue objects of the component
            for key, value in routine_kwargs.items():
                if 'queue' in key.lower():
                    routine_kwargs[key] = self.components[component_name]\
                        .get_queue(queue_name=value)

            self.components[component_name] \
                .register_routine(routine_object(**routine_kwargs)
                                  .as_thread())
            return self._create_response(
                True,
                f"The routine {routine_kwargs['name']} has been added"
            )
        except QueueDoesNotExist as e:
            return self._create_response(
                False,
                e.message()
            )
        return False

    # TODO - implement a check if queue in me in each routine
    def remove_routine_from_component(self, component_name, routine_name):
        if not self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} doesn't exist"
            )
        if self._does_component_running(self.components[component_name]):
            return self._create_response(
                False,
                "You can't remove a routine while your component is running"
            )
        self.components[component_name].remove_routine(routine_name)
        return self._create_response(
            True,
            f"Removed routines with the name {routine_name} from the component"
        )

    def create_queue_to_component(self, component_name,
                                  queue_name, queue_size=1):
        if not self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} doesn't exist"
            )
        if self.components[component_name].does_queue_exist(queue_name):
            return self._create_response(
                False,
                f"Queue named {queue_name} already exist"
            )

        self.components[component_name].create_queue(queue_name=queue_name,
                                                     queue_size=queue_size)
        return self._create_response(
            True,
            f"The Queue {queue_name} has been created"
        )

    def remove_queue_from_component(self, component_name, queue_name):
        if not self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} doesn't exist"
            )
        if not self.components[component_name].does_queue_exist(queue_name):
            return self._create_response(
                False,
                f"Queue named {queue_name} doesn't exist"
            )

        if self.components[component_name].\
                does_routines_use_queue(queue_name):
            return self._create_response(
                False,
                f"Can't remove a queue that is being used by routines"
            )

        self.components[component_name].delete_queue(queue_name=queue_name)
        return self._create_response(
            True,
            f"The Queue {queue_name} has been removed"
        )

    def run_component(self, component_name):
        if not self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} doesn't exist"
            )
        elif self._does_component_running(self.components[component_name]):
            return self._create_response(
                False,
                f"The component {component_name} already running"
            )
        else:
            self.components[component_name].run()
            return self._create_response(
                True,
                f"The component {component_name} is now running"
            )

    def stop_component(self, component_name):
        if not self._does_component_exist(component_name):
            return self._create_response(
                False,
                f"Component named {component_name} doesn't exist"
            )
        elif self._does_component_running(self.components[component_name]):
            return self._create_response(
                False,
                f"The component {component_name} is not running running"
            )
        else:
            self.components[component_name].stop_run()
            return self._create_response(
                True,
                f"The component {component_name} has been stopped"
            )

    def run_all_components(self):
        for component in self.components.values():
            if not self._does_component_running(component):
                component.run()
        return self._create_response(
            True,
            f"All of the components are running"
        )

    def stop_all_components(self):
        for component in self.components.values():
            if self._does_component_running(component):
                component.stop_run()
        return self._create_response(
            True,
            f"All of the components have been stopped"
        )

    def get_all_routines(self):
        routine_file_names = [f for f in
                              listdir(self.ROUTINES_FOLDER_PATH)
                              if isfile(join(self.ROUTINES_FOLDER_PATH, f))]

        routine_file_names = [file_name[:-3] for
                              file_name in routine_file_names]
        routine_file_names = \
            [file_name[0].upper() + re.sub(r'_\w',
                                           self._remove_string_with_underscore,
                                           file_name)[1:]
             for file_name in routine_file_names]

        routines = []
        for routine_name in routine_file_names:
            current_routine_type = \
                self._get_routine_object_by_name(routine_name)\
                    .routine_type.value
            routines.append({"name": routine_name,
                             "type": current_routine_type})
        return routines

    # helping method for changing the file name to class name
    @staticmethod
    def _remove_string_with_underscore(match):
        return match.group(0).upper()[1]

    # helping method for changing the class name to file name
    @staticmethod
    def _add_underscore_before_uppercase(match):
        return '_' + match.group(0).lower()

    def get_routine_params(self, routine_name):
        routine_object = self._get_routine_object_by_name(routine_name)
        params = routine_object.get_constructor_parameters()
        return params

    def setup_components(self, components):
        """
        vvv Expecting to get vvv
        [
            {
                name: str,
                queues: [str],
                routines:
                    [
                        {
                            routine_type_name: str,
                            ...(routine params)
                        },
                        ...
                    }
            },
            ...
        ]
        """
        for component in components:
            self.create_component(component["name"])
            for queue in component["queues"]:
                self.create_queue_to_component(component["name"], queue)
            for routine in component["routines"]:
                routine_name = routine.pop("routine_type_name", None)
                self.add_routine_to_component(component["name"],
                                              routine_name, **routine)

        return self._create_response(
            True,
            f"All of the components have been created"
        )

    def test_create_component(self):
        self.setup_components([
            {
                "name": "Stream",
                "queues": ["video"],
                "routines":
                [
                    {
                        "routine_type_name": "ListenToStream",
                        "stream_address":
                            "/home/internet/Desktop/video.mp4",
                        "out_queue": "video",
                        "fps": 30,
                        "name": "capture_frame"
                    },
                    {
                        "routine_type_name": "MessageToRedis",
                        "redis_send_key": "cam",
                        "message_queue": "video",
                        "max_stream_length": 10,
                        "name": "upload_redis"
                    }
                ]
            },
            {
                "name": "Display",
                "queues": ["messages"],
                "routines":
                [
                    {
                        "routine_type_name": "MessageFromRedis",
                        "redis_read_key": "cam",
                        "message_queue": "messages",
                        "name": "get_frames"
                    },
                    {
                        "routine_type_name": "DisplayCv2",
                        "frame_queue": "messages",
                        "name": "draw_frames"
                    }
                ]
            },
        ])

    def _get_routine_object_by_name(self, routine_name: str) -> Routine:
        path = self.ROUTINES_FOLDER_PATH.replace('/', '.') + "." + \
            re.sub(r'[A-Z]',
                   self._add_underscore_before_uppercase,
                   routine_name)[1:]
        absolute_path = "pipert." + path[3:] + "." + routine_name
        return self._get_object_by_path(absolute_path)

    def _get_component_object_by_name(self, component_type_name):
        path = self.COMPONENTS_FOLDER_PATH.replace('/', '.') + "." + \
            re.sub(r'[A-Z]',
                   self._add_underscore_before_uppercase,
                   component_type_name)[1:]
        absolute_path = "pipert." + path[3:] + "." + component_type_name
        return self._get_object_by_path(absolute_path)

    def _get_object_by_path(self, absolute_path):
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

    @staticmethod
    def _does_component_running(component):
        return not component.stop_event.is_set()

    @staticmethod
    def _create_response(succeeded, message):
        return {
            "Succeeded": succeeded,
            "Message": message
        }

    def set_up_components_cv2(self):
        self.create_component("Stream")
        self.create_component("Display")
        self.create_queue_to_component("Stream", "video")
        self.create_queue_to_component("Display", "messages")
        self.add_routine_to_component(
            component_name="Stream",
            routine_type_name="ListenToStream",
            stream_address="/home/internet/Desktop/video.mp4",
            out_queue="video",
            fps=30,
            name="capture_frame")
        # self.add_routine_to_component(component_name="Stream",
        #                               routine_type_name="MessageToRedis",
        #                               redis_send_key="camera:0",
        #                               message_queue="video",
        #                               max_stream_length=10,
        #                               name="upload_redis")
        self.add_routine_to_component(component_name="Display",
                                      routine_type_name="MessageFromRedis",
                                      redis_read_key="camera:0",
                                      message_queue="messages",
                                      name="get_frames")
        self.add_routine_to_component(component_name="Display",
                                      routine_type_name="DisplayCv2",
                                      frame_queue="messages",
                                      name="draw_frames")

    def set_up_components_flask(self):
        self.create_component("Stream")
        self.create_queue_to_component("Stream", "video")
        self.add_routine_to_component(
            component_name="Stream",
            routine_type_name="ListenToStream",
            stream_address="/home/internet/Desktop/video.mp4",
            out_queue="video",
            fps=30,
            name="capture_frame")
        self.add_routine_to_component(component_name="Stream",
                                      routine_type_name="MessageToRedis",
                                      redis_send_key="cam",
                                      message_queue="video",
                                      max_stream_length=10,
                                      name="upload_redis")

        self.create_component("FaceDet")
        self.create_queue_to_component("FaceDet", "frames")
        self.create_queue_to_component("FaceDet", "preds")

        self.add_routine_to_component(component_name="FaceDet",
                                      routine_type_name="MessageFromRedis",
                                      redis_read_key="cam",
                                      message_queue="frames",
                                      name="from_redis")

        self.add_routine_to_component(component_name="FaceDet",
                                      routine_type_name="FaceDetection",
                                      in_queue="frames",
                                      out_queue="preds",
                                      name="create_preds")

        self.add_routine_to_component(component_name="FaceDet",
                                      routine_type_name="MessageToRedis",
                                      redis_send_key="camera:1",
                                      message_queue="preds",
                                      max_stream_length=10,
                                      name="upload_redis")

        self.create_premade_component("FlaskDisplay", "FlaskVideoDisplay")
        self.create_queue_to_component("FlaskDisplay", "messages")

        self.add_routine_to_component(
            component_name="FlaskDisplay",
            routine_type_name="MetaAndFrameFromRedis",
            redis_read_image_key="cam",
            redis_read_meta_key="camera:1",
            image_meta_queue="messages",
            name="get_frames_and_pred")

        self.add_routine_to_component(component_name="FlaskDisplay",
                                      routine_type_name="VisLogic",
                                      in_queue="messages",
                                      out_queue="flask_display",
                                      name="create_image")


# use_user_interface = os.environ.get("UI").lower() == 'true'
use_user_interface = sys.argv[1].lower() == 'true'
pipeline_manager = PipelineManager(open_zerorpc=not use_user_interface)

if use_user_interface:
    app = Flask(__name__)

    @app.route("/routines")
    def get_routines():
        return jsonify(pipeline_manager.get_all_routines())

    @app.route("/routineParams/<routine_name>")
    def get_routine_params(routine_name):
        return pipeline_manager.get_routine_params(routine_name)

    @app.route("/component")
    def get_component():
        return "TBD"

    @app.route("/pipeline", methods=['POST'])
    def create_pipeline():
        return pipeline_manager.setup_components(request.json)

    @app.route("/kill", methods=['PUT'])
    def stop_components():
        return pipeline_manager.stop_all_components()

    @app.route("/run", methods=['PUT'])
    def start_components():
        return pipeline_manager.run_all_components()

    app.run(port=5005)
