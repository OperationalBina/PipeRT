from psycopg2.extensions import register_adapter, AsIs
from .handler import PSQLDBHandler, format_sqla_error
import numpy as np

"""psycopg2 (and thus SQLAlchemy) doesn't know the numpy numeric types and thus doesn't know how to treat them.
   Here we just register some adapters which tell them to treat them as normal pythonic float or int"""

# register numpy float types
register_adapter(np.float128, lambda float128: AsIs(float128))
register_adapter(np.float64, lambda float64: AsIs(float64))
register_adapter(np.float32, lambda float32: AsIs(float32))
register_adapter(np.float16, lambda float16: AsIs(float16))

# register numpy int types
register_adapter(np.int64, lambda int64: AsIs(int64))
register_adapter(np.int32, lambda int32: AsIs(int32))
register_adapter(np.int16, lambda int16: AsIs(int16))
register_adapter(np.int8, lambda int8: AsIs(int8))
