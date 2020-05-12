.. PipeRT documentation master file, created by
   sphinx-quickstart on Wed Jan 15 18:36:06 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to PipeRT's documentation!
==================================

High level diagram of the pipeline

.. image:: ../source/_static/images/sphx_glr_pipeline_diagram.png
  :width: 800

The components transfer data to each other using their routines.
The data flows from one component’s “output routine” to another component’s “input routine” through a Redis server.
The current default approach is to host all of the components on one machine in order to minimize latency within the
pipeline. The reason is that it allows the frame data to be quickly transferred between components by having them store
it in their shared memory, and then passing its address to the Redis server.



.. toctree::
   :maxdepth: 2
   :caption: Contents:


   component
   routine

* :ref:`genindex`
* :ref:`search`



