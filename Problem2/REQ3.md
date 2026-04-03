# Introduction

## Purpose
This documnet provides complete software requirements specification for the Seats Reservation system. SeatsReservation is a psecialized management tool designed for event companies to automate seat booking for various events. The primary goals of the program are listed below:

- **G-01** - The system shall manage a rectangular seating grid for varoius events.
- **G-02** - The system should hadle both numbered and non-numbered seating configurations.
- **G-03** - The system shall accurately calculate dynamic ticket prices based on timing and seat category.
- **G-04** - SeatsReservation system must ensure integrity of the reservation process.

## Scope

The SeatsReservation program is focused on the logic of event management and reservation handling. It provide interface for both administrators and users. World and shared phenomenas of the system envioronment are defined as listed below.

### World Phenomenas
- **WP-01** - Real-world events with specified dates and seating layout.
- **WP-02** - Seats as a physical locations within a venue with a assigned category.
- **WP-03** - Customers as individuals attempting to reserve seats and perform payment.
- **WP-04** - The progression of time which triggers discounts and expiration of pending reservations.

### Shared phenomenas:
Interactions controlled by the world:
- **SP-01** - Creation of events and seating grids by the administrator.
- **SP-02** - Seat selection and reservation request from user.
- **SP-03** - Payment confirmation or abandonmnet from user.

, and interactions controlled by the machine:
- **SP-04** - Dynamic calculation and display fo the final seat price.
- **SP-05** - Updates to seat availability.


## Product overview

### Product perspective
Product overview can be described using a domain class diagram as a conceptual model of entities and relations between them in the SeatsReservation. The diagram does not determine the class for implementation.

### Product functions

state machines

### User characteristics
The system serves two distinct types of users:
- **Administrators** - Employees of the event management company. They are expected to have a full understanding of the business rules regarding pricing and seating layouts. They want to have a tool for simple and effective event setup and monitoring of sales performance.
- **Custormers** - Individuals interested in attending events. They range from casual users to frequent attendees. They require a clear interface for seat selection and a reliable reservation process.They must be aware of the app limitations.


### Limitations
- **L-01** - 


## Definitions
- Seat Category - a classification that determines the base price and relative price floor for a seat. Possible class are: VIP, Premium, and Economy
- Numbered event - an event where seats have specific row and column coordinates.
- Non-numbered event - an event where seats are sold from a pool without specific physical placement requirements.
- Early Bird - a pricing period occuring more than 30 days before the event.
- Last Minute - a pricing period occuring less than 48 hours before the event.
- Atomicity - 


# Requirements

## Functions

**Functional requirements for SeatsReservation problem are listed below.**


### FR-01 - Event Lifecycle and Configuration
The system shall enable the Administrator to fully define an event's enviormnet, including its name, date and time, and a fixed-size rectangular seating grid. During setup, the system must enforce a uniform event type: strictly numbered or non-numbered, and ensure that seats have category assigned (VIP, Premium, Economy) and a corresponding base price.

### FR-02 - Reservation Logic
The SeatsReservation system should manage the complete reservation lifecycle by processing booking requests as atomic transactions. It must strictly enforce seat adjacency for numbered events and limit each user to a maximum of two concurrent 15-minute pending locks. If payment is not confirmed within this window, the system must revert seats to the availabe pool.

### FR-03 - Pricing engine
The system shall automatically calculate the final ticket price at the moment of reservation by applying time-based rules: an Early Bird discount of 20% for booking of at least 30 days in advance, a Last Minute surcharge of 30% for booking made less than 48 hours before the event and at events with occupancy sold less than 80%. Throughout these calculations, the system must maintain a strict financial hierarchy, ensuring that effectively always price of VIP ticket is greater then Premimum ticket and Premium ticket price greater then Ecomony.

### FR-04 - Administration
The SeatsReservation program must allow users to cancel confiramed reservations up until 2 hours before the event start and provide comprehensive status reports for both roles, such as real-time occupancy and revenue summaries for administrators and personal booking histories for users.

## Performance requirements
- Program shall process reservation requests in under 200ms.
- It must maintain strict data integrity and prevent race conditions for at least 50 concurrent user per event.
- The system shall support the management of 100 active events with seating grids up to 250,00 units (500x500).
- The automated 15-minute expiration logic for Pending reservations must operate with a maximum drift of 5 seconds.

## Usability requirements
- The system shall provide a clear, graphical representaion of the seating grid. Avaiable, and reserved seats must be distinguishable through color-coding.
- During the reservation process, the system shall display a real-time countdown timer for the 15-minute interval.
- The breakdown of the final reservation price should be shown before the user proceeds to the payment stage.

## Interface requirements

Administraotr desktop modeule should include dedicated interface for event management. Key views must include:
- Event creator - form for entering event metadata and grid dimensions.
- Grid configuratior - interactive tool for category assignment and base price setting.
- Dashboard - real-time summary of occupancy and financial performance per event.

A customer desktop module as a dedicated interface for seat booking should include views such as:
- Event browser - a list of upcoming events with search/filter capabilities
- Booking view - an interactive grid for seat selection and adjacency validation.
- Reservation manager - personal dashboard for tracking payment status and performing cancellations.

Both customer's and administrator's panel should be accesible trough the same logging panel, where user can switch between user or administaror role and provide cradentials.

## Logical database requirements
The system shall maintain a persistent data model to ensure consistency across appliaction restarts. The logical schema is presented below thourgh entity relationship diagram:

ERD

## Design constraints

### Security
Administrative functions must be proteced from unauthorized access by standard authentication mechanisms.

### Maintainability
The system should be implemented in a way that is easy to scale, maintain, and test. The code must remain readable, maintainable, and documented.

### Portability
The web application shall be compatible with moder web browsers (e.g. Google Chrome, Mozilla Firefox, Microsoft Edge, Safari).

## Software system attributes
3.5

# Verification
SeatsReseration shall be verified through a combination of tests and inspections.

# Appendices

## Assumptions and dependencies

### Domain assumptions
- **DA-01** - The system clock on the host machine is considered the source of thruth for all time-based calculations.
- **DA-02** - A month for the discounts is defined as eactly 30 calendar days.
- **DA-03** - Payment confirmation is provided by an external signal or simulated user action.

## Acronyms and abbreviations
- VIP - Very Important Person (highest seat category)
- G - Goal
- SP - Shared Phenomena
- WP - World Phenomena
- FR - Functional Requirements
- DA - Domain Assumtion
