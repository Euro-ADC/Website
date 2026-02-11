import os
import markdown
from flask import Flask, render_template

app = Flask(__name__)

ARTICLES_FOLDER = 'articles'

@app.route('/')
def index():
    articles_data = []
    if os.path.exists(ARTICLES_FOLDER):
        for filename in sorted(os.listdir(ARTICLES_FOLDER)):
            if filename.endswith('.md'):
                with open(os.path.join(ARTICLES_FOLDER, filename), "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        title = lines[0].replace('#', '').strip()
                        content_md = "".join(lines[1:])
                        content_html = markdown.markdown(content_md, extensions=['extra'])
                        content_html = content_html.replace("[", "<img src=\"/static/images/").replace("]", "\">")
                        articles_data.append({'title': title, 'content': content_html})
    
    return render_template('index.html', articles=articles_data)

if __name__ == '__main__':
    app.run(debug=True)