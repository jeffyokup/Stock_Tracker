import csv
import os
import time

import nltk
import praw
import requests

from config import discord_webhook_url, vantage_api_key

dirname = os.path.dirname(__file__)

tickers = {}
name_to_ticker = {}


def init_ticker_dictionaries(file_path) -> None:
    with open(file_path) as csv_file:
        print('Reading CSV')
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                print(f'Column names are {", ".join(row)}')
                line_count += 1
            else:
                ticker = row[0].upper()
                name = row[1].upper()
                tickers[ticker] = 0
                name_to_ticker[name] = ticker
                line_count += 1
        print(f'Processed {line_count} lines.')


def reset_ticker_counts() -> None:
    for k in tickers:
        tickers[k] = 0
    print('Ticker counts reset to 0.')


def get_sentence_analysis(reddit_comment: str) -> list:
    tokens = nltk.word_tokenize(reddit_comment)
    tokens_with_tags = nltk.pos_tag(tokens)
    return tokens_with_tags


def process_comment(reddit_comment, comment_count: int, only_check_for_capital_tickers: bool) -> None:
    text = reddit_comment.body
    author = reddit_comment.author
    if '' in text.lower():
        tokens_mentioned = []
        tokens_with_tags = get_sentence_analysis(text)
        for token_with_tag in tokens_with_tags:
            token, tag = token_with_tag[0], token_with_tag[1]
            if not only_check_for_capital_tickers:
                token = token.upper()

            exclude_list = ['DD']

            if tag == 'NNP' and token in tickers and token not in exclude_list and token not in tokens_mentioned:
                current_count = tickers[token]
                tickers[token] = current_count + 1
                tokens_mentioned.append(token)
                print(f'#################### Ticker: {token}, Count: {tickers[token]}####################')
                print(f'~~~~~~~~~~ {comment_count}, {author} ~~~~~~~~~~')
                print(text[0:200] + "  ", "\n\n\n")


def get_top_tickers():
    max_ticker = ''
    max_count = 0
    for i, (k, v) in enumerate(tickers.items()):
        if v > max_count:
            max_ticker = k
            max_count = v
    return max_ticker, max_count


def post_to_discord_server(data) -> None:
    data = {"content": data}
    response = requests.post(discord_webhook_url, json=data)
    print(response.status_code)
    print(response.content)


def get_count_reaction_emoji(ticker_count: int) -> str:
    if ticker_count < 20:
        return ':face_vomiting:'
    elif ticker_count < 50:
        return ':thinking:'
    elif ticker_count < 100:
        return ':face_with_monocle:'
    else:
        return ':exploding_head:'


def create_discord_comment(ticker, ticker_count) -> str:
    reaction_emoji = get_count_reaction_emoji(ticker_count)
    percent_change = get_daily_percent_change(ticker)
    move = 'DOWN' if percent_change[0] == '-' else 'UP'
    comment = f'Ticker: {ticker} Count: {ticker_count} ~~~ {move}: {percent_change} {reaction_emoji}'
    return comment


def get_top_x_tickers(num):
    sorted_ticker_list = sorted(tickers.items(), key=lambda x: x[1], reverse=True)
    return sorted_ticker_list[0:num]


def get_daily_percent_change(ticker: str):
    url = 'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=' + ticker + '&apikey=' + vantage_api_key
    req = requests.get(url)
    percent = req.json()['Global Quote']['10. change percent']
    return percent


if __name__ == "__main__":
    print("Starting program")

    ticker_file_path = os.path.join(dirname, 'stock_tickers.csv')
    init_ticker_dictionaries(ticker_file_path)
    count = 0
    last_post_time = time.time()
    min_wait_time = 3600  # 1 hour

    only_check_for_capd_tickers = True
    if not only_check_for_capd_tickers:
        print('Case IN-sensitive ticker search.')
    else:
        print('Case sensitive ticker search.')

    reddit = praw.Reddit('bot1')
    subreddit = reddit.subreddit("wallstreetbets")
    comments = subreddit.stream.comments(skip_existing=True)
    print("Awaiting comments...")
    for comment in comments:
        process_comment(comment, count, only_check_for_capd_tickers)

        current_time = time.time()
        time_diff = current_time - last_post_time
        if min_wait_time <= time_diff:
            last_post_time = current_time

            top_ticker_list = get_top_x_tickers(5)
            print(top_ticker_list)
            if not top_ticker_list:
                print('No top tickers found.')
                continue

            for ticker in top_ticker_list:
                t, v = ticker
                if v > 0:
                    comment = create_discord_comment(t, v)
                    post_to_discord_server(comment)
            reset_ticker_counts()
        count += 1
