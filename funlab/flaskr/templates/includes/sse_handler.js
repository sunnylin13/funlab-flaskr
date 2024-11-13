// sse_handler.js

function subscribeToEvent(eventType, renderFunction) {
    const eventSource = new EventSource(`/sse/${eventType}`);
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        renderFunction(data, eventType);
    };

    eventSource.onerror = function(event) {
        console.error("EventSource failed:", event);
    };

    window.addEventListener('beforeunload', function() {
        eventSource.close();
    });
}

function renderNotification(data, elementId) {
    const eventDiv = document.createElement('div');
    eventDiv.classList.add('list-group-item');
    eventDiv.innerHTML = `
        <div class="row align-items-center">
            <div class="col-auto"><span class="status-dot status-dot-animated bg-red d-block"></span></div>
            <div class="col text-truncate">
                <a href="#" class="text-body d-block">${data.payload.title}</a>
                <div class="d-block text-muted text-truncate mt-n1">
                    ${data.payload.message}
                </div>
            </div>
            <div class="col-auto">
                <a href="#" class="list-group-item-actions">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon text-muted" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                        <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                        <path d="M12 17.75l-6.172 3.245l1.179 -6.873l-5 -4.867l6.9 -1l3.086 -6.253l3.086 6.253l6.9 1l-5 4.867l1.179 6.873z"/>
                    </svg>
                </a>
            </div>
        </div>
    `;
    document.getElementById(elementId).appendChild(eventDiv);
}