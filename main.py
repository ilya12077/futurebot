from flask import Flask, request
from waitress import serve

from tools import *

app = Flask(__name__)
max_duplicate_messages = 3
load_dotenv(find_dotenv())
url = os.environ.get('URL')
future_group_id = int(os.environ.get('FUTURE_GROUP_ID'))
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    path = '/etc/telegrambot/'
else:
    path = ''
with open(f'{path}wordlist.txt', 'r', encoding='utf-8') as fl:
    wordlist = fl.read().split()
with open(f'{path}data/captcha_denied.txt', 'r', encoding='utf-8') as fl:
    captcha_denied = fl.read().split()


@app.route('/', methods=['GET', 'POST'])
def firewall():
    if request.method == "GET":
        return 'I\'m working'
    r = request.get_json()
    print(r)
    if 'callback_query' in r:
        if r['callback_query']['message']['chat']['id'] == future_group_id:
            if str(r['callback_query']['from']['id']) == r['callback_query']['message']['reply_markup']['inline_keyboard'][0][0]['callback_data']:
                try:
                    captcha_denied.remove(r['callback_query']['message']['reply_markup']['inline_keyboard'][0][0]['callback_data'])
                    with open(f'{path}captcha_denied.txt', 'w', encoding='utf-8') as f:
                        f.write(' '.join(captcha_denied))
                except ValueError:
                    pass
                delete_message(future_group_id, r['callback_query']['message']['message_id'])
            requests.post(url + f"answerCallbackQuery?callback_query_id={r['callback_query']['id']}")
    elif 'message' in r:
        chat_id = int(r['message']['chat']['id'])
        if chat_id == future_group_id:
            group_handler(r)
        elif r['message']['chat']['type'] == 'private':
            dm_handler(r)
    return 'OK'


def group_handler(r):
    user_id = str(r['message']['from']['id'])
    message_id = r['message']['message_id']
    chat_id = int(r['message']['chat']['id'])
    first_name = r['message']['from']['first_name']
    append_history(user_id, r)
    if user_id in captcha_denied:
        delete_message(chat_id, message_id)
    if 'text' in r['message']:
        msg = r['message']['text']
        if count_duplicate_messages(user_id, message=msg) > max_duplicate_messages or any(word in msg.lower() for word in wordlist):
            delete_message(chat_id, message_id)
            append_log('', f'удалено сообщение от {first_name}({user_id}): {msg}')
            return
    elif 'sticker' in r['message']:
        file_unique_id = r['message']['sticker']['thumbnail']['file_unique_id']
        if count_duplicate_messages(user_id, file_unique_id=file_unique_id) > max_duplicate_messages:
            delete_message(chat_id, message_id)
            append_log('', f'удалено сообщение от {first_name}({user_id}): *sticker*')
            return
    elif 'left_chat_participant' in r['message']:
        try:
            captcha_denied.remove(str(r['message']['left_chat_participant']['id']))
            with open(f'{path}captcha_denied.txt', 'w', encoding='utf-8') as f:
                f.write(' '.join(captcha_denied))
        except ValueError:
            pass
    elif 'new_chat_participant' in r['message']:
        if 'username' in r['message']['from']:
            username = '@' + r['message']['from']['username']
        else:
            username = first_name
        send_message(chat_id, f'{username}, добро пожаловать в чатик! Нажимайте кнопку ниже, только если вы человек. Иначе вы не сможете писать в чат', {'inline_keyboard': [[{'text': 'Подтверждаю', 'callback_data': user_id}]]})
        captcha_denied.append(str(r['message']['new_chat_participant']['id']))
        with open(f'{path}captcha_denied.txt', 'w', encoding='utf-8') as f:
            f.write(' '.join(captcha_denied))


def dm_handler(r):
    user_id = str(r['message']['from']['id'])
    first_name = r['message']['from']['first_name']
    if 'text' not in r['message']:
        send_message(user_id, 'Я понимаю только текст')
        return
    msg = r['message']['text']
    if user_id != '647372660':
        append_log(first_name, msg)

    match msg:
        case '/start':
            send_message(user_id, 'Чего желаешь? (я пока ничего не умею)')
        case _:
            send_message(user_id, 'Неизвестная команда')


if __name__ == '__main__':
    if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
        serve(app, host='0.0.0.0', port=8881, url_scheme='http')
    else:
        app.run(host='192.168.1.10', port=8881)
        # app.run(host='192.168.1.21', port=8881)

'''TODO:
settings.*
'''
