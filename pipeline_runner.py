from parser import ParserError
from pprint import pprint

from yaml.scanner import ScannerError

from pipert.core.pipeline_manager import PipelineManager
import yaml


def load_config_file(file_path):
    """
    Loading a configuration file of the pipeline to be configured
    """
    try:
        with open(file_path) as config_file:
            components = yaml.load(config_file, Loader=yaml.FullLoader)
        return components
    except FileNotFoundError as error:
        print(error.args[1], "'{}'".format(file_path))
    except IsADirectoryError as error:
        print("'{}' is a directory not a file".format(file_path))
    except (ScannerError, ParserError):
        print("Expecting yaml file, can't parse the file '{}'".format(file_path))


pm = PipelineManager()
pipeline_cfg = load_config_file("pipert/utils/config_files/single_yolo_conf.yaml")
if pipeline_cfg:
    pprint(pipeline_cfg, indent=2)
    pm.setup_components(pipeline_cfg)
    input("Press enter to show the pipeline config")
    print("Current pipeline configuration: \n")
    print(pm.get_pipeline_creation())
    input("Press enter to start running the pipeline")
    pm.run_all_components()
    input("Press enter to shut down the pipeline")
    pm.stop_all_components()

