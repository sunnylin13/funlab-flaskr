from __future__ import annotations
import argparse
import queue
import time

from funlab.flaskr.sse.manager import EventManager
from funlab.flaskr.sse.models import EventBase, EventPriority, SystemNotificationEvent
from http.client import HTTPException
from pathlib import Path
import traceback

from flask import (Blueprint, Flask, Response, g, jsonify, redirect, render_template, request, stream_with_context, url_for)
from flask_login import current_user, login_required
from funlab.core.auth import admin_required
from funlab.core.menu import MenuItem, MenuDivider
from funlab.core.config import Config
from funlab.core.appbase import _FlaskBase
from funlab.utils import vars2env

class FunlabFlask(_FlaskBase):
    def __init__(self, configfile:str, envfile:str, *args, **kwargs):
        super().__init__(configfile=configfile, envfile=envfile, *args, **kwargs)
        self.app:FunlabFlask
        EventManager.register_event(SystemNotificationEvent)
        self.event_manager = EventManager(self.dbmgr)

    def get_user_data_storage_path(self, username:str)->Path:
        data_path =  Path(self.static_folder).joinpath('_users').joinpath(username.lower().replace(' ', ''))
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    def save_user_data(self, username:str, filename:str, data:bytes):
        data_path = self.get_user_data_storage_path(username)
        with open(data_path.joinpath(filename), 'wb') as f:
            f.write(data)

    def send_all_users_system_notification(self, title:str, message:str,
                    priority: EventPriority = EventPriority.NORMAL, expire_after: int = None)-> EventBase:  # minutes
        online_user_ids = self.app.event_manager.connection_manager.get_eventtype_users(event_type="SystemNotification")
        for target_userid in online_user_ids:
            self.app.event_manager.create_event(event_type="SystemNotification",
                    target_userid=target_userid, priority=priority,
                    expire_after=expire_after, title=title, message=message)

    def send_user_system_notification(self, title:str, message:str,
                    target_userid: int = None,
                    priority: EventPriority = EventPriority.NORMAL, expire_after: int = None)-> EventBase:  # minutes
        return self.app.event_manager.create_event(event_type="SystemNotification",
                target_userid=target_userid, priority=priority,
                expire_after=expire_after, title=title, message=message)

    def load_user_file(self, username:str, filename:str):
        data_path = self.get_user_data_storage_path(username)
        with open(data_path.joinpath(filename), 'r') as f:
            data = f.read()
        return data

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
                return redirect(url_for(self.login_manager.login_view))

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
        @admin_required()
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

        @self.blueprint.route('/ssetest')
        @login_required
        def ssetest():
            return render_template('ssetest.html')

        # # Add this route to your blueprint
        @self.blueprint.route('/generate_notification', methods=['POST'])
        @login_required
        def generate_notification():
            title = request.form.get('title', 'Test Notification')
            message = request.form.get('message', 'This is a test notification.')
            target_user = request.form.get('target_userid', None)
            target_userid = int(target_user) if target_user else current_user.id
            priority_level = request.form.get('priority', 'NORMAL')
            priority = EventPriority[priority_level] if priority_level in EventPriority.__members__ else EventPriority.NORMAL
            expire_after = request.form.get('expire_after', 5, type=int)

            event = self.send_user_system_notification(
                title=title,
                message=message,
                target_userid=target_userid,
                priority=priority,
                expire_after=expire_after
            )

            if event:
                return jsonify({
                    "status": "success",
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "created_at": event.created_at.isoformat()
                }), 201
            else:
                return jsonify({"status": "error", "message": "Failed to create notification"}), 500

        @self.blueprint.route('/mark_event_read/<int:event_id>', methods=['POST'])
        @login_required
        def mark_event_read(event_id):
            """Mark an event as read by the current user"""
            self.mylogger.debug(f"收到標記已讀請求：event_id={event_id}, user_id={current_user.id}")

            try:
                # Find the event in the database
                with self.dbmgr.session_context() as session:
                    from funlab.flaskr.sse.models import EventEntity
                    event_entity = session.query(EventEntity).filter_by(
                        id=event_id,
                        target_userid=current_user.id
                    ).first()

                    if event_entity:
                        self.mylogger.debug(f"找到事件：{event_entity.event_type}, 當前 is_read={event_entity.is_read}")

                        if event_entity.is_read:
                            self.mylogger.debug(f"事件 {event_id} 已經被標記為已讀")
                            return jsonify({"status": "warning", "message": "Event already marked as read"}), 200

                        event_entity.is_read = True
                        session.commit()
                        self.mylogger.debug(f"事件 {event_id} 已成功標記為已讀 by user {current_user.id}")
                        return jsonify({"status": "success", "message": "Event marked as read"}), 200
                    else:
                        self.mylogger.warning(f"事件未找到或無權限：event_id={event_id}, user_id={current_user.id}")
                        return jsonify({"status": "error", "message": "Event not found or access denied"}), 404

            except Exception as e:
                self.mylogger.error(f"標記事件 {event_id} 為已讀時發生錯誤: {e}")
                return jsonify({"status": "error", "message": "Internal server error"}), 500

        @self.blueprint.route('/mark_events_read', methods=['POST'])
        @login_required
        def mark_events_read():
            """Mark multiple events as read by the current user."""
            data = request.get_json()
            event_ids = data.get('event_ids')

            if not event_ids or not isinstance(event_ids, list):
                return jsonify({"status": "error", "message": "Invalid or missing event_ids"}), 400

            self.mylogger.debug(f"收到批量標記已讀請求：event_ids={event_ids}, user_id={current_user.id}")

            try:
                with self.dbmgr.session_context() as session:
                    from funlab.flaskr.sse.models import EventEntity

                    # Use 'in_' for an efficient batch update query
                    updated_count = session.query(EventEntity).filter(
                        EventEntity.id.in_(event_ids),
                        EventEntity.target_userid == current_user.id,
                        EventEntity.is_read == False
                    ).update({'is_read': True}, synchronize_session=False)

                    session.commit()

                    self.mylogger.debug(f"成功將 {updated_count} 個事件標記為已讀 for user {current_user.id}")
                    return jsonify({"status": "success", "message": f"{updated_count} events marked as read"}), 200

            except Exception as e:
                self.mylogger.error(f"批量標記事件為已讀時發生錯誤: {e}")
                return jsonify({"status": "error", "message": "Internal server error"}), 500

        @self.blueprint.route('/sse/<event_type>')
        @login_required
        def stream_events(event_type):
            user_id = current_user.id
            stream_id = self.event_manager.register_user_stream(user_id, event_type)
            if not stream_id:
                return Response("Max connections reached.", status=429)

            # self.mylogger.debug(f"Client connected: user_id={user_id}, stream_id={stream_id}, event_type={event_type}")
            def event_stream():
                try:
                    # Safely get the stream queue
                    user_streams = self.event_manager.connection_manager.user_connections.get(user_id, {})
                    user_stream = user_streams.get(stream_id)

                    if not user_stream:
                        self.mylogger.warning(f"Stream {stream_id} not found for user {user_id} upon stream start.")
                        return

                    while True:
                        try:
                            event: EventBase = user_stream.get(timeout=10)  # Wait for an event or timeout

                            # 對於恢復的事件和即時事件使用統一的序列化
                            event_data = event.to_dict()
                            import json
                            sse = f"event: {event.event_type}\ndata: {json.dumps(event_data)}\n\n"
                            yield sse
                        except queue.Empty:
                            # Send a heartbeat if no event is received within the timeout
                            yield f"event: heartbeat\ndata: {{\"status\": \"heartbeat\"}}\n\n"
                except GeneratorExit:
                    # This block is executed when the client disconnects
                    pass
                except Exception as e:
                    self.mylogger.error(f"Event stream error for user_id={user_id}, stream_id={stream_id}: {e}")
                finally:
                    # self.mylogger.debug(f"Client disconnected: user_id={user_id}, stream_id={stream_id}, event_type={event_type}")
                    self.event_manager.unregister_user_stream(user_id, stream_id, event_type)

            response = Response(stream_with_context(event_stream()), content_type='text/event-stream')
            return response

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
        self.append_usermenu([MenuDivider(),
                        MenuItem(title='Configuration',
                            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-octagon-filled" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M14.897 1a4 4 0 0 1 2.664 1.016l.165 .156l4.1 4.1a4 4 0 0 1 1.168 2.605l.006 .227v5.794a4 4 0 0 1 -1.016 2.664l-.156 .165l-4.1 4.1a4 4 0 0 1 -2.603 1.168l-.227 .006h-5.795a3.999 3.999 0 0 1 -2.664 -1.017l-.165 -.156l-4.1 -4.1a4 4 0 0 1 -1.168 -2.604l-.006 -.227v-5.794a4 4 0 0 1 1.016 -2.664l.156 -.165l4.1 -4.1a4 4 0 0 1 2.605 -1.168l.227 -.006h5.793zm-2.897 10h-1l-.117 .007a1 1 0 0 0 0 1.986l.117 .007v3l.007 .117a1 1 0 0 0 .876 .876l.117 .007h1l.117 -.007a1 1 0 0 0 .876 -.876l.007 -.117l-.007 -.117a1 1 0 0 0 -.764 -.857l-.112 -.02l-.117 -.006v-3l-.007 -.117a1 1 0 0 0 -.876 -.876l-.117 -.007zm.01 -3l-.127 .007a1 1 0 0 0 0 1.986l.117 .007l.127 -.007a1 1 0 0 0 0 -1.986l-.117 -.007z" stroke-width="0" fill="currentColor" /></svg>',
                            href='/conf_data', admin_only=True),
                        MenuItem(title='about',
                            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-square-rounded" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9h.01" /><path d="M11 12h1v4h1" /><path d="M12 3c7.2 0 9 1.8 9 9s-1.8 9 -9 9s-9 -1.8 -9 -9s1.8 -9 9 -9z" /></svg>',
                            href='/about'),
                        MenuItem(title='ssetest',
                            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-info-square-rounded" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9h.01" /><path d="M11 12h1v4h1" /><path d="M12 3c7.2 0 9 1.8 9 9s-1.8 9 -9 9s-9 -1.8 -9 -9s1.8 -9 9 -9z" /></svg>',
                            href='/ssetest'),
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
        app.mylogger.info(f"Start Waitress server at {host}:{port}")
        serve(app, **kwargs)
    elif wsgi == 'gunicorn':
        try:
            # https://stackoverflow.com/questions/70396641/how-to-run-gunicorn-inside-python-not-as-a-command-line
            try:
                from gevent import monkey
                monkey.patch_all() # thread=False, select=False)  # for issue: https://github.com/gevent/gevent/issues/1016
                # import gunicorn
                from gunicorn.app.wsgiapp import WSGIApplication  # pylint: disable=import-error # ignore the warning: "No module named 'gunicorn.app.wsgiapp'"
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
        log_file = './sqmif.log'
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.DEBUG)
        app.logger.addHandler(handler)
        app.run(port=config['PORT'], use_reloader=False)

def main(args=None):
    if not args:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Programing by 013 ...")
    parser.add_argument("-c", "--configfile", dest="configfile", default='config.toml', help="specify config.toml name and path")
    parser.add_argument("-e", "--envfile", dest="envfile", default='.env', help="specify .env file name and path")
    args = parser.parse_args(args)
    configfile=args.configfile
    envfile=args.envfile
    start_server(create_app(configfile=configfile, envfile=envfile))

import sys
if __name__ == "__main__":
    sys.exit(main())
    envfile=args.envfile
    start_server(create_app(configfile=configfile, envfile=envfile))

import sys
if __name__ == "__main__":
    sys.exit(main())
