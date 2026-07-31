# solution.py
"""CulturalExchangeHub - a web-based platform for collaborative cultural exchanges.

Single-file, stdlib-only, deterministic implementation. No external libraries,
no randomness, no clock dependence. Layered by module with strict build-order
dependency gating executed through a stage counter.

Modules (mandated build order):
  1. Registration & Profile management   (prerequisite for everything)
  2. Virtual Tour                        (requires 1)
  3. Language Learning & practice        (requires 2)
  4. Cultural Workshop                   (requires 3)
  5. Feedback & Rating                   (requires 4, final)
"""


class HubError(Exception):
    """Base error for CulturalExchangeHub."""


class DependencyError(HubError):
    """Raised when a feature is used before its prerequisite stage is active."""


class NotFoundError(HubError):
    """Raised when a referenced entity does not exist."""


class InvalidInputError(HubError):
    """Raised when input data is invalid (duplicate, out-of-range, etc.)."""


# ---------------------------------------------------------------------------
# Data-layer containers
# ---------------------------------------------------------------------------
class _Store:
    """In-memory store with deterministic auto-incrementing integer ids."""

    def __init__(self):
        self._seq = 0
        self._items = {}

    def _next_id(self):
        self._seq += 1
        return self._seq

    def add(self, item):
        item_id = item["id"]
        if item_id is None:
            item_id = self._next_id()
            item["id"] = item_id
        self._items[item_id] = item
        return item_id

    def get(self, item_id):
        return self._items.get(item_id)

    def require(self, item_id, kind="record"):
        item = self._items.get(item_id)
        if item is None:
            raise NotFoundError("No {0} with id {1}".format(kind, item_id))
        return item

    def all(self):
        return list(self._items.values())

    def __len__(self):
        return len(self._items)


# ---------------------------------------------------------------------------
# Module 1: Registration & Profile management
# ---------------------------------------------------------------------------
class ProfileManager:
    """User account + profile management. Stage 1 (foundation)."""

    MIN_STAGE = 1

    def __init__(self):
        self._users = _Store()
        self._seen_usernames = set()
        self._seen_emails = set()
        self._active = False

    def activate(self):
        self._active = True

    def create_user(self, username, email, cultural_background="", interests="",
                    profile_picture=None):
        """Register a new user. Returns the new user id."""
        if not self._active:
            raise DependencyError(
                "Registration module is not active yet (required stage "
                "{0})".format(self.MIN_STAGE))
        username = (username or "").strip()
        email = (email or "").strip()
        if not username or not email:
            raise InvalidInputError("username and email are required")
        if username in self._seen_usernames:
            raise InvalidInputError("username already taken: {0}".format(username))
        if email in self._seen_emails:
            raise InvalidInputError("email already registered: {0}".format(email))

        user = {
            "id": None,
            "username": username,
            "email": email,
            "cultural_background": cultural_background or "",
            "interests": interests or "",
            "profile_picture": profile_picture or "default_avatar.png",
        }
        user_id = self._users.add(user)
        self._seen_usernames.add(username)
        self._seen_emails.add(email)
        return user_id

    def update_profile(self, user_id, cultural_background=None, interests=None,
                       profile_picture=None):
        """Update profile fields for an existing user."""
        user = self._users.require(user_id, "user")
        if cultural_background is not None:
            user["cultural_background"] = cultural_background
        if interests is not None:
            user["interests"] = interests
        if profile_picture is not None:
            # Profile picture: accept a real path/bytes string, else placeholder.
            user["profile_picture"] = profile_picture or "default_avatar.png"
        return user

    def get_user(self, user_id):
        return self._users.require(user_id, "user")

    def list_users(self):
        return self._users.all()

    def user_count(self):
        return len(self._users)


# ---------------------------------------------------------------------------
# Module 2: Virtual Tour
# ---------------------------------------------------------------------------
class VirtualTourManager:
    """3D landmark models, clickable hotspots, audio guides. Requires stage 2."""

    MIN_STAGE = 2

    def __init__(self, profiles):
        self._profiles = profiles
        self._tours = _Store()
        self._hotspots = _Store()
        self._audio_guides = _Store()
        self._active = False

    def activate(self):
        self._active = True

    def _check(self):
        if not self._active:
            raise DependencyError(
                "Virtual Tour module not active (requires stage "
                "{0})".format(self.MIN_STAGE))

    def create_tour(self, name, owner_id, model_url, description=""):
        self._check()
        self._profiles.get_user(owner_id)  # owner must exist
        tour = {
            "id": None,
            "name": name,
            "owner_id": owner_id,
            "model_url": model_url,
            "description": description or "",
            "hotspots": [],
            "audio_guides": [],
        }
        return self._tours.add(tour)

    def add_hotspot(self, tour_id, label, info, position=(0, 0, 0)):
        """Add a clickable hotspot with additional info to a tour."""
        self._check()
        tour = self._tours.require(tour_id, "tour")
        hotspot = {
            "id": None,
            "tour_id": tour_id,
            "label": label,
            "info": info,
            "position": tuple(position),
        }
        hid = self._hotspots.add(hotspot)
        tour["hotspots"].append(hid)
        return hid

    def add_audio_guide(self, tour_id, title, audio_url, language="en"):
        """Attach an audio guide to a tour."""
        self._check()
        tour = self._tours.require(tour_id, "tour")
        guide = {
            "id": None,
            "tour_id": tour_id,
            "title": title,
            "audio_url": audio_url,
            "language": language,
        }
        gid = self._audio_guides.add(guide)
        tour["audio_guides"].append(gid)
        return gid

    def get_tour(self, tour_id):
        """Return enriched tour with resolved hotspots and audio guides."""
        self._check()
        tour = self._tours.require(tour_id, "tour")
        enriched = dict(tour)
        enriched["hotspots"] = [self._hotspots.get(h) for h in tour["hotspots"]]
        enriched["audio_guides"] = [
            self._audio_guides.get(g) for g in tour["audio_guides"]]
        return enriched

    def list_tours(self):
        self._check()
        return [self.get_tour(t["id"]) for t in self._tours.all()]


# ---------------------------------------------------------------------------
# Module 3: Language Learning & practice
# ---------------------------------------------------------------------------
class TranslationTool:
    """Deterministic string mapping table with passthrough fallback."""

    def __init__(self):
        self._table = {
            ("en", "es"): {"hello": "hola", "thank you": "gracias",
                           "goodbye": "adios"},
            ("es", "en"): {"hola": "hello", "gracias": "thank you",
                           "adios": "goodbye"},
            ("en", "zh"): {"hello": "nihaoma", "thank you": "xiexie"},
            ("zh", "en"): {"nihaoma": "hello", "xiexie": "thank you"},
        }

    def translate(self, text, from_lang, to_lang):
        text = (text or "").strip()
        if not text:
            return ""
        if from_lang == to_lang:
            return text
        mapping = self._table.get((from_lang, to_lang), {})
        # Word-wise mapping; unknown tokens pass through unchanged.
        return " ".join(mapping.get(word, word) for word in text.split())


class LanguageLearningManager:
    """Real-time user pairing + translation. Requires stage 3."""

    MIN_STAGE = 3

    def __init__(self, profiles):
        self._profiles = profiles
        self._translation = TranslationTool()
        self._partnerships = _Store()
        self._messages = _Store()
        self._active = False
        self._pair_index = {}  # frozenset of user ids -> partnership id

    def activate(self):
        self._active = True

    def _check(self):
        if not self._active:
            raise DependencyError(
                "Language Learning module not active (requires stage "
                "{0})".format(self.MIN_STAGE))

    def pair_users(self, user_a, user_b, language_a="en", language_b="es"):
        """Pair two users for a real-time exchange."""
        self._check()
        if user_a == user_b:
            raise InvalidInputError("cannot pair a user with themselves")
        self._profiles.get_user(user_a)
        self._profiles.get_user(user_b)
        key = frozenset((user_a, user_b))
        if key in self._pair_index:
            raise InvalidInputError("these users are already paired")
        pair = {
            "id": None,
            "user_a": user_a,
            "user_b": user_b,
            "language_a": language_a,
            "language_b": language_b,
        }
        pid = self._partnerships.add(pair)
        self._pair_index[key] = pid
        return pid

    def get_partnership(self, partnership_id):
        self._check()
        return self._partnerships.require(partnership_id, "partnership")

    def send_message(self, partnership_id, sender_id, text, target_lang=None):
        """Record a message; optionally auto-translate to receiver's language."""
        self._check()
        pair = self._partnerships.require(partnership_id, "partnership")
        if sender_id not in (pair["user_a"], pair["user_b"]):
            raise InvalidInputError(
                "sender is not part of this partnership")
        if target_lang is None:
            src = ("language_a" if sender_id == pair["user_a"]
                   else "language_b")
            dst = ("language_b" if sender_id == pair["user_a"]
                   else "language_a")
            translated = self._translation.translate(
                text, pair[src], pair[dst])
        else:
            translated = self._translation.translate(text, "en", target_lang)
        msg = {
            "id": None,
            "partnership_id": partnership_id,
            "sender_id": sender_id,
            "text": text,
            "translated": translated,
        }
        return self._messages.add(msg)

    def get_translation(self, text, from_lang, to_lang):
        self._check()
        return self._translation.translate(text, from_lang, to_lang)

    def messages_for(self, partnership_id):
        self._check()
        self._partnerships.require(partnership_id, "partnership")
        return [m for m in self._messages.all()
                if m["partnership_id"] == partnership_id]


# ---------------------------------------------------------------------------
# Module 4: Cultural Workshop
# ---------------------------------------------------------------------------
class WorkshopManager:
    """Live + pre-recorded sessions by experts; join/ask/discuss. Stage 4."""

    MIN_STAGE = 4

    def __init__(self, profiles):
        self._profiles = profiles
        self._workshops = _Store()
        self._questions = _Store()
        self._discussions = _Store()
        self._active = False

    def activate(self):
        self._active = True

    def _check(self):
        if not self._active:
            raise DependencyError(
                "Cultural Workshop module not active (requires stage "
                "{0})".format(self.MIN_STAGE))

    def create_workshop(self, title, expert_id, kind="live", scheduled_at=None):
        """kind: 'live' or 'prerecorded'."""
        self._check()
        if kind not in ("live", "prerecorded"):
            raise InvalidInputError("kind must be 'live' or 'prerecorded'")
        self._profiles.get_user(expert_id)
        workshop = {
            "id": None,
            "title": title,
            "expert_id": expert_id,
            "kind": kind,
            "scheduled_at": scheduled_at,
            "participants": [],
        }
        return self._workshops.add(workshop)

    def join_workshop(self, workshop_id, user_id):
        self._check()
        ws = self._workshops.require(workshop_id, "workshop")
        self._profiles.get_user(user_id)
        if user_id not in ws["participants"]:
            ws["participants"].append(user_id)
        return ws["participants"]

    def ask_question(self, workshop_id, user_id, text):
        self._check()
        ws = self._workshops.require(workshop_id, "workshop")
        self._profiles.get_user(user_id)
        q = {"id": None, "workshop_id": workshop_id, "user_id": user_id,
             "text": text}
        return self._questions.add(q)

    def post_discussion(self, workshop_id, user_id, text):
        """Participate in discussion; returns comment id."""
        self._check()
        self._workshops.require(workshop_id, "workshop")
        self._profiles.get_user(user_id)
        c = {"id": None, "workshop_id": workshop_id, "user_id": user_id,
             "text": text}
        return self._discussions.add(c)

    def get_workshop(self, workshop_id):
        self._check()
        ws = self._workshops.require(workshop_id, "workshop")
        enriched = dict(ws)
        enriched["questions"] = [
            q for q in self._questions.all()
            if q["workshop_id"] == workshop_id]
        enriched["discussions"] = [
            c for c in self._discussions.all()
            if c["workshop_id"] == workshop_id]
        return enriched


# ---------------------------------------------------------------------------
# Module 5: Feedback & Rating (final)
# ---------------------------------------------------------------------------
class FeedbackManager:
    """Rate/review virtual tours, language exchanges, workshops. Stage 5 (final)."""

    MIN_STAGE = 5

    def __init__(self):
        self._feedback = _Store()
        self._active = False

    def activate(self):
        self._active = True

    def _check(self):
        if not self._active:
            raise DependencyError(
                "Feedback module not active (requires stage "
                "{0})".format(self.MIN_STAGE))

    def submit_feedback(self, target_type, target_id, user_id, rating, review=""):
        """target_type in {'tour','exchange','workshop'}; rating 1-5."""
        self._check()
        if target_type not in ("tour", "exchange", "workshop"):
            raise InvalidInputError(
                "target_type must be one of tour/exchange/workshop")
        if not (1 <= rating <= 5):
            raise InvalidInputError("rating must be an integer in [1, 5]")
        fb = {
            "id": None,
            "target_type": target_type,
            "target_id": target_id,
            "user_id": user_id,
            "rating": rating,
            "review": review or "",
        }
        return self._feedback.add(fb)

    def average_rating(self, target_type, target_id):
        self._check()
        ratings = [f["rating"] for f in self._feedback.all()
                   if f["target_type"] == target_type
                   and f["target_id"] == target_id]
        if not ratings:
            return 0.0
        return sum(ratings) / len(ratings)

    def reviews_for(self, target_type, target_id):
        self._check()
        return [f for f in self._feedback.all()
                if f["target_type"] == target_type
                and f["target_id"] == target_id]


# ---------------------------------------------------------------------------
# Facade / Coordinator
# ---------------------------------------------------------------------------
class CulturalExchangeHub:
    """Wires the five modules in the mandated build order via stage gating."""

    def __init__(self):
        self.profiles = ProfileManager()
        self.tours = VirtualTourManager(self.profiles)
        self.language = LanguageLearningManager(self.profiles)
        self.workshops = WorkshopManager(self.profiles)
        self.feedback = FeedbackManager()
        self._stage = 0

    # -- staging ------------------------------------------------------------
    def stage(self):
        return self._stage

    def build(self, target_stage):
        """Advance the platform through the mandated build stages (1..5)."""
        if not 1 <= target_stage <= 5:
            raise InvalidInputError("stage must be in [1, 5]")
        while self._stage < target_stage:
            nxt = self._stage + 1
            if nxt == 1:
                self.profiles.activate()
            elif nxt == 2:
                if self._stage < 1:  # pragma: no cover - guarded by loop
                    raise DependencyError("stage 1 required before stage 2")
                self.tours.activate()
            elif nxt == 3:
                if self._stage < 2:
                    raise DependencyError("stage 2 required before stage 3")
                self.language.activate()
            elif nxt == 4:
                if self._stage < 3:
                    raise DependencyError("stage 3 required before stage 4")
                self.workshops.activate()
            elif nxt == 5:
                if self._stage < 4:
                    raise DependencyError("stage 4 required before stage 5")
                self.feedback.activate()
            self._stage = nxt
        return self._stage


# ---------------------------------------------------------------------------
# Convenience helpers / demo
# ---------------------------------------------------------------------------
def build_demo_hub():
    """Build a fully staged hub with sample data for manual inspection."""
    hub = CulturalExchangeHub()
    hub.build(5)

    ann = hub.profiles.create_user(
        "anna", "anna@example.com", cultural_background="French",
        interests="art, history", profile_picture="anna.jpg")
    ben = hub.profiles.create_user(
        "ben", "ben@example.com", cultural_background="Japanese",
        interests="language, food", profile_picture="ben.jpg")
    chen = hub.profiles.create_user(
        "chen", "chen@example.com", cultural_background="Chinese",
        interests="music, architecture")

    tour = hub.tours.create_tour(
        "Louvre", ann, "models/louvre.glb", "Virtual tour of the Louvre")
    hub.tours.add_hotspot(tour, "Mona Lisa", "Leonardo da Vinci, c. 1503",
                          (1.0, 2.0, 3.0))
    hub.tours.add_audio_guide(tour, "Louvre Highlights", "audio/louvre.mp3")

    pair = hub.language.pair_users(ann, ben, "en", "es")
    hub.language.send_message(pair, ann, "hello")
    hub.language.send_message(pair, ben, "gracias")

    ws = hub.workshops.create_workshop(
        "Tea Ceremony", chen, "live", scheduled_at="2026-08-01T10:00:00Z")
    hub.workshops.join_workshop(ws, ann)
    hub.workshops.ask_question(ws, ben, "Which tea is used?")
    hub.workshops.post_discussion(ws, ann, "This is fascinating.")

    hub.feedback.submit_feedback("tour", tour, ben, 5, "Excellent tour!")
    hub.feedback.submit_feedback("exchange", pair, chen, 4, "Great practice.")
    hub.feedback.submit_feedback("workshop", ws, ann, 5, "Very informative.")

    return hub


if __name__ == "__main__":
    hub = build_demo_hub()
    feedback_total = (len(hub.feedback.reviews_for("tour", 1))
                      + len(hub.feedback.reviews_for("exchange", 1))
                      + len(hub.feedback.reviews_for("workshop", 1)))
    print("CulturalExchangeHub demo: stage={0}, users={1}, tours={2}, "
          "partnerships={3}, feedback={4}".format(
              hub.stage(), hub.profiles.user_count(),
              len(hub.tours.list_tours()),
              len([p for p in hub.language._partnerships.all()]),
              feedback_total))
