import zerorpc
import re
import importlib.util
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

    def __init__(self):
        """
        Args:
        """
        super().__init__()
        self.components = {}
        self.ROUTINES_FOLDER_PATH = "pipert/contrib/routines"
        self.COMPONENTS_FOLDER_PATH = "pipert/contrib/components"

    @component_name_existence_error(need_to_be_exist=False)
    def create_component(self, component_name, use_shared_memory=False):
        self.components[component_name] = \
            BaseComponent(name=component_name, use_memory=use_shared_memory)
        return self._create_response(
            True,
            f"Component {component_name} has been created"
        )

    @component_name_existence_error(need_to_be_exist=False)
    def create_premade_component(self, component_name, component_type_name, use_shared_memory=False):
        component_class = \
            self._get_component_class_object_by_type_name(component_type_name)
        if component_class is None:
            return self._create_response(
                False,
                f"The component type {component_type_name} doesn't exist"
            )
        self.components[component_name] = \
            component_class(name=component_name, use_memory=use_shared_memory)
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

        routine_class_object = self._get_routine_class_object_by_type_name(routine_type_name)

        if routine_class_object is None:
            return self._create_response(
                False,
                f"The routine type '{routine_type_name}' doesn't exist"
            )

        if "name" not in routine_parameters_kwargs:
            return self._create_response(
                False,
                "Routine must have a name"
            )

        if self.components[component_name] \
                .does_routine_name_exist(routine_parameters_kwargs["name"]):
            return self._create_response(
                False,
                f"Routine with the name {routine_parameters_kwargs['name']}"
                f" already exist in this component"
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
        except TypeError as error:
            return self._create_response(
                False,
                str(error)
            )

    @component_name_existence_error(need_to_be_exist=True)
    def remove_routine_from_component(self, component_name, routine_name):
        if self._does_component_running(self.components[component_name]):
            return self._create_response(
                False,
                "You can't remove a routine while your component is running"
            )
        if self.components[component_name].remove_routine(routine_name):
            return self._create_response(
                True,
                f"Removed routine with the name {routine_name} from the component"
            )
        else:
            return self._create_response(
                False,
                f"There is no routine with the name {routine_name}"
                f" inside the component {component_name}"
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
                "Can't remove a queue that is being used by routines"
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
            "All of the components are running"
        )

    def stop_all_components(self):
        for component in self.components.values():
            if self._does_component_running(component):
                component.stop_run()
        return self._create_response(
            True,
            "All of the components have been stopped"
        )

    def get_all_routine_types(self):
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

    @component_name_existence_error(need_to_be_exist=True)
    def change_component_execution_mode(self, component_name, execution_mode):
        try:
            getattr(self.components[component_name], "as_" + execution_mode.lower())()
            return self._create_response(
                True,
                f"The component {component_name} changed execution mode to {execution_mode}"
            )
        except AttributeError:
            return self._create_response(
                False,
                f"Cannot find execution mode '{execution_mode}'"
            )

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

          "components": {
            "component_name": {
              "queues": [str],
              "routines": {
                "routine_name": {
                  "routine_type_name": str,
                  ...(routine params)
                },
                ...(more routines)
              }
            }
            ...(more components)
          }
        """
        component_validator = {
            "type": "object",
            "properties": {
                "queues": {"type": "array", "items": {"type": "string"}},
                "routines": {"type": "object"}
            },
            "required": ["queues", "routines"]
        }

        # Delete all of the current components
        self.components = {}
        responses = []
        # gc.collect()

        if (type(components) is not dict) and ("components" not in components):
            return self._create_response(
                False,
                "All of the components must be inside a dictionary with the key 'components'"
            )

        for component_name, component_parameters in components["components"].items():
            try:
                validate(instance=component_parameters, schema=component_validator)
                to_use_shared_memory = component_parameters.get("shared_memory", False)
                if "component_type_name" in component_parameters:
                    responses.append(self.create_premade_component(
                        component_name=component_name,
                        component_type_name=component_parameters["component_type_name"],
                        use_shared_memory=to_use_shared_memory))
                else:
                    responses.append(self.create_component(component_name=component_name,
                                                           use_shared_memory=to_use_shared_memory))
                if "execution_mode" in component_parameters:
                    responses.append(self.change_component_execution_mode(
                        component_name=component_name,
                        execution_mode=component_parameters["execution_mode"]))
                for queue in component_parameters["queues"]:
                    responses.append(self.create_queue_to_component(
                        component_name=component_name,
                        queue_name=queue))
                for routine_name, routine_parameters in component_parameters["routines"].items():
                    routine_type_name = routine_parameters.pop("routine_type_name", "")
                    routine_parameters["name"] = routine_name
                    responses.append(self.add_routine_to_component(
                        component_name=component_name,
                        routine_type_name=routine_type_name, **routine_parameters))
            except ValidationError as error:
                responses.append(self._create_response(
                    False,
                    error.message
                ))

        if all(response["Succeeded"] for response in responses):
            return self._create_response(
                True,
                "All of the components have been created"
            )
        else:
            return list(filter(lambda response: not response["Succeeded"], responses))

    def _get_routine_class_object_by_type_name(self, routine_name: str) -> Routine:
        path = self.ROUTINES_FOLDER_PATH + "/" + \
            re.sub(r'[A-Z]',
                   self._add_underscore_before_uppercase,
                   routine_name)[1:] + ".py"
        return self._get_class_object_by_path(path, routine_name)

    def _get_component_class_object_by_type_name(self, component_type_name):
        path = self.COMPONENTS_FOLDER_PATH + "/" + \
            re.sub(r'[A-Z]',
                   self._add_underscore_before_uppercase,
                   component_type_name)[1:] + ".py"
        return self._get_class_object_by_path(path, component_type_name)

    def _get_class_object_by_path(self, path, class_name):
        spec = importlib.util.spec_from_file_location(class_name, path)
        class_object = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(class_object)
        try:
            return getattr(class_object, class_name)
        except AttributeError:
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
        components = {}
        for component_name in self.components.keys():
            components[component_name] = self._get_component_creation(component_name)

        return {"components": components}

    def _get_component_creation(self, component_name):

        component_dict = {
            "queues":
                list(self.components[component_name].
                     get_all_queue_names()),
            "routines": {}
        }

        if type(self.components[component_name]).__name__ != BaseComponent.__name__:
            component_dict["component_type_name"] = type(self.components[component_name]).__name__
        for current_routine_object in self.components[component_name]._routines.values():
            routine_creation_object = self._get_routine_creation(
                component_name, current_routine_object)
            routine_name = routine_creation_object.pop("name")
            component_dict["routines"][routine_name] = \
                routine_creation_object

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
