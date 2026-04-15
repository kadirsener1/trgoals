import asyncio
import re
import json
import os
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page, BrowserContext

# ─────────────────────────────────────────────
#  KANAL TANIMI
# ─────────────────────────────────────────────
CHANNELS = [
    {"name": "Patron TV",  "group": "Canlı TV", "logo": "", "url": "https://patronizle35.cfd/ch.html?id=patron"},
    {"name": "B2 TV",      "group": "Canlı TV", "logo": "", "url": "https://patronizle35.cfd/ch.html?id=b2"},
]

BASE_DOMAIN_PREFIX  = "patronizle"
BASE_DOMAIN_SUFFIX  = ".cfd"
ALT_EXTENSIONS      = [".cfd", ".xyz", ".live", ".online", ".tv", ".me", ".net", ".org"]
DOMAIN_NUMBER_RANGE = range(30, 55)

OUTPUT_FILE = "playlist.m3u"
STATE_FILE  = "last_known_domain.json"

# Network isteği beklenecek maksimum süre (saniye)
WAIT_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


# ─────────────────────────────────────────────
#  STATE (SON BİLİNEN DOMAIN)
# ─────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"number": 35, "ext": ".cfd"}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ─────────────────────────────────────────────
#  DOMAIN KEŞİF SİSTEMİ (requests tabanlı - hafif)
# ─────────────────────────────────────────────

def probe_domain(number: int, ext: str) -> bool:
    import requests
    domain = f"{BASE_DOMAIN_PREFIX}{number}{ext}"
    try:
        r = requests.get(
            f"https://{domain}/",
            headers=HEADERS,
            timeout=8,
            allow_redirects=True
        )
        return r.status_code < 400
    except Exception:
        return False


def discover_active_domain(current_number: int = 35, current_ext: str = ".cfd") -> str:
    if probe_domain(current_number, current_ext):
        domain = f"{BASE_DOMAIN_PREFIX}{current_number}{current_ext}"
        print(f"  ✓ Mevcut domain aktif: {domain}")
        return domain

    print("  ⚠ Mevcut domain yanıt vermiyor, alternatifler taranıyor...")
    for ext in ALT_EXTENSIONS:
        for num in DOMAIN_NUMBER_RANGE:
            if num == current_number and ext == current_ext:
                continue
            domain = f"{BASE_DOMAIN_PREFIX}{num}{ext}"
            print(f"  → Deneniyor: {domain}")
            if probe_domain(num, ext):
                print(f"  ✓ Yeni domain bulundu: {domain}")
                return domain

    fallback = f"{BASE_DOMAIN_PREFIX}{current_number}{current_ext}"
    print(f"  ✗ Aktif domain bulunamadı, varsayılana dönülüyor: {fallback}")
    return fallback


# ─────────────────────────────────────────────
#  PLAYWRIGHT: M3U8 NETWORK INTERCEPT
# ─────────────────────────────────────────────

async def intercept_m3u8(context: BrowserContext, url: str, channel_name: str) -> str | None:
    """
    Sayfayı Playwright ile aç, tüm network isteklerini dinle,
    .m3u8 içeren ilk isteği yakala ve döndür.
    """
    page: Page = await context.new_page()
    found_url: list[str] = []

    # ── 1. Network request dinleyicisi ──────────────────────────────
    def on_request(request):
        req_url = request.url
        if ".m3u8" in req_url and not found_url:
            print(f"  📡 [Request]  {req_url[:100]}")
            found_url.append(req_url)

    def on_response(response):
        resp_url = response.url
        if ".m3u8" in resp_url and not found_url:
            print(f"  📡 [Response] {resp_url[:100]}")
            found_url.append(resp_url)

    page.on("request",  on_request)
    page.on("response", on_response)

    # ── 2. Sayfayı yükle ────────────────────────────────────────────
    print(f"  🌐 Sayfa açılıyor: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"  ✗ Sayfa açılamadı: {e}")
        await page.close()
        return None

    # ── 3. iframe'leri bul ve onlara da listener ekle ───────────────
    try:
        # iframe'lerin yüklenmesini bekle
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass  # timeout olsa bile devam et

    frames = page.frames
    print(f"  🖼  Toplam frame sayısı: {len(frames)}")
    for frame in frames:
        if frame.url and frame.url != "about:blank":
            print(f"  🖼  Frame URL: {frame.url[:80]}")

    # ── 4. Oynatıcıyı başlatmaya çalış ──────────────────────────────
    # Play butonuna tıkla (farklı player'lar için ortak seçiciler)
    play_selectors = [
        "button.play",
        ".vjs-big-play-button",
        ".plyr__control--overlaid",
        "[class*='play']",
        "video",
        ".jwplayer",
        "#player",
        "[id*='player']",
        "[class*='player']",
    ]
    for selector in play_selectors:
        try:
            el = await page.query_selector(selector)
            if el:
                await el.click(timeout=3000)
                print(f"  🖱  Tıklandı: {selector}")
                break
        except Exception:
            continue

    # iframe içindeki play butonlarını da dene
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        for selector in play_selectors:
            try:
                el = await frame.query_selector(selector)
                if el:
                    await el.click(timeout=3000)
                    print(f"  🖱  iframe'de tıklandı: {selector}")
                    break
            except Exception:
                continue

    # ── 5. M3U8 linki için bekle ────────────────────────────────────
    print(f"  ⏳ M3U8 bekleniyor (max {WAIT_TIMEOUT}s)...")
    for _ in range(WAIT_TIMEOUT * 2):   # 0.5s aralıklarla kontrol
        if found_url:
            break
        await asyncio.sleep(0.5)

    await page.close()

    if found_url:
        print(f"  ✅ M3U8 bulundu: {found_url[0][:100]}")
        return found_url[0]

    print(f"  ✗ M3U8 bulunamadı: {channel_name}")
    return None


# ─────────────────────────────────────────────
#  M3U DOSYASI OLUŞTURUCU
# ─────────────────────────────────────────────

def build_m3u(entries: list[dict]) -> str:
    lines = ["#EXTM3U", ""]
    for e in entries:
        name  = e.get("name",  "Kanal")
        logo  = e.get("logo",  "")
        group = e.get("group", "Canlı TV")
        url   = e.get("url",   "")
        if not url:
            continue
        lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
        lines.append(url)
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  ANA FONKSİYON
# ─────────────────────────────────────────────

async def main():
    # 1. Domain keşfi
    state = load_state()
    current_number = state.get("number", 35)
    current_ext    = state.get("ext",    ".cfd")

    print("=" * 60)
    print("  DOMAIN KEŞİF SİSTEMİ")
    print("=" * 60)
    active_domain = discover_active_domain(current_number, current_ext)

    match = re.match(rf"^{re.escape(BASE_DOMAIN_PREFIX)}(\d+)(.+)$", active_domain)
    if match:
        state["number"] = int(match.group(1))
        state["ext"]    = match.group(2)
    save_state(state)

    # 2. Kanal URL'lerini aktif domain ile güncelle
    updated_channels = []
    for ch in CHANNELS:
        parsed = urlparse(ch["url"])
        new_url = ch["url"].replace(
            f"{parsed.scheme}://{parsed.netloc}",
            f"https://{active_domain}"
        )
        updated_channels.append({**ch, "url": new_url})

    # 3. Playwright ile m3u8 linkleri çek
    print("\n" + "=" * 60)
    print("  PLAYWRIGHT - M3U8 YAKALAMA")
    print("=" * 60)

    entries = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--autoplay-policy=no-user-gesture-required",  # otomatik oynatma izni
            ],
        )

        # Her kanal için ayrı context (cookie izolasyonu)
        for ch in updated_channels:
            print(f"\n[{ch['name']}] → {ch['url']}")

            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 720},
                # Medya izinleri
                permissions=["camera", "microphone"],
                ignore_https_errors=True,
            )

            # Gereksiz kaynakları engelle (hızlandırır, m3u8'i engellemez)
            await context.route(
                re.compile(r"\.(png|jpg|jpeg|gif|svg|woff2?|css)(\?.*)?$"),
                lambda route: route.abort()
            )

            m3u8_url = await intercept_m3u8(context, ch["url"], ch["name"])
            await context.close()

            if m3u8_url:
                entries.append({
                    "name":  ch["name"],
                    "group": ch.get("group", "Canlı TV"),
                    "logo":  ch.get("logo",  ""),
                    "url":   m3u8_url,
                })
            else:
                print(f"  ⚠ '{ch['name']}' atlandı.")

        await browser.close()

    # 4. M3U dosyasını yaz
    print("\n" + "=" * 60)
    if entries:
        content = build_m3u(entries)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ playlist.m3u oluşturuldu → {len(entries)} kanal")
        print("-" * 60)
        print(content)
    else:
        print("❌ Hiç kanal bulunamadı! playlist.m3u güncellenmedi.")


if __name__ == "__main__":
    asyncio.run(main())
