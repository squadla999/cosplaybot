#!/usr/bin/env python3
"""
Bot Telegram Auto Posting Cosplay
- Jalan terus di Railway (loop harian)
- Posting 5x sehari: 16:00, 19:30, 21:23, 00:02, 02:05 WIB
- 3 foto sekaligus (media group) + caption terpisah
- Tanpa hashtag
"""

import json
import os
import random
import time
import re
import requests
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────
BOT_TOKEN        = os.environ.get('BOT_TOKEN', 'GANTI_TOKEN')
CHAT_ID          = os.environ.get('CHAT_ID', '@cosplayscann')
WEB_URL          = 'https://cosplayscan.vercel.app'
ALBUM_PER_SESI   = 1
DELAY_ANTAR_POST = 60
MAX_FOTO         = 3

JADWAL_POSTING = [
    (16,  0),
    (19, 30),
    (21, 23),
    ( 0,  2),
    ( 2,  5),
]

WIB = timezone(timedelta(hours=7))

JSON_FILES = [
    'xidaidai_database.json',
    'yibei_database.json',
    'mashu_database.json',
    'mojiu_database.json',
    'puppyporn090_database.json',
    'nekokoyoshi_database.json',
    'chenxi_database.json',
    'cherry_database.json',
    'nikumikyo_database.json',
    'nnia_database.json',
    'sakurai_database.json',
    'kaor_database.json',
]

NAMA_AKTOR = {
    'xidaidai_database.json'    : 'Xidaidai',
    'yibei_database.json'       : 'Yibei',
    'mashu_database.json'       : 'Mashu',
    'mojiu_database.json'       : 'Mojiu',
    'puppyporn090_database.json': 'Puppyporn090',
    'nekokoyoshi_database.json' : 'Nekokoyoshi',
    'chenxi_database.json'      : 'Chenxi',
    'cherry_database.json'      : 'Cherry',
    'nikumikyo_database.json'   : 'Nikumikyo',
    'nnia_database.json'        : 'Nnia',
    'sakurai_database.json'     : 'Sakurai',
    'kaor_database.json'        : 'KaOri',
}

TERKIRIM_FILE = 'telegram_terkirim.json'
API_BASE      = f'https://api.telegram.org/bot{BOT_TOKEN}'


# ─────────────────────────────────────────────
# SLUG & URL GENERATOR (Sesuai Web)
# ─────────────────────────────────────────────
def slugify(teks: str) -> str:
    teks = teks.lower().strip()
    teks = re.sub(r'[^a-z0-9\s-]', '', teks)
    teks = re.sub(r'\s+', '-', teks)
    teks = re.sub(r'-+', '-', teks).strip('-')
    return teks


def generate_slug(album: dict) -> tuple:
    """
    Return (album_slug, cosplayer_slug) sesuai format web
    album.html?id=ALBUM_SLUG&c=COSPLAYER_SLUG
    """
    source_file   = album.get('_source_file', '')
    nama_aktor    = NAMA_AKTOR.get(source_file, source_file.replace('_database.json', ''))
    nama_karakter = album.get('karakter', '')
    
    cos_slug = slugify(nama_aktor)
    char_slug = slugify(nama_karakter)
    album_slug = f"{cos_slug}-{char_slug}"
    
    return album_slug, cos_slug


def ambil_game(judul: str) -> str:
    pisah = re.split(r'\s*[–—]\s*|\s+-\s+', judul)
    return pisah[-1].strip() if len(pisah) >= 2 else ''


def buat_caption(album: dict) -> str:
    source_file   = album.get('_source_file', '')
    nama_aktor    = NAMA_AKTOR.get(source_file, source_file.replace('_database.json', ''))
    nama_karakter = album.get('karakter', '')
    judul         = album.get('judul', '')
    gambar        = album.get('gambar_cloudinary', [])
    jumlah        = len(gambar)
    game          = ambil_game(judul)
    
    # Generate slug & URL langsung ke album spesifik
    album_slug, cos_slug = generate_slug(album)
    url = f"{WEB_URL}/album.html?id={album_slug}&c={cos_slug}"

    caption  = f"👤 {nama_aktor}\n"
    caption += f"🎭 {nama_karakter}\n"
    if game:
        caption += f"🎮 {game}\n"
    caption += f"📸 {jumlah} photos\n\n"
    caption += f"🔗 Full album:\n{url}"
    return caption


# ─────────────────────────────────────────────
# LOAD & SIMPAN DATA
# ─────────────────────────────────────────────
def load_semua_album() -> list:
    semua      = []
    script_dir = os.path.dirname(os.path.abspath(__file__))

    for nama_file in JSON_FILES:
        path = os.path.join(script_dir, nama_file)
        if not os.path.exists(path):
            print(f"  ⚠️  Tidak ditemukan: {nama_file}")
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            albums = data if isinstance(data, list) else data.get('albums', [data])
            valid  = 0
            for album in albums:
                if album.get('status') != 'selesai':
                    continue
                if not album.get('gambar_cloudinary'):
                    continue
                album['_source_file'] = nama_file
                semua.append(album)
                valid += 1
            print(f"  ✅ {nama_file}: {valid} album")
        except Exception as e:
            print(f"  ❌ {nama_file}: {e}")

    return semua


def load_terkirim() -> set:
    if os.path.exists(TERKIRIM_FILE):
        try:
            with open(TERKIRIM_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def simpan_terkirim(terkirim: set):
    with open(TERKIRIM_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(terkirim), f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# KIRIM KE TELEGRAM
# ─────────────────────────────────────────────
def kirim_media_group(foto_list: list) -> bool:
    media = [{'type': 'photo', 'media': url} for url in foto_list]
    try:
        resp  = requests.post(
            f'{API_BASE}/sendMediaGroup',
            json={'chat_id': CHAT_ID, 'media': media},
            timeout=30
        )
        hasil = resp.json()
        if hasil.get('ok'):
            return True
        print(f"    ⚠️  Error media group: {hasil.get('description')}")
        return False
    except Exception as e:
        print(f"    ⚠️  Error: {e}")
        return False


def kirim_pesan(teks: str) -> bool:
    try:
        resp  = requests.post(
            f'{API_BASE}/sendMessage',
            json={
                'chat_id'                : CHAT_ID,
                'text'                   : teks,
                'disable_web_page_preview': True,
            },
            timeout=30
        )
        hasil = resp.json()
        if hasil.get('ok'):
            return True
        print(f"    ⚠️  Error pesan: {hasil.get('description')}")
        return False
    except Exception as e:
        print(f"    ⚠️  Error: {e}")
        return False


def kirim_album(album: dict) -> bool:
    gambar_list = album.get('gambar_cloudinary', [])
    cover       = album.get('cover_cloudinary') or (gambar_list[0] if gambar_list else None)

    if not cover:
        print("    ⚠️  Tidak ada gambar")
        return False

    album_slug, cos_slug = generate_slug(album)
    caption = buat_caption(album)

    foto_list = [cover]
    for url in gambar_list:
        if url == cover:
            continue
        if len(foto_list) >= MAX_FOTO:
            break
        foto_list.append(url)

    print(f"    🖼️  Kirim {len(foto_list)} foto (media group)...")
    if not kirim_media_group(foto_list):
        return False

    time.sleep(2)

    print(f"    💬 Kirim caption...")
    print(f"    🔗 URL: {WEB_URL}/album.html?id={album_slug}&c={cos_slug}")
    return kirim_pesan(caption)


# ─────────────────────────────────────────────
# SESI POSTING
# ─────────────────────────────────────────────
def jalankan_sesi(label: str):
    print("=" * 55)
    print(f"  📅 {datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')} WIB  [{label}]")
    print("=" * 55)

    print("\n📂 Membaca database...")
    semua_album = load_semua_album()
    print(f"   Total valid : {len(semua_album)}")

    if not semua_album:
        print("❌ Tidak ada album.")
        return

    terkirim = load_terkirim()
    
    # Tracking pakai album_slug (bukan url_album)
    belum = []
    for a in semua_album:
        slug, _ = generate_slug(a)
        if slug not in terkirim:
            belum.append(a)
    
    print(f"   Terkirim    : {len(terkirim)}")
    print(f"   Belum       : {len(belum)}")

    if not belum:
        print("\n✅ Semua album sudah terkirim! Reset telegram_terkirim.json untuk mulai ulang.")
        return

    random.shuffle(belum)
    sesi     = belum[:ALBUM_PER_SESI]
    berhasil = 0
    gagal    = 0

    print(f"\n🚀 Posting {len(sesi)} album...\n")

    for i, album in enumerate(sesi, 1):
        slug, _ = generate_slug(album)
        print(f"[{i}/{len(sesi)}] {album.get('judul', '')} | slug: {slug}")
        ok = kirim_album(album)

        if ok:
            berhasil += 1
            terkirim.add(slug)
            simpan_terkirim(terkirim)
            print(f"    ✅ Berhasil!\n")
        else:
            gagal += 1
            print(f"    ❌ Gagal.\n")

        if i < len(sesi):
            print(f"    ⏳ Jeda {DELAY_ANTAR_POST} detik...\n")
            time.sleep(DELAY_ANTAR_POST)

    sisa = len(semua_album) - len(terkirim)
    print("=" * 55)
    print(f"  ✅ Berhasil : {berhasil}/{len(sesi)}")
    print(f"  ❌ Gagal    : {gagal}/{len(sesi)}")
    print(f"  📦 Sisa     : {sisa} album")
    print("=" * 55)


# ─────────────────────────────────────────────
# CEK JADWAL
# ─────────────────────────────────────────────
def cek_jadwal(sekarang: datetime) -> tuple:
    for jam, menit in JADWAL_POSTING:
        if sekarang.hour == jam and sekarang.minute == menit:
            return True, f"{jam:02d}:{menit:02d}"
    return False, ''


def hitung_detik_ke_jadwal_berikutnya(sekarang: datetime) -> tuple:
    kandidat = []
    for jam, menit in JADWAL_POSTING:
        target = sekarang.replace(hour=jam, minute=menit, second=0, microsecond=0)
        if sekarang >= target:
            target += timedelta(days=1)
        selisih = (target - sekarang).total_seconds()
        kandidat.append((selisih, f"{jam:02d}:{menit:02d}"))

    kandidat.sort()
    return int(kandidat[0][0]), kandidat[0][1]


# ─────────────────────────────────────────────
# LOOP UTAMA
# ─────────────────────────────────────────────
def main():
    print("🤖 Bot Cosplay Railway — aktif!")
    print("   Jadwal posting (WIB):")
    for jam, menit in JADWAL_POSTING:
        print(f"     • {jam:02d}:{menit:02d}")

    sesi_berjalan = False

    while True:
        sekarang = datetime.now(WIB)
        cocok, label = cek_jadwal(sekarang)

        if cocok and not sesi_berjalan:
            sesi_berjalan = True
            jalankan_sesi(label)
            time.sleep(61)
            sesi_berjalan = False
        else:
            if not cocok:
                sesi_berjalan = False
            detik, jadwal_berikutnya = hitung_detik_ke_jadwal_berikutnya(sekarang)
            jam_hitung   = detik // 3600
            menit_hitung = (detik % 3600) // 60
            print(
                f"⏰ {sekarang.strftime('%H:%M')} WIB — "
                f"jadwal berikutnya {jadwal_berikutnya} "
                f"(dalam {jam_hitung}j {menit_hitung}m)"
            )
            time.sleep(30)


if __name__ == '__main__':
    main()
