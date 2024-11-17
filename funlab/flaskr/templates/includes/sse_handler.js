// sse_handler.js
function handleEvent(event) {
    const data = JSON.parse(event.data);
    const notificationDiv = document.getElementById('notifications');
    const notification = document.createElement('div');
    notification.innerHTML = `<strong>${data.title}</strong>: ${data.message}`;
    notificationDiv.appendChild(notification);
}

function subscribeToEvent(eventType, renderFunction) {
    // Create a new EventSource instance to connect to the SSE endpoint
    //const eventSource = new EventSource('/sse/SystemNotification');
    const eventSource = new EventSource(`/sse/${eventType}`);
    console.log("sbucribeToEvent called with eventType:", eventType);
    // Add event listener for 'SystemNotification' events
    eventSource.addEventListener('SystemNotification', handleEvent);
    eventSource.onmessage = function(event) {
        // Check if the message is a heartbeat
        if (event.data === "heartbeat") {
            console.log("Received heartbeat");
            return; // Ignore heartbeat messages
        }
        console.log("Received event data:", event.data);
        const data = JSON.parse(event.data);
        renderFunction(data, eventType);
    };

    eventSource.onerror = function(event) {
        console.error("SSE connection error:", event);
    };

    window.addEventListener('beforeunload', function() {
        eventSource.close();
    });
    // Log connection open
    eventSource.onopen = function(event) {
        console.log('SSE connection opened:', event);
    };

    // Log messages
    eventSource.onmessage = function(event) {
        console.log('SSE message received:', event);
    };

}



// Create a new EventSource instance to connect to the SSE endpoint
const eventSource = new EventSource('/sse/SystemNotification');

// Add event listener for 'SystemNotification' events
eventSource.addEventListener('SystemNotification', handleEvent);

// Handle connection errors
eventSource.onerror = function(event) {
    console.error('SSE connection error:', event);
};

// Log connection open
eventSource.onopen = function(event) {
    console.log('SSE connection opened:', event);
};

// Log messages
eventSource.onmessage = function(event) {
    console.log('SSE message received:', event);
};

// Handle form submission to trigger notification
document.getElementById('notificationForm').addEventListener('submit', function(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    fetch('/generate_notification', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        console.log('Notification sent:', data);
    })
    .catch(error => {
        console.error('Error sending notification:', error);
    });
});
