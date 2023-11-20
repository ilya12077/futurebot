from flask import Flask, request
from waitress import serve

from tools import *

global ids, wordlist
app = Flask(__name__)
future_group_id = int(os.environ.get('FUTURE_GROUP_ID'))
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    path = '/etc/futurebot/'
else:
    path = ''

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
            callback_data = str(r['callback_query']['data'])
            if str(r['callback_query']['from']['id']) == callback_data:
                try:
                    captcha_denied.remove(callback_data)
                    with open(f'{path}data/captcha_denied.txt', 'w', encoding='utf-8') as f:
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

    if 'reply_markup' in r['message']:
        msg = r['message']['reply_markup']['inline_keyboard'][0][0]['text']
        if count_duplicate_messages(user_id, message=msg) > max_duplicate_messages or is_in_wordlist(msg) and user_id not in ids:
            delete_message(chat_id, message_id)
            append_log(f'удалено сообщение от {first_name}({user_id}): {msg}')
            return
    elif 'sticker' in r['message']:
        file_unique_id = r['message']['sticker']['thumbnail']['file_unique_id']
        if count_duplicate_messages(user_id, file_unique_id=file_unique_id) > max_duplicate_messages and user_id not in ids:
            delete_message(chat_id, message_id)
            append_log(f'удалено сообщение от {first_name}({user_id}): *sticker*')
            return
    elif 'left_chat_participant' in r['message']:
        try:
            captcha_denied.remove(str(r['message']['left_chat_participant']['id']))
            with open(f'{path}data/captcha_denied.txt', 'w', encoding='utf-8') as f:
                f.write(' '.join(captcha_denied))
        except ValueError:
            pass
    elif 'new_chat_participant' in r['message']:
        if 'username' in r['message']['from']:
            username = '@' + r['message']['from']['username']
        else:
            username = first_name
        untrust_user_id = str(r['message']['new_chat_participant']['id'])
        send_message(chat_id, f'{username}, добро пожаловать в чатик! Нажимайте кнопку ниже, только если вы человек. Иначе вы не сможете писать в чат', {'inline_keyboard': [[{'text': 'Подтверждаю', 'callback_data': untrust_user_id}]]})
        if untrust_user_id not in captcha_denied:
            captcha_denied.append(untrust_user_id)
            with open(f'{path}data/captcha_denied.txt', 'w', encoding='utf-8') as f:
                f.write(' '.join(captcha_denied))
    elif 'text' in r['message']:
        msg = r['message']['text']
        if count_duplicate_messages(user_id, message=msg) > max_duplicate_messages or is_in_wordlist(msg) and user_id not in ids:
            delete_message(chat_id, message_id)
            append_log(f'удалено сообщение от {first_name}({user_id}): {msg}')
            return
        else:
            if 'reply_to_message' in r['message'] and msg == '/untrust':  # and user_id in ids:
                reply_to_message_id = r['message']['reply_to_message']['message_id']
                untrust_user_id = str(r['message']['reply_to_message']['from']['id'])
                if untrust_user_id in ids:
                    upload_video(chat_id, 'sad_joke.mp4', reply_to_message_id=reply_to_message_id)
                else:
                    delete_message(chat_id, reply_to_message_id)
                    if 'username' in r['message']['reply_to_message']['from']:
                        username = '@' + r['message']['reply_to_message']['from']['username']
                    else:
                        username = r['message']['reply_to_message']['from']['first_name']
                    send_message(chat_id, f'{username}, добро пожаловать в чатик! Нажимайте кнопку ниже, только если вы человек. Иначе вы не сможете писать в чат', {'inline_keyboard': [[{'text': 'Подтверждаю', 'callback_data': untrust_user_id}]]})
                    if untrust_user_id not in captcha_denied:
                        captcha_denied.append(untrust_user_id)
                        with open(f'{path}data/captcha_denied.txt', 'w', encoding='utf-8') as f:
                            f.write(' '.join(captcha_denied))
    elif 'photo' in r['message'] or 'video' in r['message'] or 'document' in r['message'] or 'animation' in r['message']:
        if 'caption' in r['message']:
            msg = r['message']['caption']
        else:
            msg = 'document or smt'
        if count_duplicate_messages(user_id, message=msg) > max_duplicate_messages or is_in_wordlist(msg) and user_id not in ids:
            delete_message(chat_id, message_id)
            append_log(f'удалено сообщение от {first_name}({user_id}): {msg}')
            return


def waiting_user_handler(r):
    msg = r['message']['text']
    user_id = str(r['message']['from']['id'])
    reason = ids[user_id]['waiting']['params']['reason']
    if msg == 'Отмена':
        ids[user_id]['waiting']['is_waiting'] = False
        del ids[user_id]['waiting']['params']
        with open(f'{path}names.json', 'w') as f:
            json.dump(ids, f, indent=2)
        send_message(user_id, 'Действие отменено', keyboards(user_id))
        return
    match reason:
        case 'add word':
            msg = msg.lower()
            was_added = False
            for wrd in msg.split():
                if wrd not in wordlist:
                    wordlist.append(wrd)
                    was_added = True
                else:
                    send_message(user_id, f'<i>{wrd}</i> уже в списке')
            if was_added:
                with open(f'{path}wordlist.txt', 'w', encoding='utf-8') as f:
                    f.write(' '.join(wordlist))
                send_message(user_id, f'Добавил, теперь он выглядит так:\n<pre>{" ".join(wordlist)}</pre>', keyboards(user_id))
            else:
                send_message(user_id, 'Ничего не изменилось', keyboards(user_id))
            ids[user_id]['waiting']['is_waiting'] = False
            del ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(ids, f, indent=2)
        case 'del word':
            msg = msg.lower()
            was_deleted = False
            for wrd in msg.split():
                if wrd in wordlist:
                    wordlist.remove(wrd)
                    was_deleted = True
                else:
                    send_message(user_id, f'<i>{wrd}</i> не был в списке')
            if was_deleted:
                with open(f'{path}wordlist.txt', 'w', encoding='utf-8') as f:
                    f.write(' '.join(wordlist))
                send_message(user_id, f'Удалил, теперь он выглядит так:\n<pre>{" ".join(wordlist)}</pre>', keyboards(user_id))
            else:
                send_message(user_id, 'Ничего не изменилось', keyboards(user_id))
            ids[user_id]['waiting']['is_waiting'] = False
            del ids[user_id]['waiting']['params']
            with open(f'{path}names.json', 'w') as f:
                json.dump(ids, f, indent=2)


def dm_handler(r):
    user_id = str(r['message']['from']['id'])
    first_name = r['message']['from']['first_name']
    if 'text' not in r['message']:
        send_message(user_id, 'Я понимаю только текст')
        return
    msg = r['message']['text']
    if user_id in ids and ids[user_id]['waiting']['is_waiting']:
        waiting_user_handler(r)
        return
    if user_id in ids and user_id != "647372660":
        append_dm_log(user_id, msg, first_name)
    match msg:
        case '/start':
            send_message(user_id, 'Чего желаешь?', keyboards(user_id))
        case 'Добавить запрещенное слово' if user_id in ids:
            data = {'keyboard': [[{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            send_message(user_id, f'Введите одно слово или несколько через пробел (например: <i>работа</i> или <i>работа зарплата лс</i>). Также можно ввести слова через &, тогда сообщение удалится, только если присутствуют оба слова. Текущий список слов:\n<pre>{" ".join(wordlist)}</pre>', data)
            ids[user_id]['waiting']['is_waiting'] = True
            ids[user_id]['waiting']['params'] = {'reason': 'add word'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(ids, f, indent=2)
        case 'Удалить запрещенное слово' if user_id in ids:
            data = {'keyboard': [[{'text': 'Отмена'}]],
                    'one_time_keyboard': True,
                    'resize_keyboard': True}
            send_message(user_id, f'Введите <b>одно</b> слово или <b>несколько через пробел</b> (например: <i>работа</i> или <i>работа зарплата лс</i>). Текущий список слов:\n<pre>{" ".join(wordlist)}</pre>', data)
            ids[user_id]['waiting']['is_waiting'] = True
            ids[user_id]['waiting']['params'] = {'reason': 'del word'}
            with open(f'{path}names.json', 'w') as f:
                json.dump(ids, f, indent=2)
        case '/logs' if user_id in ids:
            with open(f'{path}data/log.txt', 'r', encoding='cp1251') as f:
                log = f.read()
                if len(log) <= 4096:
                    send_body = {
                        'chat_id': user_id,
                        'text': log,
                        'reply_markup': keyboards(user_id)
                    }
                else:
                    send_body = {
                        'chat_id': user_id,
                        'text': log[-4096:],
                        'reply_markup': keyboards(user_id)
                    }
                requests.post(url + 'sendMessage', json=send_body)
        case '/dm_logs' if user_id == "647372660":
            with open(f'{path}data/dm_log.txt', 'r', encoding='cp1251') as f:
                log = f.read()
                if len(log) <= 4096:
                    send_body = {
                        'chat_id': user_id,
                        'text': log,
                        'reply_markup': keyboards(user_id)
                    }
                    requests.post(url + 'sendMessage', json=send_body)
                else:
                    upload_file(user_id, 'dm_log.txt')
        case _:
            send_message(user_id, 'Неизвестная команда', keyboards(user_id))


if __name__ == '__main__':
    if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
        serve(app, host='0.0.0.0', port=8881, url_scheme='http')
    else:
        app.run(host='192.168.1.10', port=8881)
        # app.run(host='192.168.1.21', port=8881)


