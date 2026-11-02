"""
The cat's phrases: little remarks in its bubble ("Chatty cat" in the settings).

How it works:
  PHRASES[situation]["ru" | "en"] is a list of phrases. The English ones are not literal
  translations but the same mood "in English". Add, remove and edit them as you like:
  * keep a phrase short (about 75 characters max): the bubble is small;
    tools/check_layout.py checks that every phrase fits;
  * a phrase may use placeholders:
        {n}   - a number (clicks, steps, loops),
        {w}   - the word for that number in the right form ("clicks", "laps"...;
                Russian has three plural forms),
        {key} - the name of a key;
    a phrase with a placeholder is used only when that number is known,
    so it is useful to keep phrases without numbers in the list too;
  * every situation needs at least 8 phrases in each language (a test checks this).

The cat speaks calmly and rarely: while idle the phrase changes every 40-90 seconds,
and the same phrase is never repeated twice in a row (PhrasePicker).
Important messages (errors, hints) always win over phrases: phrases are just "mood".
"""
import random
import string

MIN_PER_SITUATION = 8

PHRASES = {
    # ------------------------------------------------------------- greetings
    "greet_morning": {
        "ru": [
            "Доброе утро. Я ещё не проснулся, но лапу на кнопку уже положил.",
            "Утро… Мышка уже сварила кофе. Мне — сливки.",
            "Мрр, утро. Давай начнём медленно и без суеты.",
            "С добрым утром! Кликать буду, но сначала потянусь.",
            "Утречко. Солнце греет подоконник — лучшее рабочее место.",
            "Проснулся, умылся лапкой. Готов кликать.",
            "Доброе утро! Мышка говорит, день будет продуктивный. Я ей верю.",
            "Утро — время великих дел. Или маленького сна. Посмотрим.",
            "Привет! Шапка на месте, хвост на месте, можно начинать.",
        ],
        "en": [
            "Morning. I'm not awake yet, but my paw's on the button.",
            "Good morning! The mouse made coffee. I'll take the cream.",
            "Mrrp, morning. Let's start slow.",
            "Morning! I'll click in a moment. First, a big stretch.",
            "Sun's on the windowsill. Best office in the house.",
            "Washed my face with one paw. Ready for work.",
            "Good morning! The mouse says it's a productive day. I trust her.",
            "Mornings are for big plans. Or a small nap. We'll see.",
            "Hi! Headset on, tail present. We can begin.",
        ],
    },
    "greet_day": {
        "ru": [
            "Привет! Я тут, на посту. Почти не сплю.",
            "Добрый день. Лапы размяты, хвост в порядке.",
            "О, ты пришёл. Мышка, доставай блокнот!",
            "День в разгаре. Самое время что-нибудь покликать.",
            "Привет! Если что — я рядом. Обычно лежу.",
            "Мрр. Обед был, теперь можно и поработать.",
            "Добрый день! Покажи, где кликать, — я разберусь.",
            "Привет-привет. Шапка заряжена, усы настроены.",
            "Котоклик на связи. Мышка тоже, но она стесняется.",
        ],
        "en": [
            "Hi! On duty. Mostly awake.",
            "Good afternoon. Paws stretched, tail in order.",
            "Oh, you're here. Mouse, get the notebook!",
            "Middle of the day. Perfect time for some clicking.",
            "Hi! I'm right here if you need me. Usually lying down.",
            "Lunch is done, so I suppose I can work now.",
            "Good afternoon! Show me where to click, I'll handle it.",
            "Hey there. Headset charged, whiskers calibrated.",
            "KotoClick reporting. The mouse is here too, just shy.",
        ],
    },
    "greet_evening": {
        "ru": [
            "Добрый вечер. Самое уютное время для кликов.",
            "Вечер… Лампа тёплая, лапки тоже.",
            "Привет! Мышка зажгла свечку и открыла блокнот.",
            "Вечерком можно и покликать. Неспешно.",
            "Добрый вечер! Устал? Давай я покликаю.",
            "Вечер. Я как раз выспался после дневного сна.",
            "Мрр, вечер. Чай заварен, кнопка ждёт.",
            "Добрый вечер! Шапка на ушах, я весь внимание.",
            "Солнце село, а котик только проснулся. Удобно.",
        ],
        "en": [
            "Good evening. The coziest time to click.",
            "Evening… The lamp is warm, and so are my paws.",
            "Hi! The mouse lit a candle and opened her notebook.",
            "A little evening clicking? Nice and slow.",
            "Good evening! Tired? Let me do the clicking.",
            "Evening. Just woke up from my afternoon nap. Perfect timing.",
            "Tea's brewed, the button is waiting.",
            "Good evening! Headset on, all ears. Literally.",
            "Sun's down, cat's up. Works out nicely.",
        ],
    },
    "greet_night": {
        "ru": [
            "Ночь на дворе, а мы кликаем. Я не против.",
            "Тсс… Мышка спит. Будем кликать тихонько.",
            "Доброй ночи. Котики ночью самые бодрые.",
            "Ночная смена? Я принёс плед.",
            "Луна светит, кнопка ждёт. Красота.",
            "Не спится? Мне тоже. Давай покликаем.",
            "Ночью клики особенно мягкие. Проверено.",
            "Мрр… поздновато. Но если надо — я с тобой.",
            "Тихая ночь. Только ты, я и кнопка.",
        ],
        "en": [
            "It's late and we're clicking. I'm fine with that.",
            "Shh… the mouse is asleep. Let's click quietly.",
            "Good night. Cats are at their best after dark.",
            "Night shift? I brought a blanket.",
            "The moon is out, the button is waiting.",
            "Can't sleep? Me neither. Let's click a bit.",
            "Night clicks are extra soft. Trust me.",
            "Bit late, isn't it? Still, I'm here with you.",
            "Quiet night. Just you, me and the button.",
        ],
    },
    # ------------------------------------------------------------- idle
    "idle": {
        "ru": [
            "Мрр… снится, что я кликаю. Очень реалистично.",
            "Лежу. Это тоже работа, просто незаметная.",
            "Мышка пересчитывает записи. Я пересчитываю сны.",
            "Если что — буди. Но нежно.",
            "Хвост на месте. Проверил.",
            "Шапка немного съехала. Пусть.",
            "Мышка шепчет, что кнопка скучает.",
            "Думаю о сметане. Без причины.",
            "Здесь тепло. Я никуда не тороплюсь.",
            "Одним глазом сплю, другим слежу за курсором.",
            "Мурлычу на низких частотах. Для настроения.",
            "Мышка принесла печенье. Делим пополам.",
            "Пусть клики подождут. Они терпеливые.",
            "Тишина. Только где-то тикают часы.",
        ],
        "en": [
            "Purr… dreaming that I'm clicking. Very realistic.",
            "Lying down. It's work, just the quiet kind.",
            "The mouse counts her notes. I count my dreams.",
            "Wake me if you need me. Gently, please.",
            "Tail's still here. I checked.",
            "My headset slipped a little. That's fine.",
            "The mouse whispers that the button misses us.",
            "Thinking about cream. No reason.",
            "It's warm here. I'm in no hurry.",
            "One eye asleep, the other on your cursor.",
            "Purring in low frequencies. For the vibe.",
            "The mouse brought a cookie. We're sharing.",
            "The clicks can wait. They're patient.",
            "So quiet. Just a clock ticking somewhere.",
        ],
    },
    # ------------------------------------------------------------- auto-click
    "click_countdown": {   # during the countdown the phrase replaces the hint, so each one reminds about the cursor
        "ru": [
            "Потягиваюсь… Отведи курсор, куда надо.",
            "Сейчас, хвост поправлю. Курсор — на место клика.",
            "Разминаю лапку. Наведи курсор и не шевели.",
            "Целюсь… Курсор туда, где кликать.",
            "Уже встаю! Курсор убери на нужное место.",
            "Зеваю перед работой. Курсор пока наведи.",
            "Ещё чуть-чуть. Покажи курсором, куда жать.",
            "Прицеливаюсь усами. Курсор держи на месте.",
        ],
        "en": [
            "Stretching… put the cursor where it should go.",
            "One sec, fixing my tail. Cursor on the target.",
            "Warming up the paw. Point and hold still.",
            "Aiming… move the cursor where I should click.",
            "Getting up! Park the cursor on the spot.",
            "A big yawn first. Aim the cursor meanwhile.",
            "Nearly there. Show me with the cursor where to tap.",
            "Aiming with my whiskers. Keep the cursor still.",
        ],
    },
    "click_start": {
        "ru": [
            "Поехали! Тап-тап-тап.",
            "Лапа пошла. Ты отдыхай.",
            "Кликаю. Можешь налить чаю.",
            "Включил режим «трудолюбивый котик».",
            "Тык. Тык. Тык. Нравится.",
            "Работаю! Мышка, засекай время.",
            "Кнопка, держись. Я иду.",
            "Всё под контролем. Под лапой, точнее.",
            "Начали. Ритм хороший, мурчательный.",
        ],
        "en": [
            "Here we go! Tap-tap-tap.",
            "Paw's on it. You relax.",
            "Clicking away. Go get some tea.",
            "Hard-working cat mode: on.",
            "Tap. Tap. Tap. I like this.",
            "On it! Mouse, start the timer.",
            "Hold on, button. I'm coming.",
            "Everything's under control. Under paw, really.",
            "And we're off. Nice purring rhythm.",
        ],
    },
    "clicking": {   # calm clicking, changes rarely
        "ru": [
            "Тап… тап… Медитативно.",
            "Кликаю в такт мурчанию.",
            "Работа идёт, хвост качается.",
            "Не спешу, но и не сплю.",
            "Мышка говорит, у меня отличный ритм.",
            "Клик за кликом — вот и вся философия.",
            "Лапа ровная, мысли тёплые.",
            "Ещё немножко? Мне не трудно.",
            "Если что, я тут. Кликаю.",
        ],
        "en": [
            "Tap… tap… very meditative.",
            "Clicking in time with my purr.",
            "Work's going, tail's swaying.",
            "Not hurrying, not sleeping either.",
            "The mouse says my rhythm is great.",
            "Click after click. That's the whole philosophy.",
            "Steady paw, warm thoughts.",
            "A bit more? No trouble at all.",
            "Still here. Still clicking.",
        ],
    },
    "lively": {     # medium speed
        "ru": [
            "О, разогнались! Шапка подпрыгивает.",
            "Вошёл во вкус. Хвост сам качается.",
            "Бодренько! Мышка еле успевает считать.",
            "Ух, вот это темп. Мне нравится.",
            "Лапки нашли ритм.",
            "Уши торчком — значит, интересно.",
            "Это уже не работа, это танец.",
            "Мрр-тап-тап! Отлично идём.",
        ],
        "en": [
            "Ooh, picking up speed! The headset's bouncing.",
            "Getting into it. My tail sways on its own.",
            "Lively! The mouse can barely keep count.",
            "Now that's a pace. I like it.",
            "Paws found the groove.",
            "Ears up. This is getting fun.",
            "That's not work anymore, that's dancing.",
            "Purr-tap-tap! Going great.",
        ],
    },
    "hyper": {      # fast
        "ru": [
            "Лапки мелькают! Не моргай.",
            "Я быстрый. Очень быстрый кот.",
            "Мышка просит помедленнее. Не слышу!",
            "Тыгыдык-тыгыдык!",
            "Ещё немного — и будет дискотека…",
            "Усы развеваются от скорости.",
            "Это мой спринт. Обычно я так к миске бегаю.",
            "Шапка держится на честном слове.",
        ],
        "en": [
            "Paws are a blur! Don't blink.",
            "I'm fast. A very fast cat.",
            "The mouse says slow down. Can't hear her!",
            "Zoomies, but productive.",
            "A little longer and the disco begins…",
            "Whiskers flapping from the speed.",
            "This is my sprint. I usually save it for dinner.",
            "The headset's hanging on by a thread.",
        ],
    },
    "disco": {
        "ru": [
            "Дискотека! Мышка, свет!",
            "Танцую лапами. И немножко хвостом.",
            "Мой любимый трек: клик-клик-клик.",
            "Кот-диджей. Кот-танцор. Кот-всё.",
            "Огоньки! Кто включил огоньки?",
            "Не останавливай музыку. То есть клики.",
            "Мышка в очках зажигает рядом.",
            "Пушистый диско-шар — это я.",
        ],
        "en": [
            "Disco! Mouse, lights!",
            "Dancing with my paws. And a bit of tail.",
            "My favorite track: click-click-click.",
            "Cat DJ. Cat dancer. Cat everything.",
            "Lights! Who turned on the lights?",
            "Don't stop the music. I mean the clicks.",
            "The mouse is grooving in her sunglasses.",
            "The fluffy disco ball? That's me.",
        ],
    },
    "click_stop": {
        "ru": [
            "Готово: {n} {w}. Лапка довольна.",
            "Фух. {n} {w} — и ни одного промаха.",
            "Всё, отдыхаю. Это было приятно.",
            "Остановился. Мышка записала: {n} {w}.",
            "Хорошо поработали. Можно и подремать.",
            "Лапа на паузе. Хвост тоже.",
            "Сделано. Где моя заслуженная сметана?",
            "{n} {w}! Я впечатлён собой.",
            "Перерыв. Позови, когда снова понадоблюсь.",
        ],
        "en": [
            "Done: {n} {w}. My paw is pleased.",
            "Phew. {n} {w} and not a single miss.",
            "That's it, resting now. That was nice.",
            "Stopped. The mouse wrote down: {n} {w}.",
            "Good work. Nap time, I think.",
            "Paw on pause. Tail too.",
            "All done. Where's my well-earned cream?",
            "{n} {w}! I'm impressed with myself.",
            "Break time. Call me when you need me.",
        ],
    },
    "milestone": {  # 100, 1000, 10 000... clicks in one session
        "ru": [
            "{n} {w}! Мышка, записывай рекорд.",
            "Ого, уже {n} {w}. Лапа даже не устала.",
            "{n} {w}. Это повод для лёгкого мурчания.",
            "Юбилей: {n} {w}! Где торт?",
            "Целых {n} {w}. Я начинаю гордиться.",
            "{n} {w} позади. Хвост салютует.",
            "Отметка {n}! Мышка рисует звёздочку в блокноте.",
            "{n} {w}. Можно я теперь буду зваться мастером?",
        ],
        "en": [
            "{n} {w}! Mouse, write down the record.",
            "Whoa, {n} {w} already. Paw's not even tired.",
            "{n} {w}. Worth a little purr.",
            "Anniversary: {n} {w}! Where's the cake?",
            "A whole {n} {w}. I'm getting proud.",
            "{n} {w} behind us. Tail salute.",
            "{n} reached! The mouse draws a star in her notebook.",
            "{n} {w}. May I be called a master now?",
        ],
    },
    # ------------------------------------------------------------- recording (the mouse)
    "record_countdown": {
        "ru": [
            "Мышка точит карандаш…",
            "Мышка открывает блокнот на чистой странице.",
            "Тсс, мышка готовится. Сейчас будет «мяу».",
            "Мышка поправляет очки. Почти готово.",
            "Сейчас начнём. Делай всё спокойно.",
            "Мышка разминает лапки. Ещё секунда.",
            "Карандаш наготове. Ждём «мяу».",
            "Мышка шепчет: «Готова… почти»."
        ],
        "en": [
            "The mouse is sharpening her pencil…",
            "The mouse turns to a fresh page.",
            "Shh, the mouse is getting ready. Meow incoming.",
            "The mouse adjusts her glasses. Almost there.",
            "Starting soon. Take it nice and easy.",
            "The mouse stretches her tiny paws. One more second.",
            "Pencil ready. Waiting for the meow.",
            "The mouse whispers: “Ready… almost.”",
        ],
    },
    "record_start": {
        "ru": [
            "Мяу! Мышка пишет, ты показываешь.",
            "Запись пошла. Мышка не пропустит ни шага.",
            "Мышка строчит в блокноте. Действуй.",
            "Показывай, а мы запомним.",
            "Пишем! Не торопись, мышка успевает.",
            "Мышка вся внимание. Я тоже. Почти.",
            "Начали. Каждый клик — в блокнот.",
            "Мяу — и поехали. Мышка за тебя.",
        ],
        "en": [
            "Meow! The mouse writes, you show.",
            "Recording. The mouse won't miss a step.",
            "The mouse is scribbling. Go ahead.",
            "Show us, we'll remember.",
            "Writing it down! No rush, she keeps up.",
            "The mouse is all ears. So am I. Mostly.",
            "Here we go. Every click goes in the notebook.",
            "Meow, and we're rolling. The mouse has your back.",
        ],
    },
    "recording": {  # while recording, they change every 20-35 s
        "ru": [
            "Мышка пишет мелко-мелко.",
            "Скрип-скрип карандашом. Всё записано.",
            "Подглядываю в блокнот. Красиво пишет.",
            "Мышка просит не спешить. Ей нравится твой темп.",
            "Страница почти кончилась. Мышка берёт новую.",
            "Всё запоминаем. Даже то, как ты задумался.",
            "Мышка шепчет: «Отличный шаг!»",
            "Я сторожу блокнот. Это важная работа.",
        ],
        "en": [
            "The mouse writes in tiny letters.",
            "Scritch-scratch goes the pencil.",
            "I'm peeking at the notebook. Lovely handwriting.",
            "No need to rush, the mouse likes your pace.",
            "Page almost full. The mouse grabs another.",
            "Noting it all. Even your thinking pauses.",
            "The mouse whispers: “Nice step!”",
            "I'm guarding the notebook. Important job.",
        ],
    },
    "record_done": {
        "ru": [
            "Записано! {n} {w} в блокноте.",
            "Мышка закрыла блокнот. Вышло {n} {w}.",
            "Готово. Мышка довольна своим почерком.",
            "Всё запомнили. Теперь могу повторить.",
            "Записали. Мышка просит печеньку за труды.",
            "{n} {w} — аккуратно, по порядку.",
            "Блокнот пополнен. Котик готов повторять.",
            "Отлично записали. Мышка сдувает с листа крошки.",
        ],
        "en": [
            "Got it! {n} {w} in the notebook.",
            "The mouse closes the notebook. {n} {w} total.",
            "Done. The mouse is proud of her handwriting.",
            "All memorized. Now I can repeat it.",
            "Recorded. The mouse asks for a cookie.",
            "{n} {w}, neat and in order.",
            "Notebook updated. The cat is ready to replay.",
            "Nicely done. The mouse brushes crumbs off the page.",
        ],
    },
    # ------------------------------------------------------------- macro replay
    "play_start": {
        "ru": [
            "Читаю мышкин блокнот. Повторяю.",
            "Так, что тут написано… Ага, понял.",
            "Повторяю за мышкой. Слово в слово.",
            "Мышка диктует, я кликаю.",
            "Поехали по записям!",
            "Котик-исполнитель приступил.",
            "Всё как записано. Ни шагу в сторону.",
            "Мышка следит, чтобы я не халтурил.",
        ],
        "en": [
            "Reading the mouse's notebook. Repeating.",
            "Let's see what it says… Ah, got it.",
            "Following the mouse's notes to the letter.",
            "The mouse dictates, I click.",
            "Off we go, by the notes!",
            "Performer cat, at your service.",
            "Exactly as written. No improvising.",
            "The mouse is watching so I don't slack off.",
        ],
    },
    "play_loop": {  # {n} = how many loops are done
        "ru": [
            "Круг {n} позади. Идём дальше.",
            "Уже {n} {w}. Голова не кружится.",
            "Ещё кружок! Мышка ставит галочку.",
            "{n} {w}. Блокнот я уже знаю наизусть.",
            "Опять сначала. Мне не надоедает.",
            "Мышка считает круги: {n}.",
            "По кругу, как часики. Тик-так.",
            "Круг {n}. Хвост уже сам знает, что делать.",
        ],
        "en": [
            "Lap {n} done. Onward.",
            "{n} {w} already. Not dizzy at all.",
            "Another lap! The mouse ticks a box.",
            "{n} {w}. I know the notebook by heart now.",
            "From the top again. Never gets old.",
            "The mouse is counting laps: {n}.",
            "Round and round like clockwork. Tick-tock.",
            "Lap {n}. My tail knows the moves by now.",
        ],
    },
    "play_done": {  # the macro finished by itself
        "ru": [
            "Готово! Всё по записям.",
            "Блокнот прочитан до конца.",
            "Повторил. Мышка ставит пятёрку.",
            "Всё сделал. Можно мне на подоконник?",
            "Конец записи. Хвост доволен.",
            "Сделано точно как написано.",
            "Финиш. Мышка закрывает блокнот.",
            "Отработал. Теперь положено мурлыкать.",
        ],
        "en": [
            "Done! Everything by the notes.",
            "Read the notebook cover to cover.",
            "Repeated it all. The mouse gives me an A.",
            "All done. Can I go back to the windowsill?",
            "End of the notes. Happy tail.",
            "Done exactly as written.",
            "Finish line. The mouse closes the notebook.",
            "Shift's over. Purring is now mandatory.",
        ],
    },
    "play_stop": {  # replay was stopped with a key
        "ru": [
            "Остановился на полуслове. Ладно.",
            "Стоп. Мышка закрыла блокнот.",
            "Хорошо, хватит. Блокнот подождёт.",
            "Стоп так стоп. Я не спорю.",
            "Остановились. Лапы свободны.",
            "Отдыхаю. Продолжим, когда скажешь.",
            "Понял, перерыв. Хвост расслаблен.",
            "Мышка вздохнула и убрала карандаш.",
        ],
        "en": [
            "Stopped mid-sentence. Fair enough.",
            "Stop. The mouse shuts the notebook.",
            "Alright, that's enough. The notebook can wait.",
            "Stop it is. No arguments here.",
            "Stopped. Paws free.",
            "Resting. We'll go again when you say.",
            "Got it, break time. Tail relaxed.",
            "The mouse sighs and puts her pencil away.",
        ],
    },
    # ------------------------------------------------------------- events
    "panic": {
        "ru": [
            "Стоп! Всё бросил, лапы вверх.",
            "Ой. Замер. Даже хвостом не шевелю.",
            "Стоп-кран сработал. Я спокоен.",
            "Всё остановил. Что случилось?",
            "Замираю, как статуэтка котика.",
            "Остановился мгновенно. Тренировался на пылесосе.",
            "Тормоза — это важно. Всё стоит.",
            "Мышка юркнула в норку. Тишина.",
        ],
        "en": [
            "Stop! Paws up, dropping everything.",
            "Whoa. Frozen. Not even a tail twitch.",
            "Emergency brake pulled. I'm calm.",
            "Everything stopped. What happened?",
            "Freezing like a cat statue.",
            "Instant stop. I practice on the vacuum.",
            "Brakes matter. Everything's still.",
            "The mouse dove into her hole. All quiet.",
        ],
    },
    "hotkey_set": {
        "ru": [
            "Новая клавиша: {key}. Запомнил.",
            "{key}? Хороший выбор, удобная.",
            "Записал на подушечке лапы: {key}.",
            "Понял, теперь откликаюсь на {key}.",
            "Мышка вписала {key} в блокнот.",
            "Отлично. Новая кнопка — новая жизнь.",
            "Запомнил. Котики не забывают.",
            "Клавиша поменялась. Я — нет.",
        ],
        "en": [
            "New key: {key}. Got it.",
            "{key}? Good pick, comfy.",
            "Noted on my paw pad: {key}.",
            "Got it, I answer to {key} now.",
            "The mouse wrote {key} in her notebook.",
            "Nice. New key, new life.",
            "Memorized. Cats never forget.",
            "The key changed. I didn't.",
        ],
    },
    "macro_created": {
        "ru": [
            "Новая страница в блокноте. Чистенькая.",
            "Мышка завела новую тетрадку.",
            "Новый макрос! Пахнет свежей бумагой.",
            "Чистый лист. Что запишем?",
            "Мышка подписала обложку. Красиво.",
            "Ещё один макрос в коллекцию.",
            "Новенький. Будем знакомиться.",
            "Пусто, но уютно. Начнём запись?",
        ],
        "en": [
            "A fresh page in the notebook.",
            "The mouse started a new notebook.",
            "New macro! Smells like fresh paper.",
            "Blank page. What shall we write?",
            "The mouse labeled the cover. Neat.",
            "One more macro for the collection.",
            "A new one. Let's get acquainted.",
            "Empty, but cozy. Shall we record?",
        ],
    },
    "macro_saved": {
        "ru": [
            "Сохранил. Мышка спрятала копию под подушку.",
            "Всё на месте, ничего не потеряется.",
            "Сохранено. Можно спать спокойно.",
            "Мышка аккуратно подшила листочки.",
            "Записи в безопасности. Я сторожу.",
            "Готово. Блокнот на полке.",
            "Сохранили. Хвост одобряет.",
            "Порядок в бумагах — порядок в голове.",
        ],
        "en": [
            "Saved. The mouse tucked a copy under her pillow.",
            "All safe, nothing will get lost.",
            "Saved. We can nap in peace.",
            "The mouse neatly bound the pages.",
            "Notes are safe. I'm on guard.",
            "Done. The notebook's on the shelf.",
            "Saved. Tail approves.",
            "Tidy papers, tidy mind.",
        ],
    },
    "macro_deleted": {
        "ru": [
            "Удалил. Мышка вздохнула, но согласилась.",
            "Страница вырвана. Было и прошло.",
            "Минус один. Блокнот стал легче.",
            "Прощай, макрос. Ты был неплох.",
            "Убрали. Меньше бумаг — больше места для сна.",
            "Удалено. Мышка подмела крошки.",
            "Ладно, этот нам больше не нужен.",
            "Чистота и порядок. Мрр.",
        ],
        "en": [
            "Deleted. The mouse sighed but agreed.",
            "Page torn out. Gone, but fondly remembered.",
            "One fewer. The notebook's lighter.",
            "Farewell, macro. You were alright.",
            "Removed. Less paper, more room to nap.",
            "Deleted. The mouse swept up the crumbs.",
            "Fine, we don't need that one anymore.",
            "Clean and tidy. Purr.",
        ],
    },
    "lang_switched": {
        "ru": [
            "Говорю по-русски. Мур!",
            "Русский? Конечно. Мяу по-нашему.",
            "Переключился. Мышка тоже понимает.",
            "По-русски мурчать удобнее.",
            "Мрр, родные буквы.",
            "Хорошо, теперь говорю по-русски.",
            "Язык сменил, характер оставил.",
            "Мышка перевернула блокнот. Готово.",
        ],
        "en": [
            "Speaking English now. Meow!",
            "English? Sure. Same meow, new accent.",
            "Switched. The mouse understands too.",
            "Purring in English now.",
            "Okay, English it is.",
            "New language, same cat.",
            "The mouse flipped her notebook. Done.",
            "Mrrp. Cats are multilingual, you know.",
        ],
    },
    "sound_muted": {
        "ru": [
            "Тишина. Буду мяукать про себя.",
            "Звук выключен. Мурчу беззвучно.",
            "Тихий режим. Мышка на цыпочках.",
            "Ладно, без звуков. Я и так милый.",
            "Тсс. Теперь только шёпот.",
            "Звук на нуле. Уши отдыхают.",
            "Молчу. Но смотрю выразительно.",
            "Тишина — тоже музыка. Кошачья.",
        ],
        "en": [
            "Silence. I'll meow in my head.",
            "Sound off. Purring silently.",
            "Quiet mode. The mouse is tiptoeing.",
            "Fine, no sounds. I'm cute enough without.",
            "Shh. Whispers only now.",
            "Volume at zero. Ears resting.",
            "Silent, but staring meaningfully.",
            "Silence is music too. Cat music.",
        ],
    },
    "error": {
        "ru": [
            "Ой. Что-то пошло не так, но мы разберёмся.",
            "Хм. Не получилось. Давай спокойно разберёмся.",
            "Лапа соскользнула. Бывает.",
            "Мышка нахмурилась. Что-то не так.",
            "Неудача. Я не расстроился. Почти.",
            "Что-то мешает. Попробуем ещё раз?",
            "Мрр… странно. Такого в блокноте не было.",
            "Споткнулся. Сейчас встану.",
        ],
        "en": [
            "Oops. Something went wrong, but we'll sort it out.",
            "Hmm. That didn't work. Let's figure it out calmly.",
            "Paw slipped. Happens.",
            "The mouse frowned. Something's off.",
            "A miss. I'm not upset. Mostly.",
            "Something's in the way. Try again?",
            "Hmm… odd. That wasn't in the notebook.",
            "Tripped. Getting back up.",
        ],
    },
    "no_hotkeys": {  # hotkeys did not start: suggest the paw button
        "ru": [
            "Клавиши меня не слышат. Жми на лапку.",
            "Горячие клавиши уснули. Лапка работает.",
            "Не слышу клавиатуру. Лапка в окне — к твоим услугам.",
            "Уши не ловят клавиши. Кликай по лапке.",
            "Без клавиш тоже можно. Есть большая лапка.",
            "Клавиатура молчит. Давай через лапку.",
            "Мышка не слышит клавиши. Кнопка-лапка выручит.",
            "Горячие клавиши не отвечают. Лапка — да.",
        ],
        "en": [
            "I can't hear the keys. Use the paw button.",
            "Hotkeys fell asleep. The paw still works.",
            "Can't hear the keyboard. The big paw is here for you.",
            "My ears can't catch the keys. Click the paw.",
            "No hotkeys? We have a big paw.",
            "Keyboard's silent. Let's use the paw.",
            "The mouse can't hear the keys. The paw will help.",
            "Hotkeys aren't answering. The paw is.",
        ],
    },
}

SITUATIONS = tuple(PHRASES)
MILESTONES = (100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000)


def greeting_situation(hour: int) -> str:
    """Greeting by time of day: morning 5-11, day 11-17, evening 17-23, night 23-5."""
    if 5 <= hour < 11:
        return "greet_morning"
    if 11 <= hour < 17:
        return "greet_day"
    if 17 <= hour < 23:
        return "greet_evening"
    return "greet_night"


def milestone_reached(count: int, already: int) -> int:
    """The largest "round" milestone reached, if it is above the one already celebrated; otherwise 0."""
    best = 0
    for m in MILESTONES:
        if count >= m:
            best = m
    return best if best > already else 0


def fields(phrase: str) -> set:
    """Which placeholders ({n}, {w}, {key}) the phrase contains."""
    return {name for _, name, _, _ in string.Formatter().parse(phrase) if name}


class PhrasePicker:
    """Picks a phrase at random, but never the same as last time (in this situation or overall)."""

    def __init__(self, phrases=None, rng=None):
        self.phrases = phrases if phrases is not None else PHRASES
        self.rng = rng or random.Random()
        self._last = {}        # (situation, language) -> last phrase
        self._last_any = ""    # the last phrase said overall

    def options(self, situation: str, lang: str, **fmt) -> list:
        bank = self.phrases.get(situation, {})
        items = bank.get(lang) or bank.get("en") or []
        have = {k for k, v in fmt.items() if v is not None}
        return [p for p in items if fields(p) <= have]

    def pick(self, situation: str, lang: str, **fmt) -> str:
        opts = self.options(situation, lang, **fmt)
        if not opts:
            return ""
        last = self._last.get((situation, lang))
        fresh = [p for p in opts if p != last and p.format(**fmt) != self._last_any] or opts
        phrase = self.rng.choice(fresh)
        self._last[(situation, lang)] = phrase
        text = phrase.format(**fmt)
        self._last_any = text
        return text
