from __future__ import annotations
import argparse
import logging
from pathlib import Path
import sys
from werkzeug.routing import BuildError

from flask import (Blueprint, Flask, redirect, render_template, url_for, current_app)
from flask_login import current_user
from funlab.core.auth import policy_required
from funlab.core.menu import MenuItem, MenuDivider
from funlab.core.config import Config
from funlab.core.appbase import _FlaskBase
from funlab.core.notification import INotificationProvider
from funlab.core.policy import is_admin, is_authenticated_user
from funlab.utils import vars2env
from funlab.flaskr.plugin_mgmt_view import PluginManagerView

import re

# 機密欄位名稱偵測（FLK-03）：渲染設定頁前先遮罩。
# 注意用「包含」而非「等於」：SECRET_KEY / XXX_PASSWORD / DB_TOKEN 都要命中；
# 刻意不含裸 'KEY' 以外的一般詞，避免把 HOME_ENTRY 等一般鍵誤遮。
# SECRET_KEY 同時是 vars2env 的 env 檔加解密主金鑰（ADR-016 D2/R3），必須遮罩。
_SENSITIVE_KEY_RE = re.compile(
    r'(SECRET|PASSWORD|PASSWD|PASSPHRASE|TOKEN|APIKEY|API_KEY|ACCESS_KEY|'
    r'PRIVATE_KEY|CREDENTIAL|CERT_PASS|KEYSTORE)', re.IGNORECASE)


def _mask_sensitive(mapping):
    """遞迴遮罩 dict 中機密鍵的值（不回傳原 dict）。"""
    masked = {}
    for key, value in dict(mapping).items():
        if isinstance(value, dict):
            masked[key] = _mask_sensitive(value)
        elif _SENSITIVE_KEY_RE.search(str(key)):
            masked[key] = '***masked***'
        else:
            masked[key] = value
    return masked


class FunlabFlask(_FlaskBase):
    def __init__(self, configfile:str, envfile:str, *args, **kwargs):
        from funlab.utils import log
        import logging
        mylogger = log.get_logger(self.__class__.__name__, level=logging.INFO)
        mylogger.progress("Creating FunlabFlask ...", key='funlabflask')

        # --- CSRF (ADR-016 D2) ------------------------------------------
        # Create the CSRFProtect instance BEFORE plugin registration so
        # plugins can declare exemptions at construction time, e.g.::
        #
        #     flask_restx.Api(blueprint, decorators=[app.csrf.exempt])
        #
        # Enforcement is only wired in *after* plugin registration
        # completes (``self.csrf.init_app(self)`` below), matching the ADR
        # timing "plugin 註冊完成後 CSRFProtect(app)".  Exemptions are
        # allowed on flask-restx read-only api namespaces only; notifications
        # and plugin-management JSON POSTs are covered by the shared
        # X-CSRFToken bootstrap JS (statics/js/csrf_ajax.js + meta tag in
        # layouts/base*.html), not exempted.
        from flask_wtf import CSRFProtect
        from flask_wtf.csrf import CSRFError
        self.csrf = CSRFProtect()

        super().__init__(configfile=configfile, envfile=envfile, *args, **kwargs)
        self.app:FunlabFlask

        # ✅ 註冊內建的 PluginManagerView
        self._register_plugin_manager_view()

        # Wire global CSRF protection now that (and only now that) all
        # plugins have had their chance to register exemptions.
        self._init_csrf_protection(CSRFError)
        # FLK-06: 基本安全標頭（不依賴 CSRF 設定，獨立常駐）
        self._init_security_headers()
        mylogger.end_progress("FunlabFlask created.", key='funlabflask')

    def _init_csrf_protection(self, csrf_error_cls) -> None:
        """Activate global CSRFProtect and its error surface (ADR-016 D2).

        - ``CSRFProtect.init_app`` intercepts every POST/PUT/PATCH/DELETE at
          request-dispatch time (fail-closed default for future routes).
        - A dedicated ``CSRFError`` handler is required: ``_FlaskBase``
          registers a catch-all ``errorhandler(Exception)`` that would
          otherwise swallow the 400 CSRF rejection and surface it as a 500.
        - Hard deployment condition (ADR-016 D2 / risk R3): a randomly
          generated SECRET_KEY makes tokens invalid across restarts /
          workers; warn loudly at startup so operators pin it.
        """
        self.csrf.init_app(self)

        @self.errorhandler(csrf_error_cls)
        def csrf_validation_error(error):
            # 400 is the canonical CSRF rejection status.  Keep it a 400
            # (never let the generic Exception handler turn it into a 500).
            description = getattr(error, 'description', None) or str(error)
            from flask import jsonify, request as req
            if req.is_json:
                return jsonify(error='CSRF validation failed',
                               detail=description), 400
            return ('CSRF validation failed. Please reload the page and '
                    'submit again.'), 400

        if getattr(self, 'secret_key_is_random', False):
            self.mylogger.warning(
                "CSRF is enabled but SECRET_KEY was NOT pinned in config; a "
                "random key is in use.  All POST/PUT/PATCH/DELETE requests "
                "will fail after restart or across workers.  Pin "
                "SECRET_KEY in the deployment config before serving traffic "
                "(ADR-016 D2).")
        else:
            self.mylogger.info("Global CSRF protection enabled (flask-wtf CSRFProtect).")

    def _init_security_headers(self) -> None:
        """FLK-06: 為所有回應掛上基本安全標頭。

        - X-Frame-Options: SAMEORIGIN — 防 clickjacking。模板目前無
          iframe 自我嵌入需求；如日後有特定頁面允許嵌入，用
          config['X_FRAME_OPTIONS_ALLOW'] 逐頁放行的後續案再議。
        - X-Content-Type-Options: nosniff
        - Referrer-Policy: same-origin
        - Content-Security-Policy：預設**不發**（模板含大量 inline script
          與 rsms.me 字體 CDN，強制 CSP 需先整理模板）。部署者可設
          config['CSP_HEADER']（整條 CSP 字串）或保守的
          config['CSP_REPORT_ONLY']（僅報告不封鎖）啟用。
        """
        @self.after_request
        def _add_security_headers(response):
            response.headers.setdefault('X-Frame-Options',
                                        self.config.get('X_FRAME_OPTIONS', 'SAMEORIGIN'))
            response.headers.setdefault('X-Content-Type-Options', 'nosniff')
            response.headers.setdefault('Referrer-Policy',
                                        self.config.get('REFERRER_POLICY', 'same-origin'))
            csp = self.config.get('CSP_HEADER')
            if csp:
                response.headers['Content-Security-Policy'] = csp
            csp_ro = self.config.get('CSP_REPORT_ONLY')
            if csp_ro:
                response.headers['Content-Security-Policy-Report-Only'] = csp_ro
            return response

    def get_user_data_storage_path(self, username:str)->Path:
        # 使用者私有資料（含券商憑證）絕不可位於任何 static 路由之下
        data_path =  Path(self.root_path).joinpath('_users').joinpath(username.lower().replace(' ', ''))
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
            if not self._is_security_component_enabled(PluginManagerView):
                self.mylogger.info(
                    "PluginManagerView skipped in %s mode because it requires authorization.",
                    getattr(self, 'security_mode', 'public'),
                )
                return
            plugin_mgr_view = PluginManagerView(self)
            # 註冊到應用中，使其可用
            if hasattr(plugin_mgr_view, 'blueprint'):
                self.register_blueprint(plugin_mgr_view.blueprint)
            # ✅ 調用 setup_menus() 以註冊選單
            # plugin_mgr_view.setup_menus()
            self.mylogger.info("PluginManagerView registered successfully")
        except Exception as e:
            self.mylogger.error(f"Failed to register PluginManagerView: {e}")

    def _is_security_component_enabled(self, component_cls) -> bool:
        """Return whether a built-in component may activate in the current security mode."""
        security_mode = str(getattr(component_cls, 'security_mode', 'public') or 'public').lower()
        if getattr(component_cls, 'provides_security', False):
            return True
        if security_mode == 'required' and not getattr(self, 'authorization_enabled', False):
            return False
        return True

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
                if not getattr(current_app, 'authorization_enabled', False):
                    return redirect(url_for('root_bp.home'))
                if not current_app.login_manager or not current_app.login_manager.login_view:  # 系統不做登入及權限管理
                    return redirect(url_for('root_bp.home'))
                return redirect(url_for(current_app.login_manager.login_view))

        @self.blueprint.route('/blank')
        def blank():
            return render_template('blank.html')

        @self.blueprint.route('/home')
        def home():
            if getattr(current_app, 'authorization_enabled', False) and not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            home_entry:str=None
            if home_entry:=self.config.get("HOME_ENTRY", None):
                if home_entry.endswith(('.html', '.htm',)):
                    return render_template(home_entry)
                else:
                    try:
                        return redirect(url_for(home_entry))
                    except BuildError:
                        if not getattr(current_app, 'authorization_enabled', False):
                            self.mylogger.info(
                                "HOME_ENTRY '%s' is unavailable in public mode; falling back to blank page.",
                                home_entry,
                            )
                            return render_template('blank.html')
                        raise
            else:
                return render_template('blank.html')

        @self.blueprint.route('/conf_data')
        @policy_required(is_admin)
        def conf_data():
            # FLK-03: 設定頁絕不輸出金鑰/密碼值；遞迴遮罩後再渲染。
            return render_template('conf-data.html',
                                   app_conf=_mask_sensitive(self.config),
                                   all_conf=_mask_sensitive(self._config.as_dict()))

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
            """健康檢查。

            明細（plugins/prewarm 逐項狀態）只在以下條件回傳：
            - 來源為回環位址（127.0.0.1/::1，本机 curl 驗收流程沿用），或
            - HEALTH_DETAIL='admin' 且當前使用者為 admin，或
            - HEALTH_DETAIL='open'（明確選擇公開發布）。
            其餘情況只回 {'status': 'ok'|'degraded'}。
            HEALTH_DETAIL 預設 'local'。

            late（run() 後註冊、永不執行）的 pending 不計入 degraded：
            late 殭屍任務永遠不會被執行清空，否則會把 /health 永久打到
            degraded/503。
            """
            from flask import jsonify, request as req
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
            # late=True（run() 之後註冊、永不執行）的 pending 不計入 degraded：
            # 否則 late 殭屍任務會讓 /health 永久停在 degraded/503。
            has_prewarm_pending = any(v.get('status') == 'pending' and not v.get('late')
                                      for v in prewarm_status.values())
            system_ok = all_plugins_healthy and not has_prewarm_pending

            mode = str(self.config.get('HEALTH_DETAIL', 'local')).lower()
            loopback = req.remote_addr in ('127.0.0.1', '::1')
            admin = bool(getattr(current_user, 'is_authenticated', False)) and is_admin(current_user)
            show_detail = (mode == 'open') or loopback or (mode == 'admin' and admin)

            if show_detail:
                payload = {
                    'status': 'ok' if system_ok else 'degraded',
                    'plugins': plugin_health,
                    'prewarm': prewarm_status,
                }
            else:
                payload = {'status': 'ok' if system_ok else 'degraded'}
            return jsonify(payload), (200 if system_ok else 503)

        # ------------------------------------------------------------------
        # Notification routes: dispatch through current_app.notification_provider
        # ------------------------------------------------------------------
        # These routes are provider-agnostic and work with any INotificationProvider
        # implementation. The actual backend (in-memory polling or DB-backed SSE)
        # is selected at request time via current_app.notification_provider.

        @self.blueprint.route('/notifications/poll')
        @policy_required(is_authenticated_user)
        def poll_notifications():
            """Return all undismissed notifications for the current user.

            Dispatches to the active provider's fetch_unread().
            Works with both polling and SSE backends.
            """
            items = current_app.notification_provider.fetch_unread(current_user.id)
            from flask import jsonify
            return jsonify(items)

        @self.blueprint.route('/notifications/clear', methods=['POST'])
        @policy_required(is_authenticated_user)
        def clear_notifications():
            """Dismiss every notification for the current user (Clear All button)."""
            current_app.notification_provider.dismiss_all(current_user.id)
            from flask import jsonify
            return jsonify({"status": "ok"})

        @self.blueprint.route('/notifications/dismiss', methods=['POST'])
        @policy_required(is_authenticated_user)
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

        # Error handlers. 未捕捉例外的統一處理在 funlab-libs 的
        # _FlaskBase.register_request_handler:handle_error（含
        # controller_error_handler hook 與 JSON 錯誤回應）；flaskr 只補
        # 特定狀態碼的頁面。這裡不可再註冊 @self.errorhandler(Exception)：
        # register_request_handler() 在本方法之後執行，後註冊者會覆蓋前者，
        # flaskr 端重複註冊只會產生死碼。
        @self.errorhandler(403)
        def access_deny_error(error):
            return render_template('error-403.html', msg=str(error)), 403

        @self.errorhandler(404)
        def not_found_error(error):
            return render_template('error-404.html', msg=str(error)), 404

        @self.errorhandler(500)
        def internal_error(error):
            return render_template('error-500.html', msg=str(error)), 500

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
                            href='/conf_data', required_policy=is_admin),
                        MenuItem(title='about',
                            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-square-rounded" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9h.01" /><path d="M11 12h1v4h1" /><path d="M12 3c7.2 0 9 1.8 9 9s-1.8 9 -9 9s-9 -1.8 -9 -9s1.8 -9 9 -9z" /></svg>',
                            href='/about'),
                        # MenuItem(title='ssetest',
                        #     icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-square-rounded" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9h.01" /><path d="M11 12h1v4h1" /><path d="M12 3c7.2 0 9 1.8 9 9s-1.8 9 -9 9s-9 -1.8 -9 -9s1.8 -9 9 -9z" /></svg>',
                        #     href='/ssetest'),
                        ])

def create_app(configfile, envfile:str=None):
    # static_folder=None：不註冊 app 級 static 路由。舊值 "" 會把套件根目錄以
    # URL "/" 公開（含 _users/ 憑證、conf/、*.py）。前端資源由 root_bp 的 /static 提供。
    app = FunlabFlask(configfile=configfile, envfile=envfile, import_name=__name__, template_folder="", static_folder=None)
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
        log_file = './funlab.log'
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.DEBUG)
        app.logger.addHandler(handler)
        app.run(port=config['PORT'], use_reloader=False)

def main(args=None):
    from funlab.utils import log
    mylogger = log.get_logger(__name__, level=logging.INFO)
    if args is None:
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

if __name__ == "__main__":
    sys.exit(main())
