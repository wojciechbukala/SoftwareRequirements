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

![Domain Class Diagram](/Problem2%20-%20SeatsReservation/Diagrams/P2_DCD.drawio.png)

### 1.3.2. Product functions
at a high level, the Seats Reseravtion system provides the following groups of functions:
- **Event management** - creataion and configuration of events, performed by the Administrators.
- **Reservation handling** - seat selection, atomic locking, and autoamtic release of expired locks.
- **Dynamic pricing** - calculation of the final ticket price at reservation time based on seat category and booking moment.
- **Reporting and monitoring** - summaries for the Administroator, and personal booking history for the User.
- **Access control** - authentication and role-based routing to either the user or the administrator interface through a single login panel.

A detiled view of these functions is provided by the use case diagram and sequence diagrams in Section 3.1, and by the functional requirements FR-01 to FR-04.

### 1.3.3. User characteristics
The system serves two distinct types of users:
- **Administrators** - Employees of the event management company. They are expected to have a full understanding of the business rules regarding pricing and seating layouts. They want to have a tool for simple and effective event setup and monitoring of sales performance.
- **Custormers** - Individuals interested in attending events. They range from casual users to frequent attendees. They require a clear interface for seat selection and a reliable reservation process. They must be aware of the app limitations.


### 1.3.4. Limitations
- **L-01** - Web Application - The system operates exclusively as a web application. 
- **L-02** - No Mixed Seat Configuration - Within a single event, all seats must be either numbered or non-numbered. Mixed configurations are not supported.


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
The system shall enable the Administrator to create and configure events, covering event metadata, a fixed-size rectangular seating grid with a uniform numbering type (strictly numbered or non-numbered), seat category assignment(VIP, Premium, or Economy), and base price definition per category. The detailed interaction flow is specified in use case UC-03.

### FR-02 - Reservation Logic
The SeatsReservation system should manage the complete reservation lifecycle by processing booking requests as atomic transactions. It must strictly enforce seat adjacency for numbered events and limit each user to a maximum of two concurrent pending locks, with fixed lock window (see UC-01 sequence). If payment is not confirmed within this window, the system must revert seats to the available pool.

### FR-03 - Pricing engine
The system shall automatically calculate the final ticket price at the moment of reservation by applying time-based rules: an Early Bird discount of 20% for booking at least 30 days in advance, and a Last Minute surcharge of 30% for booking less than 48 hours before the event and at events with occupancy sold more than 80%. Throughout these calculations, the system must maintain a strict financial hierarchy, ensuring that the effective price of a VIP ticket is always greater then a Premimum ticket and the Premium ticket price is always greater then Ecomony.

### FR-04 - Administration
The SeatsReservation program must allow users to cancel confirmed reservations up until 2 hours before the event start and provide comprehensive status reports for both roles, such as real-time occupancy and revenue summaries for administrators and personal booking histories for users.

## 3.2. Functions - Use cases
Actors and their use cases includend in the system evironment can be described by the use cases diagram as below: 
![Use Case Diagram](/Problem2%20-%20SeatsReservation/Diagrams/P2_UCD.drawio.png)

## UC-01 - Make reservation
The main functionality of the system is the possibility to reserve a seat by a user for a specified event. Process is presented with the usage of 3 sequence diagrams. The split was made to make a clear distingush between numbered and nonnumbered events.

Seqence diagram - user selects event form the list displayed on the website:
![Sequence Diagram - select event](/Problem2%20-%20SeatsReservation/Diagrams/P2_SD1_1.drawio.png)

If event is numbered, the process of reservation and confirmation looks as provided below:
![Sequence Diagram - numbered event](/Problem2%20-%20SeatsReservation/Diagrams/P2_SD1_2.drawio.png)

Otherwise, if the event is nonnumbered, the seqence looks like that:
![Sequence Diagram - nonnumbered event](/Problem2%20-%20SeatsReservation/Diagrams/P2_SD1_3.drawio.png)

## UC-02 - Cancel reservation
Other key use case of the ystem is the possibility for a user to cancel reservation, presented at the sequence diagram below:
![Sequence Diagram - cancel reservation](/Problem2%20-%20SeatsReservation/Diagrams/P2_SD_2.drawio.png)

## UC-03 - Add event
THe key functionality of the administarot is the possibilibty to add an event, as presented below:
![Sequence Diagram - add event](/Problem2%20-%20SeatsReservation/Diagrams/P2_SD3.drawio.png)

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

The SeatsReservation system is logically divided into three user interfaces, each accessible through the same single entry point:

1. **Login / Register panel** - the single entry point for all users. It allows authentication and account creation, and after successful login routes the user to the appropriate interface based on their role.
2. **User interface** - accessible after login as a Customer. It consists of the following views:
   - *Events* - a list of upcoming events; selecting an event initiates the "Reserve seats" use case (UC-01).
   - *Bookings* - a history of the user's reservations with their current status, used for tracking payments and performing cancellations.
   - *Profile* - personal account details.
   - *Settings* - application settings.
3. **Administrator interface** - accessible after login as an Administrator. It consists of the following views:
   - *Dashboard* - real-time summary of occupancy and revenue across managed events.
   - *Events* - a table of all managed events with their configuration options.
   - *Event Creator* - a form-based tool for event metadata entry, interactive grid or pool configuration, and base price setup; initiates the "Add event" use case (UC-03).

## 3.6. Logical database requirements
The system shall maintain a persistent data model to ensure consistency across appliacation restarts. The logical schema is presented below thourgh entity relationship diagram:

![Entity Relatioship Diagram](/Problem2%20-%20SeatsReservation/Diagrams/P2_ERD.drawio.png)

## 3.7. Design constraints
- **Platform** - the system shall be delivered as a web application compatible with modern web browsers (see 3.8 Portability).
- **Visual style** - the key views of the system (Login panel, User interface, and Administrator interface) are provided as mockups in the *UI_Mockups* folder (*LoginRegister.png*, *User.png*, *Admin.png*). All views not explicitly covered by the mockups shall follow the same graphical style — colour palette, typography, proportions, component shapes, and interaction patterns — as established by the mockups.

![LoginRegister Mockup](/Problem2%20-%20SeatsReservation/UI_Mockups/LoginRegister.png
)

![User panel Mockup](/Problem2%20-%20SeatsReservation/UI_Mockups/User.png
)

![Admin panel Mockup](/Problem2%20-%20SeatsReservation/UI_Mockups/Admin.png)

- **Single entry point** - authentication for both roles is handled by the same Login / Register panel; no separate admin login URL or credential store is permitted.

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
Verification of the SeatsReservation system shall be performed by the evaluator through black_box assessment of program outputs and resonses to given actions. No specific testing framework or automated test suite is prescribed. The delivered software shall be submitted to an authorized evaluator responsible for all testing and verification activities.

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
