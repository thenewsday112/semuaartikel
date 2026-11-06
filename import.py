  import sqlite3
import feedparser
import requests
from bs4 import BeautifulSoup
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import json

DB_PATH = r"C:\laragon\www\database_hasil5\database.sqlite"
RSS_FILE = r"C:\laragon\www\rss_list.txt"
OUTPUT_DIR = r"C:\laragon\www"
BASE_URL = "https://thenewsday112.github.io/tekno"

# Header HTTP agar scraping tidak diblokir
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# --------------------------------------------------------------------------
# KODE IKLAN ADSTERRA
# --------------------------------------------------------------------------
ADSTERRA_CODE = """
<div style="text-align:center; margin:20px 0;">
    <script type="text/javascript">
        atOptions = {
            'key' : 'f9e40eb3b3cd05f1038aac7b36b33ad2',
            'format' : 'iframe',
            'height' : 90,
            'width' : 728,
            'params' : {}
        };
    </script>
    <script type="text/javascript" src="https://upholdbrilliancerecast.com/f9e40eb3b3cd05f1038aac7b36b33ad2/invoke.js"></script>
</div>
"""

# --------------------------------------------------------------------------
# INISIALISASI DATABASE (tambah kolom tanggal)
# --------------------------------------------------------------------------
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artikel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            judul TEXT,
            konten TEXT,
            gambar TEXT,
            tanggal_publish TEXT,
            tanggal_update TEXT
        )
    """)
    
    # Cek apakah kolom baru sudah ada, kalau belum tambahkan
    cursor.execute("PRAGMA table_info(artikel)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'gambar' not in columns:
        cursor.execute("ALTER TABLE artikel ADD COLUMN gambar TEXT")
    if 'tanggal_publish' not in columns:
        cursor.execute("ALTER TABLE artikel ADD COLUMN tanggal_publish TEXT")
    if 'tanggal_update' not in columns:
        cursor.execute("ALTER TABLE artikel ADD COLUMN tanggal_update TEXT")
    
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# EXTRACT KONTEN + GAMBAR + TANGGAL
# --------------------------------------------------------------------------
def extract_full_content(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        if response.status_code != 200:
            return None, None, None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ambil gambar OG
        image_url = None
        og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
        if og_image and og_image.get('content'):
            image_url = og_image['content']
        
        # Ambil tanggal publish
        tanggal = None
        for meta_prop in ['article:published_time', 'article:modified_time', 'datePublished']:
            meta = soup.find('meta', property=meta_prop) or soup.find('meta', attrs={'name': meta_prop})
            if meta and meta.get('content'):
                tanggal = meta['content']
                break
        
        # Ambil paragraf
        paragraphs = soup.find_all('p')
        full_text = []
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 40 and not any(x in text.lower() for x in ['cookie', 'privacy policy', 'subscribe', 'all rights reserved', 'terms of use']):
                full_text.append(f"<p>{text}</p>")
                
        if not full_text:
            return None, image_url, tanggal
            
        return "\n".join(full_text), image_url, tanggal
    except Exception:
        return None, None, None


# --------------------------------------------------------------------------
# PROCESS SINGLE FEED
# --------------------------------------------------------------------------
def process_single_feed(feed_url):
    feed_url = feed_url.strip()
    if not feed_url or feed_url.startswith("#"):
        return 0, 0

    baru = 0
    duplikat = 0
    
    try:
        feed = feedparser.parse(feed_url)
        conn = sqlite3.connect(DB_PATH, timeout=15)
        cursor = conn.cursor()
        
        for entry in feed.entries:
            link = entry.get('link', '')
            judul = entry.get('title', 'Tanpa Judul')
            
            if not link:
                continue

            # Cek duplikat
            cursor.execute("SELECT id FROM artikel WHERE link = ?", (link,))
            if cursor.fetchone():
                duplikat += 1
                continue

            # Extract konten lengkap
            full_text_html, image_url, tanggal = extract_full_content(link)
            
            if not full_text_html:
                summary = entry.get('summary', entry.get('description', 'Konten tidak tersedia.'))
                full_text_html = f"<p>{summary}</p>"
            
            # Fallback tanggal
            if not tanggal:
                published_parsed = entry.get('published_parsed')
                if published_parsed:
                    tanggal = datetime(*published_parsed[:6]).isoformat()
                else:
                    tanggal = datetime.now().isoformat()
            
            tanggal_update = datetime.now().isoformat()
            
            # Gambar
            img_tag = f'<div style="text-align:center; margin-bottom:20px;"><img src="{image_url}" alt="{judul}" style="max-width:100%; height:auto; border-radius:8px;" loading="lazy"></div>' if image_url else ""
            
            # Konten lengkap dengan iklan
            konten_lengkap = f"""
            {img_tag}
            {ADSTERRA_CODE}
            <div class="article-body" style="font-size: 16px; line-height: 1.8; color: #333;">
                {full_text_html}
                <p style="margin-top: 25px;">
                    <a href="{link}" target="_blank" rel="nofollow noopener" style="color: #0d6efd; text-decoration: none; font-weight: bold;">
                        &rarr; Baca artikel asli
                    </a>
                </p>
            </div>
            {ADSTERRA_CODE}
            """
            
            try:
                cursor.execute(
                    "INSERT INTO artikel (link, judul, konten, gambar, tanggal_publish, tanggal_update) VALUES (?, ?, ?, ?, ?, ?)",
                    (link, judul, konten_lengkap, image_url, tanggal, tanggal_update)
                )
                conn.commit()
                baru += 1
            except sqlite3.IntegrityError:
                duplikat += 1
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return baru, duplikat


# --------------------------------------------------------------------------
# GENERATE SITEMAP.XML
# --------------------------------------------------------------------------
def generate_sitemap():
    sitemap_path = os.path.join(OUTPUT_DIR, "sitemap.xml")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, tanggal_update FROM artikel ORDER BY id DESC")
    articles = cursor.fetchall()
    conn.close()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Homepage
    xml_parts.append(f"""
    <url>
        <loc>{BASE_URL}/</loc>
        <lastmod>{today}</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>""")
    
    # Part 1
    xml_parts.append(f"""
    <url>
        <loc>{BASE_URL}/artikel_part1.html</loc>
        <lastmod>{today}</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>""")
    
    # Part 2
    xml_parts.append(f"""
    <url>
        <loc>{BASE_URL}/artikel_part2.html</loc>
        <lastmod>{today}</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.9</priority>
    </url>""")
    
    # Detail artikel (anchor)
    for artikel_id, tanggal_update in articles:
        lastmod = tanggal_update[:10] if tanggal_update else today
        xml_parts.append(f"""
    <url>
        <loc>{BASE_URL}/artikel_part1.html#artikel-{artikel_id}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.7</priority>
    </url>""")
    
    xml_parts.append('</urlset>')
    
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_parts))
    
    print(f"✅ Sitemap: {sitemap_path} ({len(articles)} artikel)")


# --------------------------------------------------------------------------
# GENERATE ROBOTS.TXT
# --------------------------------------------------------------------------
def generate_robots():
    robots_path = os.path.join(OUTPUT_DIR, "robots.txt")
    
    content = f"""User-agent: *
Allow: /

# Sitemap
Sitemap: {BASE_URL}/sitemap.xml

# Crawl delay
Crawl-delay: 1
"""
    
    with open(robots_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Robots.txt: {robots_path}")


# --------------------------------------------------------------------------
# GENERATE SCHEMA JSON-LD PER ARTIKEL
# --------------------------------------------------------------------------
def generate_article_schema(artikel_id, judul, gambar, tanggal_publish, tanggal_update, link):
    """Generate JSON-LD NewsArticle untuk SEO"""
    schema = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": judul[:110],
        "image": [gambar] if gambar else [],
        "datePublished": tanggal_publish or datetime.now().isoformat(),
        "dateModified": tanggal_update or datetime.now().isoformat(),
        "author": {
            "@type": "Organization",
            "name": "Portal Berita Indonesia",
            "url": BASE_URL
        },
        "publisher": {
            "@type": "Organization",
            "name": "Portal Berita Indonesia",
            "logo": {
                "@type": "ImageObject",
                "url": f"{BASE_URL}/logo.png",
                "width": 600,
                "height": 60
            }
        },
        "description": f"Baca berita terbaru: {judul[:160]}",
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{BASE_URL}/artikel_part1.html#artikel-{artikel_id}"
        },
        "url": link
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# EXPORT KE 2 FILE HTML DENGAN SEO LENGKAP
# --------------------------------------------------------------------------
def export_to_two_files():
    if not os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, judul, konten, gambar, tanggal_publish, tanggal_update, link FROM artikel ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return

    total_articles = len(rows)
    mid_point = (total_articles + 1) // 2

    parts = [
        ("artikel_part1.html", rows[:mid_point], "Bagian 1 (Update Terkini)", "artikel_part2.html"),
        ("artikel_part2.html", rows[mid_point:], "Bagian 2 (Arsip Berita)", "artikel_part1.html")
    ]

    for filename, chunk, part_name, other_part in parts:
        output_file = os.path.join(OUTPUT_DIR, filename)
        canonical_url = f"{BASE_URL}/{filename}"
        
        # Ambil judul untuk meta description
        sample_titles = ", ".join([row[1][:50] for row in chunk[:5]])
        meta_desc = f"Kumpulan berita terbaru: {sample_titles}. Update harian dengan informasi terpercaya."
        meta_desc = meta_desc[:160]
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        html_parts = []
        html_parts.append(f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
    <meta name="googlebot" content="index, follow">
    <meta name="bingbot" content="index, follow">
    
    <title>Portal Berita Terkini - {part_name} | Update Harian</title>
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="berita terkini, info terbaru, update harian, berita Indonesia">
    <meta name="author" content="Portal Berita Indonesia">
    
    <link rel="canonical" href="{canonical_url}">
    
    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="Portal Berita Terkini - {part_name}">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:site_name" content="Portal Berita Indonesia">
    <meta property="og:locale" content="id_ID">
    
    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Portal Berita Terkini - {part_name}">
    <meta name="twitter:description" content="{meta_desc}">
    
    <!-- Google Search Console Verification (GANTI DENGAN KODE ANDA) -->
    <meta name="google-site-verification" content="GANTI_DENGAN_KODE_GSC_ANDA">
    
    <!-- Preconnect -->
    <link rel="preconnect" href="https://cdnjs.cloudflare.com">
    <link rel="dns-prefetch" href="https://cdnjs.cloudflare.com">
    
    <!-- Schema JSON-LD CollectionPage -->
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "Portal Berita Terkini - {part_name}",
      "description": "{meta_desc}",
      "url": "{canonical_url}",
      "isPartOf": {{
        "@type": "WebSite",
        "name": "Portal Berita Indonesia",
        "url": "{BASE_URL}"
      }},
      "dateModified": "{today}",
      "inLanguage": "id-ID"
    }}
    </script>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; color: #333; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header-actions {{ text-align: center; margin-bottom: 30px; background: #fff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
        .ad-container {{ margin: 20px 0; display: flex; justify-content: center; overflow: hidden; }}
        .article-card {{ background: #fff; padding: 25px; margin-bottom: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); position: relative; }}
        .article-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 15px; margin-bottom: 15px; }}
        .article-card h2 {{ color: #111; margin: 0; font-size: 20px; flex-grow: 1; }}
        .article-meta {{ font-size: 12px; color: #888; margin-bottom: 15px; }}
        .btn-pdf {{ background-color: #e74c3c; color: #ffffff; border: none; padding: 8px 14px; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; white-space: nowrap; }}
        .btn-pdf:hover {{ background-color: #c0392b; }}
        .article-body {{ line-height: 1.6; }}
        .related-articles {{ margin-top: 30px; padding: 20px; background: #f9f9f9; border-radius: 8px; }}
        .related-articles h3 {{ margin-top: 0; font-size: 16px; color: #333; }}
        .related-articles ul {{ list-style: none; padding: 0; }}
        .related-articles li {{ margin: 8px 0; }}
        .related-articles a {{ color: #0d6efd; text-decoration: none; }}
        .related-articles a:hover {{ text-decoration: underline; }}
        .pagination {{ text-align: center; margin: 40px 0; }}
        .pagination a {{ display: inline-block; padding: 12px 24px; margin: 0 6px; background: #fff; border-radius: 6px; text-decoration: none; color: #333; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .pagination a.active {{ background: #27ae60; color: #fff; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-actions">
            <h1>Katalog Berita & Artikel Terkini - {part_name}</h1>
            <p>Menampilkan {len(chunk)} informasi pilihan dari total {total_articles} database berita.</p>
            <p style="font-size: 12px; color: #888;">Terakhir update: {today}</p>
            <div class="ad-container">
                <script>
                    atOptions = {{'key' : 'f9e40eb3b3cd05f1038aac7b36b33ad2', 'format' : 'iframe', 'height' : 90, 'width' : 728, 'params' : {{}}}};
                </script>
                <script src="https://upholdbrilliancerecast.com/f9e40eb3b3cd05f1038aac7b36b33ad2/invoke.js"></script>
            </div>
            <p><a href="{other_part}" style="color: #27ae60; text-decoration: none; font-weight: bold;">📄 Lihat {("Bagian 2" if "1" in filename else "Bagian 1")} →</a></p>
        </div>
        <div id="pdf-content">""")

        # Render setiap artikel
        for idx, item in enumerate(chunk):
            artikel_id, judul, konten, gambar, tanggal_publish, tanggal_update, link = item
            safe_title = str(judul).replace('"', '').replace("'", '').replace('/', '_').replace('\\', '_')
            
            # Format tanggal
            try:
                tgl_pub = datetime.fromisoformat(tanggal_publish.replace('Z', '+00:00')).strftime('%d %B %Y') if tanggal_publish else '-'
            except:
                tgl_pub = tanggal_publish[:10] if tanggal_publish else '-'
            
            # Schema NewsArticle per artikel
            article_schema = generate_article_schema(artikel_id, judul, gambar, tanggal_publish, tanggal_update, link)
            
            # Related articles (3 artikel berikutnya)
            related = chunk[idx+1:idx+4]
            related_html = ""
            if related:
                related_html = '<div class="related-articles"><h3>📚 Baca Juga:</h3><ul>'
                for rel in related:
                    related_html += f'<li><a href="#artikel-{rel[0]}">#{rel[0]}. {rel[1][:80]}</a></li>'
                related_html += '</ul></div>'
            
            html_parts.append(f"""
            <article class="article-card" id="artikel-{artikel_id}" itemscope itemtype="https://schema.org/NewsArticle">
                <script type="application/ld+json">
{article_schema}
                </script>
                <div class="article-header">
                    <h2 itemprop="headline">#{artikel_id}. {judul}</h2>
                    <button class="btn-pdf no-print" onclick="downloadSinglePDF('artikel-{artikel_id}', '{safe_title}')">📄 PDF</button>
                </div>
                <div class="article-meta">
                    <span itemprop="datePublished" content="{tanggal_publish}">📅 {tgl_pub}</span>
                    {' | <a href="' + link + '" target="_blank" rel="nofollow" itemprop="url">Sumber</a>' if link else ''}
                </div>
                <div class="article-body" itemprop="articleBody">
                    {konten}
                </div>
                {related_html}
            </article>""")

        p1_active = "active" if filename == "artikel_part1.html" else ""
        p2_active = "active" if filename == "artikel_part2.html" else ""

        html_parts.append(f"""
        </div>
        <div class="pagination">
            <a href="artikel_part1.html" class="{p1_active}">⬅️ Bagian 1</a>
            <a href="artikel_part2.html" class="{p2_active}">Bagian 2 ➡️</a>
        </div>
    </div>
    
    <script>
        function downloadSinglePDF(elementId, filename) {{
            const element = document.getElementById(elementId);
            const btn = element.querySelector('.btn-pdf');
            btn.style.display = 'none';
            const opt = {{ margin: 10, filename: filename + '.pdf', image: {{ type: 'jpeg', quality: 0.98 }}, html2canvas: {{ scale: 2, useCORS: true }}, jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }} }};
            html2pdf().set(opt).from(element).save().then(() => {{ btn.style.display = 'inline-block'; }});
        }}
    </script>
</body>
</html>""")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))

        print(f"✅ HTML + SEO: {output_file} ({len(chunk)} artikel)")


# --------------------------------------------------------------------------
# SCRAPE MASSIVE RSS
# --------------------------------------------------------------------------
def scrape_massive_rss():
    if not os.path.exists(RSS_FILE):
        print(f"[ERROR] File {RSS_FILE} tidak ditemukan!")
        return

    init_db()
    
    with open(RSS_FILE, "r", encoding="utf-8") as f:
        rss_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"[*] Memulai penarikan data FULL CONTENT + GAMBAR + OPTIMASI SEO dari {len(rss_urls)} sumber RSS...\n")

    total_baru = 0
    total_duplikat = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_single_feed, url): url for url in rss_urls}
        
        for future in as_completed(futures):
            b, d = future.result()
            total_baru += b
            total_duplikat += d

    print("\n" + "="*45)
    print(f"[SELESAI PEMANENAN]")
    print(f" - Berhasil disimpan (Artikel Baru) : {total_baru}")
    print(f" - Dilewati (Sudah ada di DB)        : {total_duplikat}")
    print("="*45)

    print("\n[*] Generate HTML dengan SEO lengkap...")
    export_to_two_files()
    
    print("\n[*] Generate sitemap.xml...")
    generate_sitemap()
    
    print("\n[*] Generate robots.txt...")
    generate_robots()
    
    print("\n" + "="*45)
    print("[SELESAI] File siap di-deploy ke Surge.sh!")
    print("="*45)
    print("\n📋 Checklist Deploy:")
    print("1. Upload semua file ke Surge.sh")
    print("2. Verifikasi Google Search Console")
    print("3. Submit sitemap.xml ke GSC")
    print("4. Request indexing halaman utama")
    print("5. Tunggu 1-4 minggu untuk hasil")


if __name__ == "__main__":
    scrape_massive_rss()
