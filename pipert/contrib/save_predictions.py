from queue import Queue
from urllib.parse import urlparse
from pipert.core.mini_logics import MessageFromRedis
from pipert.core import Routine, BaseComponent, QueueHandler
from pipert.contrib.database import DBHandler
from datetime import datetime as dt
import argparse
import logging
import yaml
import os


class OutputLogger(BaseComponent):
    def __init__(self, endpoint, in_key, db_conf, redis_url):
        super().__init__(endpoint, self.__class__.__name__, 8084)
        self.queue = Queue(maxsize=10)

        t_get = MessageFromRedis(in_key, redis_url, self.queue, name="get_preds_from_redis", component_name=self.name).as_thread()
        self.register_routine(t_get)

        t_save = PredsToDatabase(self.queue, db_conf, name="save_preds_to_db", component_name=self.name).as_thread()
        self.register_routine(t_save)

    def toggle(self):
        """Toggle saving to the database on or off. To be used with zpc.

        :return: None
        """
        self._routines[1].is_on = not self._routines[1].is_on
        self._routines[1].logger.info("Saving predictions toggled " + "ON" if self._routines[1].is_on else "OFF")


class PredsToDatabase(Routine):
    def __init__(self, in_queue, db_conf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = QueueHandler(in_queue)
        self.logger.addHandler(logging.StreamHandler())
        self.dbh = DBHandler(db_conf, logger=self.logger)
        self.is_on = True

    def main_logic(self, *args, **kwargs):
        msg = self.queue.non_blocking_get()

        # Only do something if msg isn't empty and saving is toggled on
        if self.is_on and msg:
            msg_id = msg.id.split("_")[-1]
            timestamp = dt.fromtimestamp(msg.history["VideoCapture"]["entry"])
            for predictions in msg.get_payload():
                # get the needed fields and convert to a format that is good to be inserted into the db
                box = predictions.pred_boxes.tensor.numpy().squeeze().astype(int) if predictions.has("pred_boxes") else None
                objectness = predictions.scores.numpy().item() if predictions.has("scores") else None
                class_scores = predictions.class_scores.numpy().squeeze() if predictions.has("class_scores") else None

                # convert the list of class scores into a dict. astype(float) since np.float32 is not JSON-Serializable
                score_dict = {idx: val.astype(float) for idx, val in enumerate(class_scores)}

                # create the object and insert
                pred = self.Prediction(msg_id, box, objectness, score_dict, msg.source_address, timestamp)
                self.dbh.insert(pred)

    def setup(self, *args, **kwargs):
        # get the needed tables
        self.Prediction = self.dbh.tables['predictions']

    def cleanup(self, *args, **kwargs):
        # make sure session is closed
        self.dbh.db.session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input_im', help='Input stream key name', type=str, default='camera:2')
    parser.add_argument('-p', '--dbconf', help='Path to db config file', type=str,
                        default='pipert/contrib/database/pipe_db.yml')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4250')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')

    opts = parser.parse_args()

    # Set up Redis connection
    # url = urlparse(opts.url)
    url = os.environ.get('REDIS_URL')
    url = urlparse(url) if url is not None else urlparse(opts.url)

    # load db config from file
    with open(opts.dbconf, "r") as cfg:
        db_config = yaml.safe_load(cfg)

    zpc = OutputLogger(endpoint=f"tcp://0.0.0.0:{opts.zpc}", in_key=opts.input_im, db_conf=db_config, redis_url=url)

    print(f"run {zpc.name}")
    zpc.run()
    print(f"Killed {zpc.name}")
