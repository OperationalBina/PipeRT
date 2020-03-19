# import os
import sys
from flask import Flask, jsonify, request
from pipert.core.pipeline_manager import PipelineManager

# use_user_interface = os.environ.get("UI").lower() == 'true'
use_user_interface = sys.argv[1].lower() == 'true'
pipeline_manager = PipelineManager(open_zerorpc=not use_user_interface)

if use_user_interface:
    app = Flask(__name__)

    @app.route("/routines")
    def get_routines():
        return jsonify(pipeline_manager.get_all_routines())

    @app.route("/routineParams/<routine_name>")
    def get_routine_params(routine_name):
        return pipeline_manager.get_routine_params(routine_name)

    @app.route("/component")
    def get_component():
        return "TBD"

    @app.route("/pipeline", methods=['POST'])
    def create_pipeline():
        return pipeline_manager.setup_components(request.json)

    @app.route("/kill", methods=['PUT'])
    def stop_components():
        return pipeline_manager.stop_all_components()

    @app.route("/run", methods=['PUT'])
    def start_components():
        return pipeline_manager.run_all_components()

    app.run(port=5005)
