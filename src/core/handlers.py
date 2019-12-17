import time
import logging
from src.core.routine_engine import RoutineMixin
import numpy as np


def tick(routine: RoutineMixin):
    routine.state.tick = time.time()


def tock(routine: RoutineMixin):
    if routine.state.output:
        logging.getLogger().debug(f"routine {routine.name} iteration {routine.state.count} took"
                                  f" {np.round(time.time() - routine.state.tick, 4)} seconds")
