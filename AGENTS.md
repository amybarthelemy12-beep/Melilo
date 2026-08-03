✅ Approved (can ingest, derive, surface in any product including paid tiers)
Public domain — federal works under 17 USC § 105, court opinions, state statutes (uncopyrightable government edicts)
CC0 — fully clean, no attribution required
CC BY (Attribution-only) — clean; surface attribution wherever the data renders
❌ Dealkillers (cannot ingest, period)
License	Why
CC BY-NC (NonCommercial)	Incompatible with for-profit / PBC plans (paid Caselore tiers, county dashboards, institutional API access). Retired ProPublica + Eviction Lab on this.
CC BY-SA (ShareAlike)	The ShareAlike clause forces every downstream derivative to be re-released under CC BY-SA — cascades into UI rendering, Civic Health Score derivations, every paid product. Retired CCDI (LSC Civil Court Data Initiative) + CourtListener on this.
CC BY-ND (NoDerivatives)	Incompatible with any data transformation or schema derivation. Effectively un-ingestable.
Aggregator-licensed	License ambiguity, registration walls, vendor terms claiming copyright on public records. Functionally restrict redistribution — same effect as the CC NonCommercial/ShareAlike dealkillers. Retired SAM.gov (D&B contamination + automated-gathering prohibition) + ICPSR (redistribution clause) on this.
🔍 Verify-at-source rule
Verify the license at the upstream source itself (the dataset's own license page or footer), not from secondary documentation or our own internal notes. Re-check at every revision. The CCDI lesson is the reason: it was recorded as CC0 in our docs but was actually CC BY-SA upstream, and the wrong record sat for months before audit caught it. LegiScan is the mirror image — was on the deny-list as "commercial API" until 2026-05-21 when verify-at-source confirmed CC BY 4.0.

🪶 Indigenous data sovereignty (separate hard gate — not a license question)
GovParti does not assert any right to automated capture or redistribution of content from sovereignty-affiliated jurisdictions. Manual curation only for:

Alaska (state FIPS 02) — ANCSA blanket
Hawaii (state FIPS 15) — Native Hawaiian sovereignty
Lower-48 indigenous-jurisdiction counties — curated ~140 FIPS list
Tribal sovereign / nonprofit hostnames — *.oyate.org, *.tribe.*, *.nation.*, *.nsn.us, etc.
Enforced by shouldExcludeFromAutoSweep in workers/scrapers/_shared/tribal-jurisdictions.ts before any HTTP fetch. CARE Principles (Collective Benefit, Authority to Control, Responsibility, Ethics) are the policy frame. Adding to the curated FIPS list is fine; removing requires sovereignty review.

🎥 Legislative floor video (separate licensing regime from text)
The Congressional Record text + bills + statutes are federal PD and ingest normally. Floor video carries its own terms:

C-SPAN — privately copyrighted, noncommercial/educational use only. Dealkiller for our posture.
Senate floor video — government work but restricted (no campaign/commercial-ad use)
House floor video — terms vary by access path
State legislatures — 50 separate regimes, many routed through Granicus
Hard rule: GovParti embeds chamber video players (iframe to the chamber's own stream); never downloads, re-hosts, transcribes, or redistributes. Embedding ≠ ingesting. Every channel ToS-classified per-source via embed_kind on state_legislature_entries.

🛡️ R2 Open Archive promotion gate
Three checks run before any object copies from govparti-internal → govparti-archive (public):

License compatibility — re-confirms upstream license against the allowlist
Indigenous sovereignty — re-applies shouldExcludeFromAutoSweep at the public-archive boundary
PII pattern scan — source-class-aware (federal aggregates pass; CFPB narratives, court party fields, NIH PI emails need per-source audit)
Per-source audit log lives at archive.govparti.org/methodology/internal/audit-log.json (planned).

📜 Living deny-list
The canonical NO-NO-LIST lives at docs/handover/00_overview/decisions/NO-NO-LIST. Every retirement carries dated rationale + the upstream-source citation. Notable entries: SAM.gov, ICPSR/NACJD/SAMHDA, ProPublica, Eviction Lab, CCDI, Prison Policy Initiative (CC BY-NC-SA + commercial bar), Vera Institute, OpenStates API/website. Entries get struck off when verify-at-source corrects a stale false-positive (LegiScan 2026-05-21).

TL;DR — the rules in 30 seconds
PD, CC0, CC BY only. Anything with NC, SA, or ND is out.
Verify the license at the upstream source — don't trust internal notes.
Aggregator licenses with restrictive terms are dealkillers even if they're not CC.
Indigenous jurisdictions = manual curation only. Hard gate.
Legislative video = embed-only. Never ingest.
R2 public archive = license + sovereignty + PII gates run before promotion.