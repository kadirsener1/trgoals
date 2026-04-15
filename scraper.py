import asyncio
import re
import json
import requests
from playwright.async_api import async_playwright

BASE_CHANNELS = "https://patronsports2.cfd/channels.php"
BASE_PLAYER = "https://patronizle35.cfd/ch.html?id="

# 1) kanal listesini çek
def get_channels():
    html = requests.get(BASE_CHANNELS).text

    # JSON varsa direkt yakala
    try:
        data = json.loads(html)
        return data
    except:
        pass

    # JS object yakala
    matches = re.findall(r'"(yayin[^"]+)"\s*:\s*"([^"]+)"', html)
    return {k: v for k, v in matches}


async def run():
    channels = get_channels()
    print("Kanal sayısı:", len(channels))

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for slug, name in channels.items():
            print("Deneme:", name)

            found = set()

            def handle_response(resp):
                if ".m3u8" in resp.url:
                    found.add(resp.url)

            page.on("response", handle_response)

            await page.goto(BASE_PLAYER + slug, wait_until="domcontentloaded")
            await page.wait_for_timeout(6000)

            # iframe içi kontrol
            frames = page.frames
            for f in frames:
                try:
                    content = await f.content()
                    urls = re.findall(r"https?://[^\s'\"]+\.m3u8[^\s'\"]*", content)
                    for u in urls:
                        found.add(u)
                except:
                    pass

            page.remove_listener("response", handle_response)

            if found:
                for u in found:
                    print("[OK]", name, u)
                    results.append((name, u))
            else:
                print("[X] Yok:", name)

        await browser.close()

    # M3U yaz
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, url in results:
            f.write(f"#EXTINF:-1,{name}\n{url}\n")


if __name__ == "__main__":
    asyncio.run(run())
