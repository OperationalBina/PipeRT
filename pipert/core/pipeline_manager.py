import zerorpc
import re
from pipert.core.component import BaseComponent
from pipert.core.errors import QueueDoesNotExist
from pipert.core.routine import Routine
from os import listdir
from os.path import isfile, join
from jsonschema import validate, ValidationError
import functools


# import gc

def component_name_existence_error(need_to_be_exist):
    def decorator(func):
        @functools.wraps(func)
        def function_wrapper(self, *args, **kwargs):
            if not (self._does_component_exist(
                    kwargs['component_name']) == need_to_be_exist):
                error_word = "doesn't" if need_to_be_exist else 'already'
                return self._create_response(
                    False,
                    f"Component named {kwargs['component_name']} {error_word} exist"
                )
            return func(self, *args, **kwargs)

        return function_wrapper

    return decorator


class PipelineManager:

    def __init__(self, endpoint="tcp://0.0.0.0:4001", open_zerorpc=True):
        """
        Args:
            endpoint: the endpoint the PipelineManager's
             zerorpc server will listen in.
        """
        super().__init__()
        self.components = {}
        self.endpoint_port_counter = 4002
        self.ROUTINES_FOLDER_PATH = "../contrib/routines"
        self.COMPONENTS_FOLDER_PATH = "../contrib/components"
        if open_zerorpc:
            self.zrpc = zerorpc.Server(self)
            self.zrpc.bind(endpoint)
            self.zrpc.run()

    @component_name_existence_error(need_to_be_exist=False)
    def create_component(self, component_name):
        self.components[component_name] = \
            BaseComponent(name=component_name,
                          endpoint="tcp://0.0.0.0:{0:0=4d}"
                          .format(self.endpoint_port_counter))
        self.endpoint_port_counter += 1
        return self._create_response(
            True,
            f"Component {component_name} has been created"
        )

    @component_name_existence_error(need_to_be_exist=False)
    def create_premade_component(self, component_name, component_type_name):
        component_class = \
            self._get_component_class_object_by_type_name(component_type_name)
        if component_class is None:
            return self._create_response(
                False,
                f"The component type {component_type_name} doesn't exist"
            )
        self.components[component_name] = \
            component_class(name=component_name)
        return self._create_response(
            True,
            f"Component {component_name} has been created"
        )

    @component_name_existence_error(need_to_be_exist=True)
    def remove_component(self, component_name):
        if self._does_component_running(self.components[component_name]):
            self.components[component_name].stop_run()
        del self.components[component_name]
        return self._create_response(
            True,
            f"Component {component_name} has been removed"
        )

    @component_name_existence_error(need_to_be_exist=True)
    def add_routine_to_component(self, component_name,
                                 routine_type_name, **routine_parameters_kwargs):
        if self._does_component_running(self.components[component_name]):
            return self._create_response(
                False,
                "You can't add a routine while your component is running"
            )

        if "name" not in routine_parameters_kwargs:
            return self._create_response(
                False,
                f"Routine must have a name"
            )

        if self.components[component_name] \
                .does_routine_name_exist(routine_parameters_kwargs["name"]):
            return self._create_response(
                False,
                f"Routine with the name {routine_parameters_kwargs['name']}"
                f" already exist in this component"
            )

        routine_class_object = self._get_routine_class_object_by_type_name(routine_type_name)

        if routine_class_object is None:
            return self._create_response(
                False,
                f"The routine type '{routine_type_name}' doesn't exist"
            )

        try:
            # replace all queue names with the queue objects of the component before creating routine
            for key, value in routine_parameters_kwargs.items():
                if 'queue' in key.lower():
                    routine_parameters_kwargs[key] = self.components[component_name] \
                        .get_queue(queue_name=value)

            routine_parameters_kwargs["component_name"] = component_name

            self.components[component_name] \
                .register_routine(routine_class_object(**routine_parameters_kwargs)
                                  .as_thread())
            return self._create_response(
                True,
                f"The routine {routine_parameters_kwargs['name']} has been added"
            )
        except QueueDoesNotExist as e:
            return self._create_response(
                False,
                e.message()
            )

    @component_name_existence_error(need_to_be_exist=True)
    def remove_routine_from_component(self, component_name, routine_name):
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

    @component_name_existence_error(need_to_be_exist=True)
    def create_queue_to_component(self, component_name,
                                  queue_name, queue_size=1):
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

    @component_name_existence_error(need_to_be_exist=True)
    def remove_queue_from_component(self, component_name, queue_name):
        if not self.components[component_name].does_queue_exist(queue_name):
            return self._create_response(
                False,
                f"Queue named {queue_name} doesn't exist"
            )

        if self.components[component_name]. \
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

    @component_name_existence_error(need_to_be_exist=True)
    def run_component(self, component_name):
        if self._does_component_running(self.components[component_name]):
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

    @component_name_existence_error(need_to_be_exist=True)
    def stop_component(self, component_name):
        if not self._does_component_running(self.components[component_name]):
            return self._create_response(
                False,
                f"The component {component_name} is not running running"
            )
        else:
            if self.components[component_name].stop_run() == 0:
                return self._create_response(
                    True,
                    f"The component {component_name} has been stopped"
                )
            else:
                return self._create_response(
                    False,
                    f"An error has occurred, can't "
                    f"stop the component {component_name}"
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
                self._get_routine_class_object_by_type_name(routine_name) \
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

    def get_routine_parameters(self, routine_type_name):
        routine_class_object = self._get_routine_class_object_by_type_name(routine_type_name)
        if routine_class_object is not None:
            return routine_class_object.get_constructor_parameters()
        else:
            return self._create_response(
                False,
                f"Routine named {routine_type_name} doesn't exist"
            )

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
        components_validator = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "queues": {"type": "array", "items": {"type": "string"}},
                    "routines": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "routine_type_name": {"type": "string"}
                            },
                            "required": ["routine_type_name"]

                        }
                    }
                },
                "required": ["name", "queues", "routines"]
            }
        }

        try:
            validate(instance=components, schema=components_validator)
        except ValidationError as error:
            return self._create_response(
                False,
                error.message
            )

        # Delete all of the current components
        self.components = {}
        # gc.collect()
        for component in components:
            if "component_type_name" in component:
                self.create_premade_component(
                    component_name=component["name"],
                    component_type_name=component["component_type_name"])
            else:
                self.create_component(component_name=component["name"])
            for queue in component["queues"]:
                self.create_queue_to_component(
                    component_name=component["name"],
                    queue_name=queue)
            for routine in component["routines"]:
                routine_type_name = routine.pop("routine_type_name", "")
                self.add_routine_to_component(
                    component_name=component["name"],
                    routine_type_name=routine_type_name, **routine)

        return self._create_response(
            True,
            f"All of the components have been created"
        )

    def _get_routine_class_object_by_type_name(self, routine_name: str) -> Routine:
        path = self.ROUTINES_FOLDER_PATH.replace('/', '.') + "." + \
            re.sub(r'[A-Z]',
                   self._add_underscore_before_uppercase,
                   routine_name)[1:]
        absolute_path = "pipert." + path[3:] + "." + routine_name
        return self._get_class_object_by_path(absolute_path)

    def _get_component_class_object_by_type_name(self, component_type_name):
        path = self.COMPONENTS_FOLDER_PATH.replace('/', '.') + "." + \
            re.sub(r'[A-Z]',
                   self._add_underscore_before_uppercase,
                   component_type_name)[1:]
        absolute_path = "pipert." + path[3:] + "." + component_type_name
        return self._get_class_object_by_path(absolute_path)

    def _get_class_object_by_path(self, absolute_path):
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

    def get_pipeline_creation(self):
        pipeline = []
        for component_name in self.components.keys():
            pipeline.append(self._get_component_creation(component_name))

        return pipeline

    def _get_component_creation(self, component_name):
        component_dict = {"name": component_name,
                          "queues":
                              list(self.components[component_name].
                                   queues.keys()),
                          "routines": []
                          }
        if type(self.components[component_name]).__name__ != BaseComponent.__name__:
            component_dict["component_type_name"] = type(self.components[component_name]).__name__
        for current_routine_object in self.components[component_name]._routines:
            component_dict["routines"]. \
                append(self._get_routine_creation(component_name,
                                                  current_routine_object))
        return component_dict

    def _get_routine_creation(self, component_name, routine):
        routine_dict = routine.get_creation_dictionary()
        routine_dict["routine_type_name"] = routine.__class__.__name__
        for routine_param_name in routine_dict.keys():
            if "queue" in routine_param_name:
                for queue_name in self.components[component_name].queues.keys():
                    if getattr(routine, routine_param_name) is \
                            self.components[component_name].queues[queue_name]:
                        routine_dict[routine_param_name] = queue_name

        return routine_dict
