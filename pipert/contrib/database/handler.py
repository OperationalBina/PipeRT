from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc as sql_exc
from abc import ABCMeta, abstractmethod
import re


class PSQLDBHandler(metaclass=ABCMeta):
	def __init__(self, db_conf: dict, logger) -> None:
		"""
		Initializes the database handler, establishes a connection and defines the needed tables.

		Args:
			db_conf: A dictionary with *at least* the following keys: (user, pw, host, port, db)
					that defines the connection parameters to the postgres database.

			logger: logging.logger object that should be used to log any error/debug messages.
		"""
		self.logger = logger
		self.tables = dict()

		# init app and db connection
		self.app = Flask(__name__)
		self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # silence the deprecation warning
		try:
			self.user = db_conf['user']
			self.pw = db_conf['pw']
			self.host = db_conf['host']
			self.port = db_conf['port']
			self.db_name = db_conf['db']
		except KeyError as ke:
			self.logger.critical(str(ke))
			raise
		else:
			self.app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://' \
				f'{self.user}:{self.pw}@{self.host}:{self.port}/{self.db_name}'

			self.db = SQLAlchemy(self.app)

	def test_connection(self) -> bool:
		"""
		Test the connection to the currently configured DataBase.

		Returns:
			True if has connection, False otherwise
		"""

		try:
			self.db.engine.execute("SELECT 1")
		except sql_exc.OperationalError as oe:
			self.logger.critical(format_sqla_error(str(oe)) + f"\nError code: {oe.code}")
			return False
		else:
			self.logger.debug(f"Connected to database '{self.db_name}' at host '{self.host}'" 
							f" on port '{self.port}' as user '{self.user}'")
			return True

	@property
	def session(self):
		"""
		Exposes the session for syntactic-sugar purposes

		Returns: The current session
		"""
		return self.db.session

	@abstractmethod
	def define_tables(self, *args, **kwargs):
		"""
		Any table that should be used by the handler must be defined and
		registered in 'self.tables' inside this method.

		Args:
			*args: (Optional) Any required positional arguments
			**kwargs: (Optional) Any required keyword arguments

		Example usage (bare bones):

		.. code-block:: python

		# Define one or more tables..
		class User(self.db.Model):
			__tablename__ = 'users'
			user_id = Column(Integer, primary_key=True)
			user_name = Column(Integer, nullable=False)
			user_birth_date = Column(DateTime)

			def __init__(self, user_id, name, dob):
				self.user_id = user_id
				self.user_name = name
				self.user_birth_date = dob


		# Then register them
		self.tables[User.__tablename__] = User
		"""
		raise NotImplementedError


def format_sqla_error(err_: (str, sql_exc.SQLAlchemyError)) -> str:
	"""
	Formats the error messages from SQLAlchemy exceptions and cleans them up a bit.

	Args:
		err_: SQLAlchemy exception or the error message of such an exception.

	Returns:
		Formatted string representation of the error in question.
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
