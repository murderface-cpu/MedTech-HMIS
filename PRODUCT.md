# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Hospital staff across the patient journey: front-desk registration clerks, triage nurses,
doctors, laboratory technicians, radiology and cardiology staff, pharmacists, store keepers,
cashiers and administrators. They work at desktop stations, and on tablets and phones at the
bedside and on ward rounds, so touch and small screens matter as much as desktop. Shifts are
long, and the system is open all day.

## Product Purpose

MedSafe is a Health Management Information System for Kenyan hospitals and clinics. It records
the patient journey from registration through triage, consultation, laboratory, imaging,
pharmacy, procedures, billing and insurance. It also runs inventory, staff access and
administration. Success means staff finish each step faster than on paper, and nothing is lost
between departments.

## Positioning

One record follows the patient through every department. Each department works from its own
queue (requests, prescriptions, bookings, invoices) of orders placed elsewhere, rather than
keeping separate registers.

## Operating Context

- Kenya: KES currency, East Africa Time, English (Swahili planned). SHA claims, KRA eTIMS
  submissions and M-Pesa payments are recorded by staff in the system; the live SHA, eTIMS and
  Daraja API connections are still on the roadmap (HMIS Master Blueprint). MOH 705A/B and 717
  returns are produced from the records for entry into KHIS.
- Bright clinic rooms, shared workstations, and mid-range monitors and tablets.
- Departments hand work to each other through orders: the doctor orders, and lab, imaging,
  pharmacy or theatre fulfil.
- Comparable category products include Unumed (EHR plus ERP for African hospitals).

## Capabilities and Constraints

- Django server-rendered pages, plus a versioned REST API for the patient and doctor workspaces.
  No frontend build step.
- Module-based access: staff see only the workspaces their modules allow.
- Every menu page is live, including emergency, inpatient, appointments, procurement and
  reports. The menu can still show a future page as Planned with a reserved route.
- The home page is a hospital overview whose sections follow the modules the user holds.
- Pharmacy and the main store share one stock count per batch; requisitions from the pharmacy
  are a record, not a transfer.
- Undecided: the patient-facing interface, and telemedicine.

## Brand Commitments

None fixed. The MedSafe name stays. The current logo (blue hand with heart, "Health & Beyond")
and colours are placeholders that may change.

Visual direction (chosen 2026-10-30): the category standard, executed at full craft. The
conventions of a clean, white, blue-accent clinical system, with no novelty. The quality bar
is set by Unumed and modern EHRs such as Epic: a patient banner, worklists, orders, and the
conventions clinicians already know.

## Evidence on Hand

- `static/auth-logo/med-tech-hmis-logo.png`: the current placeholder logo.
- There are no real customer names, testimonials or usage figures. Do not invent any.

## Product Principles

- The patient's current step and the next action are always obvious.
- Each department's queue is its home screen.
- Safe by default: irreversible actions confirm, and billed items cannot be silently removed.
- Built for long shifts: calm, legible and fast, with nothing to wait for.

## Accessibility & Inclusion

WCAG 2.2 AA, plus a larger default text size and high contrast. It must stay comfortable for
older staff and on low-quality monitors and tablets.
