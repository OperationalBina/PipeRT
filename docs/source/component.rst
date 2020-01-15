Component
=========

Each component has a zerorpc server and a list of routines.
The zerorpc server exposes all of the component's functions, allowing other components/processes (both local and remote ones)
to call them.
For example, the video display component has a function called "flip_im" which flips the video.
So any remote (or local) process can connect to the component's zerorpc server and make a call to the "flip_im" function
in order to flip the video.
See zerorpc.io_ for more intuitive examples.

.. _zerorpc.io: https://www.zerorpc.io/

.. currentmodule:: pipert.core.component

.. autoclass:: BaseComponent
   :members: