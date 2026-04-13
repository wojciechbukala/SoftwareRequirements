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
SeatsReservation is a web application operated by an event management company as its primary tool for selling seats to events held at physical venues.

On the input side, SeatsReservation received information from two kinds of human users. Administrators, acting on behalf of the event company, and customers, acting on their own behalf. The program treats these two user roles strictly separately and exposes a dedicated interface to each.

On the output side, SeatsReservation is the sole source of truth about the state of every seat in every managed event.  It presents this state to users in the form of interactive seating layouts, availability summaries, and personal booking histories, and it presents it to administrators in the form of occupancy and revenue overviews. Outside the system itself, SeatsReservation interacts with one external part- a payment service- to which customers are redirected during the reservation flow and which signals back whether payment was confirmed or abandoned. 

Finally, SeatsReservation depends on the progression of real time, which drives several parts of its behavior: the pricing adjustments that apply depending on how close the current moment is to the event, the fixed time window in which a customer must complete payment after selecting seats, and the deadline after which cancellations are no longer allowed.

### 1.3.2. Product functions
At a high level, the SeatsReservation system provides the following groups of functions:
- **Event management** - creataion and configuration of events, performed by the Administrators.
- **Reservation handling** - seat selection, atomic locking, and automatic release of expired locks.
- **Dynamic pricing** - calculation of the final ticket price at reservation time based on seat category and booking moment.
- **Reporting and monitoring** - summaries for the Administrator, and personal booking history for the User.
- **Access control** - authentication and role-based routing to either the user or the administrator interface through a single login panel.

A detailed view of these functions is provided by the use case diagram and sequence diagrams in Section 3.1 and by the functional requirements FR-01 to FR-04.

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
The system shall enable the Administrator to fully define an event's environment, including its name, date and time, and a fixed-size rectangular seating grid. During setup, the system must enforce a uniform event type: strictly numbered or non-numbered, and ensure that seats have a category assigned (VIP, Premium, or Economy) and a corresponding base price.

### FR-02 - Reservation Logic
The SeatsReservation system should manage the complete reservation lifecycle by processing booking requests as atomic transactions. It must strictly enforce seat adjacency for numbered events and limit each user to a maximum of two concurrent 15-minute pending locks. If payment is not confirmed within this window, the system must revert seats to the available pool.

### FR-03 - Pricing engine
The system shall automatically calculate the final ticket price at the moment of reservation by applying time-based rules: an Early Bird discount of 20% for booking at least 30 days in advance, and a Last Minute surcharge of 30% for booking less than 48 hours before the event and at events with occupancy sold more than 80%. Throughout these calculations, the system must maintain a strict financial hierarchy, ensuring that the effective price of a VIP ticket is always greater then a Premimum ticket and the Premium ticket price is always greater then Ecomony.

### FR-04 - Administration
The SeatsReservation program must allow users to cancel confirmed reservations up until 2 hours before the event start and provide comprehensive status reports for both roles, such as real-time occupancy and revenue summaries for administrators and personal booking histories for users.

## 3.2. Functions - Use cases
Two human actors interact directly with the SeatsReservation system: the Customer, who places and manages reservations for their own attendance at events, and the Administrator, who configures events and monitors their sales. In addition, the system interacts with one external actor, an external payment service, during the reservation flow and during the refund step of a cancellation.

## UC-01 - Make reservation
| | |
|---|---|
| **Actor** | Customer, participation of the external payment service |
| **Entry condition** | The customer is authenticated and has selected an upcoming event from the list of events displayed in the customer interface. |
| **Event flow** | Descripeb below. |
| **Exit condition** | Either the seats selected by the customer have been permanently reserved to them, or the seats have been released back to the pool. |
| **Exceptions** | EX1 - Pending reservation limit reached |

**Event flow**: 
1. Upon selecting an event, the system first determines whether the event uses numbered or non-numbered seating and presents the customer with the appropriate seat selection view.
2. For numbered seating events, the system renders an interactive graphical layout of the venue, in which every seat is shown with its current availability status. The customer picks seats by clicking on them; the system accepts a click only if the corresponding seat is currently available and if the resulting selection continues to form a group of seats adjacent to one another in the layout. Clicks that would violate either of these conditions are silently ignored. The customer confirms their final selection when satisfied.
3. For non-numbered events, the system renders, for each seat category offered at the event, the number of seats still available in that category. The customer picks a category and a quantity and confirms their selection.
4. The system checks that the customer does not already hold two pending reservations; if they do, the new selection is rejected.
5. The system marks the selected seats (numbered events) or the requested quantity of the chosen category (non-numbered events) as held for this customer, computes the final price of the selection according to the rules in FR-03, and starts a 15-minute timer. The customer is informed of the seats held, the computed price, and the deadline by which payment must be completed and is then redirected to the external payment service.
6. If the payment service signals a successful payment before the timer expires, the system marks the held seats as permanently reserved to this customer, stops the timer, and the reservation is complete. If the 15-minute window expires without a payment confirmation signal, the system automatically releases the held seats and informs the customer that the reservation has been canceled.


## UC-02 - Cancel reservation
| | |
|---|---|
| **Actor** | Customer |
| **Entry condition** | The customer is authenticated and has an existing reservation visible in their personal booking history. |
| **Event flow** | Descripeb below. |
| **Exit condition** |  Either the reservation has been cancelled and its seats released back to the pool, or the customer has been informed that the cancellation cannot be performed. |
| **Exceptions** | EX1 - Requester is not the owner of the reservation, EX2 - Reservation is not in the confirmed state, EX3 - Cancellation window closed |

**Event flow**:
1. The customer requested the cancellation of one of their reservations.
2. The system verifies three conditions before proceeding: that the customer requesting the cancellation is the owner of the reservation, that the reservation is currently in the confirmed state, and that the current moment is no later than two hours before the start of the event to which the reservation applies.
3. If conditions are met, the system releases the seats that were part of the reservation back to the pool of available seats, marks the reservation as cancelled, and updates the customer's view.
4.  If any of the three conditions is not met, the system displays an informative error message explaining which condition failed and leaves the reservation unchanged.

## UC-03 - Add event
| | |
|---|---|
| **Actor** | Administrator |
| **Entry condition** | The customer is authenticated and has an existing reservation visible in their personal booking history. |
| **Event flow** | Descripeb below. |
| **Exit condition** |  Either the reservation has been cancelled and its seats released back to the pool, or the customer has been informed that the cancellation cannot be performed. |
| **Exceptions** | EX1 - Administrator abandons the flow before final confiramtion |

**Event flow**:
1. The administrator begins by submitting the metadata of the new event.
2. The system validates this metadata, checking that no conflicting event already exists and that the supplied values are internally consistent. If validation fails, the system informs the administrator of the specific error; administrator may correct the data and resubmit.
3. Once the metadata has been accepted, the system presents a category configuration view whose form depends on the event type. For numbered events, the system displays an interactive layout of the seating grid. For non-numbered events, the system asks the administrator to declare, for each category, the quantity of seats of that category available in the pool. In both cases, the system validates the assignment.
4. The administrator adds information about the base price for each category. The system validates these prices against the hierarchy required by FR-03.
5. If metaadata, category, configuration, and base prices have all been validated, the administrator confirms the creation of the event. The system persists the new event together with its seats and prices and redirects the administrator to the event's dashboard. 

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
The system shall maintain a persistent data model to ensure consistency across appliacation restarts. Specifically, the system shall persist, for each event, its identifying metadata, its seating configuration, and its per-category base pricing. For every user of the system the program shall persist the information neccessary to authenticate the user and to determine whether they are acting as a customer or as an administrator. For every reservation the program shall persist its lifecycle status, the customer to whom it belongs, the event to which it applies, the set of seats it involves, and the timestamps relevant to its processing. The following integrity constraints shall hold in the system:
- Every reservation shall belong to exactly one customer and exactly one administrator.
- Every event created in the system shall have been created by exactly one administrator.
- Every seat shall belong to exactly one event and shall carry exactly one category assignemnet.
- A seat shall belong to at most one active reservation at any given moment. A reservation is active if it is currently pending (held, awaiting payment) or confirmed. 

These constraints shall be enforced under the concurrency conditions specified in the Section 3.3.

## 3.7. Design constraints
- **Platform** - the system shall be delivered as a web application compatible with modern web browsers (see 3.8 Portability).
- **Visual style** - the key views of the system (Login panel, User interface, and Administrator interface) are provided as mockups in the *UI_Mockups* folder (*LoginRegister.png*, *User.png*, *Admin.png*). All views not explicitly covered by the mockups shall follow the same graphical style — colour palette, typography, proportions, component shapes, and interaction patterns — as established by the mockups.
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