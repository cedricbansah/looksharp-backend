"""
Seed script: clients, offers, surveys (all question types), and users.

Conventions:
  - client_code format: LKSHP-XXXXX (unique per client)
  - offer_code: inherits the owning client's client_code
  - Survey IDs mirror Firestore doc-ID style (stable strings)

Idempotent — safe to re-run. Fixed IDs mean re-runs skip existing records.
Stock images are fetched from picsum.photos and uploaded to Cloudflare R2.

Run:
    python scripts/seed_db.py
"""

import io
import os
import sys
import uuid
from datetime import timedelta

import django
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.utils import timezone  # noqa: E402

from apps.clients.models import Client  # noqa: E402
from apps.offers.models import Offer  # noqa: E402
from apps.surveys.models import Question, Survey  # noqa: E402
from apps.users.models import User  # noqa: E402
from services.r2 import upload_file  # noqa: E402


# ── Fixed IDs (changing these = duplicates on re-run) ────────────────────────

CLIENT_IDS = {
    "mtn":       "client-mtn-ghana-001",
    "hubtel":    "client-hubtel-gh-001",
    "accra_mall": "client-accra-mall-001",
}

# client_code drives the offer_code for every offer under that client
CLIENT_CODES = {
    "mtn":       "LKSHP-10001",
    "hubtel":    "LKSHP-10002",
    "accra_mall": "LKSHP-10003",
}

SURVEY_IDS = {
    "mobile":   "survey-mobile-exp-001",
    "consumer": "survey-consumer-habits-001",
    "health":   "survey-health-lifestyle-001",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_and_upload(picsum_seed: str, r2_key: str, size: str = "800/600") -> str:
    """Download a stock image from picsum.photos and upload it to R2."""
    url = f"https://picsum.photos/seed/{picsum_seed}/{size}"
    print(f"    ↓ {url}")
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        content_type = "image/jpeg"
    return upload_file(io.BytesIO(resp.content), key=r2_key, content_type=content_type)


# ── Clients ───────────────────────────────────────────────────────────────────

def seed_clients() -> list[Client]:
    print("\n─── Clients ───────────────────────────────────────────────")

    definitions = [
        {
            "id":          CLIENT_IDS["mtn"],
            "name":        "MTN Ghana",
            "email":       "business@mtn.com.gh",
            "phone":       "+233302202020",
            "address":     "MTN House, Independence Avenue, Accra",
            "website_url": "https://mtn.com.gh",
            "description": "Ghana's largest telecommunications company, offering mobile voice, data, and MoMo services.",
            "client_code": CLIENT_CODES["mtn"],
            "_logo_seed":  "telecom-tower-yellow",
        },
        {
            "id":          CLIENT_IDS["hubtel"],
            "name":        "Hubtel",
            "email":       "info@hubtel.com",
            "phone":       "+233302900900",
            "address":     "No. 2 Radar Road, Labone, Accra",
            "website_url": "https://hubtel.com",
            "description": "Ghana's largest mobile commerce and digital payments platform.",
            "client_code": CLIENT_CODES["hubtel"],
            "_logo_seed":  "fintech-payments-blue",
        },
        {
            "id":          CLIENT_IDS["accra_mall"],
            "name":        "Accra Mall",
            "email":       "marketing@accramall.com.gh",
            "phone":       "+233302785010",
            "address":     "Spintex Road, Accra",
            "website_url": "https://accramall.com.gh",
            "description": "Ghana's premier shopping destination with over 60 stores and entertainment options.",
            "client_code": CLIENT_CODES["accra_mall"],
            "_logo_seed":  "shopping-center-retail",
        },
    ]

    clients = []
    for defn in definitions:
        logo_seed = defn.pop("_logo_seed")
        client = Client.objects.filter(id=defn["id"]).first()

        if client:
            print(f"  [skip] {defn['name']} ({defn['client_code']})")
            clients.append(client)
            continue

        print(f"  Creating: {defn['name']} ({defn['client_code']})")
        logo_url = fetch_and_upload(logo_seed, f"clients/{defn['id']}/logo", size="400/400")
        client = Client.objects.create(**defn, logo_url=logo_url)
        print(f"  ✓ {client.name}")
        clients.append(client)

    return clients


# ── Offers ────────────────────────────────────────────────────────────────────

def seed_offers(clients: list[Client]) -> list[Offer]:
    print("\n─── Offers ────────────────────────────────────────────────")

    mtn  = next(c for c in clients if c.id == CLIENT_IDS["mtn"])
    hub  = next(c for c in clients if c.id == CLIENT_IDS["hubtel"])
    mall = next(c for c in clients if c.id == CLIENT_IDS["accra_mall"])
    now  = timezone.now()

    # offer_code = client.client_code (inherited — all offers under a client
    # share the same redemption code prefix so partners can identify the source)
    definitions = [
        {
            "title":           "MTN 1GB Data Bundle",
            "description":     "Get 1 GB of MTN data valid for 7 days. Redeem via *170# using the code sent to your number.",
            "status":          "active",
            "category":        "Data & Airtime",
            "url":             "https://mtn.com.gh/data-bundles",
            "client":          mtn,
            "points_required": 150,
            "end_date":        now + timedelta(days=90),
            "is_featured":     True,
            "_poster_seed":    "wireless-network-data",
            "_dedup_key":      "title",  # field used to detect existing row
        },
        {
            "title":           "MTN Free Night Calls",
            "description":     "Unlimited calls from midnight to 5 AM for 3 days. Code delivered via SMS within minutes.",
            "status":          "active",
            "category":        "Data & Airtime",
            "url":             "https://mtn.com.gh/voice",
            "client":          mtn,
            "points_required": 100,
            "end_date":        now + timedelta(days=60),
            "is_featured":     False,
            "_poster_seed":    "night-city-phone",
            "_dedup_key":      "title",
        },
        {
            "title":           "Hubtel GHS 5 Cashback",
            "description":     "GHS 5 cashback credited to your Hubtel wallet on your next payment. Valid 30 days from redemption.",
            "status":          "active",
            "category":        "Finance & Payments",
            "url":             "https://hubtel.com",
            "client":          hub,
            "points_required": 200,
            "end_date":        now + timedelta(days=45),
            "is_featured":     True,
            "_poster_seed":    "mobile-payment-app",
            "_dedup_key":      "title",
        },
        {
            "title":           "Accra Mall GHS 20 Voucher",
            "description":     "GHS 20 off any in-store purchase of GHS 100 or more. Show voucher code at any till point.",
            "status":          "active",
            "category":        "Shopping",
            "url":             "https://accramall.com.gh",
            "client":          mall,
            "points_required": 400,
            "end_date":        now + timedelta(days=120),
            "is_featured":     True,
            "_poster_seed":    "retail-shopping-bags",
            "_dedup_key":      "title",
        },
        {
            "title":           "Accra Mall Free Day Parking",
            "description":     "One complimentary day of parking at Accra Mall. Valid Monday–Friday, excludes public holidays.",
            "status":          "active",
            "category":        "Shopping",
            "url":             "https://accramall.com.gh/parking",
            "client":          mall,
            "points_required": 80,
            "end_date":        now + timedelta(days=60),
            "is_featured":     False,
            "_poster_seed":    "parking-lot-urban",
            "_dedup_key":      "title",
        },
    ]

    offers = []
    for defn in definitions:
        poster_seed = defn.pop("_poster_seed")
        defn.pop("_dedup_key")
        client = defn.pop("client")

        existing = Offer.objects.filter(
            title=defn["title"],
            client_id=client.id,
            is_deleted=False,
        ).first()
        if existing:
            print(f"  [skip] {defn['title']}")
            offers.append(existing)
            continue

        offer_id = str(uuid.uuid4())
        print(f"  Creating: {defn['title']}")
        poster_url = fetch_and_upload(poster_seed, f"offers/{offer_id}/poster")

        offer = Offer.objects.create(
            id=offer_id,
            **defn,
            # offer_code inherits the client's LookSharp code
            offer_code=client.client_code,
            client_id=client.id,
            client_name=client.name,
            client_logo_url=client.logo_url,
            poster_url=poster_url,
        )
        print(f"  ✓ {offer.title} — {offer.points_required} pts — code: {offer.offer_code}")
        offers.append(offer)

    return offers


# ── Surveys & Questions ───────────────────────────────────────────────────────

def seed_surveys(clients: list[Client]) -> None:
    print("\n─── Surveys & Questions ───────────────────────────────────")

    mtn  = next(c for c in clients if c.id == CLIENT_IDS["mtn"])
    hub  = next(c for c in clients if c.id == CLIENT_IDS["hubtel"])
    mall = next(c for c in clients if c.id == CLIENT_IDS["accra_mall"])
    now  = timezone.now()

    # Each survey covers all 6 question types:
    #   text, single_select, multi_select,
    #   single_select_other, multi_select_other, linear_scale

    surveys = [
        {
            "id":             SURVEY_IDS["mobile"],
            "title":          "Mobile Network Experience",
            "description":    "Help us understand how Ghanaians experience mobile network quality and what matters most to them.",
            "status":         "active",
            "category":       "Technology",
            "client_id":      mtn.id,
            "client_name":    mtn.name,
            "points":         50,
            "estimated_time": 5,
            "end_date":       now + timedelta(days=30),
            "created_by":     "seed-script",
            "_questions": [
                {
                    "question_type": "single_select",
                    "question_text": "Which mobile network is your primary SIM?",
                    "question_subtext": "Select the network you use most.",
                    "choices": ["MTN", "Telecel", "AirtelTigo", "Glo"],
                },
                {
                    "question_type": "multi_select",
                    "question_text": "Which services do you use on your mobile network?",
                    "question_subtext": "Select all that apply.",
                    "choices": ["Voice calls", "Mobile data", "Mobile money (MoMo)", "SMS", "International roaming"],
                },
                {
                    "question_type": "linear_scale",
                    "question_text": "How would you rate your network's data speed?",
                    "question_subtext": "1 = Very slow, 5 = Very fast.",
                    "scale_lower_limit": 1,
                    "scale_upper_limit": 5,
                },
                {
                    "question_type": "single_select_other",
                    "question_text": "How often do you experience dropped calls?",
                    "choices": ["Rarely or never", "Once a week", "Several times a week", "Daily"],
                },
                {
                    "question_type": "multi_select_other",
                    "question_text": "What would motivate you to switch to a different network?",
                    "question_subtext": "Select everything that applies to you.",
                    "choices": ["Faster data speeds", "Lower data prices", "Better call quality", "Wider coverage", "Better customer service"],
                },
                {
                    "question_type": "text",
                    "question_text": "Describe the biggest frustration you have with your current mobile network.",
                    "question_subtext": "Be as specific as possible — your feedback helps improve service quality.",
                },
            ],
        },
        {
            "id":             SURVEY_IDS["consumer"],
            "title":          "Shopping Habits in Ghana",
            "description":    "Tell us about your shopping preferences — both in-store and online — to help brands serve you better.",
            "status":         "active",
            "category":       "Consumer",
            "client_id":      mall.id,
            "client_name":    mall.name,
            "points":         75,
            "estimated_time": 7,
            "end_date":       now + timedelta(days=45),
            "created_by":     "seed-script",
            "_questions": [
                {
                    "question_type": "single_select",
                    "question_text": "How often do you shop for non-grocery items?",
                    "question_subtext": "Think about clothing, electronics, home goods, etc.",
                    "choices": ["Once a week or more", "2–3 times a month", "Once a month", "Less than once a month"],
                },
                {
                    "question_type": "multi_select",
                    "question_text": "Which product categories do you regularly shop for?",
                    "question_subtext": "Select all that apply.",
                    "choices": ["Clothing & fashion", "Electronics & gadgets", "Home & kitchen", "Beauty & personal care", "Sports & fitness"],
                },
                {
                    "question_type": "single_select_other",
                    "question_text": "Where do you prefer to shop?",
                    "question_subtext": "Choose the option that best describes your primary habit.",
                    "choices": ["In a mall or physical store", "Online with home delivery", "Local market or roadside", "A mix of online and in-store"],
                },
                {
                    "question_type": "multi_select_other",
                    "question_text": "What factors most influence your purchase decision?",
                    "question_subtext": "Select everything that matters to you.",
                    "choices": ["Price and discounts", "Brand reputation", "Product reviews", "Availability", "Return and refund policy"],
                },
                {
                    "question_type": "linear_scale",
                    "question_text": "Overall, how satisfied are you with the shopping experience in Ghana?",
                    "question_subtext": "1 = Very dissatisfied, 10 = Extremely satisfied.",
                    "scale_lower_limit": 1,
                    "scale_upper_limit": 10,
                },
                {
                    "question_type": "text",
                    "question_text": "What one change would most improve your shopping experience in Ghana?",
                    "question_subtext": "There are no wrong answers — we want your honest opinion.",
                },
            ],
        },
        {
            "id":             SURVEY_IDS["health"],
            "title":          "Health & Lifestyle Survey",
            "description":    "Help us understand the health habits and wellness priorities of Ghanaians so we can support you better.",
            "status":         "active",
            "category":       "Health",
            "client_id":      hub.id,
            "client_name":    hub.name,
            "points":         60,
            "estimated_time": 6,
            "end_date":       now + timedelta(days=60),
            "created_by":     "seed-script",
            "_questions": [
                {
                    "question_type": "single_select",
                    "question_text": "How would you describe your current level of physical activity?",
                    "choices": ["Very active — I exercise daily", "Moderately active — 3 to 4 times a week", "Lightly active — 1 to 2 times a week", "Mostly sedentary"],
                },
                {
                    "question_type": "multi_select",
                    "question_text": "Which health or wellness activities do you currently engage in?",
                    "question_subtext": "Select all that apply.",
                    "choices": ["Gym workouts", "Running or walking", "Football or team sports", "Yoga or stretching", "Swimming"],
                },
                {
                    "question_type": "linear_scale",
                    "question_text": "How would you rate your overall physical health right now?",
                    "question_subtext": "1 = Very poor, 5 = Excellent.",
                    "scale_lower_limit": 1,
                    "scale_upper_limit": 5,
                },
                {
                    "question_type": "single_select_other",
                    "question_text": "Where do you go first when you feel unwell?",
                    "choices": ["Government hospital or clinic", "Private clinic", "Pharmacy — I self-medicate", "Traditional or herbal medicine"],
                },
                {
                    "question_type": "multi_select_other",
                    "question_text": "What are the biggest barriers to living a healthier lifestyle for you?",
                    "question_subtext": "Select everything that applies.",
                    "choices": ["Cost of healthy food", "Lack of time", "No gym or park nearby", "Work stress", "Lack of motivation"],
                },
                {
                    "question_type": "text",
                    "question_text": "What health or wellness goal are you currently working towards?",
                    "question_subtext": "Describe in your own words — there are no wrong answers.",
                },
            ],
        },
    ]

    for survey_data in surveys:
        questions_data = survey_data.pop("_questions")

        survey, created = Survey.objects.get_or_create(
            id=survey_data["id"],
            defaults={**survey_data, "question_count": len(questions_data)},
        )

        if not created:
            print(f"  [skip] {survey.title}")
            continue

        print(f"  Creating: {survey.title}")
        for i, q in enumerate(questions_data):
            Question.objects.create(
                survey=survey,
                position_index=i,
                question_text=q["question_text"],
                question_subtext=q.get("question_subtext", ""),
                question_type=q["question_type"],
                choices=q.get("choices", []),
                scale_lower_limit=q.get("scale_lower_limit"),
                scale_upper_limit=q.get("scale_upper_limit"),
            )

        types = [q["question_type"] for q in questions_data]
        print(f"  ✓ {survey.title} — {len(questions_data)} questions — {survey.points} pts")
        print(f"    types: {', '.join(types)}")


# ── Users ─────────────────────────────────────────────────────────────────────

def seed_users() -> None:
    print("\n─── Users ─────────────────────────────────────────────────")

    users_data = [
        {
            "id":                   "seed-user-kofi-001",
            "email":                "kofi.mensah@example.com",
            "first_name":           "Kofi",
            "last_name":            "Mensah",
            "phone":                "+233244123456",
            "gender":               "male",
            "country":              "Ghana",
            "points":               320,
            "is_verified":          True,
            "welcome_bonus_claimed": True,
        },
        {
            "id":                   "seed-user-ama-001",
            "email":                "ama.owusu@example.com",
            "first_name":           "Ama",
            "last_name":            "Owusu",
            "phone":                "+233277654321",
            "gender":               "female",
            "country":              "Ghana",
            "points":               150,
            "is_verified":          True,
            "welcome_bonus_claimed": True,
        },
        {
            "id":                   "seed-user-kwame-001",
            "email":                "kwame.asante@example.com",
            "first_name":           "Kwame",
            "last_name":            "Asante",
            "phone":                "+233200111222",
            "gender":               "male",
            "country":              "Ghana",
            "points":               50,
            "is_verified":          False,
            "welcome_bonus_claimed": True,
        },
        {
            "id":                   "seed-user-abena-001",
            "email":                "abena.darko@example.com",
            "first_name":           "Abena",
            "last_name":            "Darko",
            "phone":                "+233551999888",
            "gender":               "female",
            "country":              "Ghana",
            "points":               800,
            "is_verified":          True,
            "welcome_bonus_claimed": True,
        },
        {
            "id":                   "seed-user-yaw-001",
            "email":                "yaw.boateng@example.com",
            "first_name":           "Yaw",
            "last_name":            "Boateng",
            "phone":                "+233302334455",
            "gender":               "male",
            "country":              "Ghana",
            "points":               0,
            "is_verified":          False,
            "welcome_bonus_claimed": False,
        },
    ]

    for data in users_data:
        user, created = User.objects.get_or_create(id=data["id"], defaults=data)
        tag = "✓ created" if created else "[skip] exists"
        print(f"  {tag}: {user.first_name} {user.last_name} — {user.points} pts — verified={user.is_verified}")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary() -> None:
    print("\n─── Summary ───────────────────────────────────────────────")
    print(f"  Clients   : {Client.objects.count()}")
    print(f"  Offers    : {Offer.objects.filter(is_deleted=False).count()}")
    print(f"  Surveys   : {Survey.objects.filter(is_deleted=False).count()}")
    print(f"  Questions : {Question.objects.filter(is_deleted=False).count()}")
    print(f"  Users     : {User.objects.count()}")
    print()
    print("  Client codes:")
    for c in Client.objects.order_by("name"):
        print(f"    {c.client_code}  →  {c.name}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("LookSharp seed script")
    clients = seed_clients()
    seed_offers(clients)
    seed_surveys(clients)
    seed_users()
    print_summary()
    print("\nDone.")
