Routine
=======


A routine is responsible for performing one of the component’s main tasks.
It can be run either as a thread or as a process. First it runs a setup function, then it runs its main logic function in a
continuous loop (until it is told to terminate), and finally it runs a cleanup function.
The routines of a component use queues in order to pass the data between them.

Routines can also register events (and event handlers) which can be triggered at any point.
By default, each routine registers 2 events which are triggered at the beginning and at the end of each iteration of the
routine’s main logic loop. Each routine can implement its own handlers for the events.

.. currentmodule:: pipert.core.routine

.. autoclass:: Routine
   :members:
