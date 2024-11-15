// sse_handler.js

function subscribeToEvent(eventType, renderFunction) {
    const eventSource = new EventSource(`/sse/${eventType}`);
    eventSource.onmessage = function(event) {
        // Check if the message is a heartbeat
        if (event.data === "heartbeat") {
            // console.log("Received heartbeat");
            return; // Ignore heartbeat messages
        }
        const data = JSON.parse(event.data);
        console.log("Received notitication:", data);
        renderFunction(data, eventType);
    };

    eventSource.onerror = function(event) {
        console.error("EventSource failed:", event);
    };

    window.addEventListener('beforeunload', function() {
        eventSource.close();
    });
}

