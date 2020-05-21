import os
from pprint import pprint
import yaml
import zerorpc
from yaml.parser import ParserError
from yaml.scanner import ScannerError
import sys
from subprocess import call

EXIT_METHOD_TEXT = 'exit'
SHOW_METHODS_METHOD_TEXT = 'show_methods'


def load_config_file():
    """
    Loading a configuration file of the pipeline to be configured
    """
    file_path = input("Enter the config file path: ")
    try:
        with open(file_path) as config_file:
            components = yaml.load(config_file, Loader=yaml.FullLoader)
        print(connection.execute_method("setup_components", {"components": components}))
    except FileNotFoundError as error:
        print(error.args[1], "'{}'".format(file_path))
    except IsADirectoryError as error:
        print("'{}' is a directory not a file".format(file_path))
    except (ScannerError, ParserError):
        print("Expecting yaml file, can't parse the file '{}'".format(file_path))


def export_config_file():
    """
        Exporting a configuration file of the current pipeline state
    """
    with open("config.yaml", 'w') as config_file:
        yaml.dump(connection.
                  execute_method("get_pipeline_creation", {}),
                  config_file)
        print("Exported successfully to config.yaml")


def execute_method(method_name, connection):
    """
    Executing a method inside the pipeline manager
    Args:
        method_name: the method name
        connection: the connection to the pipeline manager
                    object for executing methods
    """
    parameters_values = {}
    parameters = connection.get_method_parameters(method_name)
    for parameter_name in parameters:
        if parameter_name == 'self':
            continue
        elif "kwargs" in parameter_name:
            user_input = input("Enter key - value for " + parameter_name + ". To stop enter stop: ")
            while user_input != "stop":
                try:
                    key, value = user_input.split("-")
                    parameters_values[key.strip()] = value.strip()
                except ValueError:
                    print("Can't parse", user_input, "to key - value format")
                user_input = input("Enter key - value for " + parameter_name + ". To stop enter stop: ")
        else:
            parameters_values[parameter_name] = input("Enter value for " + parameter_name + ": ")
    return connection.execute_method(method_name, parameters_values)


connection = zerorpc.Client()
endpoint = input("Enter a zerorpc endpoint to connect to: ")
connection.connect(endpoint)
try:
    print("Connecting to", endpoint + "...")
    if connection.check_connection():
        print("Connected successfully")
except zerorpc.LostRemote:
    sys.exit("Unable to connect to " + endpoint)

own_methods = {
    EXIT_METHOD_TEXT: lambda: print("exiting"),
    SHOW_METHODS_METHOD_TEXT: None,
    "load_config_file": load_config_file,
    "export_config_file": export_config_file,
    "clear": lambda: call('clear' if os.name == 'posix' else 'cls')
}
methods = connection.get_methods()
own_methods[SHOW_METHODS_METHOD_TEXT] = lambda: pprint(methods + list(own_methods.keys()), width=400)
user_input = input("Enter method to execute: ")

while user_input != EXIT_METHOD_TEXT:
    if user_input in own_methods:
        own_methods[user_input]()
    elif user_input in methods:
        pprint(execute_method(user_input, connection), indent=2)
    else:
        print(f"Cant find method '{user_input}', enter {SHOW_METHODS_METHOD_TEXT} to view all methods")
    user_input = input("Enter method to execute : ")
