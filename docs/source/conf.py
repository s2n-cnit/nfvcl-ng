# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import subprocess

def get_version_from_git():
    """Get version from git tags, fallback to importlib.metadata if installed"""
    try:
        # Try to get version from installed package first
        from importlib.metadata import version as get_version
        print("ImportLibrary: importlib.metadata is installed. Getting version from package.")
        return get_version('nfvcl')
    except ImportError:
        print("ImportError: importlib.metadata is not installed. Falling back to git version.")
        pass
    except Exception:
        pass

    # Fallback: get version from git tags
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--match', 'v[0-9]*', '--abbrev=0'],
            capture_output=True,
            text=True,
            check=True
        )
        version = result.stdout.strip().lstrip('v')
        return version
    except Exception:
        return 'unknown'

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'NFVCL-NG'
copyright = '2026, CNIT'
author = 'CNIT'
release = get_version_from_git()

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["myst_parser",
              'sphinxemoji.sphinxemoji']

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

html_theme_options = {
    #'analytics_id': 'G-XXXXXXXXXX',  #  Provided by Google in your dashboard
    #'analytics_anonymize_ip': False,
    #'logo_only': False,
    'display_version': True,
    #'prev_next_buttons_location': 'bottom',
    #'style_external_links': False,
    #'vcs_pageview_mode': '',
    #'style_nav_header_background': 'white',
    # Toc options
    'collapse_navigation': True,
    #'sticky_navigation': True,
    #'navigation_depth': 4,
    # To include hidden toctrees
    'includehidden': True

    #'titles_only': False
}
