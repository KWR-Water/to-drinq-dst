# Copyright (c) KWR Water Research Institute
# Licensed under the EUPL
import sphinx_rtd_theme
# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import tomllib
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('../..'))


# -- Project information -----------------------------------------------------

project = 'todrinq_dst'
copyright = '2019-2026, KWR Water Research Institute, licensed under the EUPL'
author = 'Martin Korevaar, Martin van der Schans, Erwin Vonk'

# The full version, including alpha/beta/rc tags; single source is pyproject.toml
with open(os.path.abspath('../../pyproject.toml'), 'rb') as _pyproject:
    release = tomllib.load(_pyproject)['project']['version']


# -- General configuration ---------------------------------------------------

master_doc = 'index'
# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "IPython.sphinxext.ipython_directive",
    "IPython.sphinxext.ipython_console_highlighting",
    "matplotlib.sphinxext.plot_directive",
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
    'sphinx_rtd_theme',
    'sphinxcontrib.mermaid',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
html_show_sphinx = False

# matplotlib plot directive
plot_include_source = False
plot_formats = [("png", 90)]
plot_html_show_formats = False
plot_html_show_source_link = False
plot_pre_code = """import numpy as np
import pandas as pd"""

# notebook directives
nbsphinx_allow_errors = True

nbsphinx_execute_arguments = [
    "--InlineBackend.figure_formats={'svg', 'pdf'}", #  recommended for matplotlib
    "--InlineBackend.rc={'figure.dpi': 96}",  # recommended for matplotlib
]
