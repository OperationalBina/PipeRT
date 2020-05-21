import os
from flask import Flask, jsonify, request, Response
from pipert.core.pipeline_manager import PipelineManager
import inspect
import zerorpc


class CliConnection(object):

    def __init__(self, pipeline_manager):
        self.pipeline_manager = pipeline_manager

    def execute_method(self, method_name, parameters_values):
        return getattr(self.pipeline_manager, method_name)(**parameters_values)

    def get_methods(self):
        methods = inspect.getmembers(self.pipeline_manager, predicate=inspect.ismethod)
        methods = [method[0] for method in methods if (not method[0].startswith('_'))]
        return methods

    # need to be tested
    def get_method_parameters(self, method_name):
        return list(inspect.signature(getattr(self.pipeline_manager, method_name)).parameters.keys())

    def check_connection(self):
        return True


pipeline_manager = PipelineManager()

if not os.environ.get("UI", "").lower() == 'true':
    cli_server = zerorpc.Server(CliConnection(pipeline_manager))
    cli_server.bind("tcp://0.0.0.0:" + os.environ.get("CLI_ENDPOINT", "4001"))
    cli_server.run()
else:
    app = Flask(__name__)

    def return_response(res_object):
        return Response(res_object["Message"], 200 if res_object["Succeeded"] else 400)

    @app.route("/routines", methods=['GET'])
    def get_routines():
        return jsonify(pipeline_manager.get_all_routine_types())

    @app.route("/routineParams/<routine_name>", methods=['GET'])
    def get_routine_params(routine_name):
        return jsonify(pipeline_manager.get_routine_parameters(routine_name))

    @app.route("/component", methods=['GET'])
    def get_component():
        return "TBD"

    @app.route("/pipeline", methods=['POST', 'GET'])
    def create_pipeline():
        if request.method == 'GET':
            return jsonify(
                [
                    {
                        "name": "name of component",
                        "queues": "[array of names of queues]",
                        "routines":
                            [
                                {
                                    "routine_type_name": "name of the routine type",
                                    "routine_param_name": "the values of the routine parameters that can be fount in"
                                                          "/routineParams/routineTypeName"
                                }
                            ]
                    }
                ]
            )
        elif request.method == 'POST':
            return return_response(pipeline_manager.setup_components(request.json))

    @app.route("/kill", methods=['PUT'])
    def stop_components():
        return return_response(pipeline_manager.stop_all_components())

    @app.route("/run", methods=['PUT'])
    def start_components():
        return_response(pipeline_manager.run_all_components())

    app.run(port=os.environ.get("UI_PORT", 5005), host='0.0.0.0')
