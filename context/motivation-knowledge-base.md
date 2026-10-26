# База знаний: мотивация, привычки, Duolingo → NoteTask

Собрано: 2026-10-04. Для дизайна ежедневок, уведомлений и (позже) ИИ-тактик.  
Сырые выдачи поиска: `research-habit-science.json`, `research-duolingo.json`, `research-duolingo-official.json`, `research-primary-papers.json`, `research-habit-apps.json`, `research-habit-apps-2.json`, `research-gamification.json`.

**Проблема пользователя:** уведомления идут потоком, к ним привык, в приложение не заходит, задания не делает. Не «фейковый complete» — просто габитуация к спаму.

---

## 1. Что говорит наука о привычках

### 1.1 Автоматичность, не стрик

[Lally et al., 2010, *European Journal of Social Psychology*](https://doi.org/10.1002/ejsp.674) (96 человек, 12 недель, ежедневный самоотчёт): медиана до ~95% потолка автоматичности — **66 дней**, разброс **18–254**. «21 день» — не исследование привычек, а наблюдение Maltz (1960) про адаптацию к операции. По вторичным разборам той же статьи: один пропуск почти не ломает кривую; ломает серия пропусков. Простая привычка (вода за завтраком) автоматизируется быстрее сложной (50 приседаний). Источник модели: [PsycNet record](https://psycnet.apa.org/record/2010-22273-010). Пояснение автора: [University of Surrey / Pippa Lally](https://www.surrey.ac.uk/news/does-it-really-take-66-days-form-habit-we-asked-expert-dr-pippa-lally).

**Вывод для продукта:** считать привычку по «сделал в том же контексте», а не по огню. Наказывать за один пропуск — против данных Lally.

### 1.2 Привычка = ответ на контекстный якорь

Wendy Wood и др.: привычка — повтор одного ответа в одном контексте, пока поведение не станет автоматическим ([обзор *Psychology of Habit*, Annual Review of Psychology, 2016](https://www.academia.edu/87762408/Psychology_of_Habit)). Напоминание «сделай отжимания» без якоря («после чистки зубов / после кофе») — это не привычка, это каждый раз новая волевая задача.

### 1.3 Implementation intentions («если — то»)

[Gollwitzer & Sheeran, 2006, meta-analysis](https://archive.org/download/06GollwitzerSheeranImplementationIntentionsAndGoalAchievement/06GollwitzerSheeran_ImplementationIntentionsAndGoalAchievement.pdf): if–then план заранее привязывает действие к ситуации и даёт «instant habits» (быстрый запуск без отдельного решения). Эффект сильнее, когда саморегуляции не хватает.

Формат: `Когда [якорь], я сделаю [микро-действие]`. Не: «надо отжиматься каждый день».

### 1.4 Fogg: B = MAP

[Fogg Behavior Model, Stanford Behavior Design Lab](https://behaviordesign.stanford.edu/resources/fogg-behavior-model) (paper 2009): поведение случается, только если в один момент сходятся **Motivation × Ability × Prompt**. Нет любого из трёх — нет действия. Мотивацию и способность можно менять местами: при низкой мотивации действие должно быть почти нулевой сложности. Prompt без способности и мотивации = игнор.

Практический приём из [клинического применения FBM у ординаторов](https://pmc.ncbi.nlm.nih.gov/articles/PMC12360234/): «минимум 10 минут» при нулевой энергии + карточка `Whenever I … I will …`.

**Диагноз NoteTask:** prompt есть (TG каждые 3 часа). Ability низкая (полный сет отжиманий / планка / «открыть веб»). Motivation после привыкания к спаму ≈ 0. Модель предсказывает ровно то, что происходит.

### 1.5 Self-Determination Theory

[Ryan & Deci, 2000, *American Psychologist*, 55(1), 68–78](https://doi.org/10.1037/0003-066X.55.1.68): устойчивая мотивация держится на **автономии, компетентности, связанности**. Внешний контроль («долби, пока не нажмёшь») даёт краткосрочный compliance и потом отчуждение. Награды и давление могут подрывать intrinsic motivation (cognitive evaluation theory внутри SDT). Обзор: [APA Breakthrough Research](https://www.apa.org/research-practice/conduct-research/breakthrough-research).

**Для ИИ:** стыдящий коуч бьёт по автономии. Лучше: выбор микро-версии, ощущение прогресса, якорь «я тот, кто делает утренний ритуал».

---

## 2. Почему поток уведомлений умирает

Habituation: повторный стимул без последствия перестаёт вызывать ориентировочную реакцию. Частый nag без немедленного действия тренирует **скип как привычку** (контекст = пуш, ответ = смахнуть).

Следствия:

1. Частота 3h (NoteTask `remind_rule=hourly`, слоты 00/03/06/09/12/15/18/21) — слишком много проб «игнор».
2. Канал Telegram — лента, не рабочий стол. Нет якоря «открыл телефон утром».
3. Кнопка «Выполнить» в TG закрывает петлю без поведения (риск hollow engagement — см. ниже).
4. Нет ставки, которую жалко потерять *до* пуша. Пуш без ставки — «напоминание незнакомцу» ([разбор Mazal / streak-saver](https://www.lennysnewsletter.com/p/how-duolingo-retains-users)).

---

## 3. Как устроен Duolingo (официальные цифры)

Источник: блог product/engineering, не маркетинговые гайды.

### 3.1 Стрик = привычка дня, цель — отдельно

[Improving the streak (2020-11-19)](https://blog.duolingo.com/improving-the-streak): раньше стрик требовал дневную цель (уроки/XP). Люди с «intense» целью чаще **ходили каждый день и всё равно не были на стрике** (~40% из «два дня подряд без стрика» — intense). Эксперимент: стрик за **один урок**, цель отдельно.

Результаты (относительные): **+3.3% Day-14 retention**, **+1% DAU**, за 20 дней **+10.5%** доли на стрике; через год **+40%** людей на стрике 7+ дней. 7-дневный стрик: **в 2.4 раза** выше шанс зайти завтра.

**Урок:** планка «засчитать день» должна быть стыдно низкой. Цель (полная тренировка) — второй слой, не условие привычки.

### 3.2 Язык «привычка», не «огонь»

[Putting in the work (2021-01-08)](https://blog.duolingo.com/putting-in-work-the-habit-of-language-learning): копирайт opt-in пушей про *building a long-term habit* vs keep streak → **+5% opt-in**. Экран после первого урока «Reach a 7 day streak to start building a daily habit» лучше возвращал на следующий день, чем «This starts your streak».

### 3.3 Freeze снимает спираль стыда

[How the streak uses habit research (2022-01-31)](https://blog.duolingo.com/how-duolingo-streak-builds-habit): до **двух** Streak Freeze сразу → **+0.38%** daily active (не падение дисциплины). [Protecting streaks from site issues](https://blog.duolingo.com/protecting-streaks-from-site-issues): компания чинит стрик при своём даунтайме (Big Red Button, >2M стриков) — ставка священна, продукт не имеет права её украсть.

### 3.4 Ставка до пуша; социальный слой

[Streak Wager](https://blog.duolingo.com/how-streaks-keep-duolingo-learners-committed-to-their-language-goals): пари «держи 7 дней, удвой гемы» → значимый рост D1/D7/D14, **D7 +14%**.  
[Friend Streak](https://blog.duolingo.com/friend-streak/): ≥1 общий стрик → **+22%** шанс закрыть дневной урок; можно ткнуть друга.  
Пуш «сейчас потеряешь стрик» работает *потому что* стрик уже есть, а не вместо него.

### 3.5 Сессии короткие, путь видимый

Интерфейс — путь навыков (компетентность SDT). Урок ~минуты (ability Fogg). Маскот Duo — персона, не дайджест задач.

### 3.6 Вторичные разборы (не путать с paper)

[Behavioral Design Hub teardown](https://zicozhou10.github.io/behavioral-design-hub/teardowns/duolingo): стрик как loss aversion (Kahneman/Tversky); XP/лиги — variable ratio (Skinner); после ~дня 14 внешние триггеры тускнеют, нужен переход к intrinsic. Утверждения вроде «8–12 пушей/день», «D7 55% / D30 35% SensorTower», «2.3× DAU/MAU в письме акционерам» — **не проверялись по первоисточнику**, в дизайн не класть как факт.

Риск, который разборы подсвечивают верно по смыслу: люди заходят *чтобы не потерять*, а не чтобы сделать настоящее действие ([Just Another PM](https://www.justanotherpm.com/blog/the-psychology-behind-duolingos-streak-feature)). Для языка «один урок» всё ещё урок. Для отжиманий «открыл TG и скипнул» — ноль тренировки.

---

## 4. Что копировать в NoteTask / чего не копировать

| Копировать | Не копировать |
|---|---|
| Один крошечный «урок дня» засчитывает привычку | Стрик = полная планка / все подходы |
| Одна ставка (огонь / ритуал), один спасающий пуш | Наг каждые 3 часа по каждой задаче |
| Freeze 1–2 дня, без обнуления жизни | «Пропустил — с нуля, ты мусор» |
| If–then якорь к уже существующему ритуалу | Напоминание «вообще когда-нибудь» |
| Виджет / домашний экран как prompt | Только Telegram-лента |
| Цель (A/B/C тренировка) отдельно от daily habit | Смешать повестку, финансы, зубы и жим в один спам |
| ИИ подбирает *тактику дня* | ИИ-чат, который пишет ещё текст в TG |

---

## 5. Роль ИИ (если подключать)

ИИ не источник мотивации. Мотивация — MAP + SDT + ставка. ИИ — **селектор интервенции** по состоянию:

- Низкая энергия → крошечная версия (1 отжимание, 10 с планки) — Fogg ability.
- Нет якоря → сгенерировать if–then на существующий ритуал — Gollwitzer.
- Серия пропусков → не стыд, а freeze + «вернись завтра» — Lally + Duo freeze.
- Сделал микро → предложить полный сет как *опцию* (компетентность), не как условие дня.
- После 14 дней внешнего крючка → меньше пуша, больше identity / дерево Целей (intrinsic).

Поиск «разных способов мотивировать» = ротация тактик с измерением: открыл ли приложение, сделал ли микро, не смахнул ли пуш. Не LLM, который каждый час пишет новое остроумие в тот же канал, который уже мёртв.

---

## 6. Карта на текущий NoteTask

Уже есть: задачи daily, `remind_rule` 3h, TG «Выполнить», виджет «Сегодня» в APK/PWA, деревья Целей, план тренировок A/B/C.

Дыры относительно этой базы:

1. Нет отдельной сущности «daily habit session» (аналог одного урока).
2. Нет стрика привычки, отделённого от complete полной задачи.
3. Prompts слишком частые и в неправильном канале.
4. Нет якоря if–then в данных задачи.
5. Complete в TG закрывает задачу без доказательства микро-действия.
6. Телефон не в петле (APK есть, но не в домашнем ритуале).

Телефон: `https://todo.baski.pro/download` → `NoteTask.apk`; либо PWA «На экран Домой»; домашний Wi‑Fi — DNS `192.168.0.6` или `http://192.168.0.6/`.

---

## 7. Другие приложения (что у них работает)

### Habitica — RPG вокруг списка дел

[habitica.com](https://habitica.com/): Habits / Dailies / To-Dos. Галочка → XP, золото, броня, питомцы, квесты. Пропуск Daily → урон по HP аватара ([overview](https://habitica.com/static/overview)). Соло + пати против боссов (relatedness SDT). Кастомная награда «серия сериала» за золото — обмен неудобного на приятное, не абстрактные бейджи.

Риск: награды могут стать смыслом, задачи — фармом (overjustification). Для NoteTask: урон/XP только если есть *микро-доказательство*, иначе фарм «отметил в TG».

### Apple Activity Rings — закрыть круг

[Разбор Trophy](https://trophy.so/blog/the-psychology-of-apple-watchs-close-your-rings): три кольца (Move / Exercise / Stand) = один «день выигран». Gestalt closure: незакрытый круг чешется. Move — низкий порог; Exercise — намеренность; Stand — микро-наджи по часам, не дайджест. Сброс в полночь. [Apple, 2025](https://9to5mac.com/2025/04/14/apple-watch-rings-heart-health-sleep-mental-health/) публиковала ассоциации closed rings со сном/сердцем — это outcome, не механика.

Для NoteTask: 1–3 кольца дня (микро-привычка / движение / «открыл приложение»), не 30 задач в Сегодня.

### Forest — ставка внутри сессии

Дерево растёт, пока не уходишь из фокуса; выход = дерево умирает ([case study](https://trophy.so/blog/forest-gamification-case-study)). Это **commitment внутри 25 минут**, не стрик на 400 дней. Пользователи бесятся, когда дерево *не* умирает — значит, жало копит ценность.

Для отжиманий: таймер «держи 20 с / не закрывай экран» важнее пуша в 03:00.

### Beeminder / StickK — твёрдый commitment device

[Beeminder](https://wiki.beeminder.com/what-is-beeminder.html): график + pledge, derail → деньги, ставка растёт ($0→$5→$10→…). Против акразии (делаешь не то, что сам себе обещал). [Beeminder про loss aversion](https://blog.beeminder.com/aversion/): sting — не обязательно «иррациональная loss aversion», но угроза потери усиливает.

Полевое: [Ashraf, Karlan, Yin — commitment savings, Филиппины](https://karlan.yale.edu/sites/default/files/tying-odysseus-mast-evidence-commitment-savings-product-philippines.pdf) — добровольный замок на снятие → балансы сбережений примерно **+80%** за год vs контроль.

Для личного NoteTask деньги себе переводить бессмысленно, пока нет свидетеля. Мягкий аналог: публичный стрик, ИИ-свидетель, «долг» на завтра, блокировка развлечений.

### Streaks / home widgets

Минимальный трекер: мало привычек, виджет на рабочем столе, Watch. Prompt = домашний экран, не чат. Это ближайший канал, которого у NoteTask почти нет в ежедневном ритуале.

---

## 8. Геймификация и вовлечение (рамки)

### Octalysis (Yu-kai Chou) — 8 драйвов

[Описание, UZH / Chou 2019](https://www.gbl.uzh.ch/quartz/definitions/Octalysis-Framework) · [сайт Chou](https://yukaichou.com/gamification-examples/octalysis-gamification-framework):

1. Epic Meaning  
2. Development & Accomplishment  
3. Empowerment / Creativity & Feedback  
4. Ownership  
5. Social Influence & Relatedness  
6. Scarcity & Impatience  
7. Unpredictability & Curiosity  
8. Loss & Avoidance  

White Hat (верх: смысл, мастерство, творчество) vs Black Hat (низ: дефицит, непредсказуемость, страх потери). Left = extrinsic (цель), Right = intrinsic (процесс). Если драйвов нет — нет действия. Чёрная шляпа поднимает DAU и выжигает.

NoteTask сейчас почти только драйв 8 (долбёжка) без 2/3/5 — отсюда привыкание.

### Hooked (Nir Eyal)

Trigger → Action → Variable Reward → Investment. Внешний триггер (пуш) должен со временем смениться внутренним («после кофе странно не сделать»). Инвестиция: стрик, дерево целей, лог тренировок. Variable reward: не одинаковый текст «напомни», а сюрприз микро-квеста / медали.

После ~2 недель один внешний триггер тускнеет (как в разборах Duo) — нужен якорь + ставка, не громче пуш.

### Overjustification

Ожидаемая вещественная награда за само действие снижает intrinsic interest. Мета-анализ в обзорах: engagement-contingent rewards **d ≈ −0.40**; словесная похвала может повышать ([Science Insights разбор](https://scienceinsights.org/the-overjustification-effect-why-rewards-kill-motivation); [Wikipedia](https://en.wikipedia.org/wiki/Overjustification_effect)). XP за «открыл приложение» опасны. XP за *сделанный* микросет — ближе к competence feedback.

### Commitment devices (мягкие vs твёрдые)

[HabitBox обзор](https://habitbox.app/blog/commitment-device): hard = деньги/блокер; soft = репутация, партнёр, видимый стрик. Нужны: ставка, яркая линия правила, видимость каждый день.

---

## 9. Каталог инструментов возврата в NoteTask

Не внедрять всё. Слой привычки = 3–5 штук. ИИ потом выбирает, какую включить сегодня.

| # | Инструмент | Откуда | Зачем тебе | Риск |
|---|------------|--------|------------|------|
| A | **Виджет / PWA / иконка на первом экране** | Streaks, Duo | Prompt там, куда смотришь утром | Hairpin Wi‑Fi |
| B | **Одно «кольцо дня»** (микро-урок) | Apple, Duo 1 lesson | День засчитан за стыдно малое | Hollow complete |
| C | **Стрик кольца + Freeze** | Duo | Ставка до пуша | Фарм пустых дней |
| D | **Один streak-saver вечером** | Duo Mazal | Пуш только если ставка под угрозой | Снова спам, если без ставки |
| E | **If–then якорь** («после зубов — 1 отжимание») | Gollwitzer, Fogg | Привычка к ритуалу, не к пушу | Якорь не выбран |
| F | **Сессия Forest** (экран нельзя смахивать N секунд) | Forest | Complete ≠ тап в TG | Бесит, если долго |
| G | **Кольца 2–3** (микро / движение / «зашёл») | Apple | Закрытый гештальт | Три кольца = три провала |
| H | **Дерево Целей как XP мастерства** | уже есть Cytoscape | Драйв 2, не бейдж | Далеко от ежедневки |
| I | **Долг на завтра** (пропуск копится) | Beeminder yellow brick | Не обнуление, а график | Тревога |
| J | **Свидетель** (друг / ИИ вечером: «сделал?») | Friend Streak, StickK soft | Relatedness | Игнор чата как TG |
| K | **Переменная тактика дня** | Skinner VR, Octalysis 7 | Не привыкнуть к одному тексту | Шум |
| L | **Утреннее полноэкранное «сделай 20 с»** | будильник | Нельзя не увидеть | Бесит → удалит приложение |
| M | **Выключить 3h nag** | Fogg / habituation | Перестать тренировать скип | Страх «без долбёжки забуду» |
| N | **ИИ-селектор** по энергии/пропускам | эта база | Ротация A–L | Ещё один чат |

Минимальный пакет, который бьёт в твою поломку (не заходишь + привык к TG):

1. **M** — убить поток.  
2. **A+B+C** — домашний экран, микро-день, огонь.  
3. **D** — один пуш «кольцо не закрыто».  
4. **F** на силовых — нельзя засчитать без удержания экрана.  
5. **N** позже — не вместо 1–4.

---

## Источники

Наука:

- [Lally et al. 2010, EJSP, How are habits formed](https://doi.org/10.1002/ejsp.674)
- [PsycNet: Lally 2010](https://psycnet.apa.org/record/2010-22273-010)
- [Lally interview, University of Surrey](https://www.surrey.ac.uk/news/does-it-really-take-66-days-form-habit-we-asked-expert-dr-pippa-lally)
- [Ryan & Deci 2000, American Psychologist](https://doi.org/10.1037/0003-066X.55.1.68)
- [APA on Ryan & Deci SDT](https://www.apa.org/research-practice/conduct-research/breakthrough-research)
- [Gollwitzer & Sheeran 2006 meta-analysis PDF](https://archive.org/download/06GollwitzerSheeranImplementationIntentionsAndGoalAchievement/06GollwitzerSheeran_ImplementationIntentionsAndGoalAchievement.pdf)
- [Fogg Behavior Model, Stanford](https://behaviordesign.stanford.edu/resources/fogg-behavior-model)
- [PMC: FBM intervention in residents](https://pmc.ncbi.nlm.nih.gov/articles/PMC12360234/)
- [Wood & Rünger, Psychology of Habit, 2016](https://www.academia.edu/87762408/Psychology_of_Habit)

Duolingo official:

- [Improving the streak](https://blog.duolingo.com/improving-the-streak) (2020-11-19)
- [Putting in the work](https://blog.duolingo.com/putting-in-work-the-habit-of-language-learning) (2021-01-08)
- [Streak uses habit research](https://blog.duolingo.com/how-duolingo-streak-builds-habit) (2022-01-31)
- [Protecting streaks from site issues](https://blog.duolingo.com/protecting-streaks-from-site-issues) (2021-11-01)
- [Streak wager / commitment](https://blog.duolingo.com/how-streaks-keep-duolingo-learners-committed-to-their-language-goals)
- [Friend Streak](https://blog.duolingo.com/friend-streak/) (2024-08-05)
- [Product lessons Friend Streak](https://blog.duolingo.com/product-lessons-friend-streak) (2024-09-20)

Другие приложения и геймификация:

- [Habitica](https://habitica.com/) · [overview HP/XP](https://habitica.com/static/overview)
- [Apple rings psychology (Trophy)](https://trophy.so/blog/the-psychology-of-apple-watchs-close-your-rings)
- [Apple on Activity Rings, 2025](https://9to5mac.com/2025/04/14/apple-watch-rings-heart-health-sleep-mental-health/)
- [Forest gamification case](https://trophy.so/blog/forest-gamification-case-study)
- [Beeminder: what it is](https://wiki.beeminder.com/what-is-beeminder.html)
- [Beeminder on loss aversion](https://blog.beeminder.com/aversion/)
- [Ashraf, Karlan, Yin — commitment savings PDF](https://karlan.yale.edu/sites/default/files/tying-odysseus-mast-evidence-commitment-savings-product-philippines.pdf)
- [Octalysis, UZH](https://www.gbl.uzh.ch/quartz/definitions/Octalysis-Framework)
- [Octalysis, Yu-kai Chou](https://yukaichou.com/gamification-examples/octalysis-gamification-framework)
- [Overjustification (Wikipedia)](https://en.wikipedia.org/wiki/Overjustification_effect)
- [Overjustification meta-analytic summary](https://scienceinsights.org/the-overjustification-effect-why-rewards-kill-motivation)
- [Commitment devices overview](https://habitbox.app/blog/commitment-device)

Вторичные Duo (осторожно):

- [Behavioral Design Hub Duolingo teardown](https://zicozhou10.github.io/behavioral-design-hub/teardowns/duolingo)
- [PushPilot Duolingo push teardown](https://pushpilot.ai/blog/duolingo-push-notification-strategy-teardown)
- [Just Another PM: streak psychology](https://www.justanotherpm.com/blog/the-psychology-behind-duolingos-streak-feature)
