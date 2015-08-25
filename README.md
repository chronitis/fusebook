FuseBook
========

A FUSE filesystem for accessing the contents of Jupyter/IPython notebooks.

Notebooks are logically containers including code, documentation and output. Therefore, we can model them as folders in the filesystem inside which we can access their components directly as files.

Currently only a simple read-only view is available, but it should be possible to reflect edits to components in the original notebook, or provide virtual files like various output formats.

A notebook file viewed in this way looks like:

```
$ ls
notebook1.ipynb/    notebook2.ipynb/

$ ls notebook1.ipynb/
cell0.md    cell1_out0_stdout.txt
cell1.py    cell1_out1_data0.png

$ cat notebook1.ipynb/cell1.py
your.python.code()
```

Usage
-----

Install with `python3 setup.py install --user`. The `fusepy` library is required.

Run with `fusebook /path/to/notebook/dir /path/to/mountpoint`. **Warning**: experimental, you should definitely use a copy of your notebook directory rather than the original.

Status
------

Only simple read-only access to file contents is supported.

Some possible features might be:

 * Allow create, write and delete operations to add, remove and alter cells and their outputs.
 * Provide virtual files performing lazy formatting, either of individual outputs or the entire document.
 * Provide access to metadata as extended attributes on notebook virtual directories and cell files.
 * Name cells based on section headings extracted from markdow cells.
 * Hide empty files or cells.

Why?
----

Because it's possible.
