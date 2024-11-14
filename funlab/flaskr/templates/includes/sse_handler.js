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

