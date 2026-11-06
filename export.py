import sqlite3
import os

DB_PATH = r"C:\laragon\www\database_hasil1\database.sqlite"
OUTPUT_FILE = r"C:\laragon\www\semua_artikel.html"

def export_to_single_html():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database tidak ditemukan di {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, judul, konten FROM artikel")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("Tidak ada artikel di dalam database.")
        return

    # Ambil sampel judul teratas untuk Meta Description yang kuat di Google
    sample_titles = ", ".join([row[1] for row in rows[:5]]) if rows else "Berita Terkini"

    # Template HTML pembungkus dengan Optimasi SEO Tingkat Tinggi untuk Posisi 1
    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kumpulan Berita & Artikel Terkini Hari Ini ({len(rows)} Update Pilihan)</title>
    <meta name="description" content="Portal berita terlengkap menyajikan update informasi seputar {sample_titles} dan berita pilihan terpopuler hari ini.">
    <link rel="canonical" href="https://news2026footballforyoureadnowshareit.surge.sh/semua_artikel.html">
    
    <!-- Schema Markup JSON-LD (CollectionPage / ItemList) agar Googlebot mengenali struktur direktori berita -->
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "Kumpulan Berita & Artikel Terkini",
      "description": "Portal direktori update berita pilihan dan terpopuler.",
      "url": "https://news2026footballforyoureadnowshareit.surge.sh/semua_artikel.html"
    }}
    </script>

    <!-- Library untuk konversi HTML ke PDF -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header-actions {{
            text-align: center;
            margin-bottom: 30px;
            background: #fff;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        }}
        .header-actions h1 {{
            font-size: 26px;
            color: #111;
            margin-top: 0;
        }}
        .btn-download-all {{
            background-color: #27ae60;
            color: #ffffff;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: background-color 0.2s ease;
        }}
        .btn-download-all:hover {{
            background-color: #219653;
        }}
        .article-card {{
            background: #fff;
            padding: 25px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            position: relative;
            page-break-after: always;
        }}
        .article-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 15px;
            margin-bottom: 15px;
        }}
        .article-card h2 {{
            color: #1a0dab;
            margin: 0;
            font-size: 20px;
            flex-grow: 1;
        }}
        .btn-pdf {{
            background-color: #e74c3c;
            color: #ffffff;
            border: none;
            padding: 8px 14px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            white-space: nowrap;
        }}
        .btn-pdf:hover {{
            background-color: #c0392b;
        }}
        .article-body {{
            line-height: 1.6;
            font-size: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-actions">
            <h1>Katalog Berita & Artikel Terkini ({len(rows)} Informasi Pilihan)</h1>
            <p style="margin-bottom: 20px; color: #555;">Pusat update berita harian terlengkap, akurat, dan terstruktur dalam satu halaman.</p>
            <!-- TOMBOL DOWNLOAD SEMUA ARTIKEL -->
            <button class="btn-download-all" onclick="downloadAllPDF()">📚 Download Semua Artikel (PDF)</button>
        </div>

        <div id="pdf-content">
"""

    for item in rows:
        artikel_id, judul, konten = item
        safe_title = str(judul).replace('"', '').replace("'", '').replace('/', '_').replace('\\', '_')
        
        html_content += f"""
            <article class="article-card" id="artikel-{artikel_id}">
                <div class="article-header">
                    <h2>#{artikel_id}. {judul}</h2>
                    <!-- TOMBOL DOWNLOAD EKSKLUSIF PER ARTIKEL -->
                    <button class="btn-pdf no-print" onclick="downloadSinglePDF('artikel-{artikel_id}', '{safe_title}')">📄 PDF Artikel Ini</button>
                </div>
                <div class="article-body">
                    {konten}
                </div>
            </article>
"""

    html_content += """
        </div>
    </div>

    <script>
        function downloadSinglePDF(elementId, filename) {
            const element = document.getElementById(elementId);
            const btn = element.querySelector('.btn-pdf');
            btn.style.display = 'none';

            const opt = {
                margin:       10,
                filename:     filename + '.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2, useCORS: true },
                jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };

            html2pdf().set(opt).from(element).save().then(() => {
                btn.style.display = 'inline-block';
            });
        }

        function downloadAllPDF() {
            const element = document.getElementById('pdf-content');
            const buttons = document.querySelectorAll('.btn-pdf');
            buttons.forEach(btn => btn.style.display = 'none');

            const opt = {
                margin:       10,
                filename:     'Kumpulan_Semua_Artikel_News.pdf',
                image:        { type: 'jpeg', quality: 0.95 },
                html2canvas:  { scale: 1.5, useCORS: true },
                jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };

            html2pdf().set(opt).from(element).save().then(() => {
                buttons.forEach(btn => btn.style.display = 'inline-block');
            });
        }
    </script>
</body>
</html>
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[SELESAI] Berhasil mengeksport {len(rows)} artikel dengan optimasi SEO penunjang Posisi 1:")
    print(f" -> {OUTPUT_FILE}")

if __name__ == "__main__":
    export_to_single_html()
