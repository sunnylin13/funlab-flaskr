/**
 * FunLab Notification Manager - Polling Mode
 *
 * Handles polling-based notification display for the FunLab application.
 * Reads runtime config from window.FUNLAB_CONFIG (injected by notification_init.html).
 *
 * Notification lifecycle (Polling / NotificationStore mode)
 * ─────────────────────────────────────────────────────────
 *   New :  periodic fetch /notifications/poll → is_recovered=false → Toast + Banner
 *   Reload: same fetch → server tags already-delivered items with is_recovered=true
 *           → Banner restored, NO Toast re-popup
 *   Dismiss single : POST /notifications/dismiss {ids:[id]}
 *   Clear all      : POST /notifications/clear
 */
document.addEventListener('DOMContentLoaded', function () {
    // -----------------------------------------------------------------------
    // 1. Ensure toast container exists
    // -----------------------------------------------------------------------
    let toastContainer = document.getElementById('notification-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'notification-container';
        document.body.appendChild(toastContainer);
    }

    // -----------------------------------------------------------------------
    // 2. Grab banner notification elements
    // -----------------------------------------------------------------------
    const bannerNotificationArea = document.getElementById('SystemNotification');
    const notificationBadge      = document.getElementById('notification-badge');
    const notificationFooter     = document.getElementById('notification-footer');
    const notificationDropdownToggle = bannerNotificationArea
        ? bannerNotificationArea.closest('.dropdown-menu').previousElementSibling
        : null;

    let unreadCount          = 0;
    let isAddingNotification = false;

    // Prevent dropdown from opening while programmatically adding notifications
    if (notificationDropdownToggle) {
        notificationDropdownToggle.addEventListener('show.bs.dropdown', function (event) {
            if (isAddingNotification) event.preventDefault();
        });
    }

    // -----------------------------------------------------------------------
    // 3. Badge & footer helpers
    // -----------------------------------------------------------------------
    function updateNotificationBadge() {
        if (!notificationBadge) return;
        if (unreadCount > 0) {
            notificationBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
            notificationBadge.classList.remove('d-none');
        } else {
            notificationBadge.classList.add('d-none');
        }
    }

    function updateFooterVisibility() {
        if (!notificationFooter) return;
        notificationFooter.classList.toggle('d-none', unreadCount <= 0);
    }

    // -----------------------------------------------------------------------
    // 4. Unified render function
    //
    //    is_recovered (server-set):
    //      false → brand-new notification  → Toast + Banner
    //      true  → already delivered before (page reload recovery) → Banner only
    // -----------------------------------------------------------------------
    function renderNotification(data /*, eventType */) {
        const isRecovered  = data.is_recovered || false;
        const isPersistent = data.is_persistent !== false;
        const payload      = data.payload;
        const eventId      = data.id;

        if (!eventId) {
            console.warn('[Notification] Event has no ID, skipping.', data);
            return;
        }

        // Avoid adding the same notification twice
        if (bannerNotificationArea &&
                bannerNotificationArea.querySelector(`[data-event-id="${eventId}"]`)) {
            return;
        }

        unreadCount++;
        updateNotificationBadge();
        updateFooterVisibility();

        // A. Toast – only for fresh (non-recovered) notifications
        if (!isRecovered) {
            _showToast(data, payload, eventId);
        }

        // B. Banner drop-down item – always
        if (bannerNotificationArea) {
            _addBannerItem(data, payload, eventId, isPersistent);
        }
    }

    function _showToast(data, payload, eventId) {
        const toastNotif = document.createElement('div');
        toastNotif.className = 'toast-notification';
        toastNotif.dataset.eventId = eventId;

        if (data.priority === 'HIGH' || data.priority === 'CRITICAL') {
            toastNotif.classList.add('high-priority');
        }

        const toastContent = document.createElement('div');
        toastContent.className = 'toast-content';
        toastContent.innerHTML = `<h5>${payload.title}</h5><p>${payload.message}</p>`;

        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close-btn';
        closeBtn.innerHTML = '&times;';
        closeBtn.setAttribute('aria-label', 'Close notification');
        closeBtn.onclick = function () {
            toastNotif.style.opacity = '0';
            toastNotif.style.transform = 'translateX(100%)';
            setTimeout(() => toastNotif.remove(), 400);
        };

        toastNotif.appendChild(toastContent);
        toastNotif.appendChild(closeBtn);
        toastContainer.prepend(toastNotif);

        // Auto-dismiss after 3 s
        setTimeout(() => {
            if (toastNotif.parentElement) closeBtn.onclick();
        }, 3000);
    }

    function _addBannerItem(data, payload, eventId, isPersistent) {
        const isHighPriority = data.priority === 'HIGH' || data.priority === 'CRITICAL';
        const dotClass = isHighPriority ? 'status-dot-animated bg-red' : 'bg-blue';

        const listItem = document.createElement('div');
        listItem.className = 'list-group-item';
        listItem.dataset.eventId      = eventId;
        listItem.dataset.isPersistent = isPersistent ? '1' : '0';
        listItem.innerHTML = `
            <div class="row align-items-center">
                <div class="col-auto">
                    <span class="status-dot ${dotClass} d-block"></span>
                </div>
                <div class="col text-truncate">
                    <a href="#" class="text-body d-block">${payload.title}</a>
                    <div class="d-block text-muted text-truncate mt-n1">${payload.message}</div>
                </div>
                <div class="col-auto">
                    <a href="#" class="list-group-item-actions"
                       onclick="FunlabNotifications.closeBannerItem(event, this, '${eventId}')">
                        <svg xmlns="http://www.w3.org/2000/svg" class="icon text-muted"
                             width="24" height="24" viewBox="0 0 24 24"
                             stroke-width="2" stroke="currentColor" fill="none"
                             stroke-linecap="round" stroke-linejoin="round">
                            <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                            <path d="M18 6l-12 12M6 6l12 12"/>
                        </svg>
                    </a>
                </div>
            </div>`;
        bannerNotificationArea.insertBefore(listItem, bannerNotificationArea.firstChild);
    }

    // -----------------------------------------------------------------------
    // 5. Server dismiss helpers (polling mode)
    // -----------------------------------------------------------------------
    function _serverDismissItems(ids) {
        return fetch('/notifications/dismiss', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids }),
        }).catch(err => console.error('[Notification] dismiss failed:', err));
    }

    function _serverClearAll() {
        return fetch('/notifications/clear', { method: 'POST' })
            .catch(err => console.error('[Notification] clear failed:', err));
    }

    // -----------------------------------------------------------------------
    // 6. Public API (attached to window for inline onclick handlers)
    // -----------------------------------------------------------------------
    window.FunlabNotifications = {

        /** Close a single banner item and remove it from the server */
        closeBannerItem: function (event, element, eventId) {
            event.preventDefault();
            event.stopPropagation();

            const listItem     = element.closest('.list-group-item');

            if (listItem) {
                listItem.remove();
                unreadCount = Math.max(0, unreadCount - 1);
                updateNotificationBadge();
                updateFooterVisibility();
            }

            if (!eventId) return;

            // Polling mode: dismiss via NotificationStore API
            _serverDismissItems([parseInt(eventId, 10)]);
        },

        /** Clear all banner notifications and remove them from the server */
        clearAll: function (event) {
            event.preventDefault();
            event.stopPropagation();

            if (!bannerNotificationArea) return;
            const listItems = bannerNotificationArea.querySelectorAll('.list-group-item');
            if (listItems.length === 0) return;

            bannerNotificationArea.innerHTML = '';
            unreadCount = 0;
            updateNotificationBadge();
            updateFooterVisibility();

            // Polling mode: single clear-all call
            _serverClearAll();
        },

        /** Expose renderNotification for external use (e.g., custom plugins) */
        render: renderNotification,
    };

    // -----------------------------------------------------------------------
    // 7. Polling mode: fetch unread on page load + periodic refresh
    //    is_recovered is set by the server, so recovered items won't show Toast.
    // -----------------------------------------------------------------------
    let pollingTimer = null;

    function fetchNotifications() {
        fetch('/notifications/poll')
            .then(resp => resp.ok ? resp.json() : [])
            .then(items => {
                if (!Array.isArray(items)) return;
                items.forEach(item => renderNotification(item));
            })
            .catch(err => console.error('[Notification] Polling failed:', err));
    }

    function startNotificationPolling() {
        if (pollingTimer) return;
        fetchNotifications();                               // immediate page-load recovery
        pollingTimer = setInterval(fetchNotifications, 15000);
    }

    // Start polling
    console.log('[Notification] Polling mode enabled.');
    startNotificationPolling();

    // -----------------------------------------------------------------------
    // 8. Initial UI sync
    // -----------------------------------------------------------------------
    updateNotificationBadge();
    updateFooterVisibility();
});
