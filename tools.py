import ast
import datetime
import html
import json
import os
import threading
import time

import requests
from dotenv import load_dotenv, find_dotenv
from flask import Response

switch_safe_mode = False  # F ни малейшего запроса в сторону тг
switch_authorize_all = False  # F добавлять всех сразу в allowed_ids
switch_entire_authorization = True  # T авторизация (отправка соо, удаление)
switch_message_deletion = True  # T любое удаление сообщение

spam_timeout = 3 * 60  # в секундах
authentication_message_timeout = 60*5
max_duplicate_messages = 9999999

load_dotenv(find_dotenv())
url = os.environ.get('URL')
future_group_id = int(os.environ.get('FUTURE_GROUP_ID'))
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    path = '/etc/futurebot/'
else:
    path = ''

for filename in ['wordlist.txt', 'asked_userids.txt', 'log.txt', 'history.txt', 'dm_log.txt']:
    if not os.path.isfile(f'{path}data/{filename}'):
        # Создаем файл, если он не существует
        with open(f'{path}data/{filename}', 'w', encoding='utf-8') as fl:
            fl.write('1 1')
if not os.path.isfile(f'{path}data/allowed_userids.txt'):
    # Создаем файл, если он не существует
    with open(f'{path}data/allowed_userids.txt', 'w', encoding='utf-8') as fl:
        fl.write('136817688 1087968824')  # когда от каналов и от группы

with open(f'{path}names.json', 'r') as fl:
    ids = json.load(fl)
with open(f'{path}data/wordlist.txt', 'r', encoding='utf-8') as fl:
    wordlist = fl.read().split()
with open(f'{path}data/asked_userids.txt', 'r', encoding='utf-8') as fl:
    asked_userids = fl.read().split('\n')


def wait_for_deletion(message_id, delay: int):
    timer = threading.Timer(delay, request_delete_message, args=(future_group_id, message_id))
    timer.start()


def asked_usrids(action, user_id, username, reply_to_message_id: int | None):
    if action == 'remove' and switch_entire_authorization:
        for i in asked_userids:
            if i.split()[0] == user_id:
                asked_userids.remove(i)
        with open(f'{path}data/asked_userids.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(asked_userids))
    elif action == 'add' and switch_entire_authorization:
        if not switch_safe_mode:
            restrictChatMember_msgSend(chat_id=future_group_id, user_id=user_id)
            r = send_message(future_group_id, f'{username}, добро пожаловать в чатик! Нажимайте кнопку ниже, только если вы человек. Иначе вы не сможете писать в чат', {'inline_keyboard': [[{'text': 'Подтверждаю', 'callback_data': user_id}]]}, reply_to_message_id=reply_to_message_id)
            if r is not None:
                #print(r.json())
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


def is_in_wordlist(msg: str) -> list:
    msg = msg.lower()
    result = []
    filtered_result = []
    msg_only_ru = []
    msg_only_en = []
    alf_ru = ['а', 'б', 'в', 'г', 'д', 'е', 'ж', 'з', 'и', 'й', 'к', 'л', 'м', 'н', 'о', 'п', 'р', 'с', 'т', 'у', 'ф', 'х', 'ц', 'ч', 'ш', 'щ', 'ъ', 'ы', 'ь', 'э', 'ю', 'я']
    alf_en = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
    alf_nums = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    previous_char = None
    for char in msg:
        if char != ' ':  # удаляет пробелы
            if char != previous_char:  # удаляет повторы букв
                result.append(char)
                if char in alf_ru + alf_en + alf_nums:  # сообщение без повторов и пробелов, алфавит только ру+англ+цифр
                    filtered_result.append(char)
                if char in alf_ru:  # сообщение без повторов и пробелов, алфавит только ру
                    msg_only_ru.append(char)
                if char in alf_en:  # сообщение без повторов и пробелов, алфавит только англ
                    msg_only_en.append(char)
            previous_char = char
    msg = ''.join(result)
    filtered_msg = ''.join(filtered_result)
    msg_only_ru = ''.join(msg_only_ru)
    msg_only_en = ''.join(msg_only_en)
    msgs = [msg, filtered_msg, msg_only_ru, msg_only_en]
    # print(msgs)
    for iteration in wordlist:
        if '&' in iteration:
            banwords = iteration.split('&')  # ['12','34']
            delete = False
            for msg in msgs:  # поиск банворда в любых правила msgs
                if all(banword in msg for banword in banwords):
                    delete = True
                    break  # Прерываем цикл, так как нашли совпадение
            if delete:
                return [True, iteration]

        else:
            if any(iteration in msg for msg in msgs):
                return [True, iteration]
    return [False, '']


def keyboards(user):
    global ids
    if user in ids:
        return {'keyboard': [[{'text': 'Добавить запрещенное слово'}, {'text': 'Удалить запрещенное слово'}],
                             [{'text': '/logs'}, {'text': 'админка'}]],
                'resize_keyboard': True}
    else:
        return None


def threading_delete_message(chat_id, message_id):
    threading.Thread(target=request_delete_message, args=(chat_id, message_id)).start()


def request_delete_message(chat_id, message_id):
    if switch_safe_mode or not switch_message_deletion:
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


def send_message(chat_id: int | str, message, keyboard=None, spoiler=False, reply_to_message_id: int = None) -> None | Response:
    # print(switch_safe_mode, switch_authorize_all, switch_entire_authorization, switch_message_deletion)
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
    if switch_safe_mode:
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
    if switch_safe_mode:
        print(f'{url}sendPhoto?chat_id={chat_id}')
    else:
        requests.post(f'{url}sendPhoto?chat_id={chat_id}', files=files)


def upload_file(chat_id, file):
    files = {
        'document': open(file, 'rb')
    }
    if switch_safe_mode:
        print(f'{url}sendDocument?chat_id={chat_id}')
    else:
        requests.post(f'{url}sendDocument?chat_id={chat_id}', files=files)


def upload_video(chat_id, file, caption='', reply_to_message_id=''):
    files = {
        'video': open(file, 'rb')
    }
    if switch_safe_mode:
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


def restrictChatMember_msgSend(chat_id: int | str, user_id: int | str, until_date: int = int(time.time()) + 60 * 60 * 6):
    send_body = {
        'chat_id': chat_id,
        'user_id': user_id,
        'permissions': {"can_send_messages": False},
        'until_date': until_date
    }
    append_log(f'{user_id} ограничен в отправке до {until_date}')
    if switch_safe_mode or not switch_message_deletion:
        print(url + 'restrictChatMember', send_body)
    else:
        r = requests.post(url + 'restrictChatMember', json=send_body)
        #print(r.json())
        return r


def unRestrictChatMember_msgSend(chat_id: int | str, user_id: int | str):
    send_body = {
        'chat_id': chat_id,
        'user_id': user_id,
        'permissions': {"can_send_messages": True}
    }
    append_log(f'{user_id} разблокирован в отправке')
    if switch_safe_mode:
        print(url + 'restrictChatMember', send_body)
    else:
        r = requests.post(url + 'restrictChatMember', json=send_body)
        # print(r.json())
        return r
