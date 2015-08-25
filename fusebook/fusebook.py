"""
fusebook

A FUSE filesystem for exploring Jupyter/IPython notebooks

Notebooks are logically containers including code, documentation and output.
Therefore, we can model them as folders in the filesystem inside which we can
access their components directly as files.

Currently only a simple read-only view is available, but it should be possible
to reflect edits to components in the original notebook, or provide virtual
files like various output formats.
"""

from fuse import FuseOSError, Operations, LoggingMixIn
import nbformat
import base64
from pathlib import Path
from stat import S_IFDIR
from errno import ENOENT
import os
import re
import mimetypes

#consider naming cells by parsing markdown heading marks
#re_level1_inline = re.compile("^\s{0,3}#{1,6}\s+([^#]+)\s*(?: #+)?$")
#re_level1_multiline = re.compile("^")

maybe_join = lambda x: "".join(x) if isinstance(x, list) else x


class FuseNotebook(LoggingMixIn):
    """
    Provides FUSE operations on a single notebook (real path self.root).
    """
    def __init__(self, root, rw=False):
        self.root = root
        self.rw = rw
        self.stat = Path(self.root).lstat()
        self.fnames = {}
        self.fdata = {}
        self.node = self.loadnb()

    def loadnb(self):
        """
        Load the notebook and parse all the cells, assigning them filenames
        and extracting their contents.
        """
        with open(self.root) as f:
            node = nbformat.reader.read(f)

        # ipynb format 4 is current; update the data structure
        # for consistency if it is an older version
        ipynb_version = nbformat.reader.get_version(node)
        if ipynb_version < (4, 0):
            node = nbformat.convert(node, 4)

        # extension for code cells (TODO: this might not be available)
        codeext = node.metadata.language_info.file_extension

        # assign filenames to parts of the data
        for i, cell in enumerate(node.cells):
            if cell.cell_type == "markdown":
                fname = "cell{0}.md".format(i)
                self.fnames[fname] = ("markdown", cell)
                self.fdata[fname] = maybe_join(cell.source).encode("utf-8")
            elif cell.cell_type == "code":
                fname = "cell{0}{1}".format(i, codeext)
                self.fnames[fname] = ("code", cell)
                self.fdata[fname] = maybe_join(cell.source).encode("utf-8")
                for j, output in enumerate(cell.outputs):
                    if output.output_type == "stream":
                        fname = "cell{0}_out{1}_{2}.txt".format(i, j,
                                                                output.name)
                        self.fnames[fname] = ("stream", output)
                        self.fdata[fname] = maybe_join(output.text).encode("utf-8")
                    elif output.output_type in ("display_data",
                                                "execute_result"):
                        for k, mime in enumerate(output.data):
                            ext = mimetypes.guess_extension(mime)
                            fname = "cell{0}_out{1}_data{2}{3}".format(i, j,
                                                                       k, ext)
                            self.fnames[fname] = ("data",
                                                  (mime, output.data[mime]))

                            # interpreting these types as base64 and everything
                            # else as text matches behaviour in nbconvert
                            # but it's probably not extensible
                            # the nbformat really needs to say how display_data
                            # is encoded
                            if mime in ("image/png", "image/jpeg",
                                        "application/pdf"):
                                self.fdata[fname] = base64.decodestring(bytes(maybe_join(output.data[mime]), "ascii"))
                            else:
                                self.fdata[fname] = maybe_join(output.data[mime]).encode("utf-8")

        return node

    def readdir(self, path, fh):
        yield from ('.', '..')
        yield from sorted(self.fnames)

    def getattr(self, path, fh=None):
        fname = Path(path).name

        # all characteristics except size are copied from the .ipynb file
        # conceivably the notebook could store per-cell {a,c,m}time, but doesn't
        if fname in self.fnames:
            return {
                "st_atime": self.stat.st_atime,
                "st_ctime": self.stat.st_ctime,
                "st_gid": self.stat.st_gid,
                "st_mode": self.stat.st_mode,
                "st_mtime": self.stat.st_mtime,
                "st_nlink": self.stat.st_nlink,
                "st_size": len(self.fdata[fname]),
                "st_uid": self.stat.st_uid
            }
        else:
            raise FuseOSError(ENOENT)



    def read(self, path, length, offset, fh):
        fname = Path(path).name
        if fname in self.fnames:
            data = self.fdata[fname]
            return data[offset:offset+length]
        else:
            raise FuseOSError(ENOENT)

    # to consider - remove outputs or cells with unlink,
    # edit their contents with write
    """
    def write(self, path, buf, offset, fh):
        if self.rw:
            pass
        else:
            pass

    def unlink(self, path):
        if self.rw:
            pass
        else:
            pass
    """

class FuseNotebookDir(LoggingMixIn, Operations):
    """
    FUSE root representing a normal directory containing notebook files
    (and possibly normal subdirectories)

    Directory structure is presented identically except that notebook files
    become directories. Non-notebook files will appear in the listing but
    full passthrough access is not implemented. Operations on virtual
    notebook directories are passed to FuseNotebook objects.
    """
    def __init__(self, root, rw=False):
        self.root = Path(root).resolve()
        self.rw = rw
        self.notebooks = {}

    def _classify(self, path):
        """
        Identifies a FUSE path as being either a real dir, real (non-notebook)
        file, notebook file (fake dir) or notebook contents (fake files).

        Returns a tuple (type, fspath) where fspath is string representing the
        real path, or the notebook file.
        """

        path = Path(path)
        if path.is_absolute():
            path = Path(*path.parts[1:])
        fspath = self.root / path

        # revisit if we represent dirs inside notebooks
        if fspath.parent.is_file() and fspath.parent.suffix == '.ipynb':
            return ("nbcont", str(fspath.parent))
        elif fspath.is_dir():
            return ("dir", str(fspath))
        elif fspath.is_file():
            if fspath.suffix == '.ipynb':
                return ("nb", str(fspath))
            else:
                return ("file", str(fspath))
        else:
            return (None, str(fspath))

    def _notebook(self, fspath):
        if fspath in self.notebooks:
            return self.notebooks[fspath]
        else:
            nb = FuseNotebook(fspath, rw=self.rw)
            self.notebooks[fspath] = nb
            return nb

    def getattr(self, path, fh=None):
        type, fspath = self._classify(path)
        if type == "nbcont":
            return self._notebook(fspath).getattr(path, fh)
        elif type in ("dir", "file"):
            stat = Path(fspath).lstat()
            return {k: getattr(stat, k) for k in ("st_atime", "st_ctime",
                                                  "st_mtime", "st_uid",
                                                  "st_gid", "st_mode",
                                                  "st_nlink", "st_size")}
        elif type == "nb":
            stat = Path(fspath).lstat()
            return {
                "st_atime": stat.st_atime,
                "st_ctime": stat.st_ctime,
                "st_gid": stat.st_gid,
                "st_mode": S_IFDIR | 0o775,
                "st_mtime": stat.st_mtime,
                "st_nlink": 1,
                "st_size": 4096,
                "st_uid": stat.st_uid
            }
        else:
            raise FuseOSError(ENOENT)

    # could be used to implement notebook/cell metadata
    # def listxattr(self, path):
    # def getxattr(self, path, name, position=0):
    # def removexattr(self, path, name):

    # some further error checking is probably required in these functions

    def readdir(self, path, fh):
        type, fspath = self._classify(path)
        if type == "dir":
            yield from ('.', '..')
            for child in Path(fspath).iterdir():
                yield child.name
        elif type == "nb":
            yield from self._notebook(fspath).readdir(path, fh)

    def read(self, path, length, offset, fh):
        type, fspath = self._classify(path)
        if type == "nbcont":
            return self._notebook(fspath).read(path, length, offset, fh)
        elif type == "file":
            os.lseek(fh, offset, 0)
            return os.read(fh, length)

    # some or all of these will be required for read-write access
    """
    # def rename(self, old, new):
    # def create(self, path, mode, fi=None):

    def unlink(self, path):
        type, fspath = self._classify(path)
        if type == "nbcont":
            # RW handling left to notebook
            return self._notebook(fspath).unlink(path)
        # check what to do here for other types

    def write(self, path, buf, offset, fh):
        type, fspath = self._classify(path)
        if type == "nbcont":
            return self._notebook(fspath).write(path, buf, offset, fh)
        else:
            return os.write(fh, buf)
    """
