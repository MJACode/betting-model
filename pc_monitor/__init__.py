"""This PC: a desktop window showing the betting model's jobs on mike's PC.

Run with ``pythonw -m pc_monitor`` (the desktop shortcut does this). It reads
Task Scheduler, the running processes, the jobs' own log files and a few small
database tables, and shows them in an Edge app window at http://127.0.0.1:8790/.

It is a separate program from ``monitoring/`` (the cloud worker's dashboard):
the worker never imports it, and it keeps working when the database cannot be
reached. It writes nothing inside the repo. Its own log goes beside the other
PC jobs' logs, in ``Documents\\betting_local_copies\\logs``.

``readers`` holds the pure parsers (tested in tests/test_pc_monitor.py);
``sources`` reads the machine; ``app`` serves the page. docs/local_ops.md has
the operator notes.
"""
