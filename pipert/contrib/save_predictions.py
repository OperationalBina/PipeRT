from queue import Queue
from urllib.parse import urlparse
from pipert.core.mini_logics import MessageFromRedis
from pipert.core import Routine, BaseComponent, QueueHandler, Events
from pipert.contrib.database import PSQLDBHandler, format_sqla_error
from sqlalchemy import Column, Integer, ARRAY, Float, JSON, Text, DateTime
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime as dt
import argparse
import logging
import yaml
import os


class OutputLogger(BaseComponent):
	def __init__(self, endpoint, in_key, db_conf, redis_url):
		super().__init__(endpoint, self.__class__.__name__)
		self.queue = Queue(maxsize=10)

		t_get = MessageFromRedis(in_key, redis_url, self.queue, name="get_preds_from_redis", component_name=self.name).as_thread()
		self.register_routine(t_get)

		t_save = PredsToDatabase(self.queue, db_conf, name="save_preds_to_db", component_name=self.name).as_thread()
		self.register_routine(t_save)

	def toggle(self):
		"""Toggle saving to the database on or off. To be used with zpc.

		:return: None
		"""
		return self._routines["save_preds_to_db"].toggle()


class MarsDBHandler(PSQLDBHandler):
	def __init__(self, db_conf, logger):
		super().__init__(db_conf, logger=logger)
		self.define_tables()

	def define_tables(self):
		"""
		This method defines the structure of the tables that the handler should work with,
		as well as binds the pythonic Classes to the correct table in db within 'self.tables'.

		**THIS IS THE ONLY PLACE THAT SHOULD REQUIRE CHANGES WHEN ADDING TABLES OR CHANGING TO ANOTHER DATABASE**

		"""

		# The tables
		class Prediction(self.db.Model):
			__tablename__ = 'predictions'
			pred_id = Column(Integer, primary_key=True)
			msg_id = Column(Integer)
			bbox = Column(ARRAY(Integer), nullable=False)
			objectness = Column(Float, nullable=False)
			classes = Column(JSON, nullable=False)
			source = Column(Text, nullable=False)
			timestamp = Column(DateTime, nullable=False)

			def __init__(self, msg_id, bbox, objectness, classes, source, timestamp):
				self.msg_id = msg_id
				self.bbox = bbox
				self.objectness = objectness
				self.classes = classes
				self.source = source
				self.timestamp = timestamp

			def __repr__(self):
				timestr = self.timestamp.strftime("%m/%d/%Y %H:%M:%S.%f")
				return f"Prediction({self.pred_id}, {self.msg_id}, {self.bbox}, {self.objectness}, {self.classes}, {self.source}, {timestr})"

			def __str__(self):
				timestr = self.timestamp.strftime("%m/%d/%Y %H:%M:%S.%f")
				return f"Prediction({self.pred_id}, {self.msg_id}, {self.bbox}, {self.objectness}, {self.classes}, {self.source}, {timestr})"

		# The mapping
		self.tables[Prediction.__tablename__] = Prediction


class PredsToDatabase(Routine):
	def __init__(self, in_queue, db_conf, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.queue = QueueHandler(in_queue)
		self.logger.addHandler(logging.StreamHandler())
		self.add_event_handler(Events.AFTER_LOGIC, self.commit_to_db)
		self.dbh = MarsDBHandler(db_conf, logger=self.logger)
		self.is_on = None

	def setup(self, *args, **kwargs):
		# make sure connection to db is up and turn on
		self.toggle()

	def main_logic(self, *args, **kwargs):
		msg = self.queue.non_blocking_get()

		# Only do something if msg isn't empty and saving is toggled on
		if self.is_on and msg:
			msg_id = msg.id.split("_")[-1]
			timestamp = dt.fromtimestamp(msg.history["VideoCapture"]["entry"])
			for prediction in msg.get_payload():
				# get the needed fields and convert to a format that is good to be inserted into the db
				box = prediction.pred_boxes.tensor.numpy().squeeze().astype(int) if prediction.has("pred_boxes") else None
				objectness = prediction.scores.numpy().item() if prediction.has("scores") else None
				class_scores = prediction.class_scores.numpy().squeeze() if prediction.has("class_scores") else None

				# convert the list of class scores into a dict. astype(float) since np.float32 is not JSON-Serializable
				score_dict = {idx: val.astype(float) for idx, val in enumerate(class_scores)}

				# create the object and add to session
				pred = self.dbh.tables['predictions'](msg_id, box, objectness, score_dict, msg.source_address, timestamp)
				self.dbh.session.add(pred)

	def cleanup(self, *args, **kwargs):
		# make sure session is closed
		self.dbh.session.close()

	def toggle(self):
		"""
		Toggle saving to the database on or off. Makes sure db connection is up when
		toggled ON.

		Returns:
			A message describing the new state (On/Off)
		"""

		if self.is_on:
			self.is_on = False

		else:
			self.is_on = self.dbh.test_connection()

		msg = "Saving predictions toggled " + ("ON" if self.is_on else "OFF")
		self.logger.info(msg)
		return msg

	def commit_to_db(self, routine):
		"""
		Commit the current session to database, rollback in case of an error

		Args:
			routine: This is just a dummy argument, but its necessary if this method
			is to be used as an event handler.

		"""
		if self.is_on:
			try:
				self.dbh.session.commit()

			# if there was any Database related error
			except SQLAlchemyError as sqlae:
				self.dbh.session.rollback()
				self.logger.error(format_sqla_error(sqlae) + f"\nError code: {sqlae.code}")

			# if there was an unknown error
			except Exception:
				self.dbh.session.close()
				raise


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
