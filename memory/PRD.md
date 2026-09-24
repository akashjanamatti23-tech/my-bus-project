# GoBus — product requirements and implementation ledger

## Problem statement (static)
Build one centralized bus-booking and journey-management ecosystem with three strictly separate interfaces: Passenger, Admin (master controller), Driver/in-bus. Admin configures all buses, exact physical layouts, routes, stops, schedules, fares, drivers, offers and policies. The backend is the only source of truth. No hard-coded operating records, no generic passenger seat maps, no frontend payment confirmation. Secure RBAC, atomic multi-seat locks and distinct Source/Destination QR events are mandatory. Full supplied specification remains the acceptance checklist; this first delivery is not the complete production platform.

## User decisions
- Three separate Expo interfaces accepted, including tablet/mobile Admin.
- Razorpay chosen; user will supply credentials. No keys supplied yet.
- Default INR, English, Asia/Kolkata.
- Default empty operational database; no sample buses/routes/drivers.
- Sequential phases; SMS delivery is not configured. Never manufacture OTPs or verification.

## Architecture
Expo SDK57 React Native + Expo Router; FastAPI API under /api; MongoDB shared persistent database. DB-enforced unique identities, Argon2id, expiring JWT with server-side session revocation, DB role checks and rate limiting. Admin-only bootstrap CLI. Bus layouts contain explicit coordinate/span/type/deck/fare/status records. Published trips snapshot Admin layouts, routes and bus details. Atomic trip-document seat holds. Managed object storage for brand photography.

## Personas
- Passenger discovers Admin-published trips, selects seats, owns their account/reservations.
- Super Admin provisions Admin/staff and controls master data.
- Admin configures fleet, routes, schedules, drivers and support; cannot create peer admins.
- Driver accesses only assigned operational trip data and sequential trip controls.

## Implementation ledger — 2026-09-24
- Delivered a foundation release, NOT all ten phases or production-ready completion.
- Passenger, Admin and Driver have separate Expo navigation/entrypoints and backend authorization. Real passenger registration/email/mobile-password login; normalized formatted phone numbers; Argon2id; 60-minute revocable JWT sessions; Mongo-backed account/IP rate limits; super-admin bootstrap and privileged account creation protections.
- Admin: live DB counts/activity, bus create/edit/active status and unique registration number, route create/edit/active status with stops/boarding/dropping points, Admin/Driver provisioning and disable/enable, draft/published trips, driver/bus overlap guards. Admin-only route/bus/layout changes blocked for upcoming published trips.
- Visual layout builder starts empty, with user-chosen rows/columns, lower/upper decks, seat/berth/cabin/aisle placement, custom numbering/prices/spans, available/blocked/inactive states and ladies reservations. Backend validates unique labels, bounds, overlaps and cabin prerequisite before scheduling. No hard-coded passenger seat geometry.
- Passenger: polished home and date/city/count selection, swap cities, Admin-driven routes/search/filter/sort, bus details, same stored seat map, multi-seat selection, atomic all-or-none five-minute holds with owner release, passenger age/name/gender and stop validation, server-derived fare and reservation DRAFT review. Checkout explicitly unavailable; no fake booking/PNR/ticket generated.
- Driver: dedicated login, only assigned published trips, stops, operational manifest/occupancy layout without fares, sequential trip status controls with future-day and sold-passenger-verification guards, support access.
- Supporting modules: Admin percentage-offer publishing/editing and passenger active/unexpired display/share; passenger/driver support requests and Admin replies/status; audit trail. These are initial subsets, not complete finance/marketing/support suite.
- Managed object storage hosts actual bus brand photography; native secure token helper reused; Expo font/icon prewarming, SafeArea-aware navigation, phone/tablet Admin sidebar and large Driver controls.
- Fixed React19/RNW empty-string conditional text issue by returning undefined error state; confirmed fresh browser logs clean. Corrected modal layout to explicit 86% height + constrained inner ScrollView, verified lower phone controls/nested selects/ladies status. Invalid icon fallback resolved.

## Verification — 2026-09-24
- `yarn tsc --noEmit`: passes. Backend and substantive frontend lint checks pass.
- Testing agent initial suite 3/3 passed; repeated QA logins exhausted persistent throttles. A local-only development-counter reset (no auth bypass or weakened application limits) allowed expanded suites to run: **5 passed, 0 skipped**. `/app/test_reports/pytest/verified_foundation.xml`.
- True simultaneous ThreadPool overlapping multi-seat holds: one success, one conflict, one complete hold; owner release and expired-hold rejection verified. Mobile formatting normalization regression passes.
- Self-tested phone390x844 Admin login → bus creation → lower ladies/blocked seats + upper berth + cabin → layout save → route → driver provision → published trip. Sheets now fully actionable. Fresh logs contain no RN text-node error.
- Self-tested passenger registration/login → city/date search → filters/sort → actual layout/decks → seat hold → boarding/drop/passenger details → DRAFT review with correct ₹850 + ₹30 = ₹880. Release confirmed in DB (empty holds). Two automation-only selector ambiguities corrected/scoped; not application failures.
- Driver phone test: assigned journey, stops/manifest, future-date operational guard. Tablet1024 sidebar verified; measured document width equals viewport390/1024 (no page overflow). Native device hardware/permissions not tested; camera/location integrations not yet implemented.
- Removed only identified QA records/accounts; preserved bootstrap Admin and genuine user-created passenger account. No sample operational records remain. Prior iteration_2 rendering report referenced historical logs, resolved independently by troubleshoot agent and fresh browser validation. Final status: `/app/test_reports/foundation_final.json`.

## Prioritized backlog / full acceptance matrix
### P0 — complete transaction/journey core
- Phase 1 remaining: SMS/email verification provider, six-digit OTP/resend/change number, forgot/reset password, refresh session rotation, staff fine-grained permissions.
- Phase 2 remaining: recurring schedules, existing schedule reassignment/edit workflow, full driver name/license editing, advanced staff permissions, route-stop timings, QR exception policies.
- Phase 3 remaining: paired round-trip bookings; all requested advanced filters and ratings/reviews; saved passenger/ID proof management.
- Phase 4: Razorpay verified server orders/capture/webhooks, all payment outcomes, coupons/fare rules/taxes, immutable booking/PNR, tickets/QR, ticket download/share, cancellations/reschedules/refunds. Requires Razorpay key_id/key_secret/webhook_secret. No confirmations until verified server capture.
- Phase 5: per-passenger BOOKED → SOURCE VERIFIED → JOURNEY STARTED → IN TRANSIT → DESTINATION VERIFIED → COMPLETED state machine; separate scan records; duplicate/wrong-trip/expired/out-of-order prevention; Admin exceptional resolution/audit.
- Phase 6: source and destination camera QR scanning, manifest and occupancy, passenger verification; camera permission contract and large readable controls.
- Phase 7: contextual driver location permissions; streaming locations; map, route, ETA, speed, distance, progress, delay/approaching alerts, scoped passenger tracking and sharing.
### P1 — ecosystem
- Phase 8: wallet/add-money/transactions/cashback/refunds; Admin flat/percent/cashback/route/bus/bank offers with terms/expiry/redemption; push notifications, quiet hours/preferences; full FAQs/contact/WhatsApp/email and support assignment/replies.
- Profile photo, saved addresses/passengers/ID documents, payment methods, referrals, review/rating submission.
- Driver current/upcoming stops/counts/timings, Admin messages, emergency alerts.
- Passenger booking categories/search, rebook, refund status; scoped Admin passenger block/verification/support history.
### P2 — reporting, governance and readiness
- Phase 9: finance/revenue/commission/fees/discount/refund/wallet reports; daily/weekly/monthly booking/occupancy/route/cancellation/passenger/payment/offer/driver analytics with exports; maps/tables/charts; configurable app/legal/cancellation/refund/security policies.
- Phase 10: all 30 specified scenarios, device-native validation, load/concurrency testing, external integration tests, audit/security hardening, production readiness. Production-ready claim requires every module checked, not this foundation delivery.
- Optional biometric sign-in.

## Required test scenarios
1 registration; 2 OTP; 3 login; 4 bus CRUD; 5 dynamic layouts; 6 routes; 7 schedules; 8 driver assignment; 9 search; 10 seat selection; 11 concurrent seats; 12/13 payment success/failure; 14 bookings; 15 ticket QR; 16/17 source valid/invalid; 18 source duplicate; 19 wrong bus; 20 destination valid; 21 destination-before-source; 22 destination duplicate; 23 tracking; 24 cancellation; 25 refund; 26 driver auth; 27 passenger auth; 28 admin auth; 29 role separation; 30 logout/expiry. Unimplemented scenarios must remain marked pending, never reported as passing.

## Next tasks
Foundation ready for user review. Next: collect Razorpay test key_id/key_secret and webhook_secret via secure configuration, obtain integration playbook, implement verified order/capture/webhook/idempotent-confirmation flow, then immutable tickets and per-passenger two-stage journey QR. Choose an SMS provider for verification/reset. Preserve full remaining checklist and three-interface source-of-truth invariant.