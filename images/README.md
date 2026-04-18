# Button images (not committed)

Place PNG files here (or set `images.dir` in `deckd.toml` to another directory).

| Filename | Used for |
|----------|-----------|
| `monero_online.png` | P2Pool unit is active |
| `monero_deactivating_a.png` | First frame while unit is **deactivating** (blinks with B; names configurable in `deckd.toml`) |
| `monero_deactivating_b.png` | Second frame while **deactivating** |
| `monero_offline.png` | P2Pool unit inactive / failed / other (and while activating, etc.) |
| `onair_on.png` | On-air |
| `onair_off.png` | Off-air |

Stream Deck Mini keys use **80×80** pixels. The `streamdeck` library scales as needed; matching this size avoids surprises.

This directory is listed in `.gitignore` so your assets stay local.
