#!/usr/bin/env python3

from distutils.core import setup
from fusebook import __version__

setup(name="fusebook",
      version=__version__,
      description="FUSE virtual file system for ipython/jupyter notebooks",
      author="Gordon Ball",
      author_email="gordon@chronitis.net",
      url="https://github.com/chronitis/fusebook",
      packages=["fusebook"],
      license="MIT",
      requires=["fusepy"],
      scripts=["scripts/fusebook"])
