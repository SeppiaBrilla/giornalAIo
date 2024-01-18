import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import json

f = open('templates/article.html')
template = f.read()
f.close()

BASE_URL = './articles/article'

SUGGESTED_ARTICLE = '''
            <div class="suggested-article">
                <h3>TITLE</h3>
                <p>DESCRIPTION</p>
            </div>
'''

f = open('articles.json')
existing_articles = json.load(f)
f.close()

def create_article(article, file_name):
    f = open("docs/articles/" + file_name + ".html", 'w')
    html = template.replace("TITLE", article["title"])
    html = html.replace("BODY", article["body"])
    html = html.replace("SUGGESTIONS", '\n'.join(article["related"]))
    html = html.replace("LINK", '\n'.join(article["original_link"]))
    f.write(html)
    f.close()


def create_home(articles):
    f = open('templates/index.html')
    template = f.read()
    f.close()
    articles_data = {}
    for article in articles:
        if not article['date'] in articles_data:
            articles_data[article['date']] = []
        articles_data[article['date']].append({'title':article['title'], 'url':f'articles/article{article["index"]}.html'})
    template = template.replace('ARTICLES_DATA',json.dumps(articles_data))
    f = open('docs/index.html', 'w')
    f.write(template)

def query(query):
        body =  json.dumps({
              "model": "mistral",
              "prompt": query,
              "stream": False
        })
        response = requests.post('http://localhost:11434/api/generate', data=body)
        return response.json()['response']

def get_tag_content(html, target_class):
    try:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Find the target tag
        target_element = soup.find_all(class_=target_class)

        # Check if the target tag was found
        if target_element:
            # Return the content of the target tag
            return target_element[0].get_text(strip=True)
        else:
            return ""

    except Exception as e:
        print(f"An error occurred: {e}")

def read_rss_feed(feed_url):
    # Parse the RSS feed
    feed = feedparser.parse(feed_url)
    date_format = "%a, %d %b %Y %H:%M:%S %z"

    # Check if the feed was parsed successfully
    if feed.bozo == 0:
        for entry in feed.entries:
            entry.published = datetime.strptime(entry.published, date_format)
        return feed.entries
    else:
        return []

rss_feed_url = "https://www.ansa.it/sito/ansait_rss.xml"
feed = read_rss_feed(rss_feed_url)
articles = []
i = len(existing_articles)
tot_len = i + len(feed)
for entry in feed:
    if not "podcast" in entry.title:
        response = requests.get(entry.link)
        if response.status_code == 200:
            target_tag = 'article-main'
            content = get_tag_content(response.text, target_tag)
            if content:
                text = query(f"create an article starting from the following content. Do not create a title.:\n{content}")
                title = ''
                while title == '':
                    title = query(f"create a title for the following article. Use less than 10 words in total\n:{text}").replace('"', '').replace('\'', '')
                articles.append({
                    'title':title,
                    'body':text,
                    'index':i,
                    'original_link': entry.link,
                    'date': entry.published.date().strftime('%Y-%m-%d')
                })
                print(f'{i}/{tot_len}', end='\r')
            i += 1
        else:
            print(f"Failed to download HTML. Status code: {response.status_code}")

titles = [{'title':article['title'], 'url':f"{BASE_URL}{article['index']}", 'date': article['date'], 'index': article['index']} for article in articles]
existing_articles += titles
f = open('articles.json', 'w')
f.write(json.dumps(existing_articles))
f.close()
print()
print("articles created")
all_titles = "\n-".join([title["title"] for title in titles])
i = 0
for article in articles:
    related_news = query(f'starting from the following article, find 5 related once among the one following. Choose only articles from the list \\n. Do not add anything but the article title to the 5 articles list. Article:\n{article["body"]}\nRelated articles list:\n-{all_titles}')
    related_news = related_news.split('\n')
    related_news_snippets = []
    for news in related_news:
        if news != article['title'] and news != '':
            snippet = ''
            while snippet == '':
                snippet = query(f"create a brief snippet for the following article title: {news}")
            related_news_snippets.append(
                SUGGESTED_ARTICLE.replace('TITLE', news).replace('DESCRIPTION', snippet)
            )
    article['related'] = related_news_snippets
    create_article(article, f'article{article["index"]}')
    print(f'{i}/{len(articles)}', end='\r')
    i += 1
create_home(existing_articles)
