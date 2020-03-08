import zerorpc
from pipert.core.component import BaseComponent
from os import listdir
from os.path import isfile, join

class PipelineManager:

    def __init__(self, endpoint="tcp://0.0.0.0:4001"):
        """
        Args:
            endpoint: the endpoint the PipelineManager's zerorpc server will listen
            in.
        """
        super().__init__()
        self.components = {}
        self.endpoint_port_counter = 2
        self.zrpc = zerorpc.Server(self)
        self.zrpc.bind(endpoint)
        self.ROUTINES_FOLDER_PATH = "../contrib/routines"

    def create_component(self, component_name):
        if component_name in self.components:
            print("Component name '" + component_name + "' already exist")
            return False
        else:
            self.components[component_name] = \
                BaseComponent(name=component_name,
                              endpoint="{0:0=4d}"
                              .format(self.endpoint_port_counter))
            print("Component " + component_name + " has been created")
            return True

    def remove_component(self, component_name):
        pass

    def add_routine_to_component(self, component_name, routine_name, **routine_kwargs):
        pass

    def remove_routine_from_component(self, component_name, routine_name):
        pass

    def create_queue_to_component(self, component_name, queue_name):
        pass

    def remove_queue_from_component(self, component_name, queue_name):
        pass

    def run_component(self, component_name):
        pass

    def stop_component(self, component_name):
        pass

    def run_all_components(self):
        pass

    def stop_all_components(self):
        pass

    def get_all_routines(self):
        routine_file_names = [f for f in
                              listdir(self.ROUTINES_FOLDER_PATH)
                              if isfile(join(self.ROUTINES_FOLDER_PATH, f))]

        routine_file_names = [file_name[:-3] for file_name in routine_file_names]
        print(routine_file_names)
        return routine_file_names

    def get_routine_information(self):
        pass

    def _get_routine_object_by_name(self, routine_name):
        path = self.ROUTINES_FOLDER_PATH.replace('/', '.') + "." + routine_name
        absolute_path = "pipert." + path[3:] + "." + routine_name
        print(absolute_path)
        path = absolute_path.split('.')
        module = ".".join(path[:-1])
        m = __import__(module)
        for comp in path[1:]:
            m = getattr(m, comp)
        return m


pipeKing = PipelineManager()

cls = pipeKing._get_routine_object_by_name("TestRoutine")

test = cls(name="Guy", a="asd")
test.check()