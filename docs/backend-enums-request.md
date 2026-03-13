# Backend Request: Unified Enums / Config Endpoint

**To:** Backend Team
**From:** Admin & Mobile Frontend
**Date:** 2026-03-13

---

## The Problem

Right now, both the admin dashboard and the mobile app maintain their own hardcoded copies of enum values (statuses, types, ID types, network providers, etc.). Additionally, survey and offer categories are fetched directly from Firestore by both clients.

This creates three compounding problems:

1. **No single source of truth.** If a value changes on the backend (e.g. a new ID type is added), it must be manually updated in the admin codebase *and* the mobile codebase — and they can silently fall out of sync.
2. **Label drift.** Both clients independently maintain human-readable labels for the same values. The mobile app already has a divergence: one screen shows `"Telecel (formerly Vodafone)"` and another shows `"Telecel"` for the same enum value.
3. **Direct Firestore access is a liability.** Both clients bypass the API layer to read `survey_categories` and `offer_categories` from Firestore directly. This tightly couples clients to the database schema and prevents the backend from controlling access or evolving the data model.

---

## What We're Asking For

A single endpoint that returns all lookup/config data the clients need:

```
GET /config/enums
```

This can be unauthenticated or require a valid app-level token — your call. It should be cacheable (e.g. `Cache-Control: max-age=3600`).

---

## Required Response Shape

```json
{
  "survey_statuses": [
    { "value": "draft",     "label": "Draft" },
    { "value": "active",    "label": "Active" },
    { "value": "completed", "label": "Completed" }
  ],
  "question_types": [
    { "value": "text",                  "label": "Text" },
    { "value": "single_select",         "label": "Single Select" },
    { "value": "multi_select",          "label": "Multi Select" },
    { "value": "single_select_other",   "label": "Single Select + Text" },
    { "value": "multi_select_other",    "label": "Multi Select + Text" },
    { "value": "linear_scale",          "label": "Linear Scale" }
  ],
  "offer_statuses": [
    { "value": "active",   "label": "Active" },
    { "value": "inactive", "label": "Inactive" }
  ],
  "verification_statuses": [
    { "value": "pending",  "label": "Pending" },
    { "value": "approved", "label": "Approved" },
    { "value": "rejected", "label": "Rejected" }
  ],
  "withdrawal_statuses": [
    { "value": "pending",    "label": "Pending" },
    { "value": "processing", "label": "Processing" },
    { "value": "completed",  "label": "Completed" },
    { "value": "failed",     "label": "Failed" }
  ],
  "network_providers": [
    { "value": "MTN",     "label": "MTN" },
    { "value": "VOD", "label": "Telecel" },
    { "value": "ATL", "label": "ATMoney" }
  ],
  "id_types": [
    { "value": "ghana_card",       "label": "Ghana Card" },
    { "value": "passport",         "label": "Passport" },
    { "value": "voter_id",         "label": "Voter ID" },
    { "value": "drivers_license",  "label": "Driver's License" }
  ],
  "genders": [
    { "value": "male",   "label": "Male" },
    { "value": "female", "label": "Female" },
    { "value": "other",  "label": "Other" }
  ],
  "survey_categories": [
    { "id": "...", "name": "Technology", "icon": "💻", "survey_count": 12 }
  ],
  "offer_categories": [
    { "id": "...", "name": "Food & Drink", "icon": "🍔", "offer_count": 7 }
  ]
}
```

> **Note:** The `label` field on each enum item is important — it lets the backend control display strings instead of each client re-implementing its own mapping.

---

## Known Mismatches to Resolve Before Launch

| Field | Admin value | Mobile value | Needs decision |
|-------|-------------|--------------|----------------|
| `genders` | `other` | `unspecified` | Which value should the backend use as canonical? We'll align both clients to whatever you decide. |
| `network_providers` label | `"Telecel"` | `"Telecel (formerly Vodafone)"` (one screen) | Backend label in this response will become the canonical display string; mobile will clean up the divergent screen. |

---

## What Each Client Will Do After This Is Live

**Admin (`looksharp-admin`):**
- Remove direct Firestore reads in `src/lib/firebase/categories.ts` (`getSurveyCategories`, `getOfferCategories`)
- Fetch categories and all enum option lists from this endpoint instead
- Cache the response via TanStack Query

**Mobile (`looksharp-mobile`):**
- Remove direct Firestore reads for `survey_categories` and `offer_categories`
- Consume categories from this endpoint
- Static enums (statuses, types) will remain as Dart enums locally but will be cross-validated against this response

---

## Nice to Have (Not Blocking)

- Versioning: if enum values ever change in a breaking way, a `version` field in the response would help clients detect stale caches.
- Separate endpoints per domain (e.g. `/config/enums/surveys`, `/config/enums/offers`) if you prefer finer-grained caching — we're flexible.


draft notes after implementation to admin and mobile dev team to notify them of the new changes. update openapi.yaml as well