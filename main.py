import requests
import re
import datetime

# Ayarlar
OUTPUT_FILE = "Trgoals.m3u"
LOGO_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQGFDG5osdfPh7QmAhMmkGUW1P7HED2vWGq1cOzdj1_3Q&s=10"
BASE_DOMAIN_PREFIX = "https://patronizle"

def find_active_domain():
    print("[1/3] Aktif domain araniyor...")
    # Tarama araligini biraz genislettim
    for i in range(35, 100):
        test_domain = f"{BASE_DOMAIN_PREFIX}{i}.cfd"
        try:
            # Sadece header kontrolü yaparak hizlandiriyoruz
            response = requests.head(test_domain, timeout=2)
            if response.status_code == 200:
                print(f"✓ Bulundu: {test_domain}")
                return test_domain
        except:
            continue
    return None

def create_m3u():
    domain = find_active_domain()
    if not domain:
        print("✗ Hata: Aktif domain bulunamadi!")
        return

    channel_ids = {
        "patron":"BEIN SPORTS 1",
        "yayinzirve":"BEIN SPORTS 1",
        "yayinb2":"BEIN SPORTS 2",
        "yayinb3":"BEIN SPORTS 3",
        "yayinb4":"BEIN SPORTS 4",
        "yayinb5":"BEIN SPORTS 5",
        "yayinbm1":"BEIN SPORTS MAX 1",
        "yayinbm2":"BEIN SPORTS MAX 2",
        "yayinss":"S SPORT 1",
        "yayinss2":"S SPORT 2",
        "yayint1":"TIVIBU SPOR 1",
        "yayint2":"TIVIBU SPOR 2",
        "yayint3":"TIVIBU SPOR 3",
        "yayint4":"TIVIBU SPOR 4",
        "yayinsmarts":"SPOR SMART 1",
        "yayinsms2":"SPOR SMART 2",
        "yayintrtspor":"TRT SPOR",
        "yayintrtspor2":"TRT SPOR 2",
        "yayinas":"A SPOR",
        "yayinatv":"ATV HD",
        "yayintv8":"TV8 HD",
        "yayintv85":"TV8,5 HD",
        "yayinnbatv":"NBA TV",
        "yayinex1":"TABII 1",
        "yayinex2":"TABII 2",
        "yayinex3":"TABII 3",
        "yayinex4":"TABII 4",
        "yayinex5":"TABII 5",
        "yayinex6":"TABII 6",
        "yayinex7":"TABII 7",
        "yayinex8":"TABII 8"
    }

    print("\n[2/3] Kanallar cekiliyor...")
    m3u_content = "#EXTM3U\n"
    m3u_content += f"# Son Guncelleme: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

    for cid, cname in channel_ids.items():
        url = f"{domain}/ch.html?id={cid}"
        try:
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=5)
            r.encoding = 'utf-8'
            # Regex ile m3u8 ana yolunu bul
            match = re.search(r'const baseurl = "(.*?)"', r.text)
            
            if match:
                baseurl = match.group(1)
                stream_url = f"{baseurl}{cid}.m3u8"
                
                # M3U Formatı
                m3u_content += f'#EXTINF:-1 tvg-logo="{LOGO_URL}" group-title="TRGOALS TV", {cname}\n'
                m3u_content += f'#EXTVLCOPT:http-referer={domain}/\n' # Referer engeli icin sart
                m3u_content += f'{stream_url}\n'
                print(f" ✓ {cname} eklendi.")
            else:
                print(f" ✗ {cname} (Link ayiklanamadi)")
        except:
            print(f" ✗ {cname} (Baglanti hatasi)")

    # [3/3] Dosyayi Kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"\n[3/3] Bitti! {OUTPUT_FILE} olusturuldu.")

if __name__ == "__main__":
    create_m3u()
