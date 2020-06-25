import subprocess
from typing import Optional
import yaml
import zerorpc
import re
from pipert.core.class_factory import ClassFactory
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
        self.ports_counter = 20000

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
                " already exist in this component"
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
        if self.components[component_name].\
                create_queue(queue_name=queue_name,
                             queue_size=queue_size):
            return self._create_response(
                True,
                f"The Queue {queue_name} has been created"
            )
        else:
            return self._create_response(
                False,
                f"Queue named {queue_name} already exist"
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
            self.components[component_name].run_comp()
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
                    "An error has occurred, can't "
                    f"stop the component {component_name}"
                )

    def run_all_components(self):
        for component in self.components.values():
            if not self._does_component_running(component):
                component.run_comp()
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

        COMPONENT_FACTORY_PATH = "pipert/utils/scripts/component_factory.py"

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
                current_component_dict = {component_name: component_parameters}
                component_file_path = "pipert/utils/config_files/" + component_name + ".yaml"
                with open(component_file_path, 'w') as file:
                    yaml.dump(current_component_dict, file)

                component_port = str(self.get_random_available_port())
                cmd = "python " + COMPONENT_FACTORY_PATH + " -cp " + component_file_path + " -p " + component_port
                subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
                self.components[component_name] = zerorpc.Client()
                self.components[component_name].connect("tcp://localhost:" + component_port)
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

    def _get_routine_class_object_by_type_name(self, routine_name: str) -> Optional[Routine]:
        routine_factory = ClassFactory(self.ROUTINES_FOLDER_PATH)
        return routine_factory.get_class(routine_name)

    def _does_component_exist(self, component_name):
        return component_name in self.components

    @staticmethod
    def _does_component_running(component):
        return component.does_component_running()

    @staticmethod
    def _create_response(succeeded, message):
        return {
            "Succeeded": succeeded,
            "Message": message
        }

    def get_pipeline_creation(self):
        components = {}
        for component_name in self.components.keys():
            components.update(self.components[component_name].get_component_configuration())
        return {"components": components}

    def get_random_available_port(self):
        self.ports_counter += 1
        return self.ports_counter
