# VISTIQ — University Demonstration Script (10–15 minutes)

Grounded in what has actually been built and verified in this repository — not an aspirational script. Every claim below (scores, confidence values, messages) is what the real application actually produces; nothing here is scripted/fake output.

## Before you start

```powershell
.\start-vistiq.ps1
```

Wait for both windows to print "ready"/"Application startup complete", then open `http://127.0.0.1:5173`. Check whether the Colab GPU worker is connected (see Part 5) — if it's disconnected, that's fine, the script below has an honest fallback for exactly that.

## Part 1 — Introduction (1 min)

"VISTIQ is a personal wardrobe and outfit-recommendation app. The brief problem it solves: most 'wardrobe apps' just let you filter/search your own clothes by tag — that's not recommendation. VISTIQ actually scores and ranks outfit *combinations* from what you own, using a real rule-based scoring engine, plus a real trained image classifier so you don't have to manually tag every photo."

Architecture in one sentence: React frontend → FastAPI backend → SQLite, with two optional ML components — a small CPU classifier for wardrobe photos, and an experimental remote-GPU virtual try-on feature.

## Part 2 — Authentication (1 min)

1. Register a fresh account live, on stage (more convincing than a pre-made one).
2. Say: "Passwords are hashed with Argon2id — the modern standard, not something rolled by hand. Sessions are opaque server-side tokens in an HttpOnly cookie, so JavaScript on the page can never read the session token even if something were XSS'd. Every state-changing request also needs a CSRF header."

## Part 3 — Wardrobe: upload and classification (3 min)

1. Add Item → upload a real clothing photo.
2. Point out the **AI prediction** and its **confidence %** appearing live — "This is a real MobileNetV3-Small CNN, fine-tuned by transfer learning on a real clothing dataset (clothing-dataset-small, CC0), running inference on CPU right now — not a lookup table."
3. Point out the **suggested color** — "That's not from the same model. It's classical computer vision: OpenCV GrabCut to find the garment's pixels, then K-means clustering in HSV space to find the dominant color. Two completely different techniques for two different jobs."
4. If a quality warning appears (blurry/dark/overexposed), point it out: "That's a Laplacian-variance blur check and a brightness check — both run before you ever see a prediction."
5. **Correct the category or color if it's wrong** — "Nothing here is ever silently trusted. Whatever you confirm is what actually gets saved and scored later — the AI prediction is a suggestion, full stop."
6. Save. Show it in My Wardrobe. **Refresh the page** — still there (SQLite persistence, not browser state).

## Part 4 — AI Stylist and scoring (3 min)

1. Open AI Stylist, pick an occasion, generate.
2. Point at a result's score and say the real formula out loud: *"30% color compatibility, 20% category compatibility, 20% style, 15% occasion, 10% how often you've worn similar things, 5% weather — six real weighted components, not a black box."*
3. Expand the explanation — "Every reason shown is derived from the actual scores for this specific outfit. If color scored low, it says so; it never invents a generic reason."
4. Click a specific wardrobe item as the **anchor**, regenerate — "Every single outfit now structurally includes that exact item — it's enforced before outfits are even generated, not filtered afterward."
5. If more than one outfit is returned, mention diversity: "If I had near-duplicate outfits, there's a diversity reranker — Jaccard overlap between item sets, discounting a candidate's score by how much it overlaps what's already shown, but it never promotes a worse outfit just to look different. Rank #1 is always the single best-scoring outfit."

## Part 5 — Virtual Try-On (2–4 min)

**Check first**: does `/try-on` show the garment-selection flow normally, or the red "Could not reach the virtual try-on worker" message?

**If the Colab worker is connected:**
1. Select a garment, upload a person photo, submit.
2. "This sends an authenticated HTTPS request — bearer token, never visible to the browser — to a FastAPI worker running CatVTON on a Tesla T4 in Google Colab, over a temporary Cloudflare tunnel, since my laptop has no GPU."
3. Wait for completion (~70–80s is typical), show the before/after.
4. Refresh — still there. Delete — gone, including the file on disk.

**If the Colab worker is disconnected (the honest, disclosed state):**
1. Show the actual app's own message: *"Could not reach the virtual try-on worker. Please try again later."* — "This is deliberate honesty, not a bug — Colab's free GPU tier has a usage quota, and the app never pretends a result exists when it doesn't."
2. Open `demo-assets/saved-results-fallback/` in File Explorer (**not** inside the app) and say explicitly: *"This is a saved result from a real, verified run earlier — not generated live right now."* Never paste it into the app or call it live.

## Part 6 — Technical architecture (1–2 min)

"Frontend and backend are fully separate — React talks to FastAPI purely over HTTP with cookies, nothing shared in-process. Every wardrobe item, every recommendation request, every try-on job is scoped to the logged-in user's own ID at the database query level — a second account literally cannot address another user's rows; it gets a plain 404, not a permissions error, so it can't even confirm something exists."

## Part 7 — Testing (1 min)

"202 automated backend tests, covering authentication, cross-user isolation, the full recommendation engine across every scoring dimension, image validation, and the try-on job lifecycle including recovery from an interrupted job. Frontend TypeScript, ESLint, and the production build are all clean." (Run `pytest tests/ -q` live if there's time — it takes well under a minute.)

## If something breaks live

- **Login fails / wardrobe won't load**: almost certainly the frontend isn't bound to `127.0.0.1` — check the terminal windows `start-vistiq.ps1` opened.
- **A page is blank**: open DevTools console, check for a red error — most likely the backend isn't running; check `http://127.0.0.1:8000/health`.
- **Classification hangs** on a genuinely unusual image: wait — it will resolve (see known limitation in the viva guide); don't restart mid-request.
