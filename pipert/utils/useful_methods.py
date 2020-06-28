from typing import Union
import yaml
from yaml.parser import ParserError
from yaml.scanner import ScannerError


def open_config_file(config_path) -> Union[str, dict]:
    try:
        with open(config_path) as config_file:
            return yaml.load(config_file, Loader=yaml.FullLoader)
    except FileNotFoundError as error:
        error_msg = error.args[1] + "' {}'".format(config_path)
    except IsADirectoryError as error:
        error_msg = "'{}' is a directory not a file".format(config_path)
    except (ScannerError, ParserError):
        error_msg = "Expecting yaml file, can't parse the file '{}'".format(config_path)
    return error_msg
