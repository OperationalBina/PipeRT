import importlib
import re
from typing import Optional


class ClassFactory:
    """Class that generates the class object of files from the given folder path"""
    def __init__(self, classes_folder_path):
        self.classes_folder_path = classes_folder_path

    def get_class(self, class_name) -> Optional['class_object']:
        """

        :param class_name: The name of the class
        :return: The class object from the given name or None if the name doesn't exist
        """
        path = self.classes_folder_path + "/" + \
            re.sub(r'[A-Z]',
                   _add_underscore_before_uppercase,
                   class_name)[1:] + ".py"
        return _get_class_object_by_path(path, class_name)


def _add_underscore_before_uppercase(match):
    return '_' + match.group(0).lower()


def _get_class_object_by_path(path, class_name):
    spec = importlib.util.spec_from_file_location(class_name, path)
    class_object = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(class_object)
    try:
        return getattr(class_object, class_name)
    except AttributeError:
        return None
