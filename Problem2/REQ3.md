# Introduction

## Purpose
This document provides complete software requirements specifications for the Seats Reservation system. SeatsReservation is a specialized management tool designed for event companies to automate seat booking for various events. The primary goals of the program are listed below:

- **G-01** - The system shall manage a rectangular seating grid for various events.
- **G-02** - The system should handle both numbered and non-numbered seating configurations.
- **G-03** - The system shall accurately calculate dynamic ticket prices based on timing and seat category.
- **G-04** - SeatsReservation system must ensure the integrity of the reservation process.

## Scope

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


## Product overview

### Product perspective
Product overview can be described using a domain class diagram as a conceptual model of entities and relations between them in the SeatsReservation. The diagram does not determine the class for implementation.

    classDiagram
        class AnyUser {
            +user_id
        }
        class User {
        }
        class Administrator {
        }
        class Reservation {
            +reservation_id
            +user_id
            +event_id
            +status
            +create_time
            +expire_time
        }
        class ReservationSeat {
            +reservation_id
            +seat_id
        }
        class Event {
            +event_id
            +event_date
            +rows
            +columns
            +has_numbered_seats
        }
        class Seat {
            +seat_id
            +event_id
            +row_number
            +column_number
            +category
        }
        class EventPricing {
            +event_id
            +category
            +base_price
        }
    
        AnyUser <|-- User
        AnyUser <|-- Administrator
    
        Administrator "1" -- "0..*" Event : creates
        User "1" -- "0..*" Reservation : creates
        
        Reservation "0..*" -- "1" Event : for
        Reservation "1" -- "1..*" ReservationSeat : includes
        
        ReservationSeat "0..*" -- "1" Seat : included in
        
        Event "1" -- "1..*" Seat : has
        Event "1" -- "1..*" EventPricing : defines

### Product functions

    stateDiagram-v2
        [*] --> Pending : pending count < 2 and\nseats available
        
        Pending --> Released : timer expired
        Pending --> Released : user abandons (dashed)
        Pending --> Confirmed : payment confirmed
        
        Confirmed --> Cancelled : user cancels
        Confirmed --> [*] : event occurs
        
        Released --> [*]
        Cancelled --> [*]

### User characteristics
The system serves two distinct types of users:
- **Administrators** - Employees of the event management company. They are expected to have a full understanding of the business rules regarding pricing and seating layouts. They want to have a tool for simple and effective event setup and monitoring of sales performance.
- **Custormers** - Individuals interested in attending events. They range from casual users to frequent attendees. They require a clear interface for seat selection and a reliable reservation process. They must be aware of the app limitations.


### Limitations
- **L-01** - Web Application - The system operates exclusively as a web application. 
- **L-02** - No Mixed Seat Configuration - Within a single event, all seats must be either numbered or non-numbered. Mixed configurations are not supported.
- **L-03** - Two Interfaces - The system provides exactly two separate interfaces: one for administrators and one for users. No other access roles or interfaces are supported.


## Definitions
- Seat Category - a classification that determines the base price and relative price floor for a seat. Possible classes are: VIP, Premium, and Economy
- Numbered event - an event where seats have specific row and column coordinates.
- Non-numbered event - an event where seats are sold from a pool without specific physical placement requirements.
- Early Bird - a pricing period occurring more than 30 days before the event.
- Last Minute - a pricing period occurring less than 48 hours before the event.
- Atomicity - 


# Requirements

## Functions

**Functional requirements for the SeatsReservation problem are listed below.**


### FR-01 - Event Lifecycle and Configuration
The system shall enable the Administrator to fully define an event's environment, including its name, date and time, and a fixed-size rectangular seating grid. During setup, the system must enforce a uniform event type: strictly numbered or non-numbered, and ensure that seats have a category assigned (VIP, Premium, or Economy) and a corresponding base price.

### FR-02 - Reservation Logic
The SeatsReservation system should manage the complete reservation lifecycle by processing booking requests as atomic transactions. It must strictly enforce seat adjacency for numbered events and limit each user to a maximum of two concurrent 15-minute pending locks. If payment is not confirmed within this window, the system must revert seats to the available pool.

### FR-03 - Pricing engine
The system shall automatically calculate the final ticket price at the moment of reservation by applying time-based rules: an Early Bird discount of 20% for booking at least 30 days in advance, and a Last Minute surcharge of 30% for booking less than 48 hours before the event and at events with occupancy sold less than 80%. Throughout these calculations, the system must maintain a strict financial hierarchy, ensuring that the effective price of a VIP ticket is always greater then a Premimum ticket and the Premium ticket price is always greater then Ecomony.

### FR-04 - Administration
The SeatsReservation program must allow users to cancel confirmed reservations up until 2 hours before the event start and provide comprehensive status reports for both roles, such as real-time occupancy and revenue summaries for administrators and personal booking histories for users.

## Performance requirements
- The program shall process reservation requests in under 200ms.
- It must maintain strict data integrity and prevent race conditions for at least 50 concurrent users per event.
- The system shall support the management of 100 active events with seating grids up to 250,000 units (500x500).
- The automated 15-minute expiration logic for Pending reservations must operate with a maximum drift of 5 seconds.

## Usability requirements
- The system shall provide a clear, graphical representation of the seating grid. Available, and reserved seats must be distinguishable through color-coding.
- During the reservation process, the system shall display a real-time countdown timer for the 15-minute interval.
- The breakdown of the final reservation price should be shown before the user proceeds to the payment stage.

## Interface requirements

The Administrator desktop module should include a dedicated interface for event management. Key views must include:
- Event creator - form for entering event metadata and grid dimensions.
- Grid configuratior - interactive tool for category assignment and base price setting.
- Dashboard - real-time summary of occupancy and financial performance per event.

A customer desktop module as a dedicated interface for seat booking should include views such as:
- Event browser - a list of upcoming events with search/filter capabilities
- Booking view - an interactive grid for seat selection and adjacency validation.
- Reservation manager - personal dashboard for tracking payment status and performing cancellations.

Both the customer's and administrator's panels should be accessible through the same login panel, where the user can switch between user and administaror roles and provide cradentials.

## Logical database requirements
The system shall maintain a persistent data model to ensure consistency across appliacation restarts. The logical schema is presented below thourgh entity relationship diagram:

ERD

## Design constraints

## Software system attributes

### Reliability
Seat state transitions must not result in data inconsistency even under concurrent access. No seat shall belong to more than one active reservation at any point in time.

### Security
Administrative functions must be protected from unauthorized access by standard authentication mechanisms.

### Maintainability
The system should be implemented in a way that is easy to scale, maintain, and test. The code must remain readable, maintainable, and documented.

### Portability
The web application shall be compatible with modern web browsers (e.g., Google Chrome, Mozilla Firefox, Microsoft Edge, and Safari).


# Verification
SeatsReseration shall be verified through a combination of tests and inspections.

# Appendices

## Assumptions and dependencies

### Domain assumptions
- **DA-01** - The system clock on the host machine is considered the source of truth for all time-based calculations.
- **DA-02** - A month for the discounts is defined as exactly 30 calendar days.
- **DA-03** - Payment confirmation is provided by an external signal or simulated user action.

## Acronyms and abbreviations
- VIP - Very Important Person (highest seat category)
- G - Goal
- SP - Shared Phenomena
- WP - World Phenomena
- FR - Functional Requirements
- DA - Domain Assumption
