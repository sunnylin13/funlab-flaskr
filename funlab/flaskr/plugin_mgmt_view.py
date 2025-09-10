"""
Plugin Management API and Monitoring Interface
Plugin管理API和監控介面 - 整合版本
"""
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
from funlab.core.auth import admin_required
from funlab.core.plugin import ViewPlugin
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from funlab.flaskr.app import FunlabFlask


class PluginManagerView(ViewPlugin):
    """Plugin管理視圖 - 集成到主應用中"""

    def __init__(self, app: 'FunlabFlask', url_prefix: str = None):
        super().__init__(app, url_prefix or 'plugin-manager')
        self._register_routes()

    def _register_routes(self):
        """註冊管理路由"""
        @self._blueprint.route('/api/plugins', methods=['GET'])
        @admin_required
        def get_plugins():
            """獲取所有plugin資訊"""
            try:
                if hasattr(self.app, 'plugin_manager'):
                    stats = self.app.plugin_manager.get_plugin_stats()
                else:
                    # 向後相容：使用傳統方式收集擴充功能資訊
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
        @admin_required
        def load_plugin(plugin_name: str):
            """載入指定plugin（用於懶載入的擴充功能）"""
            try:
                if hasattr(self.app, 'plugin_manager'):
                    # 使用 get_plugin 方法來觸發懶載入
                    plugin_instance = self.app.plugin_manager.get_plugin(plugin_name)
                    success = plugin_instance is not None
                else:
                    success = False

                return jsonify({
                    'success': success,
                    'message': f'Plugin {plugin_name} load {"successful" if success else "failed"}'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/api/plugins/<plugin_name>/reload', methods=['POST'])
        @admin_required
        def reload_plugin(plugin_name: str):
            """重新載入指定plugin"""
            try:
                if hasattr(self.app, 'plugin_manager'):
                    success = self.app.plugin_manager.reload_plugin(plugin_name)
                else:
                    success = False

                return jsonify({
                    'success': success,
                    'message': f'Plugin {plugin_name} reload {"successful" if success else "failed"}'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self._blueprint.route('/api/plugins/<plugin_name>/health', methods=['GET'])
        @admin_required
        def check_plugin_health(plugin_name: str):
            """檢查plugin健康狀態"""
            try:
                plugin = None
                if hasattr(self.app, 'plugin_manager'):
                    plugin = self.app.plugin_manager.get_plugin(plugin_name)
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
        @admin_required
        def get_plugin_metrics(plugin_name: str):
            """獲取plugin效能指標"""
            try:
                plugin = None
                if hasattr(self.app, 'plugin_manager'):
                    plugin = self.app.plugin_manager.get_plugin(plugin_name)
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
        @admin_required
        def clear_plugin_cache():
            """清除plugin快取"""
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
        @admin_required
        def plugin_management():
            """Plugin管理頁面 - 整合到現有的dashboard架構"""
            # 收集擴充功能統計資訊
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

                # 格式化時間戳為可讀格式並重新計算統計數字
                if 'plugins' in stats:
                    # 重新計算正確的統計數字
                    unloaded_count = 0
                    loaded_count = 0
                    active_count = 0
                    error_count = 0

                    for plugin_name, plugin_info in stats['plugins'].items():
                        # 格式化時間戳
                        if plugin_info.get('last_access'):
                            try:
                                last_access_dt = datetime.fromtimestamp(plugin_info['last_access'])
                                plugin_info['last_access_formatted'] = last_access_dt.strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                plugin_info['last_access_formatted'] = 'Invalid timestamp'
                        else:
                            plugin_info['last_access_formatted'] = '-'

                        # 重新計算狀態統計
                        state = plugin_info.get('state', 'unknown')
                        if state == 'unloaded':
                            unloaded_count += 1
                        elif state == 'loaded':
                            loaded_count += 1
                        elif state == 'active':
                            active_count += 1
                        elif state == 'error':
                            error_count += 1

                    # 更新統計數字
                    stats['unloaded_plugins'] = unloaded_count
                    stats['loaded_plugins'] = loaded_count
                    stats['active_plugins'] = active_count
                    stats['error_plugins'] = error_count
                else:
                    # 如果沒有擴充功能數據，初始化統計
                    stats['unloaded_plugins'] = 0
                    stats['loaded_plugins'] = 0

                # 返回使用 plugin_management.html 模板的資料
                return render_template('plugin_management.html',
                                     stats=stats,
                                     current_time=datetime.now().isoformat())
            except Exception as e:
                self.app.mylogger.error(f"ERROR in plugin_management: {e}")
                import traceback
                self.app.mylogger.error(f"Traceback: {traceback.format_exc()}")
                return f"Error: {e}", 500

    def _collect_legacy_plugin_stats(self):
        """向後相容：收集傳統擴充功能系統的統計資訊"""
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
        """設置選單 - 整合到現有選單系統"""
        from funlab.core.menu import MenuItem
        super().setup_menus()

        # 添加擴充功能管理項目到主選單或用戶選單（管理員可見）
        plugin_mgmt_item = MenuItem(
            title='Plugin Management',
            icon='<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-plug" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"></path><path d="M9.785 6l8.215 8.215l-2.054 2.054a5.81 5.81 0 1 1 -8.215 -8.215l2.054 -2.054z"></path><path d="M4 20l3.5 -3.5"></path><path d="M15 4l-3.5 3.5"></path><path d="M20 9l-3.5 3.5"></path></svg>',
            href='/plugin-manager/management',
            admin_only=True
        )

        # 嘗試添加到 admin menu，如果不存在則添加到 user menu
        try:
            if hasattr(self.app, '_adminmenu') and self.app._adminmenu:
                self.app.append_adminmenu([plugin_mgmt_item])
            else:
                self.app.append_usermenu([plugin_mgmt_item])
        except Exception as e:
            self.mylogger.warning(f"Failed to add plugin management menu item: {e}")
            # 備用方案：直接添加到主選單
            try:
                self.app.append_mainmenu([plugin_mgmt_item])
            except Exception as e2:
                self.mylogger.error(f"Failed to add plugin management menu item to main menu: {e2}")
