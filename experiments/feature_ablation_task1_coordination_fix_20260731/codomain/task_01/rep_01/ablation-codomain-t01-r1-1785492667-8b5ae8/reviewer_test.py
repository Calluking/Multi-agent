# Reviewer boundary + invariant test for interface:translation_tool_to_exchange.
# Run: python3 reviewer_test.py
from solution import (
    CulturalExchangeHub, ValidationError, NotFoundError,
    TranslationTool, LanguageLearningModule,
)

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print("PASS", name)
    except Exception as e:
        failed += 1; print("FAIL", name, ":", type(e).__name__, e)

# ---------- exact contract boundary test ----------
def boundary():
    hub = CulturalExchangeHub()
    clara = hub.registry.register("clara", "clara@ex.com", "Clara", "FR", ["french"])
    dario = hub.registry.register("dario", "dario@ex.com", "Dario", "IT", ["french"])
    pair = hub.language.pair_users(clara, dario, "french")
    hub.language.send_exchange_message(pair, clara, "hello")
    msg = hub.language.exchange_messages(pair)[0]
    assert msg.delivered_text == "bonjour", msg.delivered_text
    assert msg.sender_id == clara and msg.pair_id == pair

def non_member_rejected():
    hub = CulturalExchangeHub()
    a = hub.registry.register("a", "a@ex.com", "A", "BG", ["english"])
    b = hub.registry.register("b", "b@ex.com", "B", "BG", ["english"])
    c = hub.registry.register("c", "c@ex.com", "C", "BG", ["english"])
    p = hub.language.pair_users(a, b, "english")
    try:
        hub.language.send_exchange_message(p, c, "hi"); raise AssertionError("accepted")
    except ValidationError: pass

def empty_rejected():
    hub = CulturalExchangeHub()
    a = hub.registry.register("a", "a@ex.com", "A", "BG", ["english"])
    b = hub.registry.register("b", "b@ex.com", "B", "BG", ["english"])
    p = hub.language.pair_users(a, b, "english")
    try:
        hub.language.send_exchange_message(p, a, "   "); raise AssertionError("accepted")
    except ValidationError: pass

def unknown_pair_rejected():
    hub = CulturalExchangeHub()
    a = hub.registry.register("a", "a@ex.com", "A", "BG", ["english"])
    try:
        hub.language.send_exchange_message(999, a, "hi"); raise AssertionError("accepted")
    except NotFoundError: pass

def delivered_never_empty():
    hub = CulturalExchangeHub()
    a = hub.registry.register("a", "a@ex.com", "A", "BG", ["english"])
    b = hub.registry.register("b", "b@ex.com", "B", "BG", ["english"])
    p = hub.language.pair_users(a, b, "english")
    for text in ["zzz_nonexistent", "谢谢", "123"]:
        hub.language.send_exchange_message(p, a, text)
        dt = hub.language.exchange_messages(p)[-1].delivered_text
        assert dt and dt.strip(), "delivered empty for %r" % text

def deterministic_output():
    t = TranslationTool()
    assert t.translate("hello", "es") == t.translate("hello", "es") == "hola"
    assert LanguageLearningModule._EXCHANGE_LANG_TO_TOOL["french"] == "fr"

def tool_lang_resolution():
    hub = CulturalExchangeHub()
    a = hub.registry.register("a", "a@ex.com", "A", "BG", ["french"])
    b = hub.registry.register("b", "b@ex.com", "B", "BG", ["french"])
    p = hub.language.pair_users(a, b, "french")
    hub.language.send_exchange_message(p, a, "welcome")
    assert hub.language.exchange_messages(p)[0].delivered_text == "bienvenue"

for n, f in [
    ("boundary-hello-bonjour", boundary),
    ("non-member-rejected", non_member_rejected),
    ("empty-rejected", empty_rejected),
    ("unknown-pair-rejected", unknown_pair_rejected),
    ("delivered-never-empty", delivered_never_empty),
    ("deterministic-output", deterministic_output),
    ("tool-lang-resolution", tool_lang_resolution),
]:
    check(n, f)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
