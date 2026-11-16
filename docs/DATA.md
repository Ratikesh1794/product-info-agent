# Catalog data: what's in it and what it means for the agent

Source: `backend/data/bosch_product_catalog_mock.csv`. All figures come from queries over the full file.

## Shape

- **2,261 products, 37 columns.** No duplicate `model_number` or `product_name`, no missing `msrp_usd`, and no prompt-injection or placeholder text in descriptions.
- **Categories:** Accessories 1,059 · Power Tools 631 · Measuring Tools 166 (85 line lasers) · Rotary Tool Accessories 130 · Jobsite Apparel 83 · Hand Tools 70 · Rotary Tools 58 · Digital Fabrication 27 · Batteries & Chargers 22 · Storage & Organization 15.
- **Brands:** Bosch 1,995 · Dremel 215 · CST/berger 26 · RotoZip 25.
- **Price:** $2.97 to $6,999. Median $25 for accessories, $249 for power tools, $329 for measuring tools.
- **Status:** Active 1,969 · Discontinued 217 · Temporarily Out of Stock 42 · Coming Soon 33.
- **Platforms:** Bosch 18V (502), Bosch 12V Max (195), Dremel 12V / Bosch 12V Max (16), 120V corded (117).
- **Retailers:** 12 names, led by Amazon, Home Depot, Lowe's, White Cap, Ferguson and Acme Tools. Every product lists at least one. URLs are fake (per the brief) and are never shown.
- **Missing values follow category:** `voltage_v` is blank on 63% of products, `battery_platform` 68%, `key_features` 43% and `compatible_with` 19%. These are mostly non-powered accessories, so blank means "not applicable", not dirty data.

## Structure

- **Product families.** One tool is sold as several SKUs: `-N` (tool only), `-B`/`-CB` (kit), `-B15`/`-B25` (bigger battery kits) and `-NL` (with case). Tool specs are identical within a family; only `whats_in_the_box`, `battery_included` and price change.
- **Variants are separate SKUs.** Apparel has one SKU per fit, colour and size, and these live in `technical_specs` (`fit`, `size`, `color`).
- **`technical_specs` is sparse JSON.** It has 175 keys overall: 104 in Power Tools and 1 in Hand Tools. 7,688 values are strings (`"1/2"`, `"0-600/0-2100"`, `"5/8 to 2-1/8"`), so only true numbers support range filters.
- **`compatible_with` is a small vocabulary.** 72 distinct tokens such as "Bosch 18V (CORE18V / PROFACTOR compatible)", "Dremel 4000", "SDS-plus rotary hammers" and "LR6/LR8 receivers". Whole-word matching against it is reliable.

## Traps and how the agent handles them

| # | Finding | Handling |
|---|---|---|
| 1 | **Q1 compares two kits of the same tool.** GSR18V-535CN ($70.99, bare tool) and GSR18V-535CB25 ($339) have identical specs; the CB25 adds 2× 8 Ah batteries, a charger and an L-BOXX | `compare_products` returns only the differing fields, so the answer leads with "same tool, different kit" |
| 2 | **Q2: impact wrenches have two torque specs**, `max_fastening_torque_ft_lbs` and `nut_busting_torque_ft_lbs`. "18V, ≥500 ft-lbs, <$300" gives GDS18V-30CPN ($279, 652) and GDS18V-800CPN ($299, 1,450) on fastening torque; on nut-busting it adds GDS18V-75N/55N (503, $159/$169) | The agent states which torque it used, or asks |
| 3 | Drills store torque in in-lbs and wrenches in ft-lbs | Catalog loader mirrors every `*_in_lbs` and `*_ft_lbs` key into the other unit |
| 4 | The 12 GDX two-in-one "Impact Driver/Wrench" products have **no torque spec** | Search reports `missing_spec_data`, and the agent says "torque not listed" instead of silently dropping them |
| 5 | **Replacements are not always like-for-like.** GSB12V-535B2 (12V kit) is replaced by GSB18V-75CPN (18V bare tool); GSR18V-80B (kit) by GSR18V-80N (bare) | `check_availability` lists platform, voltage and kit changes |
| 6 | **61 of the 217 discontinued products have no replacement.** No replacement chains or dangling references | The agent says "no replacement on record" and offers active alternatives |
| 7 | **All 217 discontinued products still list retailers** | "Where can I buy it?" on a discontinued product carries a stock warning |
| 8 | **All 33 "Coming Soon" products have launch dates in the past** (Jan to Apr 2026). They're also the only products without ratings | Report the status but flag the stale date |
| 9 | **Q5: lasers have two ranges.** 33 green lasers reach ≥100 ft on `working_range_ft`; 14 more reach it only with a receiver (`range_with_receiver_ft`) | Answer on the working range by default and mention receiver-only options |
| 10 | CST/berger `57-GLR400` "Green Line Laser" has empty specs (18 products have empty specs overall) | "Range not listed", never guessed |
| 11 | **Q3: three Starlock tiers.** Blades say "Starlock, StarlockPlus and StarlockMax oscillating tools", "StarlockPlus and StarlockMax oscillating tools" or "StarlockMax oscillating tools only". The catalog has no StarlockMax tools | Whole-word match on the tier name: "StarlockPlus" matches the first two and excludes Max-only. Substring "Starlock" would be wrong |
| 12 | **Tool-side Starlock data conflicts.** Every GOP tool lists "StarlockPlus blades \| Starlock blades" in `compatible_with`, but `accessory_interface` says `Starlock` on 12 of them | Trust `accessory_interface` (blade-side tokens agree with it) and surface the conflict |
| 13 | **Q7 is answerable.** PSJ18WB-M and PSJ18WG-M are 18V women's medium jackets ($199, Active). A vest, PSV18WB-M, also exists. Women's sizes run S–2XL, men's S–3XL | Filter on `fit` and `size` specs; jacket and vest are distinct; "women's 3XL" is a valid "no" |
| 14 | 5 model numbers disagree with their product name (`VF100`, `GLL332GCKB`, `GLL370GCGB`, `LBOXX-RACK`, `LB-CART`); e.g. `GLL370GCGB` is named "GLL370GCG…" but describes a different laser | `model_number` is the key; the conflict is surfaced via `Catalog.audit()` |

## Scenarios this gives us for "doesn't know / clarifies"

- Torque ambiguity, fastening vs nut-busting (trap 2): ask, or state the assumption.
- Discontinued with no replacement (trap 6): say so, then suggest active alternatives.
- Laser with no listed range (trap 10): "not listed".
- Women's 3XL jacket (trap 13): no such SKU.
- "Where can I buy it?" with no product in context: ask which product.
- Stale Coming Soon (trap 8): give the status with a caveat.
- **Blades also carry flags** `fits_starlock_tools`, `fits_starlockplus_tools`, `fits_starlockmax_tools`, and these agree with the `compatible_with` tokens.
