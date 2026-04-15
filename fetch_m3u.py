import requests
import re
import json
import os
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# =============================================
#  KANAL TANIMI
#  name: m3u dosyasında görünecek isim
#  url : kaynak HTML sayfası
# =============================================
CHANNELS = [
    {"name": "Patron TV",  "url": "https://patronizle35.cfd/ch.html?id=patron"},
    {"name": "B2 TV",      "url": "https://patronizle35.cfd/ch.html?id=b2"},
]

# Domain tabanı ve alternatif uzantı/numara aralığı
BASE_DOMAIN_PREFIX = "patronizle"   # değişmeyen kısım
BASE_DOMAIN_SUFFIX = ".cfd"         # varsayılan uzantı

# Alternatif uzantılar (domain uzantısı değişirse denenecekler)
ALT_EXTENSIONS = [".cfd", ".xyz", ".live", ".online", ".tv", ".me", ".net", ".org"]

# Numara aralığı (patronizle35 → patronizle36 gibi değişirse taranacak)
DOMAIN_NUMBER_RANGE = range(30, 50)   # 30'dan 49'a kadar dene

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://patronizle35.cfd/",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

OUTPUT_FILE = "playlist.m3u"
STATE_FILE  = "last_known_domain.json"   # Bulunan son geçerli domaini saklar


# ─────────────────────────────────────────────
#  YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

def load_state() -> dict:
    """Son bilinen çalışan domaine ait durumu yükle."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def extract_m3u8_from_html(html: str, base_url: str) -> list[str]:
    """
    HTML içeriğinden m3u8 linklerini çıkar.
    1) Doğrudan .m3u8 URL regex
    2) <source src="..."> ve <video src="..."> etiketleri
    3) JavaScript değişkenleri  (src = "...", file: "...", vb.)
    4) iframe src → alt sayfa fetch
    """
    found = set()

    # 1. Regex: http/https ile başlayan .m3u8 linkleri
    pattern = re.compile(r'https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*', re.IGNORECASE)
    for m in pattern.findall(html):
        found.add(m)

    # 2. BeautifulSoup ile <source>, <video>
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["source", "video", "script"]):
        src = tag.get("src", "")
        if src and ".m3u8" in src:
            found.add(urljoin(base_url, src))

    # 3. JS içindeki file/src/source/stream değişkenleri
    js_pattern = re.compile(
        r'(?:file|src|source|stream|hls|url)\s*[=:]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        re.IGNORECASE,
    )
    for m in js_pattern.findall(html):
        found.add(urljoin(base_url, m))

    # 4. iframe → iç sayfayı da tara
    for iframe in soup.find_all("iframe"):
        iframe_src = iframe.get("src", "")
        if iframe_src:
            try:
                resp = requests.get(
                    urljoin(base_url, iframe_src),
                    headers=HEADERS,
                    timeout=10
                )
                if resp.ok:
                    found.update(extract_m3u8_from_html(resp.text, iframe_src))
            except Exception:
                pass

    return list(found)


def fetch_m3u8(channel: dict, domain_override: str | None = None) -> str | None:
    """
    Verilen kanalın URL'sinden m3u8 linkini çek.
    domain_override verilirse URL'deki domain yerine onu kullan.
    """
    url = channel["url"]
    if domain_override:
        parsed = urlparse(url)
        url = url.replace(f"{parsed.scheme}://{parsed.netloc}", f"https://{domain_override}")

    try:
        resp = requests.get(url, headers={**HEADERS, "Referer": url}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ✗ Bağlantı hatası ({url}): {e}")
        return None

    links = extract_m3u8_from_html(resp.text, url)
    if links:
        print(f"  ✓ Bulundu → {links[0]}")
        return links[0]

    print(f"  ✗ m3u8 bulunamadı: {url}")
    return None


# ─────────────────────────────────────────────
#  DOMAIN KEŞİF SİSTEMİ
#  Domain numarası veya uzantısı değişince
#  otomatik olarak yeni domaini bulur.
# ─────────────────────────────────────────────

def probe_domain(number: int, ext: str) -> bool:
    """Verilen domain kombinasyonunun canlı olup olmadığını test et."""
    domain = f"{BASE_DOMAIN_PREFIX}{number}{ext}"
    probe_url = f"https://{domain}/"
    try:
        r = requests.get(probe_url, headers=HEADERS, timeout=8, allow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False


def discover_active_domain(current_number: int = 35, current_ext: str = ".cfd") -> str:
    """
    1) Önce mevcut domain'i dene.
    2) Başarısız olursa tüm numara × uzantı kombinasyonlarını tara.
    Bulunan ilk geçerli domain'i döndür.
    """
    # Önce bilinen domaini dene
    if probe_domain(current_number, current_ext):
        print(f"  ✓ Mevcut domain aktif: {BASE_DOMAIN_PREFIX}{current_number}{current_ext}")
        return f"{BASE_DOMAIN_PREFIX}{current_number}{current_ext}"

    print(f"  ⚠ Mevcut domain yanıt vermiyor, alternatifler taranıyor...")

    for ext in ALT_EXTENSIONS:
        for num in DOMAIN_NUMBER_RANGE:
            if num == current_number and ext == current_ext:
                continue   # zaten denendi
            domain = f"{BASE_DOMAIN_PREFIX}{num}{ext}"
            print(f"  → Deneniyor: {domain}")
            if probe_domain(num, ext):
                print(f"  ✓ Yeni aktif domain bulundu: {domain}")
                return domain

    print("  ✗ Hiçbir domain aktif bulunamadı!")
    return f"{BASE_DOMAIN_PREFIX}{current_number}{current_ext}"   # varsayılana dön


# ─────────────────────────────────────────────
#  M3U DOSYASI OLUŞTURUCU
# ─────────────────────────────────────────────

def build_m3u(entries: list[dict]) -> str:
    """
    entries: [{"name": ..., "logo": ...(opsiyonel), "group": ...(opsiyonel), "url": ...}, ...]
    """
    lines = ["#EXTM3U\n"]
    for e in entries:
        logo  = e.get("logo",  "")
        group = e.get("group", "Genel")
        name  = e.get("name",  "Kanal")
        url   = e.get("url",   "")
        if not url:
            continue
        extinf = f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}'
        lines.append(extinf)
        lines.append(url)
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  ANA FONKSİYON
# ─────────────────────────────────────────────

def main():
    state = load_state()
    current_number = state.get("number", 35)
    current_ext    = state.get("ext",    ".cfd")

    print("=" * 55)
    print("  Domain Keşif Sistemi Başlatılıyor...")
    print("=" * 55)
    active_domain = discover_active_domain(current_number, current_ext)

    # Bulunan yeni domaini state'e kaydet
    match = re.match(rf"^{re.escape(BASE_DOMAIN_PREFIX)}(\d+)(.+)$", active_domain)
    if match:
        state["number"] = int(match.group(1))
        state["ext"]    = match.group(2)
    save_state(state)

    print("\n" + "=" * 55)
    print("  M3U8 Linkleri Çekiliyor...")
    print("=" * 55)

    entries = []
    for ch in CHANNELS:
        print(f"\n[{ch['name']}] → {ch['url']}")
        m3u8_url = fetch_m3u8(ch, domain_override=active_domain)

        if m3u8_url:
            entries.append({
                "name":  ch["name"],
                "group": ch.get("group", "Canlı TV"),
                "logo":  ch.get("logo",  ""),
                "url":   m3u8_url,
            })
        else:
            print(f"  ⚠ '{ch['name']}' için m3u8 linki alınamadı, atlanıyor.")

    if entries:
        content = build_m3u(entries)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n✅ playlist.m3u dosyası oluşturuldu → {len(entries)} kanal")
        print(content)
    else:
        print("\n❌ Hiç kanal bulunamadı! playlist.m3u güncellenmedi.")


if __name__ == "__main__":
    main()
