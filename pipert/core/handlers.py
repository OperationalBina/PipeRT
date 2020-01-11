import time
import logging
from pipert.core.routine import Routine
import numpy as np

# TODO - move all handlers to contrib? or write some monitoring handlers?


def tick(routine: Routine):
    routine.state.tick = time.time()


def tock(routine: Routine):
    if routine.state.output:
        msg = f"routine {routine.name} iteration {routine.state.count} took" \
              f" {np.round(time.time() - routine.state.tick, 4)} seconds"
        logging.getLogger().debug(msg)
