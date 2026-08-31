# Access (on-campus vs offsite)

**Updated:** 2026-08-31 — H100 主机改为 **`.26`**（旧 `.25` / `.22` 退役）。

| Target | On-campus (default) | Offsite fallback |
|---|---|---|
| **125** (4090 / AirSim) | `ssh cursor-125` → `10.229.20.125` | `ssh cursor-125-public` (Cloudflare Access) |
| **H100** `.26` | From Mac: `ssh cursor-125 'ssh h100-26 …'`（key on 125: `~/.ssh/id_ed25519_h100`）。On 125: `ssh h100-26` → **`a25689@10.239.121.26 -p 31126`** | Same hop after reaching 125 via public Host |
| **Git bare (origin)** | `origin` → `cursor-125:~/repos/aerial-wam-v2.git` | Temporarily `cursor-125-public:~/repos/…` if offsite |
| **GitHub** | `github` HTTPS remote — direct when on campus | Use when LAN GitHub path works; do not force Cloudflare for git |

Cloudflare Host entries and keys stay in `~/.ssh/config` as fallback; do not delete them.
