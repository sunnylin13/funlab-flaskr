"""Public exports for the ``funlab.flaskr`` package."""

from .app import FunlabFlask, create_app, start_server
from .plugin_mgmt_view import PluginManagerView

__all__ = ["FunlabFlask", "PluginManagerView", "create_app", "start_server"]
