# CulturalExchangeHub — Implementation Plan

## Goal
Build a deterministic, stdlib-only Python web platform (single `solution.py`) connecting users via virtual tours, language exchanges, and cultural workshops, with feedback/rating as the final tier.

## Architectural Constraints
- Single file `solution.py`; stdlib only (no third-party deps).
- Deterministic behavior: seed randomness, no wall-clock-dependent logic; stable iteration order everywhere.
- Layered, dependency-ordered modules (build order enforces TASK.md sequencing).

## Module Architecture (dependency order)
1. **User System** (must exist first — everything depends on it)
   - Registration: unique username/email, password hashing (hashlib, salted), profile fields (name, bio, cultural background, interests, avatar).
   - Profile management: update profile, upload/set avatar (store as base64 string or file reference), list/search users.
2. **Virtual Tour Module** (depends on users; after #1)
   - Models of landmarks/sites: id, name, region, description, 3D model ref (string), hotspots, audio guide (text/ref), host user.
   - Interactive hotspots: clickable point → info block; audio guide attached per tour/site.
   - Permissions: only registered users create/manage tours; viewable by all.
3. **Language Exchange Module** (after tours functional)
   - Pair users for real-time language exchanges (match by target/native language interests).
   - Translation tool: deterministic stdlib-based translator (character/word-level mapping tables; no external API) to assist communication.
   - Only available once virtual tour module is functional (guard at runtime).
4. **Workshop Module** (after language complete)
   - Live & pre-recorded sessions led by cultural experts (users with `expert` role).
   - Join sessions, ask questions, participate in discussion threads (post/comment logs).
   - Guard: only enabled after language module.
5. **Feedback & Rating System** (final step, after all modules)
   - Rate & review virtual tours, language exchanges, and workshops.
   - Aggregate ratings (mean, count) per target; store review text + author + timestamp.
   - Guard: only enabled after all other modules are in place.

## Dependencies
- Users → Tours → Language → Workshops → Feedback (strict build/activation order).
- Enforce via module bootstrap flags: a subsystem is "available" only after its predecessor is initialized. Include an `availability()`/`is_ready()` check returning the current unlock stage.

## Deterministic Tests (run via `__main__` / `if __name__ == "__main__"`)
- Test user registration (duplicate username/email rejected), profile update, avatar set.
- Test tour creation with hotspots + audio guide; non-registered user cannot create.
- Test language pair matching + translation determinism (same input → same output).
- Test workshop join, question ask, discussion post.
- Test rating aggregation (mean/count correctness) for tours, exchanges, workshops.
- Test staging guards: feedback/language/workshop rejected before predecessor ready.
- All tests assert exact values; exit code 0 on pass, nonzero on failure (no assertions skipped).

## Edge Cases
- Duplicate usernames/emails; empty/whitespace fields; invalid emails.
- Unknown/unauthenticated actions (must fail gracefully).
- Avatar: oversized/failed upload fallback to default; missing file.
- Translation: empty string, unknown words (pass through), case handling — deterministic.
- Matching: user with no compatible partner → clear empty result, no crash.
- Rating: rating out of range (e.g. <0 or >5) rejected; duplicate review policy; zero reviews → no division by zero.
- Workshops: joining full/closed session rejected; non-expert cannot host.
- Determinism: no reliance on time/random in outputs used by tests (timestamps optional/metadata only, excluded from assertions).

## Output
- `solution.py` containing all modules + embedded deterministic test runner.
- Never claim tests passed without running them.
