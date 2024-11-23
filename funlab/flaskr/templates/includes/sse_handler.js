
function subscribeToEvent(eventType, renderFunction) {
    // Create a new EventSource instance to connect to the SSE endpoint
    const eventSource = new EventSource(`/sse/${eventType}`);
    //console.log("sbucribeToEvent called with eventType:", eventType);
    // Add event listener for eventType, e.g. 'SystemNotification' events
    eventSource.addEventListener(eventType, function(event) {
        console.log('SSE message received:', event);
        const data = JSON.parse(event.data);
        renderFunction(data, eventType);
    });

    // onmessage is forSSE no event type message received
    // eventSource.onmessage = function(event) {
    //     if (event.data === "heartbeat") {
    //         console.log("Received heartbeat");
    //         return;
    //     }
    //     console.log("Received event data:", event.data);
    //     const data = JSON.parse(event.data);
    //     renderFunction(data, eventType);
    // };

    eventSource.onerror = function(event) {
        console.error("SSE connection error:", event);
    };

    window.addEventListener('beforeunload', function() {
        eventSource.close();
    });
    // Log connection open
    // eventSource.onopen = function(event) {
    //     console.log('SSE connection opened:', event);
    // };
}

// Create a new EventSource instance to connect to the SSE endpoint
// const eventSource = new EventSource('/sse/SystemNotification');

