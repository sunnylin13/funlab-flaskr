"""Plugin management API and monitoring interface."""
from flask import Blueprint, jsonify, request, render_template
from funlab.core.auth import policy_required
from funlab.core.policy import is_admin
from funlab.core.plugin import Plugin
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from funlab.flaskr.app import FunlabFlask


class PluginManagerView(Plugin):
    """Built-in plugin management and monitoring view."""

    security_mode = 'required'

    def __init__(self, app: 'FunlabFlask', url_prefix: str = None):
        super().__init__(app, url_prefix or 'plugin-manager')
        self._register_routes()
        if self.plugin_config.get('HOOK_EXAMPLES', False):
            self._register_hook_examples()

    def _register_hook_examples(self):
        if not hasattr(self.app, 'hook_manager'):
            return

        self.app.hook_manager.register_hook(
            'view_layouts_base_content_bottom',
            self._hook_example_content_bottom,
            priority=50,
            plugin_name=self.name,
        )

    def _hook_example_content_bottom(self, context):
        return '<!-- pluginmanager hook example -->'

    def _register_routes(self):
        """Register management routes."""
        @self._blueprint.route('/api/plugins', methods=['GET'])
        @policy_required(is_admin)
        def get_plugins():
            """Return plugin statistics."""
            try:
                if hasattr(self.app, 'plugin_manager'):
                    stats = self.app.plugin_manager.get_plugin_stats()
                else:
                    # Compatibility fallback for legacy plugin collection.
                    stats = self._collect_legacy_plugin_stats()
                    self.app.mylogger.debug(f"legacy stats: {stats}")

                return jsonify({
                    'success': True,
                    'data': stats
                })
            except Exception as e:
                self.app.mylogger.error(f"ERROR in get_plugins: {e}")
                import traceback
                self.app.mylogger.error(f"Traceback: {traceback.format_exc()}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/api/plugins/<plugin_name>/load', methods=['POST'])
        @policy_required(is_admin)
        def load_plugin(plugin_name: str):
            """Load a plugin instance, primarily for lazy-loaded plugins."""
            try:
                if hasattr(self.app, 'plugin_manager'):
                    manager = self.app.plugin_manager
                    state = manager.get_plugin_state(plugin_name)
                    if state is None:
                        return jsonify({
                            'success': False,
                            'error': f'Plugin {plugin_name} not found'
                        }), 404

                    success = manager.load_plugin(plugin_name)
                    current_state = manager.get_plugin_state(plugin_name)
                else:
                    success = False
                    current_state = 'unknown'

                return jsonify({
                    'success': success,
                    'message': f'Plugin {plugin_name} load {"successful" if success else "failed"}',
                    'plugin_name': plugin_name,
                    'state': current_state
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/api/plugins/<plugin_name>/reload', methods=['POST'])
        @policy_required(is_admin)
        def reload_plugin(plugin_name: str):
            """Reload an existing plugin."""
            try:
                if hasattr(self.app, 'plugin_manager'):
                    manager = self.app.plugin_manager
                    state = manager.get_plugin_state(plugin_name)
                    if state is None:
                        return jsonify({
                            'success': False,
                            'error': f'Plugin {plugin_name} not found'
                        }), 404

                    # ensure application-level config is reloaded so plugin's
                    # _init_configuration() will see updated `config.toml` values
                    try:
                        if hasattr(self.app, 'reload_config'):
                            self.app.reload_config()
                    except Exception:
                        self.app.mylogger.warning('App config reload failed prior to plugin reload')

                    success = manager.reload_plugin(plugin_name)
                    current_state = manager.get_plugin_state(plugin_name)
                else:
                    success = False
                    current_state = 'unknown'

                return jsonify({
                    'success': success,
                    'message': f'Plugin {plugin_name} reload {"successful" if success else "failed"}',
                    'plugin_name': plugin_name,
                    'state': current_state
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/api/plugins/<plugin_name>/health', methods=['GET'])
        @policy_required(is_admin)
        def check_plugin_health(plugin_name: str):
            """Check plugin health."""
            try:
                plugin = None
                if hasattr(self.app, 'plugin_manager'):
                    manager = self.app.plugin_manager
                    state = manager.get_plugin_state(plugin_name)
                    if state is None:
                        return jsonify({
                            'success': False,
                            'error': 'Plugin not found'
                        }), 404
                    if state != 'active':
                        return jsonify({
                            'success': False,
                            'error': f'Plugin is {state}. Please start plugin first.',
                            'state': state,
                            'plugin_name': plugin_name
                        }), 409

                    plugin = manager.peek_plugin(plugin_name)
                elif plugin_name in self.app.plugins:
                    plugin = self.app.plugins[plugin_name]

                if not plugin:
                    return jsonify({
                        'success': False,
                        'error': 'Plugin not found'
                    }), 404

                if hasattr(plugin, 'health_check'):
                    health = plugin.health_check()
                    return jsonify({
                        'success': True,
                        'data': {
                            'healthy': health,
                            'plugin_name': plugin_name,
                            'state': 'active',
                            'check_time': datetime.now().isoformat()
                        }
                    })
                else:
                    return jsonify({
                        'success': True,
                        'data': {
                            'healthy': True,
                            'plugin_name': plugin_name,
                            'message': 'Health check not implemented'
                        }
                    })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/api/plugins/<plugin_name>/metrics', methods=['GET'])
        @policy_required(is_admin)
        def get_plugin_metrics(plugin_name: str):
            """Return plugin metrics."""
            try:
                plugin = None
                if hasattr(self.app, 'plugin_manager'):
                    manager = self.app.plugin_manager
                    state = manager.get_plugin_state(plugin_name)
                    if state is None:
                        return jsonify({
                            'success': False,
                            'error': 'Plugin not found'
                        }), 404
                    if state != 'active':
                        return jsonify({
                            'success': False,
                            'error': f'Plugin is {state}. Please start plugin first.',
                            'state': state,
                            'plugin_name': plugin_name
                        }), 409

                    plugin = manager.peek_plugin(plugin_name)
                elif plugin_name in self.app.plugins:
                    plugin = self.app.plugins[plugin_name]

                if not plugin:
                    return jsonify({
                        'success': False,
                        'error': 'Plugin not found'
                    }), 404

                if hasattr(plugin, 'metrics'):
                    metrics = plugin.metrics
                    return jsonify({
                        'success': True,
                        'data': {
                            'plugin_name': plugin_name,
                            'metrics': metrics,
                            'state': 'active',
                            'timestamp': datetime.now().isoformat()
                        }
                    })
                else:
                    return jsonify({
                        'success': True,
                        'data': {
                            'plugin_name': plugin_name,
                            'metrics': {},
                            'message': 'Metrics not available'
                        }
                    })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/api/cache/clear', methods=['POST'])
        @policy_required(is_admin)
        def clear_plugin_cache():
            """Clear the plugin metadata cache."""
            try:
                if hasattr(self.app, 'plugin_manager') and hasattr(self.app.plugin_manager, 'plugin_loader'):
                    self.app.plugin_manager.plugin_loader.cache.invalidate_cache()
                    return jsonify({
                        'success': True,
                        'message': 'Plugin cache cleared successfully'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Plugin cache not available'
                    })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/management')
        @policy_required(is_admin)
        def plugin_management():
            """Render the plugin management dashboard."""
            # Gather plugin statistics for the dashboard.
            try:
                self.app.mylogger.debug("Starting plugin_management route")
                if hasattr(self.app, 'plugin_manager'):
                    self.app.mylogger.debug("Using plugin_manager for stats")
                    stats = self.app.plugin_manager.get_plugin_stats()
                    self.app.mylogger.debug(f"plugin_manager stats: {stats}")
                else:
                    self.app.mylogger.debug("Using legacy stats collection")
                    stats = self._collect_legacy_plugin_stats()
                    self.app.mylogger.debug(f"legacy stats: {stats}")

                # Format timestamps and refresh aggregate counters.
                if 'plugins' in stats:
                    # Recompute aggregate counters.
                    unloaded_count = 0
                    loaded_count = 0
                    active_count = 0
                    error_count = 0

                    for plugin_name, plugin_info in stats['plugins'].items():
                        # Format last-access timestamps.
                        if plugin_info.get('last_access'):
                            try:
                                last_access_dt = datetime.fromtimestamp(plugin_info['last_access'])
                                plugin_info['last_access_formatted'] = last_access_dt.strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                plugin_info['last_access_formatted'] = 'Invalid timestamp'
                        else:
                            plugin_info['last_access_formatted'] = '-'

                        # Refresh counters by plugin state.
                        state = plugin_info.get('state', 'unknown')
                        if state == 'unloaded':
                            unloaded_count += 1
                        elif state == 'loaded':
                            loaded_count += 1
                        elif state == 'active':
                            active_count += 1
                        elif state == 'error':
                            error_count += 1

                    # Update summary totals.
                    stats['unloaded_plugins'] = unloaded_count
                    stats['loaded_plugins'] = loaded_count
                    stats['active_plugins'] = active_count
                    stats['error_plugins'] = error_count
                else:
                    # Initialize summary totals when detailed plugin data is absent.
                    stats['unloaded_plugins'] = 0
                    stats['loaded_plugins'] = 0

                # Render the dashboard template.
                return render_template('plugin_management.html',
                                     stats=stats,
                                     current_time=datetime.now().isoformat())
            except Exception as e:
                self.app.mylogger.error(f"ERROR in plugin_management: {e}")
                import traceback
                self.app.mylogger.error(f"Traceback: {traceback.format_exc()}")
                return f"Error: {e}", 500

    def _collect_legacy_plugin_stats(self):
        """Compatibility helper that gathers stats from the legacy plugin registry."""
        plugins = {}
        for name, plugin in self.app.plugins.items():
            plugins[name] = {
                'state': 'active',
                'load_time': None,
                'error_message': None,
                'last_access': None
            }

        return {
            'total_plugins': len(self.app.plugins),
            'active_plugins': len(self.app.plugins),
            'lazy_plugins': 0,
            'error_plugins': 0,
            'plugins': plugins
        }

    def setup_menus(self):
        """Register the plugin-management menu entry."""
        from funlab.core.menu import MenuItem
        super().setup_menus()

        # Add the plugin-management item to the main menu for administrators.
        plugin_mgmt_item = MenuItem(
            title='Plugin Management',
            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-plug" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"></path><path d="M9.785 6l8.215 8.215l-2.054 2.054a5.81 5.81 0 1 1 -8.215 -8.215l2.054 -2.054z"></path><path d="M4 20l3.5 -3.5"></path><path d="M15 4l-3.5 3.5"></path><path d="M20 9l-3.5 3.5"></path></svg>',
            href='/plugin-manager/management',
            required_policy=is_admin,
        )

        # Append directly to the main menu; accessibility checks are handled by ``required_policy``.
        try:
            self.app.append_mainmenu([plugin_mgmt_item])
            self.mylogger.info("Plugin Management menu added to main menu")
        except Exception as e:
            self.mylogger.error(f"Failed to add plugin management menu item to main menu: {e}")
