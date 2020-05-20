#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# matador documentation build configuration file, created by
# sphinx-quickstart on Tue Jan  3 17:43:56 2017.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sphinx_rtd_theme

from matador import __version__

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.napoleon",
    "sphinxarg.ext",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "nbsphinx",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
]
# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

autodoc_member_order = "bysource"
autoclass_content = "both"

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
source_suffix = [".rst"]

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "matador"
copyright = "2016-2020, Matthew Evans"
author = "Matthew Evans"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = __version__
# The full version, including alpha/beta/rc tags.
release = __version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False


# run apidoc automatically on RTD: https://github.com/rtfd/readthedocs.org/issues/1139
def run_apidoc(_):
    import subprocess
    import glob
    import shutil

    try:
        if not os.path.isfile("docs/src/img/lipzn.png"):
            os.makedirs("docs/src/img")
            shutil.copy("img/lipzn.png", "docs/src/img/lipzn.png")
    except Exception:
        pass
    src_dir = os.path.abspath(os.path.dirname(__file__))
    excludes = glob.glob(os.path.join(src_dir, "../../matador/tests/"))
    module = os.path.join(src_dir, "../../matador")
    cmd_path = "sphinx-apidoc"
    print(excludes)
    command = [cmd_path, "-M", "-o", src_dir, module, " ".join(excludes)]
    print(command)
    subprocess.check_call(command)


def setup(app):
    app.connect("builder-inited", run_apidoc)


# -- Napolean options -----------------------------------------------------

# Napoleon settings
#
# napoleon_google_docstring = True
# napoleon_numpy_docstring = True
# napoleon_include_init_with_doc = False
# napoleon_include_private_with_doc = False
# napoleon_include_special_with_doc = False
# napoleon_use_admonition_for_examples = False
# napoleon_use_admonition_for_notes = False
# napoleon_use_admonition_for_references = False
# napoleon_use_ivar = False
# napoleon_use_param = False
# napoleon_use_rtype = False
# napoleon_use_keyword = False


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"
# html_theme = 'alabaster'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {
    "canonical_url": "https://docs.matador.science",
    "display_version": True,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']


# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "matadordoc"


# -- Options for LaTeX output ---------------------------------------------
latex_elements = {}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, "matador.tex", "matador Documentation", "Matthew Evans", "manual"),
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "matador", "matador Documentation", [author], 1)]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.6", None),
    "numpy": ("http://docs.scipy.org/doc/numpy/", None),
    "pymongo": ("https://api.mongodb.com/python/current/", None),
    "np": ("http://docs.scipy.org/doc/numpy/", None),
    "matplotlib": ("http://matplotlib.org", None),
}
