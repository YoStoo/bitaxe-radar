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
