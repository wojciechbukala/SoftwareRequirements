# 1. Introduction

## 1.1. Purpose
This document provides complete software requirements specifications for the Seats Reservation system. SeatsReservation is a specialized management tool designed for event companies to automate seat booking for various events. The primary goals of the program are listed below:

- **G-01** - The system shall manage a rectangular seating grid for various events.
- **G-02** - The system should handle both numbered and non-numbered seating configurations.
- **G-03** - The system shall accurately calculate dynamic ticket prices based on timing and seat category.
- **G-04** - SeatsReservation system must ensure the integrity of the reservation process.

## 1.2. Scope
The SeatsReservation program is focused on the logic of event management and reservation handling. It provides an interface for both administrators and users. World and shared phenomena of the system environment are defined as listed below.

### World Phenomenas
- **WP-01** - Real-world events with specified dates and seating layout.
- **WP-02** - Seats as physical locations within a venue with an assigned category.
- **WP-03** - Customers as individuals attempting to reserve seats and perform payment.
- **WP-04** - The progression of time, which triggers discounts and expiration of pending reservations.

### Shared phenomenas:
**Interactions controlled by the world**:
- **SP-01** - Creation of events and seating grids by the administrator.
- **SP-02** - Seat selection and reservation request from user.
- **SP-03** - Payment confirmation or abandonment from user.

**Interactions controlled by the machine**:
- **SP-04** - Dynamic calculation and display to the final seat price.
- **SP-05** - Updates to seat availability.


## 1.3. Product overview

### 1.3.1. Product perspective
Product overview can be described using a domain class diagram as a conceptual model of entities and relations between them in the SeatsReservation. The diagram does not determine the class for implementation.

    classDiagram
        class AnyUser {
            +user_id
        }
        class User {
        }
        class Administrator {
        }

        AnyUser <|-- User
        AnyUser <|-- Administrator

        class Event {
            +event_id
            +event_date
            +name
            +location
            +rows
            +columns
            +has_numbered_seats
        }

        class EventPricing {
            +event_id
            +category
            +base_price
        }

        class Reservation {
            +reservation_id
            +user_id
            +event_id
            +status
            +create_time
            +expire_time
        }

        class Seat {
            +seat_id
            +event_id
            +row_number
            +column_number
            +category
        }

        Administrator "1" -- "0..*" Event : creates
        User "1" -- "0..*" Reservation : creates
        Event "1" -- "1..*" EventPricing : defines
        Event "1" -- "0..*" Reservation : for
        Event "1" -- "1..*" Seat : has
        Reservation "0..1" -- "1..*" Seat : includes

### 1.3.2. Product functions

### 1.3.3. User characteristics
The system serves two distinct types of users:
- **Administrators** - Employees of the event management company. They are expected to have a full understanding of the business rules regarding pricing and seating layouts. They want to have a tool for simple and effective event setup and monitoring of sales performance.
- **Custormers** - Individuals interested in attending events. They range from casual users to frequent attendees. They require a clear interface for seat selection and a reliable reservation process. They must be aware of the app limitations.


### 1.3.4. Limitations
- **L-01** - Web Application - The system operates exclusively as a web application. 
- **L-02** - No Mixed Seat Configuration - Within a single event, all seats must be either numbered or non-numbered. Mixed configurations are not supported.
- **L-03** - Two Interfaces - The system provides exactly two separate interfaces: one for administrators and one for users. No other access roles or interfaces are supported.


## 1.4. Definitions
- Seat Category - a classification that determines the base price and relative price floor for a seat. Possible classes are: VIP, Premium, and Economy
- Numbered event - an event where seats have specific row and column coordinates.
- Non-numbered event - an event where seats are sold from a pool without specific physical placement requirements.
- Early Bird - a pricing period occurring more than 30 days before the event.
- Last Minute - a pricing period occurring less than 48 hours before the event.

# 2. References
The only reference is CONTEXT-SeatsReservation.md file with the task description, in the form as received from stakeholders.

# 3. Requirements

## 3.1. Functions - Functional Requirements
Functional requirements for the SeatsReservation problem are listed below.

### FR-01 - Event Lifecycle and Configuration
The system shall enable the Administrator to fully define an event's environment, including its name, date and time, and a fixed-size rectangular seating grid. During setup, the system must enforce a uniform event type: strictly numbered or non-numbered, and ensure that seats have a category assigned (VIP, Premium, or Economy) and a corresponding base price.

### FR-02 - Reservation Logic
The SeatsReservation system should manage the complete reservation lifecycle by processing booking requests as atomic transactions. It must strictly enforce seat adjacency for numbered events and limit each user to a maximum of two concurrent 15-minute pending locks. If payment is not confirmed within this window, the system must revert seats to the available pool.

### FR-03 - Pricing engine
The system shall automatically calculate the final ticket price at the moment of reservation by applying time-based rules: an Early Bird discount of 20% for booking at least 30 days in advance, and a Last Minute surcharge of 30% for booking less than 48 hours before the event and at events with occupancy sold less than 80%. Throughout these calculations, the system must maintain a strict financial hierarchy, ensuring that the effective price of a VIP ticket is always greater then a Premimum ticket and the Premium ticket price is always greater then Ecomony.

### FR-04 - Administration
The SeatsReservation program must allow users to cancel confirmed reservations up until 2 hours before the event start and provide comprehensive status reports for both roles, such as real-time occupancy and revenue summaries for administrators and personal booking histories for users.

## 3.2. Functions - Use cases
Actors and their use cases includend in the system evironment can be described by the use cases diagram as below: 
    graph LR
    User((User))
    Admin((Administrator))
    PaymentService((External payment service))

    subgraph "SeatsReservation System"
        UC1(User Registration)
        UC2(User Login)
        UC3(Reserve seats)
        UC4(Confirm payment)
        UC5(Cancel reservation)
        UC6(Browse events)
        UC7(View personal bookings)

        UC8(Log in to Admin Interface)
        UC9(Create event)
        UC10(Configure seating grid)
        UC11(Set base prices)
        UC12(View reservation summary)
    end

    User -- "<<initiate>>" --> UC1
    User -- "<<initiate>>" --> UC2
    User -- "<<initiate>>" --> UC3
    User -- "<<participate>>" --> UC4
    User -- "<<initiate>>" --> UC5
    User -- "<<initiate>>" --> UC6
    User -- "<<initiate>>" --> UC7

    Admin -- "<<initiate>>" --> UC8
    Admin -- "<<initiate>>" --> UC9
    Admin -- "<<initiate>>" --> UC10
    Admin -- "<<initiate>>" --> UC11
    Admin -- "<<initiate>>" --> UC12

    UC3 -- "<<participate>>" --- PaymentService
    PaymentService -- "<<initiate>>" --> UC4
    UC5 -- "<<participate>>" --- PaymentService

## UC-01 - Make reservation
The main functionality of the system is the possibility to reserve a seat by a user for a specified event. Process is presented with the usage of 3 sequence diagrams. The split was made to make a clear distingush between numbered and nonnumbered events.

Seqence diagram - user selects event form the list displayed on the website:
    sequenceDiagram
    actor User
    participant RS as ReservationService
    participant Repository as SeatsRepository

    User->+RS: getEventInfo(eventId)
    RS->+Repository: fetchEventInfo(eventId)
    Repository-->>-RS: event(has_numbered_seats, date)

    alt has_numbered_seats = true
        RS->+Repository: fetchSeatsGrid(eventId)
        Repository-->>-RS: seats[] with status
        RS-->>User: render_seat_grid()
        Note over User, Repository: ref: Reserve seats - numbered
    else has_numbered_seats = false
        RS->+Repository: fetchPool(eventId)
        Repository-->>-RS: category_and_available_quantity[]
        RS-->>User: render_category_picker()
        Note over User, Repository: ref: Reserve seats - unnumbered
    end

If event is numbered, the process of reservation and confirmation looks as provided below:
    sequenceDiagram
    actor User
    participant RS as ReservationService
    participant Repository as SeatsRepository
    participant Timer

    loop selection
        User->+RS: click seat
        alt seat unavailable or not adjacent
            RS-->>User: ignore click
        else else
            RS-->>-User: update_selection_view()
        end
    end

    User->+RS: confirm selection
    alt pending count >= 2
        RS-->>User: error: limit reached, abort
    else else
        RS->+Repository: lockSeats(userId, seatIds[])
        Repository-->>-RS: seats_locked
        RS->+Repository: getSeatsInfo(seatIds[])
        Repository-->>-RS: seats_info
        RS->RS: calculatePrice(seats_info)
        RS->+Timer: startTimer()
        RS-->>User: reservation_info(seats[], prices[], price, expires_at)
        User->RS: proceed to payment
        RS-->>-User: redirect to payment service
    end

    alt payment confirmed within 15 minutes
        User->+RS: confirmPayment(reservationId)
        RS->+Repository: updateStatus(seatIds[], CONFIRMED)
        RS->+Timer: stopTimer()
        RS-->>-User: reservation confirmed
    else timer expired - no payment
        Timer->>+RS: timerExpired()
        RS->+Repository: updateStatus(seatIds[], AVAILABLE)
        RS-->>-User: reservation canceled
    end

Otherwise, if the event is nonnumbered, the seqence looks like that:
    sequenceDiagram
    actor User
    participant RS as ReservationService
    participant Repository as SeatsRepository
    participant Timer

    User->+RS: select category + quantity
    RS-->>-User: update picker
    
    User->+RS: confirm selection
    RS->+Repository: lockSeats(eventId, category, quantity)
    
    opt quantity and category unavailable
        Repository-->>RS: insufficient seats error
        RS-->>User: lack of seats signal
    end

    Repository-->>-RS: seats_locked
    
    RS->RS: calculatePrice(quantity, category)
    RS->+Timer: startTimer()
    RS-->>User: reservation_info(quantity, category, price, expires_at)
    
    User->RS: proceed to payment
    RS-->>-User: redirect to payment service

    alt payment confirmed within 15 minutes
        User->+RS: confirmPayment(reservationId)
        RS->+Repository: updateAvailability(quantity, category, UNAVAILABLE)
        RS->+Timer: stopTimer()
        RS-->>-User: reservation confirmed
    else timer expired - no payment
        Timer->>+RS: timerExpired()
        RS->+Repository: updateAvailability(quantity, category, AVAILABLE)
        RS-->>-User: reservation canceled
    end

## UC-02 - Cancel reservation
Other key use case of the ystem is the possibility for a user to cancel reservation, presented at the sequence diagram below:
    sequenceDiagram
    actor User
    participant RS as ReservationService
    participant Repository as SeatsRepository

    User->+RS: cancel_reservation(reservationId)
    RS->+Repository: fetchReservation(reservationId)
    Repository-->>-RS: reservation(status, event_date, userId)

    alt userId matches and status = Confirmed and now <= event_date -2h
        RS->+Repository: releaseSeats(reservationId)
        RS->+Repository: updateStatus(CANCELED)
        Repository-->>-RS: done
        RS-->>User: update view
    else userId != reservation.userId
        RS-->>Repository: error: unauthorized
        RS-->>User: display error message
    else status != Confirmed
        RS-->>Repository: error: reservation not confirmed
        RS-->>User: display error message
    else now > event_date -2h
        RS-->>Repository: error: cancellation window closed
        RS-->>-User: display error message
    end

## UC-03 - Add event
THe key functionality of the administarot is the possibilibty to add an event, as presented below:
    sequenceDiagram
        actor Admin as Administrator
        participant RS as ReservationService
        participant Repository as SeatsRepository

        Admin->+RS: submitMetadata(name, date, type, rows, cols)
        RS->+Repository: validateEvent(name, date, type)
        
        opt event already exist or has data error
            Repository-->>RS: validation error
            RS-->>Admin: validation error
        end

        Repository-->>-RS: validation_ok

        alt numbered event
            RS-->>Admin: render_grid_configurator
            Admin->+RS: assign_category_per_seat(interactive_grid)
            RS->RS: validation
            RS-->>-Admin: validation_info
        else nonnumbered event
            RS-->>Admin: render_pool_configurator
            Admin->+RS: assign_category_per_pool(qty_per_category)
            RS->RS: validation
            RS-->>-Admin: validation_info
        end

        Admin->+RS: submit_base_price(VIP, Premium, Economy)
        RS->RS: validation
        RS-->>-Admin: validation_info

        alt all validations passed
            Admin->+RS: confirm creation
            RS->+Repository: createEvent(metadata, seats, prices)
            Repository-->>-RS: eventId
            RS-->>-Admin: redirect_to_event_dashboard
        else else
            RS-->>Admin: retry information
        end


## 3.3. Performance requirements
- The program shall process reservation requests in under 200ms.
- It must maintain strict data integrity and prevent race conditions for at least 50 concurrent users per event.
- The system shall support the management of 100 active events with seating grids up to 250,000 units (500x500).
- The automated 15-minute expiration logic for Pending reservations must operate with a maximum drift of 5 seconds.

## 3.4. Usability requirements
- The system shall provide a clear, graphical representation of the seating grid. Available, and reserved seats must be distinguishable through color-coding.
- During the reservation process, the system shall display a real-time countdown timer for the 15-minute interval.
- The breakdown of the final reservation price should be shown before the user proceeds to the payment stage.

## 3.5. Interface requirements

The Administrator desktop module should include a dedicated interface for event management. Key views must include:
- Event creator - form for entering event metadata and grid dimensions.
- Grid configuratior - interactive tool for category assignment and base price setting.
- Dashboard - real-time summary of occupancy and financial performance per event.

A customer desktop module as a dedicated interface for seat booking should include views such as:
- Event browser - a list of upcoming events with search/filter capabilities
- Booking view - an interactive grid for seat selection and adjacency validation.
- Reservation manager - personal dashboard for tracking payment status and performing cancellations.

Both the customer's and administrator's panels should be accessible through the same login panel, where the user can switch between user and administaror roles and provide cradentials.

## 3.6. Logical database requirements
The system shall maintain a persistent data model to ensure consistency across appliacation restarts. The logical schema is presented below thourgh entity relationship diagram:

    erDiagram
    User ||--o{ Event : "created_by"
    User ||--o{ Reservation : "makes"
    Event ||--|{ EventPricing : "defines"
    Event ||--o{ Reservation : "has"
    Event ||--o{ Seat : "has"
    Reservation ||--o{ Seat : "includes"

    User {
        uuid user_id PK
        varchar role
        varchar password_hash
    }

    Event {
        uuid event_id PK
        uuid created_by FK
        varchar name
        varchar location
        varchar description
        datetime date
        int rows
        int columns
        boolean is_numbered
    }

    EventPricing {
        uuid eventpricing_id PK
        uuid event_id FK
        varchar category
        decimal base_price
    }

    Reservation {
        uuid reservation_id PK
        uuid user_id FK
        uuid event_id FK
        varchar status
        datetime created_at
        datetime expires_at
    }

    Seat {
        uuid seat_id PK
        uuid event_id FK
        uuid reservation_id FK
        int row_number
        int column_number
        varchar category
    }

## 3.7. Design constraints
The key views of the system, including the login panel, the user interface, and the administrator panel, are presented in the form of mockups in UI_Mockups folder. All remaining views not depicted here shall follow the same graphical style — colour palette typography, proportions, component shapes, and interaction patterns — as established by the mockups. The web application is logically divided into three interfaces:

1. **Login / register panel** - the single netry point for all users. The panel allows users to authenticate or create an account. After successful login the system routes the user to the user or administrator interafce, based on the role. See mockup *LoginRegister.png*.
2. **User interface** - a panel accessible after login as a customer. Consists of the *Events* (a list of upcoming events) note that booking option for every event redirects to execution of 'make reservation' use case, *Bookings* (a history of user's bookings), *Profile* (profile details), *Settings* (application settings). See mockup *User.png*.
3. **Administrator interface** - a panel accessible after login as an administrator. Consists of the *Dashboard* (real-time overview of occupancy and revenue), *Events* (table of all managed events with appropriate options), *Event Creator* (defining event meatadata and execution of 'add event' use case).

## 3.8. Software system attributes

### Reliability
Seat state transitions must not result in data inconsistency even under concurrent access. No seat shall belong to more than one active reservation at any point in time.

### Security
Administrative functions must be protected from unauthorized access by standard authentication mechanisms.

### Maintainability
The system should be implemented in a way that is easy to scale, maintain, and test. The code must remain readable, maintainable, and documented.

### Portability
The web application shall be compatible with modern web browsers (e.g., Google Chrome, Mozilla Firefox, Microsoft Edge, and Safari).


# 4. Verification
SeatsReseration shall be verified through a combination of tests and inspections.

# 5. Appendices

## 5.1. Assumptions and dependencies

### Domain assumptions
- **DA-01** - The system clock on the host machine is considered the source of truth for all time-based calculations.
- **DA-02** - A month for the discounts is defined as exactly 30 calendar days.
- **DA-03** - Payment confirmation is provided by an external signal or simulated user action.

## 5.2. Acronyms and abbreviations
- VIP - Very Important Person (highest seat category)
- G - Goal
- SP - Shared Phenomena
- WP - World Phenomena
- FR - Functional Requirements
- DA - Domain Assumption
