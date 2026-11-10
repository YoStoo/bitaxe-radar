# Eval run 20261110T193311Z-live-fix-in-data

**Score: 7/7 cases** (33/33 checks). Endpoint `https://bitaxe-radar-alerts.bitaxeradar.workers.dev/ask`, data from 2026-11-10T19:26:33Z.

| | Case | Failed checks | Answer |
|---|---|---|---|
| ✅ | `general-solo-mining` |  | Solo mining means your miner works alone on its own, with no shared pool. If it finds a block, you keep the whole reward; if not, you earn nothing, so it's essentially a lottery ticket. Pool mining instead splits rewards among many miners for smaller, steadier payouts. |
| ✅ | `general-hashrate` |  | Hashrate is how many guesses per second a miner makes while trying to solve a Bitcoin block. It's measured in TH/s (trillions of guesses per second), and a higher number means more chances to earn rewards. Our guides only touch on it briefly, so this is a general explanation. |
| ✅ | `rag-firmware` |  | Find your board number on the miner or its System page, then download the matching AxeOS file from the official GitHub releases page. Note your Wi-Fi, pool, and Bitcoin address first, then upload the firmware from your miner's dashboard. A normal update usually keeps your settings, but afterward check your pool settings and hashrate. |
| ✅ | `rag-solar` |  | Yes. A Bitaxe-class miner draws about 15 to 25 W, so one normal home panel covers it in daylight. For mining at night you'd need a battery and charge controller, or you can mine only during the day with no battery, which earns less. |
| ✅ | `rag-how-often` |  | We check the shops that sell Bitaxe-style and home miners every 6 hours, so the prices and stock shown reflect the shop's own pages. We also log a price change whenever it happens, and otherwise about one history point per day. |
| ✅ | `rag-dont-know-s19` |  | Our guides don't cover replacing thermal paste on an Antminer S19. In general, this is a job for an experienced hands-on user: you'd need to power down and unplug the unit, remove the heatsinks, clean the old paste, and apply fresh paste before reassembling. Check the manufacturer's documentation or a dedicated repair resource for the exact steps. |
| ✅ | `rag-dont-know-ha` |  | Our guides don't cover a Home Assistant integration directly. What they do cover: after setup, your Bitaxe shows its IP address on screen, and you can open that address in a browser to reach its AxeOS dashboard. Apps like Traxe, HashWatcher, and Bitaxe Baller can monitor it from your network too. |
