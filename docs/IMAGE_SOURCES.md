# Product photo sources

Each photo in `site/img/models/` is the seller's own product image for that exact model, taken from the seller's public store data on 2026-10-21. Processing: transparent padding trimmed (white studio background removed where noted), resized to max ~800 px, saved as WebP (q80). The product title was checked against the model for every image.

| File | Model | Seller | Product title checked | Original image URL |
|---|---|---|---|---|
| bitaxe-gamma.webp | Bitaxe Gamma (602 board visible) | Solo Satoshi (WooCommerce Store API `images[0].src`) | Bitaxe Gamma Bitcoin Solo Miner (602 Model) | https://www.solosatoshi.com/wp-content/uploads/2026/08/bitaxe-gamma-602-bitcoin-solo-miner.webp |
| bitaxe-gamma-duo.webp | Bitaxe Gamma Duo 650 | Solo Satoshi (`images[0].src`) | Bitaxe Gamma Duo Bitcoin Solo Miner (650 Model) | https://www.solosatoshi.com/wp-content/uploads/2026/02/bitaxe-duo-650-dual-chip-bitcoin-solo-miner-dark-horse-heatsink-solo-satoshi.png |
| bitaxe-gt-801.webp | Bitaxe GT 801 (Gamma Turbo), "801" on board | Solo Satoshi (`images[0].src`) | Bitaxe GT Gamma Turbo Bitcoin Solo Miner (801 Model) | https://www.solosatoshi.com/wp-content/uploads/2026/01/bitaxe-gt-gamma-turbo-solo-bitcoin-miner-front-heatsink-logo-e1768551010807.png |
| bitaxe-supra.webp | Bitaxe Supra ("403" on board) | Solo Satoshi (`images[0].src`) | Bitaxe Supra Bitcoin Solo Miner | https://www.solosatoshi.com/wp-content/uploads/2025/06/bitaxe-supra-bitcoin-solo-miner.webp |
| nerdaxe-gamma.webp | Nerdaxe Gamma | Power Mining (Shopify `/products/nerdaxe-gamma.js`, first image) | Nerdaxe Gamma 1.1 TH/s | https://cdn.shopify.com/s/files/1/0880/2874/1979/files/1-04.png?v=1784723113 |
| nerdaxe-gaia.webp | Nerdaxe Gaia (white background removed) | Bitaxe.de (product page `og:image`) | Nerdaxe Gaia, 2,6 TH/s | https://bitaxe.de/images/products/nerdaxe-gaia-bitcoin-miner.webp?v=1790595916 |
| nerdqaxe-pp.webp | NerdQaxe++ 4.8 TH/s standard (white background removed) | Power Mining (Shopify `/products/nerdqaxe.js`, first image) | NerdQaxe++ 4.8 TH/s | https://cdn.shopify.com/s/files/1/0880/2874/1979/files/1_ae25f8f3-3813-4817-8dac-efc617d6bdce.jpg?v=1762196760 |

## No photo (drawn placeholder kept)
* **Bitaxe Ultra**: the only tracked listing (Bitcoin Merch, "Bitaxe Ultra 1366") uses a photo whose board reads "40X" (the Supra family), and the lettering looks generated. Not reliable, so the site keeps the placeholder.

Not used: Bitcoin Merch's Gamma Duo image (filename `ChatGPT_Image_...`, i.e. AI-generated) and Solo Satoshi's NerdQaxe++ image (it shows Revision 7, while the tracked model is the 4.8 TH/s standard).

## Heater & home miners (added 2026-10-21)

Same rules: the seller's or maker's own product image for that exact model, taken from its public store data on 2026-10-21, with the listing title checked against the model. Light studio backgrounds were removed (flood fill from the edges), then trimmed, resized to max 800 px and saved as WebP (q80).

| File | Model | Seller | Product title checked | Original image URL |
|---|---|---|---|---|
| avalon-nano-3s.webp | Canaan Avalon Nano 3S | Solo Satoshi (Store API `images[0].src`, already transparent) | Avalon Nano 3S Bitcoin Solo Miner | https://www.solosatoshi.com/wp-content/uploads/2025/11/Canaan-Avalon-Nano-3S-Bitcoin-Solo-Mining-Heater-front.png |
| avalon-mini-3.webp | Canaan Avalon Mini 3 | Solo Satoshi (`images[0].src`, already transparent) | Canaan Avalon Mini 3 37.5TH Bitcoin Home Miner | https://www.solosatoshi.com/wp-content/uploads/2025/12/canaan-avalon-mini-3-37-5th-bitcoin-home-mining-space-heater-front-angle.png |
| avalon-q.webp | Canaan Avalon Q | Solo Satoshi (`images[0].src`, already transparent) | Canaan Avalon Q Bitcoin Home Miner (90 TH/s) | https://www.solosatoshi.com/wp-content/uploads/2026/01/canaan-avalon-q-bitcoin-home-miner-side-view.png |
| heatbit-trio.webp | Heatbit Trio (silver) | Heatbit (Shopify `products.json`, first image; grey background removed) | Trio | https://cdn.shopify.com/s/files/1/0382/4127/1943/files/Trio_01.png?v=1747846876 |
| heatbit-maxi.webp | Heatbit Maxi (black) | Heatbit (Shopify `products.json`, first image; grey background removed) | Maxi | https://cdn.shopify.com/s/files/1/0382/4127/1943/files/3Group_2043684061.jpg?v=1747423798 |
| heatbit-canvas.webp | Heatbit Canvas (three artwork panels) | Heatbit (Shopify `products.json`, **second** image; off-white background removed) | Canvas | https://cdn.shopify.com/s/files/1/0382/4127/1943/files/Group_2087328606.png?v=1764797155 |
| braiins-bmm-101.webp | Braiins Mini Miner BMM 101 | Braiins Forge (product page JSON-LD `image`; white background removed) | Braiins Mini Miner BMM 101 | https://braiinsforge.com/cdn/wqKml3iwlw8PY62VkXZuD5n_WL2plMhcKGzWOx3m3SY/Braiins-BMM101-product-photo-1_c4f2e1cb-6ac0-4207-b56e-ecdd678ecc51.jpg |
| hammer-bc04.webp | Hammer Miner BC04 ("HAMMER" on stand) | Altair Technology (product page JSON-LD `image[0]`; white background removed) | Hammer Miner BC04 6TH Home Bitcoin Miner | https://altairtech.io/wp-content/uploads/2026/05/UeUru.jpg |

Not used: Heatbit Canvas's first image (a see-through back view on a wheeled stand that doesn't read as the product at card size).

These are the sellers' images. If we join a seller's affiliate program, check its brand-asset terms; otherwise ask the seller or replace them with our own photos.

## Miners added 2026-10-21 (from docs/MINER_CATALOG.md)

Same rules: the seller's or maker's own image for that exact model from its public store data, title checked, light backgrounds removed by edge flood fill, trimmed, max 800 px, WebP q80.

| File | Model | Seller | Product title checked | Original image URL |
|---|---|---|---|---|
| bitaxe-gamma-hex.webp | Bitaxe Gamma Hex 1300 (AIO cooler) | Solo Satoshi (Store API `images[0].src`, already transparent) | Bitaxe Gamma Hex Bitcoin Solo Miner (1300 Model) | https://www.solosatoshi.com/wp-content/uploads/2026/07/bitaxe-hex-hydro-cooled-bitcoin-miner-rgb-aio-solo-satoshi.png |
| bitaxe-naja-duo.webp | Bitaxe Naja Duo 1201 | Solo Satoshi (`images[0].src`, already transparent) | Bitaxe Naja Duo Bitcoin Solo Miner (1201 Model) | https://www.solosatoshi.com/wp-content/uploads/2026/08/bitaxe-naja-duo-front-view-lcd-live-hashrate-4748-ghs-41-9w-38c-dual-bm1373.png |
| bitforge-nano.webp | BitForge Nano (standard, not Ghost) | DTV Electronics (Store API `images[0].src`; white background removed) | Bitforge Nano Solo Bitcoin Miner | https://dtvelectronics.com/wp-content/uploads/2026/01/Bitforge-Nano.webp |
| heatbit-bitair.webp | Heatbit Bitair | Altair Technology (product JSON-LD `image[0]`; white background removed) | Heatbit Bitair – 1.2 TH/s Bitcoin Miner & Air Purifier | https://altairtech.io/wp-content/uploads/2026/10/heatbitbitair.jpg |
| futurebit-apollo-iii.webp | FutureBit Apollo III (rear view, FutureBit logo) | FutureBit (Shopify `products.json`, Standard version image; soft shadow removed) | Apollo III - Standard Version - Miner Only | https://cdn.shopify.com/s/files/1/0006/7528/3059/files/Apollo_III_Rear_II-FIXED_2-Alt._Controller.png?v=1772089505 |
| hammer-thor-p2.webp | Hammer Thor P2 | Altair Technology (product JSON-LD image "thorp2-no-text"; white background and floor shadow removed) | Thor P2 Bitcoin Miner – 10 TH/s Dual BM1373 ASIC Miner | https://altairtech.io/wp-content/uploads/2026/08/thorp2-no-text.png |
| hammer-bc08.webp | Hammer BC08 (air-cooled, touchscreen) | Altair Technology (product JSON-LD `image[0]`; white background removed) | Hammer Miner BC08 12TH Home Bitcoin Miner | https://altairtech.io/wp-content/uploads/2026/06/jO8Do.png |
| gekko-kbox-22.webp | GekkoScience KBox 22 | Altair Technology (product JSON-LD `image[0]`; white background removed) | GekkoScience KBox 22TH All-In-One Bitcoin Miner | https://altairtech.io/wp-content/uploads/2026/06/kbox-front.jpg |

No photo (drawn placeholder kept):
* **NerdOCTaxe Gamma**: Bitcoin Merch's images are lifestyle shots on a desk and D-Central's has a branded frame; neither cuts out cleanly.
* **D-Central StealthMiner**: the only image has D-Central/partner branding in a frame.

## Bitcube (added 2026-10-21)

| File | Model | Seller | Product title checked | Original image URL |
|---|---|---|---|---|
| bitcube.webp | Power Mining Bitcube (touchscreen showing 777 GH/s) | Power Mining, the maker (Shopify `/products/bitcube.js`, first image, already transparent; trimmed) | Bitcube | https://cdn.shopify.com/s/files/1/0880/2874/1979/files/bitcube-hero-777-square.png?v=1792489005 |

## Heatbit Bitwater (added 2026-10-22)

| File | Model | Seller | Product title checked | Original image URL |
|---|---|---|---|---|
| heatbit-bitwater.webp | Heatbit Bitwater (element with controller board) | Heatbit, the maker (Shopify `products/bitwater.json`, "02-bitwater-element" image; white background removed, trimmed) | Bitwater – Water Heater Element That Mines Bitcoin | https://cdn.shopify.com/s/files/1/0382/4127/1943/files/02-bitwater-element_8bf2aecb-c998-4ad4-9185-bab65de56737.jpg |

## NMQAxe++ Nexus (added 2026-10-23)

| File | Model | Seller | Product title checked | Original image URL |
|---|---|---|---|---|
| nmqaxe-nexus.webp | NMMiner NMQAxe++ Nexus (front, screen and cooler) | NMMiner, the maker (WooCommerce Store API, first image, already transparent; trimmed) | NMQAxe++ Nexus — Powerful Dual BM1373 Bitcoin Miner | https://www.nmminer.com/wp-content/uploads/2026/09/NMQAxe-Nexus-01-Front.png |
