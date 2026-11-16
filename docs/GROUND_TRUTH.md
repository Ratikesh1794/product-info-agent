# Ground truth for the assignment questions

Computed directly from `backend/data/bosch_product_catalog_mock.csv` with plain `csv` + `json`, independent of the
app's catalog/tool code. Use it to validate the agent by hand: each section lists what a correct answer contains
and what would be wrong.

---

## Q1. "What's the difference between the GSR18V-535CN and the GSR18V-535CB25?"

**Same tool, different kit.** Every tool spec is identical: 485 in-lbs (≈40 ft-lbs) torque, 0–600/0–2,100 rpm,
1/2" keyless ratcheting chuck, 25 clutch settings, LED, Compact tier, brushed motor, 18V platform, Active.

| | GSR18V-535CN | GSR18V-535CB25 |
|---|---|---|
| MSRP | **$70.99** | **$339.00** |
| In the box | Drill/driver only | Drill/driver + **(2) GBA18V80C 8.0 Ah batteries** + **GAL18V160C charger** + **L-BOXX-2 case** |
| Battery included | No | Yes |
| Weight / dims | 3.1 lb, 5.8×3.5×11.8 in | 4.5 lb, 16.4×5.8×8.5 in (kit) |
| Rating | 4.7 (187 reviews) | 4.4 (274 reviews) |
| Sold at | Toolup, Lowe's | Acme Tools, Toolup, Ohio Power Tool |

Minor: feature lists differ by one line each (CN "Ergonomic soft-grip handle", CB25 "Precision clutch for repeatable results").

- ✅ Must say: same tool / same performance; difference is batteries + charger + case; both prices.
- ❌ Wrong: claiming different torque/speed, or that the CN includes a battery.

---

## Q2. "I need an 18V impact wrench with at least 500 ft-lbs of torque under $300."

Impact wrenches list **two** torque specs, so the answer depends on which one:

**By max fastening torque (standard)** → exactly 2, both Active, bare tool:

| Model | MSRP | Fastening | Nut-busting |
|---|---|---|---|
| GDS18V-30CPN | $279 | 652 | 913 |
| GDS18V-800CPN | $299 | 1,450 | 2,029 |

**By nut-busting torque** → adds 6 more Active (and 1 discontinued):
GDS18V-75N $159, GDS18V-55N $169, GDS18V-55B $259, GDS18V-75B $279, GDS18V-190B $289, GDS18V-55B15 $299
(503–630 nut-busting, 360–450 fastening). GDS18V-190N $189 also qualifies but is **Discontinued**.

**No torque listed:** the 10 Active "Two-in-One Impact Driver/Wrench" (GDX18V-…) under $300.

- ✅ Must name GDS18V-30CPN and GDS18V-800CPN, say it used fastening torque, mention the nut-busting option.
- ❌ Wrong: recommending GDS18V-190N (discontinued), GDS18V-30CN (160 ft-lbs), anything over $300, or giving the GDX models a torque value.

---

## Q3. "Which oscillating blades fit my StarlockPlus tool?"

A StarlockPlus tool takes **Starlock and StarlockPlus** blades, but **not StarlockMax-only** blades.

- **30 Active blades fit**: 18 Starlock-interface + 12 StarlockPlus-interface (plus 2 Temporarily Out of Stock, 1 Discontinued).
- Cheapest: OSLS7801 Starlock wood plunge $9.97 · OSLS9751 scraper $11.97 · OSLP4051 StarlockPlus wood plunge $11.97 ·
  OSLS5131 bi-metal plunge $12.97 · OSLP1351 rigid scraper $13.97.
- StarlockPlus tools in the catalog: GOP12V-50N/50B2/25N/25B2, GOP18V-1300N/B/B15, GOP18V-150N/B/B15.

- ✅ Must include both Starlock and StarlockPlus blades.
- ❌ Wrong: **any OSLM… blade** (15 of them, "StarlockMax oscillating tools only").

---

## Q4. "Is this drill still available? If not, what replaced it?"

"This drill" names no product → **the correct first reply is a clarifying question.** Then test with a model:

| Try this model | Status | Expected answer |
|---|---|---|
| **GSB12V-535B2** | Discontinued | → **GSB18V-75CPN** ($199, Active). Flag: **12V → 18V**, kit → **bare tool** |
| **GSB18V-300CPNL** | Discontinued | → **GSB12V-75B2** ($219). Flag: **18V → 12V** (a downgrade) |
| **GSR18V-80B** | Discontinued | → **GSR18V-80N** ($119). Flag: kit → bare tool |
| **GSR18V-30B15** | Discontinued | **No replacement on record**: must not invent one |
| **GSR18V-80B25** | Temporarily Out of Stock | Not discontinued; no replacement needed |
| **GDR18V-55CPN** | Coming Soon | Launch date has passed (stale status), so flag that |
| **GSR18V-535CN** | Active | Available |

---

## Q5. "Do you have a green-beam line laser with at least 100 ft range?"

- **Yes: 29 Active** green line lasers with **working range ≥ 100 ft** (4 more are discontinued:
  GLL220GCGK, GLL97GCG, GLL280GC, GLL240GCGK).
- Cheapest: GLL269GC $329 (100 ft) · GLL324GX $339 · GLL81GX $349 · GLL359GCG $359 · GLL320GC $379 (130 ft).
- **14 more reach 100 ft only with a laser receiver** (e.g. GLL46G $279: 65 ft working, 130 ft with receiver).
- CST/berger **57-GLR400** "Green Line Laser" has **no specs** (and is Discontinued), so range is unknown.

- ✅ Must answer yes with models ≥100 ft working range, ideally mention the receiver-only ones.
- ❌ Wrong: listing a 65 ft laser as meeting 100 ft without saying "with receiver"; listing discontinued ones as available.

---

## Q6. "Where can I buy it?"

Depends on context:

- **Asked cold** (no product yet) → must **ask which product**.
- **After a product was discussed** → retailers from `available_at`, names only (URLs are fake):

| Model | Sold at |
|---|---|
| GSR18V-535CN | Toolup, Lowe's |
| GSR18V-535CB25 | Acme Tools, Toolup, Ohio Power Tool |
| GDS18V-30CPN | Toolup, Lowe's, Ohio Power Tool, Amazon |
| GDS18V-800CPN | Ohio Power Tool, Lowe's |
| GSB18V-75CPN | Ferguson, White Cap, The Home Depot, Toolup, Lowe's |
| PSJ18WB-M | Acme Tools, Lowe's, Toolup |
| PSJ18WG-M | Amazon, White Cap |

- ❌ Wrong: any URL; any retailer not in that product's list; claiming live stock levels.

---

## Q7. "Do you have the 18V heated jacket in a women's medium?"

**Yes, two:**

| Model | Color | MSRP | Status | Sold at |
|---|---|---|---|---|
| **PSJ18WB-M** | Black | $199 | Active | Acme Tools, Lowe's, Toolup |
| **PSJ18WG-M** | Grey | $199 | Active | Amazon, White Cap |

Kit includes GBA18V20 2.0 Ah battery, charger, battery holder/USB adapter. Women's M = 38–40 in chest.
Women's 18V jackets come in S–2XL only (no 3XL). There's also a women's M **vest** (PSV18WB-M): a vest, not a jacket.

- ❌ Wrong: "no women's sizes" (the earlier bug), the men's PSJ18MB-M/MG-M, or the vest as a jacket.
