import ast
import datetime
import json
import os
import threading
import time

import pytz
import requests
from dotenv import load_dotenv, find_dotenv
from flask import Response

switch_safe_mode = False  # F ни малейшего запроса в сторону тг
switch_authorize_all = False  # F добавлять всех сразу в allowed_ids
switch_entire_authorization = True  # T авторизация (отправка соо, удаление)
switch_message_deletion = True  # T любое удаление сообщение
switch_forward_deletion = True  # T пересылка соо в группу
switch_mention_deletion = True  # mention and url
spam_timeout = 60 * 20  # в секундах
authentication_message_timeout = 120
max_duplicate_messages = 7
max_retries = 5

load_dotenv(find_dotenv())
url = os.environ.get('URL')
future_group_id = str(os.environ.get('FUTURE_GROUP_ID'))
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    path = '/root/futurebot/'
else:
    path = ''

for filename in ['wordlist.txt', 'asked_userids.txt', 'log.txt', 'history.txt', 'dm_log.txt']:
    if not os.path.isfile(f'{path}data/{filename}'):
        # Создаем файл, если он не существует
        with open(f'{path}data/{filename}', 'w', encoding='utf-8') as fl:
            fl.write('1 1')
if not os.path.isfile(f'{path}data/allowed_userids.txt'):
    with open(f'{path}names.json', 'r') as fl:
        ids = json.load(fl)
    # Создаем файл, если он не существует
    with open(f'{path}data/allowed_userids.txt', 'w', encoding='utf-8') as fl:
        fl.write('136817688 ' + ' '.join(ids.keys()) + ' ' + str(future_group_id))  # когда от каналов и от группы и @GroupAnonymousBot
with open(f'{path}names.json', 'r') as fl:
    ids = json.load(fl)
with open(f'{path}data/wordlist.txt', 'r', encoding='utf-8') as fl:
    wordlist = fl.read().split()
with open(f'{path}data/asked_userids.txt', 'r', encoding='utf-8') as fl:
    asked_userids = fl.read().split('\n')


def wait_for_deletion(chat_id: int, message_id, delay: int):
    timer = threading.Timer(delay, request_delete_message, args=(chat_id, message_id))
    timer.start()


def threading_delete_message(chat_id: int, message_id):
    threading.Thread(target=request_delete_message, args=(chat_id, message_id)).start()
    # request_delete_message(chat_id, message_id)


def request_delete_message(chat_id: int, message_id):
    if switch_safe_mode or not switch_message_deletion:
        print(url + f'deleteMessage?chat_id={chat_id}&message_id={message_id}')
    else:
        for i in range(max_retries):
            try:
                r = requests.post(url + f'deleteMessage?chat_id={chat_id}&message_id={message_id}', timeout=(2, 2))
                if r.json()['ok']:
                    return
            except Exception as e:
                print(str(e))


def asked_usrids(action, chat_id: int, user_id, username, reply_to_message_id: int | None, message_thread_id: int = None):
    if action == 'remove' and switch_entire_authorization:
        for i in asked_userids:
            if i.split()[0] == user_id:
                asked_userids.remove(i)
        with open(f'{path}data/asked_userids.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(asked_userids))
    elif action == 'add' and switch_entire_authorization:
        if not switch_safe_mode:
            r = send_message(chat_id, f'{username}, добро пожаловать в чат! Нажимайте кнопку ниже, только если Вы человек.', {'inline_keyboard': [[{'text': 'Подтверждаю', 'callback_data': user_id}]]}, reply_to_message_id=reply_to_message_id, message_thread_id=message_thread_id)
            threading_delete_message(chat_id, reply_to_message_id)
            restrictChatMember_msgSend(chat_id=chat_id, user_id=user_id)
            if r is not None and r.json()['ok']:  # сообщение не удалено раньше
                print(r.json())
                wait_for_deletion(chat_id, r.json()['result']['message_id'], authentication_message_timeout)  # удаляет мсг аутентификации
                asked_userids.append(f'{user_id} {int(time.time())}')
                with open(f'{path}data/asked_userids.txt', 'w', encoding='utf-8') as f:
                    f.write('\n'.join(asked_userids))
    elif action == 'is':
        flag = False
        for i in asked_userids:
            if i.split()[0] == user_id:
                flag = True
                if int(time.time()) - int(i.split()[1]) > 3:
                    asked_userids.remove(i)
                    asked_usrids('add', chat_id, user_id, username, reply_to_message_id, message_thread_id)
                else:
                    threading_delete_message(chat_id, reply_to_message_id)  # инчае остаются соо при активной авторизации и новых соо
                break
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
    for banword in wordlist:
        if '&' in banword:
            banwords = banword.split('&')
            delete = False
            for msg in msgs:  # поиск банворда в любых правила msgs
                if all(bw in msg for bw in banwords):  # all помушто тут &
                    delete = True
                    break  # Прерываем цикл, так как нашли совпадение
            if delete:
                return [True, banword]
        else:
            if any(banword in msg for msg in msgs):
                return [True, banword]
    return [False, '']


def keyboards(user):
    global ids
    if user in ids:
        return {'keyboard': [[{'text': 'Добавить запрещенное слово'}, {'text': 'Удалить запрещенное слово'}],
                             [{'text': '/logs'}, {'text': 'админка'}]],
                'resize_keyboard': True}
    else:
        return None



def count_duplicate_messages(user_id: str) -> tuple:
    with open(f'{path}data/history.txt', 'r', encoding='utf-8') as f:
        count = (1, 'default')  # счет, прошлое значение | начинается с 1, тк первое сообщение уже одно
        texts = []
        for i in f.readlines():
            if i.split()[1] == user_id:
                try:
                    r = ast.literal_eval(i[i.find('{'):])
                    if 'text' in r['message'] or 'caption' in r['message']:
                        if 'caption' in r['message']:
                            text = r['message']['caption']
                        else:
                            text = r['message']['text']
                        if text in texts:
                            count = (count[0] + 1, text)
                        else:
                            count = (count[0], text)
                            texts.append(text)
                    else:
                        if count[1] == '<i>вложение</i>':
                            count = (count[0] + 1, '<i>вложение</i>')
                        else:
                            count = (count[0], '<i>вложение</i>')
                except ValueError:  # ast syntax 153
                    pass
                print(count)
    print(count)
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


def send_message(chat_id: int | str, message, keyboard=None, spoiler=False, reply_to_message_id: int = None, message_thread_id: int = None) -> None | Response:
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
    if message_thread_id is not None:
        send_body['message_thread_id'] = message_thread_id
    if switch_safe_mode:
        print(url + 'sendMessage', send_body)
    else:
        r = None
        for i in range(max_retries):
            try:
                r = requests.post(url + 'sendMessage', json=send_body, timeout=(2, 2))
                if r.json()['ok']:
                    break
            except Exception as e:
                print(str(e))
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
        r = requests.post(f'{url}sendDocument?chat_id={chat_id}', files=files)
        print(r.json())


def upload_video(chat_id, file, caption='', reply_to_message_id=''):
    files = {
        'video': open(file, 'rb')
    }
    if switch_safe_mode:
        print('{url}sendVideo?chat_id={chat_id}&caption={caption}')
    else:
        requests.post(f'{url}sendVideo?chat_id={chat_id}&caption={caption}&reply_to_message_id={reply_to_message_id}', files=files)


def append_log(msg, ping: int = None):
    try:
        with open(f'{path}data/log.txt', 'r', encoding='utf-8') as f:
            old_data = f.read()
        with open(f'{path}data/log.txt', 'w', encoding='utf-8') as f:
            if not ping:
                f.write(f'[{datetime.datetime.now(pytz.timezone("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S")}]: {msg}' + '\n')
            else:
                f.write(f'[{datetime.datetime.now(pytz.timezone("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S")}]<b>({ping}s.)</b> : {msg}' + '\n' + old_data)
        print(msg)
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
            result.append(userid)
    return result


def restrictChatMember_msgSend(chat_id: int | str, user_id: int | str, duration: int = 60 * 15):
    until_date = int(time.time()) + duration
    send_body = {
        'chat_id': chat_id,
        'user_id': user_id,
        'permissions': {"can_send_messages": False,
                        "can_send_audios": False,
                        "can_send_photos": False,
                        "can_send_videos": False,
                        "can_send_other_messages": False,
                        "can_send_polls": False,
                        "can_invite_users": False,
                        "can_add_web_page_previews": False},
        'use_independent_chat_permissions': False,
        'until_date': until_date
    }
    # append_log(f'{user_id} ограничен в отправке до {until_date}')
    if switch_safe_mode or not switch_message_deletion:
        print(url + 'restrictChatMember', send_body)
    else:
        r = None
        for i in range(max_retries):
            try:
                r = requests.post(url + 'restrictChatMember', json=send_body, timeout=(2, 2))
                if r.json()['ok']:
                    break
            except Exception as e:
                print(str(e))


def unRestrictChatMember_msgSend(chat_id: int | str, user_id: int | str):
    send_body = {
        'chat_id': chat_id,
        'user_id': user_id,
        'permissions': {"can_send_messages": True,
                        "can_send_audios": True,
                        "can_send_photos": True,
                        "can_send_videos": True,
                        "can_send_other_messages": True,
                        "can_send_polls": True,
                        "can_invite_users": True,
                        "can_add_web_page_previews": True},
    }
    # append_log(f'{user_id} разблокирован в отправке')
    if switch_safe_mode:
        print(url + 'restrictChatMember', send_body)
    else:
        r = None
        for i in range(max_retries):
            try:
                r = requests.post(url + 'restrictChatMember', json=send_body, timeout=(2, 2))
                if r.json()['ok']:
                    return
            except Exception as e:
                print(str(e))
        # print(r.json())
        return r
