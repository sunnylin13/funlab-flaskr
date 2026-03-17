from __future__ import annotations
import argparse
from http.client import HTTPException
from pathlib import Path
import traceback

from flask import (Blueprint, Flask, redirect, render_template, url_for, current_app)
from flask_login import current_user, login_required
from funlab.core.auth import admin_required
from funlab.core.menu import MenuItem, MenuDivider
from funlab.core.config import Config
from funlab.core.appbase import _FlaskBase
from funlab.core.notification import INotificationProvider
from funlab.utils import vars2env
from funlab.flaskr.plugin_mgmt_view import PluginManagerView

class FunlabFlask(_FlaskBase):
    def __init__(self, configfile:str, envfile:str, *args, **kwargs):
        from funlab.utils import log
        import logging
        mylogger = log.get_logger(self.__class__.__name__, level=logging.INFO)
        mylogger.progress("Creating FunlabFlask ...", key='funlabflask')
        super().__init__(configfile=configfile, envfile=envfile, *args, **kwargs)
        self.app:FunlabFlask

        # ✅ 註冊內建的 PluginManagerView
        self._register_plugin_manager_view()
        mylogger.end_progress("FunlabFlask created.", key='funlabflask')

    def get_user_data_storage_path(self, username:str)->Path:
        data_path =  Path(self.static_folder).joinpath('_users').joinpath(username.lower().replace(' ', ''))
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    def save_user_data(self, username:str, filename:str, data:bytes):
        data_path = self.get_user_data_storage_path(username)
        with open(data_path.joinpath(filename), 'wb') as f:
            f.write(data)

    def send_global_notification(self, title: str, message: str,
                    priority: str = 'NORMAL', expire_after: int = None) -> None:
        """Broadcast a system notification to all users.

        ``priority`` is a plain string: 'LOW', 'NORMAL', 'HIGH', or 'CRITICAL'.
        Delegates to the active :attr:`notification_provider`.
        """
        self.notification_provider.send_global_notification(
            title=title, message=message, priority=priority, expire_after=expire_after)

    def send_user_notification(self, title: str, message: str,
                    target_userid: int = None,
                    priority: str = 'NORMAL', expire_after: int = None) -> None:
        """Send a system notification to a specific user.

        ``priority`` is a plain string: 'LOW', 'NORMAL', 'HIGH', or 'CRITICAL'.
        Delegates to the active :attr:`notification_provider`.
        """
        self.notification_provider.send_user_notification(
            title=title, message=message, target_userid=target_userid,
            priority=priority, expire_after=expire_after)

    def load_user_file(self, username:str, filename:str):
        data_path = self.get_user_data_storage_path(username)
        with open(data_path.joinpath(filename), 'r') as f:
            data = f.read()
        return data

    def set_notification_provider(self, provider: INotificationProvider) -> None:
        """Replace the active notification provider.

        Called by ``SSEService._setup()`` when the SSE plugin initialises.
        All subsequent calls to :meth:`send_user_notification` /
        :meth:`send_global_notification` and the ``/notifications/*`` HTTP
        routes will delegate to *provider* transparently.

        Note: If provider is a ServicePlugin, its blueprint is typically already
        registered by the plugin framework. We skip re-registration to avoid
        conflicts. Flask will serve static files from the registered blueprint's
        static_folder automatically.
        """
        self.notification_provider = provider

        # Log provider registration (blueprint is likely already registered by plugin framework)
        self.mylogger.info(
            f"Notification provider set: {provider.__class__.__name__} "
            f"(realtime={provider.supports_realtime})"
        )

    def _register_plugin_manager_view(self):
        """註冊內建的擴充功能管理視圖"""
        try:
            plugin_mgr_view = PluginManagerView(self)
            # 註冊到應用中，使其可用
            if hasattr(plugin_mgr_view, 'blueprint'):
                self.register_blueprint(plugin_mgr_view.blueprint)
            # ✅ 調用 setup_menus() 以註冊選單
            # plugin_mgr_view.setup_menus()
            self.mylogger.info("PluginManagerView registered successfully")
        except Exception as e:
            self.mylogger.error(f"Failed to register PluginManagerView: {e}")

    def register_routes(self):
        self.blueprint = Blueprint(
            'root_bp',
            import_name='funlab.flaskr',
            static_folder='static',
            template_folder='templates',
        )
        # set route for blueprint
        @self.blueprint.route('/')
        def index():
            if current_user.is_authenticated:
                return redirect(url_for('root_bp.home'))
            else:
                if not current_app.login_manager or not current_app.login_manager.login_view:  # 系統不做登入及權限管理
                    return redirect(url_for('root_bp.home'))
                return redirect(url_for(current_app.login_manager.login_view))

        @self.blueprint.route('/blank')
        def blank():
            return render_template('blank.html')

        @self.blueprint.route('/home')
        @login_required
        def home():
            home_entry:str=None
            if home_entry:=self.config.get("HOME_ENTRY", None):
                if home_entry.endswith(('.html', '.htm',)):
                    return render_template(home_entry)
                else:
                    return redirect(url_for(home_entry))
            else:
                return render_template('blank.html')

        @self.blueprint.route('/conf_data')
        @admin_required
        def conf_data():
            return render_template('conf-data.html', app_conf=self.config, all_conf=self._config.as_dict())

        @self.blueprint.route('/about')
        def about():
            about_entry:str=None
            if about_entry:=self.config.get("ABOUT_ENTRY", None):
                if about_entry.endswith(('.html', '.htm',)):
                    return render_template(about_entry)
                else:
                    return redirect(url_for(about_entry))
            else:
                return render_template('about.html')

        @self.blueprint.route('/health')
        def health():
            from flask import jsonify
            import funlab.core.prewarm as prewarm

            plugin_health = {}
            for name, plugin in self.plugins.items():
                try:
                    h = plugin.health
                    plugin_health[name] = {
                        'healthy': bool(getattr(h, 'is_healthy', False)),
                        'error_count': int(getattr(h, 'error_count', 0)),
                        'last_error': getattr(h, 'last_error', None),
                    }
                except Exception as exc:
                    plugin_health[name] = {
                        'healthy': False,
                        'error_count': 1,
                        'last_error': str(exc),
                    }

            prewarm_status = prewarm.status()
            all_plugins_healthy = all(v.get('healthy', False) for v in plugin_health.values()) if plugin_health else True
            has_prewarm_pending = any(v.get('status') == 'pending' for v in prewarm_status.values())
            system_ok = all_plugins_healthy and not has_prewarm_pending

            return jsonify({
                'status': 'ok' if system_ok else 'degraded',
                'plugins': plugin_health,
                'prewarm': prewarm_status,
            }), (200 if system_ok else 503)

        # ------------------------------------------------------------------
        # Notification routes: dispatch through current_app.notification_provider
        # ------------------------------------------------------------------
        # These routes are provider-agnostic and work with any INotificationProvider
        # implementation. The actual backend (in-memory polling or DB-backed SSE)
        # is selected at request time via current_app.notification_provider.

        @self.blueprint.route('/notifications/poll')
        @login_required
        def poll_notifications():
            """Return all undismissed notifications for the current user.

            Dispatches to the active provider's fetch_unread().
            Works with both polling and SSE backends.
            """
            items = current_app.notification_provider.fetch_unread(current_user.id)
            from flask import jsonify
            return jsonify(items)

        @self.blueprint.route('/notifications/clear', methods=['POST'])
        @login_required
        def clear_notifications():
            """Dismiss every notification for the current user (Clear All button)."""
            current_app.notification_provider.dismiss_all(current_user.id)
            from flask import jsonify
            return jsonify({"status": "ok"})

        @self.blueprint.route('/notifications/dismiss', methods=['POST'])
        @login_required
        def dismiss_notifications():
            """Dismiss specific notifications by ID (individual ✕ button)."""
            from flask import request as req, jsonify
            data = req.get_json(silent=True) or {}
            ids = [int(i) for i in data.get("ids", []) if str(i).isdigit()]
            if ids:
                current_app.notification_provider.dismiss_items(current_user.id, ids)
            return jsonify({"status": "ok", "dismissed": ids})

        # Allow provider to register its own provider-specific routes (e.g. /sse/*, /ssetest)
        self.notification_provider.register_routes(self.blueprint)

        # Error handlers and blueprint registration always run regardless of provider.
        @self.errorhandler(403)
        def access_deny_error(error):
            return render_template('error-403.html', msg=str(error)), 403

        @self.errorhandler(404)
        def not_found_error(error):
            return render_template('error-404.html', msg=str(error)), 404

        @self.errorhandler(500)
        def internal_error(error):
            return render_template('error-500.html', msg=str(error)), 500

        @self.errorhandler(Exception)
        def handle_unexpected_error(error):
            if isinstance(error, HTTPException):
                return error
            trace_info = traceback.format_exception(error)
            trace_info = ''.join(trace_info)
            traceback.print_exception(error)
            return render_template('error-500.html', msg=str(error), trace_info=trace_info), 500

        # Need to call flask's register_blueprint for all route, after route defined
        self.register_blueprint(self.blueprint)

    def register_menu(self):
        self.append_usermenu([
                        # MenuItem(title='Plugin Management',
                        #     icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-plug" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M9 8l3 0" /><path d="M12 8l0 13" /><path d="M12 21l0 -13" /><path d="M8 4l0 4" /><path d="M16 4l0 4" /></svg>',
                        #     href='/plugin-manager/management'),
                        MenuDivider(),
                        MenuItem(title='Configuration',
                            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-octagon-filled" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M14.897 1a4 4 0 0 1 2.664 1.016l.165 .156l4.1 4.1a4 4 0 0 1 1.168 2.605l.006 .227v5.794a4 4 0 0 1 -1.016 2.664l-.156 .165l-4.1 4.1a4 4 0 0 1 -2.603 1.168l-.227 .006h-5.795a3.999 3.999 0 0 1 -2.664 -1.017l-.165 -.156l-4.1 -4.1a4 4 0 0 1 -1.168 -2.604l-.006 -.227v-5.794a4 4 0 0 1 1.016 -2.664l.156 -.165l4.1 -4.1a4 4 0 0 1 2.605 -1.168l.227 -.006h5.793zm-2.897 10h-1l-.117 .007a1 1 0 0 0 0 1.986l.117 .007v3l.007 .117a1 1 0 0 0 .876 .876l.117 .007h1l.117 -.007a1 1 0 0 0 .876 -.876l.007 -.117l-.007 -.117a1 1 0 0 0 -.764 -.857l-.112 -.02l-.117 -.006v-3l-.007 -.117a1 1 0 0 0 -.876 -.876l-.117 -.007zm.01 -3l-.127 .007a1 1 0 0 0 0 1.986l.117 .007l.127 -.007a1 1 0 0 0 0 -1.986l-.117 -.007z" stroke-width="0" fill="currentColor" /></svg>',
                            href='/conf_data', admin_only=True),
                        MenuItem(title='about',
                            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-square-rounded" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9h.01" /><path d="M11 12h1v4h1" /><path d="M12 3c7.2 0 9 1.8 9 9s-1.8 9 -9 9s-9 -1.8 -9 -9s1.8 -9 9 -9z" /></svg>',
                            href='/about'),
                        # MenuItem(title='ssetest',
                        #     icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-square-rounded" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9h.01" /><path d="M11 12h1v4h1" /><path d="M12 3c7.2 0 9 1.8 9 9s-1.8 9 -9 9s-9 -1.8 -9 -9s1.8 -9 9 -9z" /></svg>',
                        #     href='/ssetest'),
                        ])

def create_app(configfile, envfile:str=None):
    app = FunlabFlask(configfile=configfile, envfile=envfile, import_name=__name__, template_folder="", static_folder="")
    if envfile:
        vars2env.encode_envfile_vars(envfile, key_name=app.config['SECRET_KEY'])
    return app

def start_server(app:Flask):
    config:Config = app.config
    wsgi = config.get('WSGI', 'flask')
    supported_wsgi = ('waitress', 'gunicorn', 'flask')
    if wsgi not in supported_wsgi:
        raise Exception(f'Not supported WSGI. Only {supported_wsgi} is supported.')
    if wsgi == 'waitress':
        try:
            from waitress import serve
            from funlab.flaskr.conf import waitress_conf
        except ImportError as e:
            raise Exception("If use waitress as WSGI server, please install needed packages: pip install waitress") from e
        kwargs = {name: getattr(waitress_conf, name) for name in dir(waitress_conf) if not name.startswith('__')}
        kwargs.pop('multiprocessing', None)  # dummy for import multiprocessing statement
        host = config.get('HOST', '0.0.0.0')
        port = config.get('PORT', 5000)
        kwargs['host'] = host
        kwargs['port'] = port
        app.mylogger.info(f"\nStart Waitress server at {host}:{port}")
        serve(app, **kwargs)
    elif wsgi == 'gunicorn':
        try:
            # https://stackoverflow.com/questions/70396641/how-to-run-gunicorn-inside-python-not-as-a-command-line
            try:
                from gunicorn.app.wsgiapp import WSGIApplication  # pylint: disable=import-error
            except ImportError as e:
                raise Exception("If use gunicorn as WSGI server, please install needed packages: pip install gunicorn gevent") from e
            from funlab.flaskr.conf import gunicorn_conf
        except ImportError as e:
            raise Exception("Use gunicorn as WSGI server, but not found package, please install: pip install gunicorn") from e
        class GunicornApplication(WSGIApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                gunicorn_logger = logging.getLogger('gunicorn.error')
                app.logger.handlers = gunicorn_logger.handlers
                app.logger.setLevel(gunicorn_logger.level)
                super().__init__()

            def load_config(self):
                config = {key: value for key, value in self.options.items()
                        if key in self.cfg.settings and value is not None}
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application
        kwargs = {name: getattr(gunicorn_conf, name) for name in dir(gunicorn_conf) if not name.startswith('__')}
        kwargs.pop('multiprocessing', None)  # dummy for import multiprocessing statement
        host = config.get('HOST', '0.0.0.0')
        port = config.get('PORT', 5000)
        kwargs['bind'] = f"{host}:{port}"
        app.mylogger.info(f"Start Gunicorn server at {host}:{port}")
        GunicornApplication(app, kwargs).run()
    else:  # development, use flask embeded server
        import logging
        log_file = './funlab.log'
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.DEBUG)
        app.logger.addHandler(handler)
        app.run(port=config['PORT'], use_reloader=False)

def main(args=None):
    from funlab.utils import log
    import logging
    mylogger = log.get_logger(__name__, level=logging.INFO)
    if not args:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Programing by 013 ...")
    parser.add_argument("-c", "--configfile", dest="configfile", default='config.toml', help="specify config.toml name and path")
    parser.add_argument("-e", "--envfile", dest="envfile", default='.env', help="specify .env file name and path")
    args = parser.parse_args(args)
    configfile=args.configfile
    envfile=args.envfile
    mylogger.progress("Web server starting ...", key="main_webserver")
    start_server(create_app(configfile=configfile, envfile=envfile))
    mylogger.end_progress(f"progress state:{mylogger._progress_states}", key='main_webserver')

import sys
if __name__ == "__main__":
    sys.exit(main())
