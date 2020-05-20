import importlib
import re
from typing import Optional


class ClassFactory:

    def __init__(self, classes_folder_path):
        self.classes_folder_path = "pipert/contrib/routines"
        self.classes_folder_path = classes_folder_path

    def get_class(self, class_name) -> Optional['class_object']:
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
