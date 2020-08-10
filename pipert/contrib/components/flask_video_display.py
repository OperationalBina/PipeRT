from threading import Thread
from flask import Flask, Response, request
from pipert.core.component import BaseComponent
from queue import Empty
import cv2
import time
import requests


class FlaskVideoDisplay(BaseComponent):

    def __init__(self, component_config):
        component_name, _ = list(component_config.items())[0]
        self.display_queue_name = "flask_display"
        component_config[component_name]["queues"].append(self.display_queue_name)
        try:
            self.port = component_config[component_name]["component_args"]["port"]
        except KeyError:
            self.port = 5000

        app = Flask(__name__)

        self.flask_app = app

        @app.route('/video')
        def video_feed():
            return Response(self._gen(),
                            mimetype='multipart/x-mixed-replace; '
                                     'boundary=frame')

        def shutdown_server():
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()

        @app.route('/shutdown')
        def shutdown():
            # app.do_teardown_appcontext()
            shutdown_server()
            return 'Server shutting down...'

        super().__init__(component_config)

    def _start(self):
        super()._start()
        self.server = Thread(target=self.flask_app.run, kwargs={"host": '0.0.0.0', "port": self.port})
        self.server.start()

    def stop_run(self):
        component_response = super().stop_run()
        try:
            self.server.join()
            return component_response
        except RuntimeError:
            return 1

    def _gen(self):
        q = self.get_queue("flask_display")
        while not self.stop_event.is_set():
            try:
                msg = q.get(block=False)
                image = msg.get_payload()
                if image is not None:
                    ret, frame = cv2.imencode('.jpg', image)
                    frame = frame.tobytes()
                    yield (b'--frame\r\n'
                           b'Pragma-directive: no-cache\r\n'
                           b'Cache-directive: no-cache\r\n'
                           b'Cache-control: no-cache\r\n'
                           b'Pragma: no-cache\r\n'
                           b'Expires: 0\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            except Empty:
                time.sleep(0)

    def _teardown_callback(self, *args, **kwargs):
        # self.server.terminate()
        _ = requests.get("http://127.0.0.1:5000/shutdown")
        # self.server.terminate()
        # print("kill!!!")
        # self.server.kill()

    def get_all_queue_names(self):
        queue_names = list(self.queues.keys())
        queue_names.remove(self.display_queue_name)
        return queue_names
