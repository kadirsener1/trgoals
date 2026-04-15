import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://patronizle35.cfd"

CHANNELS = {
    "yayinss": "S SPORT 1",
    "yayinss2": "S SPORT 2",
    "yayint1": "TIVIBU SPOR 1",
    "yayint2": "TIVIBU SPOR 2",
    "yayint3": "TIVIBU SPOR 3",
    "yayint4": "TIVIBU SPOR 4",
    "yayinsmarts": "SPOR SMART 1",
    "yayinsms2": "SPOR SMART 2",
    "yayintrtspor": "TRT SPOR",
    "yayintrtspor2": "TRT SPOR 2",
    "yayinas": "A SPOR",
    "yayinatv": "ATV HD",
    "yayintv8": "TV8 HD",
    "yayintv85": "TV8,5 HD",
    "yayinnbatv": "NBA TV",
    "yayinex1": "TABII 1",
    "yayinex2": "TABII 2",
    "yayinex3": "TABII 3",
    "yayinex4": "TABII 4",
    "yayinex5": "TABII 5",
    "yayinex6": "TABII 6",
    "yayinex7": "TABII 7",
    "yayinex8": "TABII 8",
}

output = []

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for slug, name in CHANNELS.items():
            m3u8_links = set()

            def handle_response(response):
                if ".m3u8" in response.url:
                    m3u8_links.add(response.url)

            page.on("response", handle_response)

            url = f"{BASE_URL}/ch.html?id={slug}"
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(3)

            page.remove_listener("response", handle_response)

            if m3u8_links:
                for link in m3u8_links:
                    output.append((name, link))
                    print(name, link)
            else:
                print(f"[!] Bulunamadı: {name}")

        await browser.close()

    # M3U dosyası yaz
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, url in output:
            f.write(f'#EXTINF:-1,{name}\n{url}\n')

if __name__ == "__main__":
    asyncio.run(run())
