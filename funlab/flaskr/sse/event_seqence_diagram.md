``` mermaid
sequenceDiagram
    participant User
    participant Client
    participant Server
    participant EventManager
    participant ConnectionManager

    User->>Client: Submit form to create event
    Client->>Server: POST /create_custom_event
    Server->>EventManager: create_event('custom_event', payload, target_userid)
    EventManager->>EventManager: _store_event(event)
    EventManager->>EventManager: _put_event(event)
    EventManager->>EventManager: Event added to event_queue
    EventManager->>ConnectionManager: register_user_stream(user_id)
    ConnectionManager->>Client: Stream ID returned
    Client->>Server: GET /events
    Server->>ConnectionManager: Get user stream
    ConnectionManager->>Server: Return user stream
    Server->>Client: Stream events
    loop Event Distribution
        EventManager->>EventManager: _distribute_event(event)
        EventManager->>ConnectionManager: Get user streams
        ConnectionManager->>EventManager: Return user streams
        EventManager->>Client: Send event to user stream
    end
    Client->>Client: Display event on page
```