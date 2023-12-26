import ast
import datetime
import html
import json
import os
import threading
import time

import requests
from dotenv import load_dotenv, find_dotenv

safe_mode = False
spam_timeout = 3 * 60  # в секундах
authentication_message_timeout = 60
max_duplicate_messages = 5

load_dotenv(find_dotenv())
url = os.environ.get('URL')
future_group_id = int(os.environ.get('FUTURE_GROUP_ID'))
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    path = '/etc/futurebot/'
else:
    path = ''

with open(f'{path}names.json', 'r') as fl:
    ids = json.load(fl)
with open(f'{path}wordlist.txt', 'r', encoding='utf-8') as fl:
    wordlist = fl.read().split()
with open(f'{path}data/asked_userids.txt', 'r', encoding='utf-8') as fl:
    asked_userids = fl.read().split('\n')


def wait_for_deletion(message_id, delay: int):
    timer = threading.Timer(delay, delete_message, args=(future_group_id, message_id))
    timer.start()


def asked_usrids(action, user_id, username, reply_to_message_id: int | None):
    if action == 'remove':
        for i in asked_userids:
            if i.split()[0] == user_id:
                asked_userids.remove(i)
        with open(f'{path}data/asked_userids.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(asked_userids))
    elif action == 'add':
        r = send_message(future_group_id, f'{username}, добро пожаловать в чатик! Нажимайте кнопку ниже, только если вы человек. Иначе вы не сможете писать в чат', {'inline_keyboard': [[{'text': 'Подтверждаю', 'callback_data': user_id}]]}, reply_to_message_id=reply_to_message_id)
        wait_for_deletion(r.json()['result']['message_id'], authentication_message_timeout)
        asked_userids.append(f'{user_id} {int(time.time())}')
        with open(f'{path}data/asked_userids.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(asked_userids))
    elif action == 'is':
        flag = False
        for i in asked_userids:
            if i.split()[0] == user_id:
                flag = True
                if int(time.time()) - int(i.split()[1]) > authentication_message_timeout:
                    asked_userids.remove(i)
                    asked_usrids('add', user_id, username, reply_to_message_id)
        return flag


def is_in_wordlist(msg: str) -> bool:
    for word in wordlist:
        if '&' in word:
            word = word.split('&')
            delete = True
            for i in word:
                if i not in msg.lower():
                    delete = False
            if delete:
                return True
        else:
            if word in msg.lower():
                return True
    return False


def keyboards(user):
    global ids
    if user in ids:
        return {'keyboard': [[{'text': 'Добавить запрещенное слово'}, {'text': 'Удалить запрещенное слово'}],
                             [{'text': '/logs'}]],
                'resize_keyboard': True}
    else:
        return None


def delete_message(chat_id, message_id):
    if safe_mode:
        print(url + f'deleteMessage?chat_id={chat_id}&message_id={message_id}')
    else:
        requests.post(url + f'deleteMessage?chat_id={chat_id}&message_id={message_id}')


def count_duplicate_messages(user_id: str, message: str = None, file_unique_id: str = None) -> int:
    count = 0
    with open(f'{path}data/history.txt', 'r', encoding='utf-8') as f:
        for i in f.readlines():
            if i.split()[1] == user_id:
                r = ast.literal_eval(i[i.find('{'):])
                if 'text' in r['message']:
                    if message == r['message']['text']:
                        count += 1
                elif 'sticker' in r['message']:
                    if file_unique_id == r['message']['sticker']['thumbnail']['file_unique_id']:
                        count += 1
    return count


def clear_history():
    with open(f'{path}data/history.txt', 'r', encoding='utf-8') as f:
        a = f.readlines()
        for index, record in enumerate(a):
            if int(time.time()) - int(record.split()[0]) > spam_timeout:
                a[index] = ''
    with open(f'{path}data/history.txt', 'w', encoding='utf-8') as f:
        f.write(''.join(a))


def append_history(user_id: int | str, r: str, date=time.time):
    clear_history()
    with open(f'{path}data/history.txt', 'a', encoding='utf-8') as f:
        try:
            f.write(f'{int(date())} {user_id} {r} \n')
        except Exception as e:
            f.write(f'Exception {e}' + '\n')


def send_message(chat_id: int | str, message, keyboard=None, spoiler=False, reply_to_message_id: int = None):
    if spoiler:
        message = f'<tg-spoiler>{message}</tg-spoiler>'
    if keyboard is None:
        send_body = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
    else:
        send_body = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'reply_markup': keyboard
        }
    if reply_to_message_id is not None:
        send_body['reply_to_message_id'] = reply_to_message_id
    if safe_mode:
        print(url + 'sendMessage', send_body)
    else:
        r = requests.post(url + 'sendMessage', json=send_body)
        # print(r.content)
        if r.status_code == 400:
            send_message(chat_id, html.escape(message), keyboard, spoiler)
        else:
            return r


def upload_photo(chat_id, file):
    files = {
        'photo': open(file, 'rb')
    }
    if safe_mode:
        print(f'{url}sendPhoto?chat_id={chat_id}')
    else:
        requests.post(f'{url}sendPhoto?chat_id={chat_id}', files=files)


def upload_file(chat_id, file):
    files = {
        'document': open(file, 'rb')
    }
    if safe_mode:
        print(f'{url}sendDocument?chat_id={chat_id}')
    else:
        requests.post(f'{url}sendDocument?chat_id={chat_id}', files=files)


def upload_video(chat_id, file, caption='', reply_to_message_id=''):
    files = {
        'video': open(file, 'rb')
    }
    if safe_mode:
        print('{url}sendVideo?chat_id={chat_id}&caption={caption}')
    else:
        requests.post(f'{url}sendVideo?chat_id={chat_id}&caption={caption}&reply_to_message_id={reply_to_message_id}', files=files)


def append_log(msg):
    try:
        with open(f'{path}data/log.txt', 'a', encoding='utf-8') as f:
            f.write(f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]: {msg}' + '\n')

    except Exception as e:
        with open(f'{path}data/log.txt', 'a', encoding='cp1251') as f:
            f.write(f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]: {msg}' + '\n')
            f.write(f'^^^^^caught exception {e}' + '\n')


def append_dm_log(user_id, msg, first_name=''):
    with open(f'{path}data/dm_log.txt', 'a', encoding='utf-8') as f:
        try:
            f.write(f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {first_name}({user_id}): {msg}' + '\n')
        except Exception as e:
            f.write(f'Exception {e}' + '\n')


def get_admins() -> list:
    with open(f'{path}names.json', 'r') as f:
        _ids = json.load(f)
        result = []
        for userid in _ids:
            if _ids[userid]['is_admin']:
                result.append(userid)
    return result
