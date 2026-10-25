# Home Bitcoin Miner Catalog (researched 2026-10-21)

Internal research doc. This doc doesn't change any site code.

**Scope:** home Bitcoin (SHA-256) miners that are sold right now and run on a normal US 120 V outlet at under about 1.6 kW. That covers desk, lottery and USB miners, open-source boards, heater miners, quiet or hydro home units, and 120 V "home edition" mods of industrial units.
**Out of scope:** Scrypt/DOGE/LTC and other-coin miners, stock industrial Antminer/Whatsminer units, EU-only 230 V heaters, and anything over about 1.6 kW.

**How the data was collected (2026-10-21):**
- Prices and stock came live from seller feeds: Shopify `products.json`, the WooCommerce Store API, or product-page HTML.
- Specs are the seller's or maker's stated figures from the listing, unless a cell says otherwise. Where a seller listing gives a range, the range is shown.
- "?" means not published or not found. Nothing was guessed.
- Prices are USD unless marked CA$ or €.

**Legend:**
- **Tracked:** ✅ means the model is in `collector/collect.py` `MODELS` (16 models).
- **Trackable:**
  - **JSON** means a Shopify or Woo feed was tested and works from the box.
  - **HTML** means the page returned 200 and the price parsed from HTML or JSON-LD.
  - **BLOCK** means the box got a 403 or a connection failure.
- **Category:** solo is under about 10 TH/s (lottery). pool is about 10 TH/s and up, for steady payouts. heater means the product is sold as a heater.
- **Flags:**
  - ⚠ means a caution.
  - **SPEC?** means the seller's claims look inflated or are missing.
  - **UNVETTED** means a seller with no track record checked by us.
  - **CLONE** means a closed-firmware derivative of the Bitaxe design.

## Seller trackability (tested with curl from the box today)

| Seller | Method | Result | Notes |
|---|---|---|---|
| bitcoinmerch.com | Shopify products.json | ✅ JSON (293 products, 3 pages) | Widest home catalog of any seller. Already a collector seller. |
| solosatoshi.com | Woo Store API | ✅ JSON | Already a collector seller. The `is_in_stock` flag can be wrong, so use `stock_availability` instead. |
| d-central.tech | Woo Store API | ✅ JSON (≈500 products, CAD) | Already a collector seller. It also lists many "Planned Board" placeholders at CA$0, which should be filtered out. |
| altairtech.io | Woo Store API returns empty; category HTML | ✅ HTML | `/product-category/home-miners/` parsed 18 products with prices. |
| dtvelectronics.com | Woo Store API | ✅ JSON | **Not yet a collector seller.** Sells the BitForge Nano at $169.99 and Bitaxe Gamma/Supra/Ultra "Retail Edition". Our affiliate application there is under review. |
| shop.futurebit.io | Shopify products.json | ✅ JSON | Official FutureBit store (Apollo III, Apollo II). |
| heatbit.com | Shopify | ✅ JSON | Already a collector seller. |
| powermining.io | Shopify | ✅ JSON (EUR) | Already a collector seller. |
| 21energy.com | Shopify | ✅ JSON (EUR) | EU heater maker (Ofen). Its products are 230 V, so they're out of scope for US buyers. |
| luckyminerclub.com | Shopify | ✅ JSON | ⚠ UNVETTED. This is a Lucky Miner reseller, not confirmed as official. It shows a "Bitaxe Gamma 602 1.8 TH/s" at $85, an inflated spec. |
| braiinsforge.com | HTML | ✅ HTML | Already a collector seller. |
| hammerminer.com | HTML (JS/Vite app) | ⚠ HTML 200 but rendered by JavaScript | Probably needs a browser or an API. Track Hammer via Altair and Bitcoin Merch instead. |
| fluminer.com, rehashheating.com, bitforge.store | HTML | 200 | Not parsed further. ReHash's USD checkout says "coming soon". |
| **shop.canaan.io** | any | ❌ **BLOCK 403** | Track Avalon at the resellers instead (already done). |
| **mineshop.eu** | products.json | ❌ **BLOCK 403** | The homepage returns 200, but the feed is blocked. |
| **ebay.com** | search | ❌ **BLOCK 403** | |
| **amazon.com** | search | ❌ **BLOCK** (connection failed) | |
| **nerdqaxestore.com, luckyminer.com, bitchimney.com, minerset.com, mineraxe.com** | any | ❌ connection failure from the box (curl 000/35) | |
| nexusminer.com | — | Redirects to a "/lander" parking page | ⚠ Nexus has no real brand site. Buy Nexus only via Bitcoin Merch. |

## A. Current home models (sold now)

### A1. Bitaxe family and other open-source boards

| Model | Maker | Hashrate | Watts | Typical price | Cat. | Where sold | Tracked | Trackable | Flags |
|---|---|---|---|---|---|---|---|---|---|
| Bitaxe Supra (403) | Open-source (various builders) | ~0.6-0.7 TH/s | ~14-15 W | $65-120 | solo | bitcoinmerch.com, solosatoshi.com (OOS), dtvelectronics.com $64.99, D-Central "BitSupra 1368" CA$245 | ✅ | JSON | Older gen |
| Bitaxe Ultra (204/207) | Open-source | ~0.425-0.5 TH/s | ~11-20 W | $60-120 | solo | bitcoinmerch.com, dtvelectronics.com $59.99 | ✅ | JSON | Older gen |
| Bitaxe Gamma (601/602/603) | Open-source | 1.1-1.5 TH/s | 15-30 W | $61-166 | solo | solosatoshi.com $61, bitcoinmerch.com $119.99, dtvelectronics.com $74.99, powermining.io €121, altairtech.io "Bitaxe Single ASIC" $99, 21energy.com €166 (603) | ✅ | JSON | Skins such as "Black Ice" and "Ice Angel" ($249.99 at Bitcoin Merch) are the same board. |
| Bitaxe Gamma++ (2 TH/s) | Open-source / Bitcoin Merch | 2 TH/s (seller) | 30 W | $149.99 | solo | bitcoinmerch.com | ❌ | JSON | SPEC? This is an overclocked Gamma claim. |
| Bitaxe Gamma Duo (650) | Open-source | ~1.6 TH/s | ~26 W | $104-240 | solo | solosatoshi.com $104.29, bitcoinmerch.com $239.99 | ✅ | JSON | |
| Bitaxe GT / Gamma Turbo (801) | Open-source | 2.0-2.4 TH/s | ~43 W | $174-270 | solo | solosatoshi.com $173.99, bitcoinmerch.com $174.99, D-Central CA$269.99 | ✅ | JSON | |
| Bitaxe 801 GTR+ | Open-source / Bitcoin Merch | 3.8 TH/s (seller) | 75 W | $249.99 | solo | bitcoinmerch.com | ❌ | JSON | SPEC? This is a tuned GT claim. |
| Bitaxe Touch | Open-source | Bitcoin Merch: 1 TH/s @ 14.5-20 W. Solo Satoshi "Turbo Touch": 1.5-3.06 TH/s @ 41-48 W | see left | $250-400 | solo | bitcoinmerch.com $399.99, solosatoshi.com $250 (OOS) | ❌ | JSON | The two sellers list different hardware under the same name. |
| Bitaxe Gamma Hex (1300) | Open-source | 8.4-11 TH/s | 140-252 W | $397-450 | solo/pool | solosatoshi.com $396.99, bitcoinmerch.com Hydro $449.99 | ❌ | JSON | New 6-chip flagship |
| Bitaxe Naja Duo (1201, 2x BM1373) | Open-source | up to ~8 TH/s | 42-92 W | $366-600 | solo | solosatoshi.com $366, bitcoinmerch.com $599.99 | ❌ | JSON | |
| Bitaxe SupraHex | Open-source | 4.2+ TH/s (title) | ? | $224.99 | solo | bitcoinmerch.com | ❌ | JSON | The listing gives no wattage. |
| Bitaxe Hex | Open-source / D-Central | ? (D-Central page mixes several models' figures) | ? | CA$389.99 | solo | d-central.tech | ❌ | JSON | Older gen. Specs unclear. |
| QAxe | Open-source / D-Central | 1.7 TH/s | ? | CA$319.99 | solo | d-central.tech | ❌ | JSON | |
| BitForge Nano (incl. Ghost Edition) | BitForge | 2.0-2.6 TH/s | 30-43 W | $169.99-399.99 | solo | dtvelectronics.com $169.99, bitcoinmerch.com $269.99 (Ghost $399.99), solosatoshi.com Ghost $349.99 | ❌ | JSON | |
| Mars Lander 3 (miner + node) | Bitcoin Merch | 1.2 TH/s | ? | $749.99 (pre-order) | solo | bitcoinmerch.com | ❌ | JSON | Pre-order |
| Mars Lander V2 | Bitcoin Merch | up to 250 GH/s | ? | $329.99 | solo | bitcoinmerch.com | ❌ | JSON | Poor value per TH/s |

### A2. Nerd family (NerdAxe / NerdQaxe / NerdOCTaxe)

| Model | Maker | Hashrate | Watts | Typical price | Cat. | Where sold | Tracked | Trackable | Flags |
|---|---|---|---|---|---|---|---|---|---|
| NerdAxe (original) | Open-source (shufps) | ? (Bitcoin Merch says 1.2 TH/s) | ? | $170-200 | solo | bitcoinmerch.com $199.99, D-Central CA$169.99 | ❌ | JSON | |
| Nerdaxe Gamma | Open-source | ~1.1-1.3 TH/s | ~18 W | $139-168 | solo | solosatoshi.com $139, powermining.io €168 | ✅ | JSON | |
| Nerdaxe Gaia (BM1373) | Open-source | 2.4-2.6 TH/s | ~25 W | $399.99 | solo | bitcoinmerch.com | ✅ | JSON | |
| NerdQaxe+ (4x BM1368) | Open-source | ~2.4-2.5 TH/s | ? | $375-380 | solo | bitcoinmerch.com $379.99, D-Central CA$529.99, solosatoshi.com (OOS) | ❌ | JSON | Being superseded by the ++ |
| NerdQaxe++ (incl. Hydro) | Open-source | 4.8-6 TH/s | ~80-100 W | $190-462 | solo | solosatoshi.com Rev 7 $189.99 (OOS), bitcoinmerch.com $274.99 (Hydro $299.99), powermining.io €363 | ✅ | JSON | |
| NerdOCTaxe Gamma (8x BM1370) | Open-source | 9-12 TH/s | ~160-200 W | $449.99-600 | pool | bitcoinmerch.com $449.99 (Hydro $599.99), D-Central CA$849.99 (OOS), luckyminerclub.com $458 | ❌ | JSON | |
| NerdQX 8T | ? | 8.1 TH/s | 138 W | $299-450 | solo | bitcoinmerch.com $449.99, luckyminerclub.com $299 | ✅ | JSON | ⚠ Maker unclear |
| NerdNOS | Open-source | ? | ? | $69-95 | solo | altairtech.io $69.42, D-Central CA$94.99 | ❌ | HTML/JSON | Specs not checked |
| NerdMiner V2 (ESP32) | Open-source | kH/s range (no ASIC) | <1 W | $30-50 | solo (toy) | bitcoinmerch.com $34.99-44.99, altairtech.io $44.99, powermining.io €50, D-Central CA$49.99 | ❌ | JSON | A novelty with effectively zero odds. It gets high search volume. |

### A3. Brand-name home miners

| Model | Maker | Hashrate | Watts | Typical price | Cat. | Where sold | Tracked | Trackable | Flags |
|---|---|---|---|---|---|---|---|---|---|
| Avalon Nano 3S | Canaan | 3.1-6 TH/s | 66-140 W | $219-350 | solo | solosatoshi.com $219, altairtech.io $249, bitcoinmerch.com $349.99, powermining.io €339.99, 21energy €283 | ✅ | JSON/HTML (Canaan BLOCK) | |
| Avalon Mini 3 | Canaan | 37.5 TH/s | up to 800 W | $750-1,150 | heater | altairtech.io $789, solosatoshi.com $749.99 (OOS), bitcoinmerch.com $1,149.99, D-Central CA$1,750 | ✅ | JSON/HTML | |
| Avalon Q | Canaan | 53-90 TH/s | 850-1,674 W | $1,349-1,795 | pool/heater | solosatoshi.com $1,349, altairtech.io $1,499, bitcoinmerch.com $1,794.99 | ✅ | JSON/HTML | ⚠ It is over 1.6 kW at max, so it needs a dedicated 20 A circuit. |
| Heatbit Trio | Heatbit | 10 TH/s | 400 W mining (1,500 W total) | $849 (Heatbit), $1,299.99 (Bitcoin Merch) | heater | heatbit.com, bitcoinmerch.com | ✅ | JSON | |
| Heatbit Maxi / Maxi Pro | Heatbit | 39 TH/s (Maxi). Maxi Pro hashrate not confirmed. | 1,500 W | $1,249 / $1,499 | heater | heatbit.com | ✅ (one entry) | JSON | Consider giving the Maxi Pro its own entry. |
| Heatbit Canvas | Heatbit | 10 TH/s | 300 W | $399 | heater | heatbit.com | ✅ | JSON | |
| Heatbit Bitair (air purifier) | Heatbit | 1.2 TH/s | 25 W | $179-179.99 | solo | heatbit.com, altairtech.io, solosatoshi.com, bitcoinmerch.com | ❌ | JSON | Four sellers, all trackable |
| Braiins Mini Miner BMM 101 | Braiins | 1 TH/s | 35-40 W | $299-499.99 | solo | braiinsforge.com, bitcoinmerch.com $499.99 | ✅ | HTML/JSON | |
| Braiins Axe Forge | Braiins | 4.8 TH/s, expandable | ? | $399.99 | solo | bitcoinmerch.com | ❌ | JSON | Wattage not listed |
| Apollo III Standard | FutureBit (USA) | 12-17 TH/s Eco to Turbo (~6 TH/s Ultra-Eco) | ~70-375 W | $899.99 | pool/solo | shop.futurebit.io | ❌ | JSON | Ships in 4-6 weeks |
| Apollo III Full Node | FutureBit | same as above, plus a node | same | from $1,099.99 | pool/solo | shop.futurebit.io | ❌ | JSON | |
| Apollo II (Full Node / Standard add-on) | FutureBit | ~9 TH/s (third-party figure, bitshopper.de) | ~270 W | $899.99 / $599.99 | pool | shop.futurebit.io | ❌ | JSON | Previous gen, still sold |
| Hammer BC01 | Hammer | 1.5 TH/s | 22-31 W | $109-115 | solo | altairtech.io $109, bitcoinmerch.com $114.99 | ❌ | HTML/JSON | |
| Hammer BC04 | Hammer | 6 TH/s | 76-108 W | $215-350 | solo | altairtech.io $215, bitcoinmerch.com $349.99 | ✅ | HTML/JSON | |
| Hammer BC08 (air with touchscreen / Hydro) | Hammer | 12 TH/s | 210 W | $519-700 | pool | altairtech.io $519, bitcoinmerch.com Hydro $699.99 | ❌ | HTML/JSON | ⚠ The Bitcoin Merch Hydro page mentions 240 V, so verify the voltage. |
| Hammer Thor X1 | Hammer | 3.2 TH/s | 35 W | $219-330 | solo | altairtech.io $219, bitcoinmerch.com $329.99 | ❌ | HTML/JSON | |
| Hammer Thor P2 (2x BM1373) | Hammer | 10 TH/s | 166 W | $369-590 | pool | altairtech.io $369, bitcoinmerch.com $589.99 | ❌ | HTML/JSON | |
| Hammer Glod P3 | Hammer | 12 TH/s | 160 W | $649.99 | pool | bitcoinmerch.com | ❌ | JSON | |
| Hammer Glod Omni (touchscreen) | Hammer | 1.2 TH/s | 20 W | $324.99 | solo | bitcoinmerch.com | ❌ | JSON | |
| Hammer Pocket | Hammer | 1.2 TH/s | ? | $249 | solo | altairtech.io | ❌ | HTML | |
| Lucky Miner LV06 | Lucky Miner | ~0.5 TH/s | 13-15 W | $59-134 | solo | luckyminerclub.com $59, minemirth.com $133.70, Amazon (BLOCK) | ❌ | JSON (unvetted seller only) | CLONE. UNVETTED sellers. |
| Lucky Miner LV07 | Lucky Miner | ~1 TH/s | 25-30 W | $89-126 | solo | luckyminerclub.com $89 | ❌ | JSON | CLONE. UNVETTED. |
| Lucky Miner LV07 Pro | Lucky Miner | 3 TH/s (seller) | ? | $178 | solo | luckyminerclub.com | ❌ | JSON | CLONE. SPEC? |
| Lucky Miner LV08 | Lucky Miner | 4.2-4.5 TH/s | ~120-140 W | $252-279 | solo | luckyminerclub.com $268, minemirth.com $251.62 | ❌ | JSON | CLONE. UNVETTED. |
| Lucky Miner LV08 Pro | Lucky Miner | 7 TH/s (seller) | ? | $338 | solo | luckyminerclub.com | ❌ | JSON | CLONE. SPEC? |
| Lucky Miner LV02 / LV03 (USB) | Lucky Miner | ~73-78 kH/s | ~1 W | $27-87 | solo (toy) | luckyminerclub.com, minemirth.com | ❌ | JSON | A toy, no ASIC |
| LuckyAxe BL04 (BTC/DOGE dual) | ? | 3.3 TH/s | 100 W | $499.99 | solo | bitcoinmerch.com | ❌ | JSON | ⚠ Maker unclear |
| LuckyAxe B101 | ? | 1.8 TH/s (seller) | ? | $99 | solo | luckyminerclub.com | ❌ | JSON | SPEC?, UNVETTED |
| GekkoScience Compac F (USB) | GekkoScience | ~250-300 GH/s per stick | ? | $134.99 (bundles $450-900) | solo | bitcoinmerch.com | ❌ | JSON | Poor value per TH/s |
| GekkoScience Terminus A2X | GekkoScience | 7-8 TH/s | 100-130 W | $399-500 | solo | altairtech.io $399, bitcoinmerch.com $499.99 | ❌ | HTML/JSON | |
| GekkoScience KBuddy | GekkoScience | 15-18 TH/s | 200-300 W | $599.99 | pool | bitcoinmerch.com | ❌ | JSON | 120/240 V |
| GekkoScience KBox 22 | GekkoScience | 22 TH/s | 330 W | $849-900 | pool/heater | altairtech.io $849, bitcoinmerch.com $899.99 | ❌ | HTML/JSON | Sold as a "Miner & Heater" |
| GekkoScience KBeast 50 | GekkoScience | 50+ TH/s | 800 W | $1,099.99 | heater | bitcoinmerch.com | ❌ | JSON | 120/240 V |
| GekkoScience Mein Coffee | GekkoScience | ? | ? | $249 | ? | altairtech.io | ❌ | HTML | Specs not found on the page |
| Nexus S1-1 (BM1373) | Nexus | 6 TH/s | 95 W | $324.99 | solo | bitcoinmerch.com | ❌ | JSON | ⚠ The brand site is a parking page. |
| Nexus S1-2 | Nexus | 10 TH/s | ? | $599.99 | pool | bitcoinmerch.com | ❌ | JSON | ⚠ Same as above |
| Nexus S1-4 Hydro | Nexus | 18 TH/s | 290 W | $899.99 | pool | bitcoinmerch.com | ❌ | JSON | ⚠ |
| Nexus S1-8 Hydro | Nexus | 40 TH/s | 550 W | $1,199.99 | pool | bitcoinmerch.com | ❌ | JSON | ⚠ |
| Bitfortun BS-4 Hydro | Bitfortun | 18 TH/s | 300 W | $649.99 | pool | bitcoinmerch.com | ❌ | JSON | ⚠ Unknown brand |
| Zyber 8S | Zyber | 6.4+ TH/s | 140 W | $299.99 | solo | bitcoinmerch.com | ❌ | JSON | ⚠ Unknown brand |
| Zyber 12G | Zyber | 15+ TH/s | 295-450 W | $849.99 | pool | bitcoinmerch.com | ❌ | JSON | ⚠ |
| Magic Miner 40TH | Magicminer | 30-50 TH/s | 450-850 W | $1,199.99 | pool/heater | bitcoinmerch.com | ❌ | JSON | ⚠ The page mentions 240 V, so verify 120 V. |
| Magicminer BG01 / BG02 / FM01 | Magicminer | ? | ? | $358 / $468 / $629 (OOS) | ? | luckyminerclub.com | ❌ | JSON | UNVETTED. Specs not checked. |
| Disruptor USB Lottery Miner | ? | ? | ~15 W | $79.99 | solo | bitcoinmerch.com | ❌ | JSON | Hashrate not stated |
| Gold Nugget / Gold Digger lottery miners | ? (ESP32, NMMiner-type) | ~1,000 kH/s | ? | $49.99 | solo (toy) | bitcoinmerch.com | ❌ | JSON | A toy |

### A4. 120 V heater editions and home mods of industrial ASICs (refurbished)

| Model | Maker | Hashrate | Watts | Typical price | Cat. | Where sold | Tracked | Trackable | Flags |
|---|---|---|---|---|---|---|---|---|---|
| Antminer S19 Space Heater Edition | D-Central (mod) | ~40-46 TH/s (page also lists other variants) | ~1,200-1,500 W | CA$755 | heater | d-central.tech | ❌ | JSON | Refurbished. CAD pricing, ships from Canada. |
| Antminer S9 Space Heater Edition | D-Central | 13.5 TH/s | ? (S9 class is ~1.3 kW) | CA$235 | heater | d-central.tech | ❌ | JSON | Very inefficient, more heater than miner |
| The StealthMiner | D-Central | 26-56 TH/s by variant | 860-1,300 W | CA$849.99 | heater/pool | d-central.tech | ❌ | JSON | |
| The BitChimney | D-Central | 13-24 TH/s by variant | 600-1,300 W | CA$540 (DIY kit CA$169.99) | heater | d-central.tech | ❌ | JSON | |
| Antminer Loki Edition | D-Central | 40-48 TH/s | 1,100-1,200 W | CA$585-803 | pool/heater | d-central.tech | ❌ | JSON | One hashboard is removed so it can run on 110 V. |
| Antminer Slim Edition | D-Central | 23-38 TH/s by variant | 860-1,200 W | CA$560 | pool/heater | d-central.tech | ❌ | JSON | |
| Antminer Pivotal Edition | D-Central | 42-46 TH/s | ? | CA$645 | pool/heater | d-central.tech | ❌ | JSON | |
| The Urlacher | Altair | 40-60 TH/s by setting | 945-1,500 W | $849 | pool/heater | altairtech.io | ❌ | HTML | 110/120 V |
| ReHash heaters (models not itemized) | ReHash Heating | 15-28 TH/s (site claim) | ? | ? | heater | rehashheating.com (USD checkout "coming soon") | ❌ | HTML | Not buyable in USD yet |

**Total current home models in sections A1 to A4: 79 rows.** That counts each Lucky LV02/LV03 pair, Gold Nugget/Digger pair and Magicminer trio as one row, and treats variants and skins as part of their base model. **Already tracked: 16. Untracked: 63.**
The "serious" models are the ones that are not toys (NerdMiner, LV02/03, Gold Nugget, Compac F, Mars Lander V2) and that sell at a vetted seller: about 60.

## B. Discontinued or not currently buyable

| Model | Notes |
|---|---|
| Canaan Avalon Nano 3 | Replaced by the 3S. Out of stock at D-Central (CA$239.99). |
| Bitaxe Max (BM1397) | First gen. Only a "Planned Board" placeholder remains. |
| Piaxe | Out of stock at D-Central (CA$160). |
| ImmergeAxe | Solo Satoshi lists it at $0, out of stock. |
| NerdQaxe+ Hydro | Out of stock at Solo Satoshi ($355). |
| FutureBit Apollo II Founders Edition | Out of stock ($2,100). |
| 21energy Ofen / Ofen Pro / Ofen 2 | Out of stock, and EU 230 V anyway. |
| GekkoScience R909 | Only spare parts are listed. |
| ASIC Block Erupter USB (336 MH/s) | Still listed at Bitcoin Merch for $109.99 as a collectible. Useless for mining. |
| Bitmain Antminer R4 (2016) | Old 110 V home unit. Only parts are listed. |

## C. Excluded on purpose (out of scope)

- **Fluminer T3 / T3 v2.** Maker spec: 105-115 TH/s at 1,650-1,700 W, 220-240 V. The Altair T3 v2 page lists 1,660-2,060 W, at $1,869.
- **21energy Ofen 3 (40-120 TH/s) and Ofen 2 Pro.** EU 230 V only, priced in euros.
- **Scrypt and other-coin home miners.** Goldshell Mini Doge, Hammer DC series, Fluminer L2, Lucky LG07, Nexus L1, VolcMiner, IceRiver, Goldshell XT Box. These aren't Bitcoin.
- **Stock Bitmain, MicroBT and Canaan industrial units (S9 and newer).** They need 200-240 V or 3-phase power. Bitmain has no stock 120 V home miner in 2026; its 2026 launches were all hydro data-center units.
- **Ebang E9+ at Bitcoin Merch for $79.99 (1,320 W).** An old industrial unit with an odd price. Excluded.

## D. Industrial ASIC context (not for tracking)

- A rough count of current SHA-256 industrial models sold new or refurbished is about 50-80 (ESTIMATE). Just 21energy's Shopify feed lists about 25 Bitmain, MicroBT and Bitdeer models.
- Main families:
  - **Bitmain:** S19 / S21 / S23 and Hydro.
  - **MicroBT:** Whatsminer M60 / M63 / M70 / M73.
  - **Canaan:** A14-A16.
  - **Bitdeer:** Sealminer A2.
  - **Others:** Auradine, Fluminer and others.
- All of them need 200-240 V or 3-phase power and are loud, so none suit a home outlet. Aggregators such as Mining Now and ASIC Miner Value list hundreds of models, including old ones.

## E. Top 15 untracked models to add next

This ranking is an ESTIMATE. It weighs search interest seen in seller guides, review sites and listing counts, the price (bigger price means a bigger commission), whether a trackable and ideally affiliate-able seller exists, and fit with our audience.

| # | Model | Why |
|---|---|---|
| 1 | **FutureBit Apollo III (Standard + Full Node)** | Best-known US home-miner brand at $900-1,100. A clean official Shopify feed. It fills the "quiet 10-17 TH/s plus node" gap we have no entry for. |
| 2 | **Bitaxe Gamma Hex 1300** | The newest Bitaxe flagship, a natural search for our existing Bitaxe audience. Two trackable US sellers at $397-450. |
| 3 | **Lucky Miner LV08 (with LV07 and LV06)** | Probably the most-searched cheap desk miners (Amazon, AliExpress). Adding them lets us capture that traffic and steer buyers to vetted alternatives. Flag them as a closed-firmware clone with unvetted sellers. |
| 4 | **NerdOCTaxe Gamma** | The next step up from the NerdQaxe++, which we already track (9-12 TH/s, $450-600). Bitcoin Merch and D-Central feeds are ready. |
| 5 | **Heatbit Bitair** | A $179 air purifier that mines, sold at 4 sellers that are all trackable. It suits the heater and home hub, and two of those sellers are affiliate targets. |
| 6 | **BitForge Nano (with Ghost)** | A popular 2.6 TH/s / 43 W miner. DTV Electronics sells it at $169.99, and our DTV affiliate application is pending. It's also at Solo Satoshi and Bitcoin Merch. |
| 7 | **Bitaxe Touch** | A screen version of the Bitaxe, $250-400. Note the different hardware under the same name at different sellers. |
| 8 | **Hammer Thor P2** | 10 TH/s at 166 W for $369 at Altair, an affiliate target. Hammer is already on the site through the BC04. |
| 9 | **GekkoScience KBox 22** | A well-known brand, sold as a miner and heater ($849-900). Good for the heating-season pages. |
| 10 | **D-Central S19 Space Heater Edition / StealthMiner** | Fills the 1 kW heater gap at a lower price than Heatbit. The D-Central affiliate application was submitted, and its Woo feed works (CAD). |
| 11 | **NerdMiner V2** | Very high search for a "$30 bitcoin miner". Earns little per sale but is a cheap traffic magnet. Label it a toy. |
| 12 | **Bitaxe Naja Duo (1201)** | A new BM1373 Bitaxe, ~8 TH/s at 92 W, at Solo Satoshi and Bitcoin Merch. |
| 13 | **Braiins Axe Forge** | The Braiins brand draws search. 4.8 TH/s, $399.99. Wattage is still unknown. |
| 14 | **GekkoScience KBeast 50** | 50 TH/s at 800 W, a 120 V heater for $1,099.99, which competes with the Avalon Mini 3 and Heatbit Maxi. A high-ticket item. |
| 15 | **Hammer BC08 (12 TH/s)** | $519 at Altair (affiliate target) plus Bitcoin Merch. Verify whether the Hydro version needs 240 V. |

**Notes for the collector worker:**
- **DTV Electronics** (Woo Store API works) and **shop.futurebit.io** (Shopify works) are the two new sellers worth adding. Every other top-15 model is already at sellers we scrape.
- Filter out D-Central "Planned Board" CA$0 items.
- Lucky Miner can't be tracked at a vetted seller. luckyminer.com was unreachable, and luckyminerclub.com is UNVETTED. Either list Lucky Miner as "specs only" or vet a seller first.
