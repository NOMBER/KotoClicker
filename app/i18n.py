"""Simple translations: a "key -> text" dictionary for Russian and English.

tr("key", **fields) returns the string in the current language.
The language is switched on the fly with set_language("ru" | "en").
"""

from __future__ import annotations

LANGUAGES = ("ru", "en")
_lang = "ru"

STRINGS = {
    "ru": {
        # window and header
        "window_title": "Котоклик — ленивый автокликер",
        "app_title": "Котоклик",
        "app_subtitle": "Ленивый котик кликает за тебя",
        "tab_simple": "Автоклик",
        "tab_macro": "Мышкины макросы",
        "badge": "офлайн · без интернета",
        "badge_tip": "Программа не выходит в интернет, не ставит автозапуск и ничего не отправляет. "
                     "Настройки и макросы хранятся только на твоём компьютере.",
        "lang_tip": "Язык интерфейса",
        # cat statuses
        "st_idle": "Котик дремлет…",
        "st_idle_lore": "Наведи курсор и нажми {click} — он лениво потянется к кнопке.",
        "st_idle_lore_macro": "{record} — мышка записывает, {play} — котик повторяет.",
        "st_countdown": "Котик потягивается… {n}",
        "st_countdown_lore": "Убери курсор туда, где нужно кликать.",
        "st_clicking": "Котик кликает за тебя!",
        "st_clicking_lore": "Можешь пить чай. Стоп — {click}{or_stop}.",
        "st_recording": "Мышка записывает…",
        "st_recording_lore": "Делай что нужно — мышка всё занесёт в блокнот. Стоп — {record}.",
        "st_playing": "Котик повторяет за мышкой",
        "st_playing_lore": "Читает мышкины записи. Стоп — {play}{or_stop}.",
        "counter": "Кликов: {n} · всего: {total}",
        "paw_start": "Старт",
        "paw_stop": "Стоп",
        "hint_simple": "{click} — старт / стоп{stop_part}",
        "hint_macro": "{record} — запись · {play} — повтор{stop_part}",
        # pieces for inserting the configured keys (empty if the second stop key is disabled)
        "or_stop": " или {key}",
        "or_stop_paren": " (или {key})",
        "stop_part": " · {key} — стоп",
        # simple mode
        "hotkey_title": "Горячая клавиша",
        "hotkey_hint": "Вкл / выкл клики, даже из свёрнутого окна",
        "hotkey_change": "Нажми на клавишу, чтобы сменить",
        "interval_title": "Интервал",
        "interval_hint": "Пауза между кликами · {rate}",
        "rate_per_sec": "≈ {n} {word}/сек",
        "rate_per_min": "≈ {n} в минуту",
        "unit_ms": "мс",
        "unit_s": "сек",
        "suffix_ms": " мс",
        "suffix_s": " с",
        "button_title": "Кнопка мыши",
        "button_hint": "Какой лапкой нажимать",
        "btn_left": "Левая",
        "btn_right": "Правая",
        "btn_middle": "Средняя",
        "type_title": "Тип клика",
        "type_hint": "Один тык или сразу два",
        "type_single": "Одинарный",
        "type_double": "Двойной",
        "repeat_title": "Сколько кликать",
        "repeat_hint": "Бесконечно, пока не остановишь, или точное число раз",
        "repeat_forever": "Пока не остановлю",
        "repeat_count": "Заданное число раз",
        "times": "раз",
        "tip": "<b>Совет котика.</b> Наведи курсор, куда нужно кликать, и нажми горячую клавишу — "
               "котик будет жать прямо там, где мышка. Ещё раз{or_stop_paren} — и он снова уснёт. "
               "Если запускаешь большой лапкой слева, у тебя будет 3 секунды, чтобы увести курсор.",
        # macros
        "macro_title": "Мышкины записи",
        "mouse_says": "«Запишу клики, зажатия, перетаскивание и колёсико — котик всё повторит!» "
                      "Новая запись заменяет шаги текущего макроса, всё сохраняется само.",
        "rec_label": "Запись",
        "play_label": "Повтор",
        "rec_moves": "Запись движений",
        "rec_moves_tip": "Мышка запишет и путь курсора, а не только клики. "
                         "Путь при перетаскивании (кнопка зажата) пишется всегда",
        "rec_keys": "Записывать клавиши",
        "rec_keys_tip": "Мышка запишет и нажатия клавиш (только пока идёт запись, хранится только у тебя). "
                        "Горячие клавиши Котоклика ({keys}) не записываются.",
        "rec_start": "●  Записать ({key})",
        "rec_stop": "■  Стоп ({key})",
        "new": "+ Новый",
        "col_n": "№",
        "col_action": "Действие",
        "col_delay": "Пауза перед, мс",
        "table_tip": "Двойной клик по X, Y или паузе — изменить число. По «Действию» — открыть шаг целиком.",
        "add_click": "+ Клик",
        "add_wait": "+ Пауза",
        "delete": "Удалить",
        "up_tip": "Поднять шаг",
        "down_tip": "Опустить шаг",
        "clear": "Очистить",
        "stats": "{clicks} {clicks_w} · {keys} {keys_w} · {steps} {steps_w} · ≈ {secs} с",
        "macro_repeat_title": "Повтор макроса",
        "loop": "По кругу",
        "default_macro": "Макрос 1",
        "new_macro": "Новый макрос",
        # footer
        "panic_title": "Стоп-кран:",
        "panic_hint": "или {key} — останавливает всё и сразу",
        "panic_hint_alone": "— останавливает всё и сразу",
        "on_top": "Поверх всех окон",
        "keycap_tip": "Нажми, затем нужную клавишу (Esc или ещё один клик — отмена)",
        "keycap_tip_stop": "Нажми, затем нужную клавишу (ещё один клик — отмена)",
        "press_key": "Нажми клавишу…",
        # steps
        "step_click": "Клик {button}",
        "step_dclick": "Двойной клик {button}",
        "step_move": "Движение",
        "step_wait": "Пауза",
        "step_key_press": "Нажать {key}",
        "step_key_release": "Отпустить {key}",
        "bn_left": "левой",
        "bn_right": "правой",
        "bn_middle": "средней",
        "step_mouse_down": "Зажать {button} кнопку",
        "step_mouse_up": "Отпустить {button} кнопку",
        "bn_acc_left": "левую",
        "bn_acc_right": "правую",
        "bn_acc_middle": "среднюю",
        "step_scroll": "Прокрутка {dirs}",
        "step_scroll_none": "Прокрутка (0)",
        "dir_up": "вверх ×{n}",
        "dir_down": "вниз ×{n}",
        "dir_left": "влево ×{n}",
        "dir_right": "вправо ×{n}",
        # step dialog
        "dlg_title": "Шаг макроса",
        "dlg_head": "Что записать в блокнот?",
        "dlg_click": "Клик",
        "dlg_move": "Движение",
        "dlg_wait": "Пауза",
        "dlg_down": "Зажать",
        "dlg_up": "Отпустить",
        "dlg_scroll": "Колёсико",
        "dlg_wheel": "Колёсико ↔ / ↕",
        "dlg_wheel_tip": "Сколько щелчков колёсика: ↔ вправо (+) или влево (−), ↕ вверх (+) или вниз (−)",
        "dlg_button": "Кнопка",
        "dlg_double": "Двойной клик",
        "dlg_xy": "Координаты X / Y",
        "dlg_delay": "Пауза перед шагом",
        "dlg_pick": "Взять позицию курсора через 3 с",
        "dlg_pick_tip": "Нажми, наведи мышь на нужное место и подожди",
        "dlg_pick_wait": "Наведи мышь… {n}",
        "dlg_pick_done": "Запомнила: {x}, {y} — ещё раз?",
        "dlg_pick_fail": "Не получилось узнать позицию",
        "cancel": "Отмена",
        "ok": "Готово",
        "yes": "Да",
        "no": "Нет",
        # messages
        "msg_stop_first": "Сначала останови котика — потом меняй клавиши.",
        "msg_key_busy": "Клавиша {key} уже занята другой командой.",
        "msg_key_set": "Готово! Теперь это {key}.",
        "msg_recorded": "Мышка записала {n} {word} в «{name}».",
        "msg_empty": "Блокнот пуст: сначала запиши макрос ({key}).",
        "msg_select_rows": "Выбери шаги в таблице, которые нужно удалить.",
        "msg_key_step_edit": "У нажатия клавиши можно менять только паузу.",
        "ask_clear": "Стереть все шаги из блокнота мышки?",
        "dlg_open": "Открыть макрос",
        "dlg_save": "Сохранить макрос",
        "file_filter": "Макрос Котоклика (*.json)",
        "msg_opened": "Мышка открыла блокнот «{name}».",
        "msg_open_fail": "Не получилось открыть файл:\n{err}",
        "msg_saved": "Сохранено! Мышка спрятала блокнот в норку.",
        "msg_save_fail": "Не получилось сохранить:\n{err}",
        "msg_settings_fail": "Не удалось сохранить настройки: {err}",
        "err_hotkeys": "Горячие клавиши недоступны: {err}",
        "err_mouse": "Не удалось подключиться к мыши: {err}",
        "err_keyboard": "Не удалось подключиться к клавиатуре: {err}",
        "err_click": "Ошибка клика: {err}",
        "err_play": "Ошибка воспроизведения: {err}",
        "err_record": "Запись недоступна: {err}",
        # cat reactions
        "st_lively": "Котик вошёл во вкус!",
        "st_lively_lore": "Шапка подпрыгивает на каждый клик. Стоп — {stop_any}.",
        "st_hyper": "Лапки так и мелькают!",
        "st_hyper_lore": "Ещё чуть быстрее и подольше — и начнётся дискотека… Стоп — {stop_any}.",
        "st_disco": "ДИСКОТЕКА!",
        "st_disco_lore": "Вайбовая дискотека: котик танцует под свои клики. Стоп — {stop_any}.",
        "st_countdown_rec": "Мышка готовится… {n}",
        "st_countdown_rec_lore": "Запись начнётся после «мяу». Отмена — {record}{or_stop}.",
        # macro library
        "tab_settings": "Настройки",
        "lib_tip": "Мышкины блокноты: каждый макрос — отдельный файл в папке macros рядом с программой",
        "more": "Ещё ▾",
        "m_rename": "Переименовать…",
        "m_duplicate": "Дублировать",
        "m_delete": "Удалить…",
        "m_import": "Импорт из файла…",
        "m_export": "Экспорт в файл…",
        "m_folder": "Открыть папку с макросами",
        "ask_rename": "Новое название макроса:",
        "ask_delete": "Удалить макрос «{name}»? Файл удалится насовсем.",
        "copy_name": "{name} (копия)",
        "msg_created": "Новый блокнот «{name}» готов — жми запись.",
        "msg_renamed": "Теперь макрос называется «{name}».",
        "msg_duplicated": "Мышка переписала блокнот: «{name}».",
        "msg_deleted": "Макрос «{name}» удалён.",
        "msg_lib_fail": "Не получилось: {err}",
        # settings
        "set_cat_title": "Котик",
        "set_cat_hint": "Реакции на частоту кликов. Не нравится — просто выключи.",
        "anim_master": "Анимации котика",
        "anim_hat": "Шапка на клик",
        "anim_hat_tip": "Гарнитура на голове котика подпрыгивает на каждый клик",
        "anim_disco": "Дискотека",
        "anim_disco_tip": "Если кликать очень быстро (от 15 кликов в секунду) дольше 5 секунд — начнётся дискотека",
        "anim_chatty": "Болтливый котик",
        "anim_chatty_hint": "Иногда говорит милые фразы в облачке — тихо и не чаще раза в минуту.",
        "anim_chatty_tip": "Котик иногда говорит милые фразы в облачке — тихо и не чаще раза в минуту. "
                           "Выключи — будут только обычные подсказки",
        "anim_master_tip": "Выключи — котик и всё вокруг замрут: только картинка «спит / не спит», без движения",
        "set_sound_title": "Звуки",
        "set_sound_hint": "Свои — WAV, MP3, OGG, M4A; котик предложит обрезать",
        "set_sound_hint_wav": "Свои звуки — файлы WAV (для MP3 нужен пакет PySide6-Addons)",
        "volume": "Громкость",
        "snd_countdown": "Пик-пик отсчёта",
        "snd_record_start": "Мяу — запись пошла",
        "snd_record_stop": "Конец записи",
        "snd_play_start": "Старт макроса",
        "snd_tick": "Тихие тики при записи",
        "snd_default": "стандартный",
        "snd_missing": "нет файла: {name}",
        "snd_custom": "Свой звук…",
        "snd_reset": "Сброс",
        "snd_preview_tip": "Послушать",
        "dlg_sound": "Выбери свой звук",
        "sound_filter": "Звуки (*.wav *.mp3 *.ogg *.oga *.m4a *.aac *.flac);;Все файлы (*)",
        "sound_filter_wav": "Звук WAV (*.wav);;Все файлы (*)",
        "msg_bad_format": "Котик такой звук не понимает: «{name}». Подойдёт WAV, MP3, OGG или M4A.",
        "msg_bad_wav": "Котик такой звук не понимает: «{name}». Нужен файл WAV.",
        "msg_no_media": "MP3 тут не играет (нет QtMultimedia) — котик взял стандартный звук.",
        "msg_bad_sound": "Не получилось сыграть «{name}» — котик взял стандартный звук.",
        "snd_broken": "не играет: {name}",
        "msg_no_audio": "Звук недоступен на этой системе.",
        "cd_record": "Отсчёт {n} с перед записью",
        "cd_record_tip": "Пик-пик-пик — и «мяу»: запись началась",
        "cd_play": "Отсчёт {n} с перед макросом по клавише",
        "cd_play_tip": "С большой лапки слева отсчёт есть всегда",
        # hotkeys (settings)
        "set_keys_title": "Горячие клавиши",
        "set_keys_hint": "Нажми на клавишу и выбери новую",
        "hk_click": "Автоклик",
        "hk_record": "Запись",
        "hk_play": "Повтор",
        "hk_panic": "Стоп-кран",
        "hk_stop": "Ещё стоп",
        "hk_stop_tip": "Вторая клавиша «стоп» (обычно Esc). Убери её крестиком — тогда Esc можно записывать в макрос",
        "hk_clear_tip": "Убрать вторую стоп-клавишу",
        "hk_none": "нет",
        "hk_reset": "Сбросить по умолчанию",
        "msg_keys_reset": "Котик вернул стандартные клавиши: F6, F7, F8, F9 и Esc.",
        "msg_stop_cleared": "Вторая стоп-клавиша убрана — теперь её можно записывать в макрос.",
        # sound trimming
        "trim_title": "Обрезать звук",
        "trim_for": "Для события «{event}»",
        "trim_total": "Длина файла: {secs} с",
        "trim_start": "Начало, с",
        "trim_end": "Конец, с",
        "trim_sel": "Выбрано: {secs} с",
        "trim_max": "Котик сыграет не больше {max} с — лишнее отрежется само.",
        "trim_play": "▶  Послушать",
        "trim_stop": "■  Стоп",
        "trim_save": "Сохранить",
        "trim_nocut": "Без обрезки",
        "trim_cancel": "Отмена",
        "trim_save_tip": "Сохранить кусочек как WAV в папку sounds_custom — исходный файл больше не понадобится",
        "trim_nocut_tip": "Взять файл целиком, как есть (играет с начала)",
        "trim_fail": "Не получилось прочитать звук для обрезки: {err}",
        "msg_trimmed": "Котик сохранил кусочек звука: «{name}».",
        "msg_trim_fail": "Не получилось обрезать ({err}) — котик взял файл как есть.",
        # bubble
        "promo": 'А у меня есть <a href="{url}">ТГ бот</a> для скачивания видео!',
        # keys
        "k_space": "Пробел",
        "k_right_suffix": " (пр.)",
    },
    "en": {
        "window_title": "KotoClick — the lazy auto-clicker",
        "app_title": "KotoClick",
        "app_subtitle": "A lazy cat clicks for you",
        "tab_simple": "Auto-click",
        "tab_macro": "Mouse's macros",
        "badge": "offline · no internet",
        "badge_tip": "The app never goes online, never adds itself to startup and sends nothing anywhere. "
                     "Settings and macros stay on your computer only.",
        "lang_tip": "Interface language",
        "st_idle": "The cat is napping…",
        "st_idle_lore": "Point the cursor and press {click} — he'll lazily reach for the button.",
        "st_idle_lore_macro": "{record} — the mouse takes notes, {play} — the cat repeats.",
        "st_countdown": "The cat is stretching… {n}",
        "st_countdown_lore": "Move the cursor to where the clicks should go.",
        "st_clicking": "The cat clicks for you!",
        "st_clicking_lore": "Go have some tea. Stop — {click}{or_stop}.",
        "st_recording": "The mouse is taking notes…",
        "st_recording_lore": "Do your thing — the mouse writes it all down. Stop — {record}.",
        "st_playing": "The cat repeats the notes",
        "st_playing_lore": "Following the mouse's notes. Stop — {play}{or_stop}.",
        "counter": "Clicks: {n} · total: {total}",
        "paw_start": "Start",
        "paw_stop": "Stop",
        "hint_simple": "{click} — start / stop{stop_part}",
        "hint_macro": "{record} — record · {play} — replay{stop_part}",
        "or_stop": " or {key}",
        "or_stop_paren": " (or {key})",
        "stop_part": " · {key} — stop",
        "hotkey_title": "Hotkey",
        "hotkey_hint": "Toggles clicking, even when minimized",
        "hotkey_change": "Click the key to change it",
        "interval_title": "Interval",
        "interval_hint": "Pause between clicks · {rate}",
        "rate_per_sec": "≈ {n} {word}/sec",
        "rate_per_min": "≈ {n} per minute",
        "unit_ms": "ms",
        "unit_s": "sec",
        "suffix_ms": " ms",
        "suffix_s": " s",
        "button_title": "Mouse button",
        "button_hint": "Which paw to press with",
        "btn_left": "Left",
        "btn_right": "Right",
        "btn_middle": "Middle",
        "type_title": "Click type",
        "type_hint": "One tap or two at once",
        "type_single": "Single",
        "type_double": "Double",
        "repeat_title": "How many clicks",
        "repeat_hint": "Forever, until you stop it, or an exact number",
        "repeat_forever": "Until I stop",
        "repeat_count": "Exact number",
        "times": "times",
        "tip": "<b>Cat's tip.</b> Point the cursor where clicks are needed and press the hotkey — "
               "the cat will click right where the mouse is. Press again{or_stop_paren} and he dozes off. "
               "If you start with the big paw on the left, you get 3 seconds to move the cursor away.",
        "macro_title": "Mouse's notebook",
        "mouse_says": "“I'll note every click, hold, drag and wheel turn — the cat repeats it all!” "
                      "A new recording replaces the current macro's steps; everything saves itself.",
        "rec_label": "Record",
        "play_label": "Replay",
        "rec_moves": "Record moves",
        "rec_moves_tip": "The mouse will also record the cursor path, not just clicks. "
                         "The path of a drag (button held) is always recorded",
        "rec_keys": "Record keystrokes",
        "rec_keys_tip": "The mouse will also record key presses (only while recording, stored only on your PC). "
                        "KotoClick hotkeys ({keys}) are never recorded.",
        "rec_start": "●  Record ({key})",
        "rec_stop": "■  Stop ({key})",
        "new": "+ New",
        "col_n": "#",
        "col_action": "Action",
        "col_delay": "Delay before, ms",
        "table_tip": "Double-click X, Y or delay to change the number. Double-click “Action” to edit the whole step.",
        "add_click": "+ Click",
        "add_wait": "+ Pause",
        "delete": "Delete",
        "up_tip": "Move step up",
        "down_tip": "Move step down",
        "clear": "Clear",
        "stats": "{clicks} {clicks_w} · {keys} {keys_w} · {steps} {steps_w} · ≈ {secs} s",
        "macro_repeat_title": "Macro repeat",
        "loop": "Loop forever",
        "default_macro": "Macro 1",
        "new_macro": "New macro",
        "panic_title": "Emergency stop:",
        "panic_hint": "or {key} — stops everything at once",
        "panic_hint_alone": "— stops everything at once",
        "on_top": "Always on top",
        "keycap_tip": "Click, then press the key you want (Esc or another click cancels)",
        "keycap_tip_stop": "Click, then press the key you want (another click cancels)",
        "press_key": "Press a key…",
        "step_click": "{button} click",
        "step_dclick": "{button} double click",
        "step_move": "Move",
        "step_wait": "Pause",
        "step_key_press": "Press {key}",
        "step_key_release": "Release {key}",
        "bn_left": "Left",
        "bn_right": "Right",
        "bn_middle": "Middle",
        "step_mouse_down": "Hold {button} button",
        "step_mouse_up": "Release {button} button",
        "bn_acc_left": "left",
        "bn_acc_right": "right",
        "bn_acc_middle": "middle",
        "step_scroll": "Scroll {dirs}",
        "step_scroll_none": "Scroll (0)",
        "dir_up": "up ×{n}",
        "dir_down": "down ×{n}",
        "dir_left": "left ×{n}",
        "dir_right": "right ×{n}",
        "dlg_title": "Macro step",
        "dlg_head": "What goes into the notebook?",
        "dlg_click": "Click",
        "dlg_move": "Move",
        "dlg_wait": "Pause",
        "dlg_down": "Hold",
        "dlg_up": "Release",
        "dlg_scroll": "Wheel",
        "dlg_wheel": "Wheel ↔ / ↕",
        "dlg_wheel_tip": "Wheel notches: ↔ right (+) or left (−), ↕ up (+) or down (−)",
        "dlg_button": "Button",
        "dlg_double": "Double click",
        "dlg_xy": "Position X / Y",
        "dlg_delay": "Delay before step",
        "dlg_pick": "Grab cursor position in 3 s",
        "dlg_pick_tip": "Click, move the mouse to the spot and wait",
        "dlg_pick_wait": "Move the mouse… {n}",
        "dlg_pick_done": "Got it: {x}, {y} — again?",
        "dlg_pick_fail": "Couldn't read the cursor position",
        "cancel": "Cancel",
        "ok": "Done",
        "yes": "Yes",
        "no": "No",
        "msg_stop_first": "Stop the cat first — then change the keys.",
        "msg_key_busy": "The {key} key is already used by another command.",
        "msg_key_set": "Done! Now it's {key}.",
        "msg_recorded": "The mouse wrote {n} {word} into “{name}”.",
        "msg_empty": "The notebook is empty: record a macro first ({key}).",
        "msg_select_rows": "Select the steps you want to delete in the table.",
        "msg_key_step_edit": "For a key step only the delay can be changed.",
        "ask_clear": "Erase all steps from the mouse's notebook?",
        "dlg_open": "Open macro",
        "dlg_save": "Save macro",
        "file_filter": "KotoClick macro (*.json)",
        "msg_opened": "The mouse opened the notebook “{name}”.",
        "msg_open_fail": "Couldn't open the file:\n{err}",
        "msg_saved": "Saved! The mouse hid the notebook in her burrow.",
        "msg_save_fail": "Couldn't save:\n{err}",
        "msg_settings_fail": "Couldn't save settings: {err}",
        "err_hotkeys": "Hotkeys are unavailable: {err}",
        "err_mouse": "Couldn't access the mouse: {err}",
        "err_keyboard": "Couldn't access the keyboard: {err}",
        "err_click": "Click error: {err}",
        "err_play": "Playback error: {err}",
        "err_record": "Recording is unavailable: {err}",
        # cat reactions
        "st_lively": "The cat is getting into it!",
        "st_lively_lore": "The headset bounces on every click. Stop — {stop_any}.",
        "st_hyper": "Paws are a blur!",
        "st_hyper_lore": "A bit faster for a bit longer and the disco starts… Stop — {stop_any}.",
        "st_disco": "DISCO TIME!",
        "st_disco_lore": "Vibe disco: the cat dances to its own clicks. Stop — {stop_any}.",
        "st_countdown_rec": "The mouse gets ready… {n}",
        "st_countdown_rec_lore": "Recording starts after the meow. Cancel — {record}{or_stop}.",
        # macro library
        "tab_settings": "Settings",
        "lib_tip": "The mouse's notebooks: each macro is a separate file in the macros folder next to the app",
        "more": "More ▾",
        "m_rename": "Rename…",
        "m_duplicate": "Duplicate",
        "m_delete": "Delete…",
        "m_import": "Import from file…",
        "m_export": "Export to file…",
        "m_folder": "Open the macros folder",
        "ask_rename": "New macro name:",
        "ask_delete": "Delete the macro “{name}”? The file will be gone for good.",
        "copy_name": "{name} (copy)",
        "msg_created": "New notebook “{name}” is ready — hit record.",
        "msg_renamed": "The macro is now called “{name}”.",
        "msg_duplicated": "The mouse copied the notebook: “{name}”.",
        "msg_deleted": "Macro “{name}” deleted.",
        "msg_lib_fail": "That didn't work: {err}",
        # settings
        "set_cat_title": "The cat",
        "set_cat_hint": "Reactions to the click rate. Don't like them? Just switch them off.",
        "anim_master": "Cat animations",
        "anim_hat": "Headset bounce",
        "anim_hat_tip": "The headset on the cat's head bounces on every click",
        "anim_disco": "Disco",
        "anim_disco_tip": "Click very fast (15+ clicks per second) for more than 5 seconds and the disco starts",
        "anim_chatty": "Chatty cat",
        "anim_chatty_hint": "Says little things in the bubble now and then. Quietly, about once a minute.",
        "anim_chatty_tip": "The cat sometimes says cute little things in the bubble, quietly, about once a minute. "
                           "Turn off for plain hints only",
        "anim_master_tip": "Turn off and everything freezes: just a still sleeping / awake picture, no motion",
        "set_sound_title": "Sounds",
        "set_sound_hint": "Custom: WAV, MP3, OGG, M4A; the cat offers to trim",
        "set_sound_hint_wav": "Custom sounds must be WAV (MP3 needs the PySide6-Addons package)",
        "volume": "Volume",
        "snd_countdown": "Countdown beeps",
        "snd_record_start": "Meow — recording",
        "snd_record_stop": "Recording ended",
        "snd_play_start": "Macro started",
        "snd_tick": "Quiet ticks while recording",
        "snd_default": "default",
        "snd_missing": "missing: {name}",
        "snd_custom": "Custom…",
        "snd_reset": "Reset",
        "snd_preview_tip": "Listen",
        "dlg_sound": "Pick your sound",
        "sound_filter": "Sounds (*.wav *.mp3 *.ogg *.oga *.m4a *.aac *.flac);;All files (*)",
        "sound_filter_wav": "WAV sound (*.wav);;All files (*)",
        "msg_bad_format": "The cat doesn't understand “{name}”. Use WAV, MP3, OGG or M4A.",
        "msg_bad_wav": "The cat doesn't understand “{name}”. It must be a WAV file.",
        "msg_no_media": "MP3 can't play here (no QtMultimedia), so the cat used the default sound.",
        "msg_bad_sound": "Couldn't play “{name}”, so the cat used the default sound.",
        "snd_broken": "won't play: {name}",
        "msg_no_audio": "Sound isn't available on this system.",
        "cd_record": "{n} s countdown before recording",
        "cd_record_tip": "Beep-beep-beep, then a meow: recording has started",
        "cd_play": "{n} s countdown before a macro (hotkey)",
        "cd_play_tip": "The big paw on the left always counts down",
        "set_keys_title": "Hotkeys",
        "set_keys_hint": "Click a key, then press a new one",
        "hk_click": "Auto-click",
        "hk_record": "Record",
        "hk_play": "Replay",
        "hk_panic": "Panic stop",
        "hk_stop": "Extra stop",
        "hk_stop_tip": "Second stop key (Esc by default). Clear it with × and Esc can be recorded into macros",
        "hk_clear_tip": "Remove the second stop key",
        "hk_none": "none",
        "hk_reset": "Reset to defaults",
        "msg_keys_reset": "Default keys are back: F6, F7, F8, F9 and Esc.",
        "msg_stop_cleared": "Second stop key removed — now it can be recorded into macros.",
        "trim_title": "Trim sound",
        "trim_for": "For “{event}”",
        "trim_total": "File length: {secs} s",
        "trim_start": "Start, s",
        "trim_end": "End, s",
        "trim_sel": "Selected: {secs} s",
        "trim_max": "The cat plays at most {max} s; anything longer is cut off.",
        "trim_play": "▶  Listen",
        "trim_stop": "■  Stop",
        "trim_save": "Save",
        "trim_nocut": "Don't trim",
        "trim_cancel": "Cancel",
        "trim_save_tip": "Save the piece as a WAV in the sounds_custom folder; the original file is no longer needed",
        "trim_nocut_tip": "Use the whole file as is (plays from the start)",
        "trim_fail": "Couldn't read the sound for trimming: {err}",
        "msg_trimmed": "The cat saved the sound piece: “{name}”.",
        "msg_trim_fail": "Couldn't trim ({err}), so the cat used the file as is.",
        # promo bubble
        "promo": 'Psst, I also have a <a href="{url}">Telegram bot</a> for downloading videos!',
        "k_space": "Space",
        "k_right_suffix": " (R)",
    },
}

# Plural forms: Russian has 3 forms, English 2
PLURALS = {
    "ru": {"click": ("клик", "клика", "кликов"), "step": ("шаг", "шага", "шагов"),
           "key": ("клавиша", "клавиши", "клавиш"), "lap": ("круг", "круга", "кругов")},
    "en": {"click": ("click", "clicks"), "step": ("step", "steps"), "key": ("key", "keys"),
           "lap": ("lap", "laps")},
}


def set_language(lang: str) -> str:
    global _lang
    _lang = lang if lang in LANGUAGES else "ru"
    return _lang


# --- system language (for the first run) ---
# ru / uk / be -> Russian UI (there is no Ukrainian or Belarusian translation, Russian is closer), otherwise English.
_RU_PREFIXES = ("ru", "uk", "be", "russian", "ukrainian", "belarusian")
_WIN_RU_LANGIDS = (0x19, 0x22, 0x23)    # PRIMARYLANGID: Russian, Ukrainian, Belarusian


def lang_from_tag(tag) -> str | None:
    """'ru-RU', 'ru_RU.UTF-8', 'Russian_Russia' -> 'ru'; 'en_US', 'de-DE' -> 'en';
    empty / 'C' / 'POSIX' -> None (nothing known)."""
    if not tag or not isinstance(tag, str):
        return None
    t = tag.strip().lower().replace("-", "_").split(".")[0].split("@")[0]
    if t in ("", "c", "posix"):
        return None
    head = t.split("_")[0]
    return "ru" if head in _RU_PREFIXES else "en"


def _windows_ui_tag():
    """Windows UI language via kernel32.GetUserDefaultUILanguage (read-only, no registry)."""
    import sys
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except (AttributeError, OSError):
        return None
    return "ru" if (langid & 0x3FF) in _WIN_RU_LANGIDS else "en"


def system_language_tags() -> list:
    """Hints about the system language, most reliable first."""
    import locale
    import os
    tags = []
    try:
        from PySide6.QtCore import QLocale
        sys_locale = QLocale.system()
        tags += list(sys_locale.uiLanguages())[:1]
        tags.append(sys_locale.name())
    except Exception:         # no Qt (e.g. in a standalone script): no problem
        pass
    tags.append(_windows_ui_tag())
    try:
        tags.append(locale.getlocale()[0])
    except (ValueError, TypeError):
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        tags.append(os.environ.get(var))
    return tags


def detect_language(tags=None) -> str:
    """Language for the first run: the first recognisable hint from the list; English by default."""
    for tag in (system_language_tags() if tags is None else tags):
        lang = lang_from_tag(tag)
        if lang:
            return lang
    return "en"


def language() -> str:
    return _lang


def tr(key: str, /, **kw) -> str:
    text = STRINGS[_lang].get(key)
    if text is None:
        text = STRINGS["ru"].get(key, key)
    return text.format(**kw) if kw else text


def plural(n: int, word: str) -> str:
    forms = PLURALS[_lang][word]
    if _lang == "en":
        return forms[0] if abs(n) == 1 else forms[1]
    n = abs(int(n)) % 100
    if 10 < n < 20:
        return forms[2]
    n %= 10
    return forms[0] if n == 1 else forms[1] if 2 <= n <= 4 else forms[2]
