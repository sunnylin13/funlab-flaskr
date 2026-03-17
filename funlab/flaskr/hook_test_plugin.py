from __future__ import annotations

from funlab.core.enhanced_plugin import EnhancedViewPlugin


class HookTestView(EnhancedViewPlugin):
    """Minimal plugin for validating HookManager integration."""

    def __init__(self, app, url_prefix=None):
        super().__init__(app, url_prefix)
        self._register_hooks()

    def _register_hooks(self) -> None:
        # View Hooks
        self.app.hook_manager.register_hook(
            "view_layouts_base_html_head",
            self._render_head_marker,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "view_layouts_base_content_top",
            self._render_content_marker,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "view_layouts_base_body_bottom",
            self._render_body_marker,
            priority=10,
            plugin_name=self.name,
        )

        # Controller Hooks
        self.app.hook_manager.register_hook(
            "controller_before_request",
            self._log_before_request,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "controller_after_request",
            self._log_after_request,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "controller_error_handler",
            self._log_error,
            priority=10,
            plugin_name=self.name,
        )

        # Plugin Lifecycle Hooks - Initialization
        self.app.hook_manager.register_hook(
            "plugin_after_init",
            self._log_plugin_init,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "plugin_service_init",
            self._log_plugin_init,
            priority=10,
            plugin_name=self.name,
        )

        # Plugin Lifecycle Hooks - Start/Stop
        self.app.hook_manager.register_hook(
            "plugin_before_start",
            self._log_plugin_lifecycle,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "plugin_after_start",
            self._log_plugin_lifecycle,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "plugin_before_stop",
            self._log_plugin_lifecycle,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "plugin_after_stop",
            self._log_plugin_lifecycle,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "plugin_before_reload",
            self._log_plugin_lifecycle,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "plugin_after_reload",
            self._log_plugin_lifecycle,
            priority=10,
            plugin_name=self.name,
        )

        # Model Hooks (示範用)
        self.app.hook_manager.register_hook(
            "model_before_save",
            self._log_model_operation,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "model_after_save",
            self._log_model_operation,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "model_after_create",
            self._log_model_operation,
            priority=10,
            plugin_name=self.name,
        )

        # Task Hooks (示範用)
        self.app.hook_manager.register_hook(
            "task_before_execute",
            self._log_task_execution,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "task_after_execute",
            self._log_task_execution,
            priority=10,
            plugin_name=self.name,
        )
        self.app.hook_manager.register_hook(
            "task_error",
            self._log_task_error,
            priority=10,
            plugin_name=self.name,
        )

    def _render_head_marker(self, context) -> str:
        return "<!-- hook_test:head -->"

    def _render_content_marker(self, context) -> str:
        return "<div style=\"display:none\" data-hook-test=\"content\"></div>"

    def _render_body_marker(self, context) -> str:
        return "<!-- hook_test:body -->"

    def _log_before_request(self, context) -> None:
        """Log before request hook execution."""
        self.mylogger.debug(f"Hook: controller_before_request - {context.get('request')}")

    def _log_after_request(self, context) -> None:
        """Log after request hook execution."""
        response = context.get('response')
        self.mylogger.debug(f"Hook: controller_after_request - status {response.status_code if response else 'N/A'}")

    def _log_error(self, context) -> None:
        """Log error handler hook execution."""
        error = context.get('error')
        self.mylogger.warning(f"Hook: controller_error_handler - {error}")

    def _log_plugin_lifecycle(self, context) -> None:
        """Log plugin lifecycle hook execution."""
        plugin = context.get('plugin')
        plugin_name = context.get('plugin_name', 'Unknown')
        self.mylogger.info(f"Hook: Plugin lifecycle event - {plugin_name} ({plugin.__class__.__name__ if plugin else 'N/A'})")

    def _log_plugin_init(self, context) -> None:
        """Log plugin initialization hook execution."""
        plugin = context.get('plugin')
        plugin_name = context.get('plugin_name', 'Unknown')
        event_type = context.get('event_type', 'init')
        self.mylogger.info(f"Hook: Plugin {event_type} - {plugin_name} ({plugin.__class__.__name__ if plugin else 'N/A'})")

    def _log_model_operation(self, context) -> None:
        """Log model operation hook execution."""
        model = context.get('model')
        model_class = context.get('model_class')
        is_new = context.get('is_new', False)
        self.mylogger.debug(
            f"Hook: Model operation - {model_class.__name__ if model_class else 'Unknown'} "
            f"({'create' if is_new else 'update'})"
        )

    def _log_task_execution(self, context) -> None:
        """Log task execution hook."""
        task = context.get('task')
        task_name = context.get('task_name', 'Unknown')
        result = context.get('result')
        self.mylogger.info(
            f"Hook: Task execution - {task_name} "
            f"(result: {result if result is not None else 'N/A'})"
        )

    def _log_task_error(self, context) -> None:
        """Log task error hook."""
        task = context.get('task')
        task_name = context.get('task_name', 'Unknown')
        error = context.get('error')
        self.mylogger.error(f"Hook: Task error - {task_name} - {error}")
