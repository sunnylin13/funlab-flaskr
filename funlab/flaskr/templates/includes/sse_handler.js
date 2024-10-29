function subscribeToEvent(eventType, elementId) {
    const eventSource = new EventSource(`/events/${eventType}`);
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        const eventDiv = document.createElement('div');
        eventDiv.textContent = `Event Type: ${data.event_type}, Data: ${JSON.stringify(data.payload)}`;
        document.getElementById(elementId).appendChild(eventDiv);
    };
}