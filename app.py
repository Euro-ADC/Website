import os
import re
import markdown
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import json

#load_dotenv("Euro-ADC-Website.env")

app = Flask(__name__)

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
BUCKET_NAME = "images"

supabase: Client = create_client(URL, KEY)

def get_user_from_token() :
    token = request.cookies.get("supabase_token")
    if not token :
        return None
    try:
        return supabase.auth.get_user(token)
    except:
        return None

def replace_image_tags(content, base_url) :
    def get_alt_text(match) :
        filename = match.group(1)

        name_part = filename.rsplit(".", 1)[0]
        
        if "_" in name_part:
            ref = name_part.rsplit("_", 1)[0]
        else:
            ref = name_part
                
        md_path = os.path.join("articles", f"{ref}.md")
        if os.path.exists(md_path) :
            with open(md_path, "r", encoding="utf-8") as f :
                first_line = f.readline()
                if first_line :
                    alt_text = first_line.lstrip("# ").strip()
        else :
            response = supabase.table("articles").select("*").eq("ref", ref).order("id", desc=True).execute()
            alt_text = response.data[0]["title"] if len(response.data) == 1 else filename

        return rf'<img src="{base_url}{filename}" alt="{alt_text}" class="img-article">'

    pattern = r"\[([^\]]+)\]"
    return re.sub(pattern, get_alt_text, content)

def get_home_article(filename) :
    path = os.path.join("articles", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f :
            lines = f.readlines()
            if lines :
                title = lines[0].lstrip("# ").strip()
                body_md = "".join(lines[1:])
                base_url = f"{URL}/storage/v1/object/public/{BUCKET_NAME}/"
                
                content_with_images = replace_image_tags(body_md, base_url)
                
                content_html = markdown.markdown(content_with_images, extensions=["extra"])
                return {"title": title, "content": content_html}

    return None

@app.route("/")
def index():
    home_fr = get_home_article("Index_French.md")
    home_en = get_home_article("Index_English.md")
    
    latest_name = "..."
    response = supabase.table("articles").select("title").order("id", desc=True).limit(1).execute()
    if response.data:
        latest_name = response.data[0]["title"]

    return render_template("index.html",
                           home_fr=home_fr,
                           home_en=home_en,
                           latest_name=latest_name)

@app.route("/articles")
def list_articles():
    response = supabase.table("articles").select("*").order("id", desc=True).execute()
    articles_db = response.data
    
    articles_data = []
    # On prépare la liste pour le JSON-LD
    json_ld_items = []
    base_url = request.url_root.rstrip('/')

    for index, art in enumerate(articles_db):
        # ... ton code actuel pour transformer le markdown ...
        content_html = markdown.markdown(art["content"], extensions=["extra"])
        
        # On crée l'URL avec l'ancre
        article_url = f"{base_url}/articles#{art['ref']}"
        
        articles_data.append({
            "title": art["title"],
            "content": content_html,
            "ref": art["ref"]
        })

        # Structure JSON-LD pour chaque article
        json_ld_items.append({
            "@type": "ListItem",
            "position": index + 1,
            "url": article_url,
            "name": art["title"]
        })

    # On crée l'objet global
    schema_data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": json_ld_items
    }

    return render_template("articles.html", 
                           articles=articles_data, 
                           schema_json=json.dumps(schema_data))

@app.route("/images")
def list_images() :
    images_data = []
    storage_client = supabase.storage.from_(BUCKET_NAME)
    files = storage_client.list()
    files = reversed(files)

    base_url = f"{URL}/storage/v1/object/public/{BUCKET_NAME}/"

    for f in files:
        filename = f["name"]

        name_part, ext = os.path.splitext(filename)
        
        parts = name_part.rsplit("_", 1)
        
        if len(parts) == 2 :
            article_ref = parts[0]
            
            images_data.append({
                "url": f"{base_url}{filename}",
                "link_to": url_for('list_articles', _anchor=article_ref)
            })

    return render_template('images.html', images=images_data)

@app.route('/login')
def login():
    return render_template('login.html', url_provided=URL, key_provided=KEY)

@app.route('/admin')
def admin_page():
    if not get_user_from_token():
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/admin/upload', methods=['POST'])
def upload_article():
    token = request.cookies.get('supabase_token')
    if not get_user_from_token():
        return "Non autorisé", 401

    if 'file' not in request.files:
        return "Aucun fichier trouvé", 400

    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.md'):
        return "Veuillez sélectionner un fichier Markdown (.md)", 400

    filename = file.filename
    reference = os.path.splitext(filename)[0]
    content_raw = file.read().decode("utf-8")
    lines = content_raw.splitlines()

    if not lines:
        return "Fichier vide", 400

    title = lines[0].replace('#', '').strip()
    body = "\n".join(lines[1:]).strip()

    try:
        supabase.auth.set_session(access_token=token, refresh_token=token)
        supabase.table("articles").insert({
            "title": title,
            "content": body,
            "ref": reference
        }).execute()
        return "Succès", 200
    except Exception as e:
        return f"Erreur BDD : {e}", 500

@app.route('/admin/upload_image', methods=['POST'])
def handle_image_upload():
    token = request.cookies.get('supabase_token')
    if not get_user_from_token():
        return "Non autorisé", 401

    if 'file' not in request.files:
        return "Aucun fichier", 400

    file = request.files['file']
    filename = file.filename

    try:
        supabase.auth.set_session(access_token=token, refresh_token=token)
        storage_client = supabase.storage.from_(BUCKET_NAME)

        existing_files = storage_client.list()
        if any(f['name'] == filename for f in existing_files):
            return f"L'image '{filename}' existe déjà.", 409

        file_content = file.read()
        storage_client.upload(
            path=filename,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        return "Succès", 200
    except Exception as e:
        return f"Erreur Storage : {e}", 500

@app.route('/sitemap.xml')
def sitemap():
    pages = []
    base_url = request.url_root.rstrip('/') 
    today = datetime.now().strftime('%Y-%m-%d')

    pages.append({'loc': f"{base_url}/", 'lastmod': today, 'priority': '1.0', 'changefreq': 'daily'})
    pages.append({'loc': f"{base_url}/articles", 'lastmod': today, 'priority': '0.8', 'changefreq': 'weekly'})
    pages.append({'loc': f"{base_url}/images", 'lastmod': today, 'priority': '0.7', 'changefreq': 'monthly'})

    try:
        response = supabase.table("articles").select("ref").execute()
        for art in response.data:
            pages.append({
                'loc': f"{base_url}/articles#{art['ref']}",
                'lastmod': today,
                'priority': '0.6',
                'changefreq': 'monthly'
            })
    except Exception as e:
        print(f"Erreur génération sitemap : {e}")

    return render_template('sitemap_xml.html', pages=pages), 200, {'Content-Type': 'application/xml'}

@app.route('/robots.txt')
def robots():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'robots.txt')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)