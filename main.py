import json
import os
import time

import requests
from flask import Flask, request
from waitress import serve

import tools

app = Flask(__name__)

if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    path = '/etc/futurebot/'
else:
    path = ''

with open(f'{path}data/allowed_userids.txt', 'r', encoding='utf-8') as fl:
    allowed_userids = fl.read().split()

pendingupdates_lastchecked = 0
pendingupdates_lastsent = 0


@app.route('/', methods=['GET', 'POST'])
def firewall():
    global pendingupdates_lastchecked, pendingupdates_lastsent
    if request.method == "GET":
        return 'I\'m working'
    r = request.get_json()
    with open(f'{path}data/quires.txt', 'a', encoding='utf-8') as f:
       f.write(str(r) + '\n')
    print(r)
    current_time = int(time.time())
    if current_time - pendingupdates_lastchecked > 60:
        pendingupdates_lastchecked = current_time
        response = requests.get(f'{tools.url}getWebhookInfo')
        if response.status_code == 200:
            pendingupdates_count = response.json().get("result", {}).get("pending_update_count", 0)
            if pendingupdates_count > 250:
                if current_time - pendingupdates_lastsent > 60 * 5:  # 3600 секунд = 1 час
                    tools.send_message(647372660, f'⭕Я заметил, что pending updates сейчас: <b>{pendingupdates_count}</b>\n{tools.url}getWebhookInfo')
                    pendingupdates_lastsent = current_time
    if 'edited_message' in r:
        r['message'] = r['edited_message']
        del r['edited_message']
    if 'callback_query' in r:
        if r['callback_query']['message']['chat']['id'] == tools.future_group_id:
            callback_data = str(r['callback_query']['data'])
            if str(r['callback_query']['from']['id']) == callback_data and tools.switch_entire_authorization:
                try:
                    tools.asked_usrids('remove', callback_data, '', None)
                    if callback_data not in allowed_userids:
                        allowed_userids.append(callback_data)
                        tools.unRestrictChatMember_msgSend(tools.future_group_id, callback_data)
                        with open(f'{path}data/allowed_userids.txt', 'w', encoding='utf-8') as f:
                            f.write(' '.join(allowed_userids))
                except ValueError:  # ????
                    pass
                tools.threading_delete_message(tools.future_group_id, r['callback_query']['message']['message_id'])
            requests.post(tools.url + f"answerCallbackQuery?callback_query_id={r['callback_query']['id']}")
    elif 'message' in r:
        chat_id = int(r['message']['chat']['id'])
        if chat_id == tools.future_group_id:
            group_handler(r)
        elif r['message']['chat']['type'] == 'private':
            dm_handler(r)
    return 'OK'


def group_handler(r):
    global allowed_userids
    if 'sender_chat' in r['message']:
        true_user_id = str(r['message']['sender_chat']['id'])
    else:
        true_user_id = None
    user_id = str(r['message']['from']['id'])
    first_name = r['message']['from']['first_name']
    if 'username' in r['message']['from']:
        username = '@' + r['message']['from']['username']
    else:
        username = first_name
    message_id = r['message']['message_id']
    chat_id = int(r['message']['chat']['id'])
    tools.append_history(user_id, r)
    if user_id not in allowed_userids and tools.switch_entire_authorization and not tools.switch_authorize_all:
        if not tools.asked_usrids('is', user_id, username, message_id):
            tools.asked_usrids('add', user_id, username, message_id)
        tools.threading_delete_message(chat_id, message_id)
        tools.append_log(f'удалено до авторизации пользователя: {r}')
        return
    elif tools.switch_authorize_all and tools.switch_entire_authorization:
        try:
            tools.asked_usrids('remove', user_id, '', None)
            if user_id not in allowed_userids:
                allowed_userids.append(user_id)
                with open(f'{path}data/allowed_userids.txt', 'w', encoding='utf-8') as f:
                    f.write(' '.join(allowed_userids))
        except ValueError:
            pass
    if 'reply_markup' in r['message']:
        msg = r['message']['reply_markup']['inline_keyboard'][0][0]['text']
        if tools.count_duplicate_messages(user_id, message=msg) > tools.max_duplicate_messages or tools.is_in_wordlist(msg)[0] and (user_id not in tools.ids and true_user_id not in tools.ids):
            tools.threading_delete_message(chat_id, message_id)
            tools.append_log(f'удалено сообщение по фильтру({tools.is_in_wordlist(msg)[1]})/количеству от {first_name}({user_id}): {msg}')
            return
    elif 'sticker' in r['message']:
        file_unique_id = r['message']['sticker']['thumbnail']['file_unique_id']
        if tools.count_duplicate_messages(user_id, file_unique_id=file_unique_id) > tools.max_duplicate_messages and (user_id not in tools.ids and true_user_id not in tools.ids):
            tools.threading_delete_message(chat_id, message_id)
            tools.append_log(f'удалено сообщение по количеству от {first_name}({user_id}): *sticker*')
            return
    elif 'text' in r['message']:
        msg = r['message']['text']
        if tools.count_duplicate_messages(user_id, message=msg) > tools.max_duplicate_messages or tools.is_in_wordlist(msg)[0] and (user_id not in tools.ids and true_user_id not in tools.ids):
            tools.threading_delete_message(chat_id, message_id)
            tools.append_log(f'удалено сообщение по фильтру({tools.is_in_wordlist(msg)[1]})/количеству от {first_name}({user_id}): {msg}')
            return
        else:
            if 'reply_to_message' in r['message'] and msg == '/notrust' and user_id in tools.ids:
                tools.threading_delete_message(chat_id, r['message']['message_id'])
                reply_to_message_id = r['message']['reply_to_message']['message_id']
                untrust_user_id = str(r['message']['reply_to_message']['from']['id'])
                if untrust_user_id in tools.ids:
                    tools.upload_video(chat_id, 'sad_joke.mp4', reply_to_message_id=reply_to_message_id)
                elif tools.switch_entire_authorization:
                    tools.restrictChatMember_msgSend(chat_id, untrust_user_id)
                    if 'username' in r['message']['reply_to_message']['from']:
                        username = '@' + r['message']['reply_to_message']['from']['username']
                    else:
                        username = r['message']['reply_to_message']['from']['first_name']
                    tools.append_log(f'/notrusted {untrust_user_id} ({username})')
                    tools.send_message(chat_id, f'done')
                    if not tools.asked_usrids('is', untrust_user_id, username, reply_to_message_id):
                        tools.asked_usrids('add', untrust_user_id, username, reply_to_message_id)
                    tools.threading_delete_message(chat_id, reply_to_message_id)
                    try:
                        if untrust_user_id in allowed_userids:
                            allowed_userids.remove(untrust_user_id)
                            with open(f'{path}data/allowed_userids.txt', 'w', encoding='utf-8') as f:
                                f.write(' '.join(allowed_userids))
                    except ValueError:
                        pass
    elif 'photo' in r['message'] or 'video' in r['message'] or 'document' in r['message'] or 'animation' in r['message']:
        if 'caption' in r['message']:
            msg = r['message']['caption']
        else:
            msg = 'документ'
        if tools.count_duplicate_messages(user_id, message=msg) > tools.max_duplicate_messages or tools.is_in_wordlist(msg)[0] and (user_id not in tools.ids and true_user_id not in tools.ids):
            tools.threading_delete_message(chat_id, message_id)
            tools.append_log(f'удалено сообщение по количеству от {first_name}({user_id}): {msg}')
            return


def waiting_user_handler(r):
    msg = r['message']['text']
    user_id = str(r['message']['from']['id'])
    reason = tools.ids[user_id]['waiting']['params']['reason']
    if msg == 'Отмена':
        tools.ids[user_id]['waiting']['is_waiting'] = False
        del tools.ids[user_id]['waiting']['params']
        with open(f'{path}names.json', 'w') as f:
            json.dump(tools.ids, f, indent=2)
        tools.send_message(user_id, 'Действие отменено', tools.keyboards(user_id))
        return
    match reason:
        case 'add word':
            msg = msg.lower()
            was_added = False
            for wrd in msg.split():
                if wrd not in tools.wordlist:
                    tools.wordlist.append(wrd)
                    was_added = True
                else:
                    tools.send_message(user_id, f'<i>{wrd}</i> уже в списке')
            if was_added:
                with open(f'{path}data/wordlist.txt', 'w', encoding='utf-8') as f:
                    f.write(' '.join(tools.wordlist))
                tools.send_message(user_id, f'Добавил, теперь он выглядит так:\n<pre>{" ".join(tools.wordlist)}</pre>', tools.keyboards(user_id))
            else:
                tools.send_message(user_id, 'Ничего не изменилось', tools.keyboards(user_id))
            tools.ids[user_id]['waiting']['is_waiting'] = False
            del tools.ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
        case 'del word':
            msg = msg.lower()
            was_deleted = False
            for wrd in msg.split():
                if wrd in tools.wordlist:
                    tools.wordlist.remove(wrd)
                    was_deleted = True
                else:
                    tools.send_message(user_id, f'<i>{wrd}</i> не был в списке')
            if was_deleted:
                with open(f'{path}data/wordlist.txt', 'w', encoding='utf-8') as f:
                    f.write(' '.join(tools.wordlist))
                tools.send_message(user_id, f'Удалил, теперь он выглядит так:\n<pre>{" ".join(tools.wordlist)}</pre>', tools.keyboards(user_id))
            else:
                tools.send_message(user_id, 'Ничего не изменилось', tools.keyboards(user_id))
            tools.ids[user_id]['waiting']['is_waiting'] = False
            del tools.ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
        case 'accept all':
            if msg == 'Да':
                tools.switch_authorize_all = not tools.switch_authorize_all
                tools.send_message(user_id, 'Готово', tools.keyboards(user_id))
            else:
                tools.send_message(user_id, 'Не понял', tools.keyboards(user_id))
            tools.ids[user_id]['waiting']['is_waiting'] = False
            del tools.ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
        case 'entire auth':
            if msg == 'Да':
                tools.switch_entire_authorization = not tools.switch_entire_authorization
                tools.send_message(user_id, 'Готово', tools.keyboards(user_id))
            else:
                tools.send_message(user_id, 'Не понял', tools.keyboards(user_id))
            tools.ids[user_id]['waiting']['is_waiting'] = False
            del tools.ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
        case 'change max dup mess':
            try:
                number = int(msg)
                tools.max_duplicate_messages = number
                tools.send_message(user_id, f'Теперь это <b>{number}</b>', tools.keyboards(user_id))
            except ValueError:  # если не число
                tools.send_message(user_id, 'Это должно быть число...', tools.keyboards(user_id))
            tools.ids[user_id]['waiting']['is_waiting'] = False
            del tools.ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
        case 'message deletion':
            if msg == 'Да':
                tools.switch_message_deletion = not tools.switch_message_deletion
                tools.send_message(user_id, 'Готово', tools.keyboards(user_id))
            else:
                tools.send_message(user_id, 'Не понял', tools.keyboards(user_id))
            tools.ids[user_id]['waiting']['is_waiting'] = False
            del tools.ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)


def dm_handler(r):
    user_id = str(r['message']['from']['id'])
    first_name = r['message']['from']['first_name']
    if 'text' not in r['message']:
        tools.send_message(user_id, 'Я понимаю только текст')
        return
    msg = r['message']['text']
    if user_id in tools.ids and tools.ids[user_id]['waiting']['is_waiting']:
        waiting_user_handler(r)
        return
    if user_id in tools.ids and user_id != "647372660":
        tools.append_dm_log(user_id, msg, first_name)
    match msg:
        case '/start':
            tools.send_message(user_id, 'Чего желаешь?', tools.keyboards(user_id))
        case 'Добавить запрещенное слово' if user_id in tools.ids:
            data = {'keyboard': [[{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            tools.send_message(user_id, f'Введите одно слово или несколько через пробел (например: <i>работа</i> или <i>работа зарплата лс</i>). Также можно ввести слова через &, тогда сообщение удалится, только если присутствуют оба слова. Текущий список слов:\n<pre>{" ".join(tools.wordlist)}</pre>', data)
            tools.ids[user_id]['waiting']['is_waiting'] = True
            tools.ids[user_id]['waiting']['params'] = {'reason': 'add word'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
        case 'Удалить запрещенное слово' if user_id in tools.ids:
            data = {'keyboard': [[{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            tools.send_message(user_id, f'Введите <b>одно</b> слово или <b>несколько через пробел</b> (например: <i>работа</i> или <i>работа зарплата лс</i>). Текущий список слов:\n<pre>{" ".join(tools.wordlist)}</pre>', data)
            tools.ids[user_id]['waiting']['is_waiting'] = True
            tools.ids[user_id]['waiting']['params'] = {'reason': 'del word'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
        case '/logs' if user_id in tools.ids:
            with open(f'{path}data/log.txt', 'r', encoding='utf-8') as f:
                log = []
                for line in f:
                    index = line.find('{')
                    if index != -1:
                        log.append(line[:index] + '\n')
                    else:
                        log.append(line)
                log = ''.join(log)
                if len(log) <= 4096:
                    send_body = {
                        'chat_id': user_id,
                        'text': log,
                        'reply_markup': tools.keyboards(user_id)
                    }
                else:
                    send_body = {
                        'chat_id': user_id,
                        'text': log[-4096:],
                        'reply_markup': tools.keyboards(user_id)
                    }
                requests.post(tools.url + 'sendMessage', json=send_body)
        case '/dm_logs' if user_id == "647372660":
            with open(f'{path}data/dm_log.txt', 'r', encoding='utf-8') as f:
                log = f.read()
                if len(log) <= 4096:
                    send_body = {
                        'chat_id': user_id,
                        'text': log,
                        'reply_markup': tools.keyboards(user_id)
                    }
                    requests.post(tools.url + 'sendMessage', json=send_body)
                else:
                    tools.upload_file(user_id, 'dm_log.txt')
        case 'админка' if user_id in tools.ids:
            data = {'keyboard': [[{'text': 'accept all авторизация'}, {'text': 'задать max_duplicate_messages'}],
                                 [{'text': 'вся авторизация (отправка, удаление)'}, {'text': 'любые удаления сообщений'}],
                                 [{'text': 'Главное меню'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            tools.send_message(user_id, 'Перехожу в админ панель', data)
        case 'accept all авторизация' if user_id in tools.ids:
            data = {'keyboard': [[{'text': 'Да'}],
                                 [{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            tools.ids[user_id]['waiting']['is_waiting'] = True
            tools.ids[user_id]['waiting']['params'] = {'reason': 'accept all'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
            tools.send_message(user_id, f'Текущее значение: <b>{tools.switch_authorize_all}</b>. Изменить на <b>{not tools.switch_authorize_all}</b>?', data)
        case 'вся авторизация (отправка, удаление)' if user_id in tools.ids:
            data = {'keyboard': [[{'text': 'Да'}],
                                 [{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            tools.ids[user_id]['waiting']['is_waiting'] = True
            tools.ids[user_id]['waiting']['params'] = {'reason': 'entire auth'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
            tools.send_message(user_id, f'Текущее значение: <b>{tools.switch_entire_authorization}</b>. Изменить на <b>{not tools.switch_entire_authorization}</b>?', data)
        case 'задать max_duplicate_messages' if user_id in tools.ids:
            data = {'keyboard': [[{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            tools.ids[user_id]['waiting']['is_waiting'] = True
            tools.ids[user_id]['waiting']['params'] = {'reason': 'change max dup mess'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
            tools.send_message(user_id, f'Текущее значение: <b>{tools.max_duplicate_messages}</b>. На что изменить?', data)
        case 'любые удаления сообщений' if user_id in tools.ids:
            data = {'keyboard': [[{'text': 'Да'}],
                                 [{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            tools.ids[user_id]['waiting']['is_waiting'] = True
            tools.ids[user_id]['waiting']['params'] = {'reason': 'message deletion'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(tools.ids, f, indent=2)
            tools.send_message(user_id, f'Текущее значение: <b>{tools.switch_message_deletion}</b>. Изменить на <b>{not tools.switch_message_deletion}</b>?', data)
        case 'Главное меню':
            tools.send_message(user_id, 'Возврат в главное меню', tools.keyboards(user_id))
        case _:
            tools.send_message(user_id, 'Неизвестная команда', tools.keyboards(user_id))


if __name__ == '__main__':
    if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
        serve(app, host='0.0.0.0', port=8881, url_scheme='http')
    else:
        app.run(host='192.168.1.10', port=8885)
        # app.run(host='192.168.1.21', port=8881)
