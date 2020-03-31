from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc as sql_exc, Column, Integer, ARRAY, Float, JSON, Text, DateTime
import re


class DBHandler:
	def __init__(self, db_conf: dict, logger) -> None:
		"""
		Initializes the database handler, establishes a connection and defines the needed tables.

		:param db_conf: A dictionary with *at least* the following keys: (user, pw, host, port, db) that defines the
						connection parameters to the postgres database.
		:param logger: logging.logger object that should be used to log any error/debug messages.
		"""
		self.user = None
		self.pw = None
		self.host = None
		self.port = None
		self.db_name = None
		self.logger = logger
		self.tables = dict()
		self.db = None
		self.has_connection = False

		# init app and db connection
		self.app = Flask(__name__)
		self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # silence the deprecation warning
		self.set_connection(**db_conf)

		# init db tables
		self._define_tables()

	def insert(self, item) -> None:
		"""
		Attempt to insert an 'item' into the database.

		'item' should be a derivative of 'self.db.Model' and should be defined (and bound to a database table) in
		'self._define_tables(), otherwise this will fail.
		:param item: A Derivative of 'self.db.Model'
		:return: None
		"""
		if item.__class__ not in self.tables.values():
			err_msg = f"DataBase Insertion Error: Can't insert {item}\n" \
				f"I don't know how to insert object of type {item.__class__}"
			self.logger.error(err_msg) if self.logger else None
			raise TypeError(err_msg)

		if self.has_connection:
			self.db.session.add(item)

			try:
				self.db.session.commit()

			# if passed data is of wrong type\shape\size
			except sql_exc.DataError as de:
				self.db.session.rollback()
				self.logger.error(self._format_sqla_error(de) + f"\nError code: {de.code}")

			# if passed data violates any constraints imposed by the Database, i.e. PersonAge<0, duplicate unique, etc..
			except sql_exc.IntegrityError as ie:
				self.db.session.rollback()
				self.logger.error(self._format_sqla_error(ie) + f"\nError code: {ie.code}")

			# if there was a connection problem
			except sql_exc.OperationalError as oe:
				self.db.session.rollback()
				self.logger.critical(self._format_sqla_error(oe) + f"\nError code: {oe.code}")

			# if there was any other Database related error
			except sql_exc.SQLAlchemyError as sqlae:
				self.db.session.rollback()
				self.logger.error(self._format_sqla_error(sqlae) + f"\nError code: {sqlae.code}")

			# if there was an unknown error
			except Exception:
				self.db.session.close()
				raise

	def _define_tables(self) -> None:
		"""
		This method defines the structure of the tables that the handler should work with, as well as binds the pythonic
		Classes to the correct table in db within 'self.tables'.

		**THIS IS THE ONLY PLACE THAT SHOULD REQUIRE CHANGES WHEN ADDING TABLES OR CHANGING TO ANOTHER DATABASE**

		:return: None
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

	def _test_connection(self) -> bool:
		"""Test the connection to the currently configured DataBase.

		:return: True if has connection, False otherwise
		"""
		try:
			self.db.engine.execute("SELECT 1")
		except sql_exc.OperationalError as oe:
			self.logger.critical(self._format_sqla_error(str(oe)) + f"\nError code: {oe.code}")
			return False
		else:
			self.logger.debug(f"Connected to database '{self.db_name}' at host '{self.host}' on port '{self.port}'"
																					f" as user '{self.user}'")
			return True

	def set_connection(self, **kwargs) -> None:
		"""Sets the connection parameters and attempts to make a connection to the database.

		This is exposed as a separate method in case the configuration changes mid run. This is an unlikely scenario
		so maybe its not necessary

		:param kwargs:
		:return:
		"""
		if self.db:
			self.db.session.close()
		try:
			self.user = kwargs['user']
			self.pw = kwargs['pw']
			self.host = kwargs['host']
			self.port = kwargs['port']
			self.db_name = kwargs['db']
		except KeyError as ke:
			self.logger.critical(str(ke))
			raise
		else:
			self.app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://' \
				f'{self.user}:{self.pw}@{self.host}:{self.port}/{self.db_name}'
			self.db = SQLAlchemy(self.app)
			self.has_connection = self._test_connection()

	@staticmethod
	def _format_sqla_error(err_: (str, Exception)) -> str:
		"""Formats the error messages from SQLAlchemy exceptions and cleans them up a bit.

		:param err_: SQLAlchemy exception or the error message of such an exception
		:return: Formatted string representation of the error in question
		"""
		err_ = str(err_) if not isinstance(err_, str) else err_
		# strip the end where the link is
		relevant = err_.split("(Background")[0].strip()
		# find the error type
		err_strt, err_end = re.match(r"^\(.+\)", relevant).span()
		# make it all a bit prettier and return
		err_type = relevant[err_strt + 1:err_end - 1]
		err_msg = relevant[err_end:]
		return f'{err_type}:{err_msg}'

