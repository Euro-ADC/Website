import os
import re
import markdown
from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client
from dotenv import load_dotenv

#load_dotenv("Euro-ADC-Website.env")

app = Flask(__name__)

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
BUCKET_NAME = "images"

supabase: Client = create_client(URL, KEY)


def get_user_from_token():
    token = request.cookies.get('supabase_token')
    if not token:
        return None
    try:
        return supabase.auth.get_user(token)
    except:
        return None


def replace_image_tags(content, base_url):
    pattern = r"\[([^\]]+)\]"
    replacement = rf'<img src="{base_url}\1" alt="\1" class="article-image">'
    return re.sub(pattern, replacement, content)


@app.route('/')
def index():
    home_article = None
    latest_name = "..."

    path_accueil = os.path.join("articles", "Accueil.md")
    if os.path.exists(path_accueil):
        try:
            with open(path_accueil, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    title = lines[0].lstrip('# ').strip()
                    body_md = "".join(lines[1:])
                    base_url = f"{URL}/storage/v1/object/public/{BUCKET_NAME}/"
                    pattern = r"\[(.*?)\.(jpg|jpeg|png|webp|gif)\]"
                    replacement = rf'<img src="{base_url}\1.\2" class="img-article">'
                    content_with_images = re.sub(pattern, replacement, body_md).replace("\\", "")
                    content_html = markdown.markdown(content_with_images, extensions=['extra'])
                    home_article = {'title': title, 'content': content_html}
        except Exception as e:
            print(f"Erreur lecture Accueil.md : {e}")

    try:
        response = supabase.table("articles").select("title").order("id", desc=True).limit(1).execute()
        if response.data:
            latest_name = response.data[0]['title']
    except Exception as e:
        print(f"Erreur récupération dernier article : {e}")

    return render_template('index.html', home_article=home_article, latest_name=latest_name)


@app.route('/articles')
def list_articles():
    try:
        response = supabase.table("articles").select("*").order("id", desc=True).execute()
        articles_db = response.data
    except Exception as e:
        print(f"Erreur : {e}")
        articles_db = []

    articles_data = []
    base_url = f"{URL}/storage/v1/object/public/{BUCKET_NAME}/"

    for art in articles_db:
        content_html = markdown.markdown(art['content'], extensions=['extra'])
        content_html = replace_image_tags(content_html, base_url)
        title_slug = re.sub(r'[^\w\s-]', '', art['title']).strip().lower().replace(' ', '-')
        article_ref = art.get('ref') or title_slug

        articles_data.append({
            'title': art['title'],
            'content': content_html,
            'ref': article_ref
        })

    return render_template('articles.html', articles=articles_data)


@app.route('/images')
def list_images():
    images_data = []
    try:
        storage_client = supabase.storage.from_(BUCKET_NAME)
        files = storage_client.list()
        files = reversed(files)

        base_url = f"{URL}/storage/v1/object/public/{BUCKET_NAME}/"

        for f in files:
            filename = f['name']
            
            if filename == '.emptyFolderPlaceholder':
                continue

            name_part, ext = os.path.splitext(filename)
            
            parts = name_part.rsplit('_', 1)
            
            if len(parts) == 2:
                article_ref = parts[0]
                
                images_data.append({
                    'url': f"{base_url}{filename}",
                    'link_to': url_for('list_articles', _anchor=article_ref)
                })

    except Exception as e:
        print(f"Erreur lors de la récupération des images : {e}")

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


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)