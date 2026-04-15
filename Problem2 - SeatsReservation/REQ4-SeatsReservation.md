# 1. Purpose
SeatsReservation is a specialized management tool designed for event companies to automate seat booking for various events. The primary goals of the program are listed below:

- **G-01** - The system shall manage a rectangular seating grid for various events.
- **G-02** - The system should handle both numbered and non-numbered seating configurations.
- **G-03** - The system shall accurately calculate dynamic ticket prices based on timing and seat category.
- **G-04** - SeatsReservation system must ensure the integrity of the reservation process.

The SeatsReservation program is focused on the logic of event management and reservation handling. It provides an interface for both administrators and users. 

# 2. Alloy model
(signatures, facts, predicates, assertions)

# 3. Operational envelope

# 3.1. I/O operations

# 3.2. Non-functional requirements
- The program shall process reservation requests in under 200ms.
- It must maintain strict data integrity and prevent race conditions for at least 50 concurrent users per event.
- The system shall support the management of 100 active events with seating grids up to 250,000 units (500x500).
- The automated 15-minute expiration logic for Pending reservations must operate with a maximum drift of 5 seconds.

# 3.3. Verification approach

# 4. Appendices

## 4.1. Domain assumptions
- **DA-01** - The system clock on the host machine is considered the source of truth for all time-based calculations.
- **DA-02** - A month for the discounts is defined as exactly 30 calendar days.
- **DA-03** - Payment confirmation is provided by an external signal or simulated user action.