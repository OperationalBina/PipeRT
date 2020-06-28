import argparse
import sys
import zerorpc
from pipert.core.class_factory import ClassFactory
from pipert.core.component import BaseComponent
from pipert.utils.useful_methods import open_config_file

COMPONENTS_FOLDER_PATH = "pipert/contrib/components"


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-cp', '--config_path', help='Configuration file path', type=str,
                        default='pipert/core/config.yaml')
    parser.add_argument('-p', '--port', help='ZeroRPC port', type=str, default=None)
    opts, unknown = parser.parse_known_args()

    if opts.port is None:
        sys.exit("Must get port for the zeroRPC server in the script parameters")

    component_config = open_config_file(opts.config_path)

    if isinstance(component_config, str):
        sys.exit(component_config)
    component_factory = ClassFactory(COMPONENTS_FOLDER_PATH)

    _, component_params = list(component_config.items())[0]

    # Checks if special component is needed or base component
    if "component_type_name" in component_params:
        component_class = component_factory.get_class(component_params["component_type_name"])
    else:
        component_class = BaseComponent

    zpc = zerorpc.Server(component_class(component_config))
    zpc.bind(f"tcp://0.0.0.0:{opts.port}")
    zpc.run()
