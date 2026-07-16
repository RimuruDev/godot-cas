# Godot CAS 4.7.4 — форк Abyss Moth (RU)

> ## ⚠️ Прочитай сначала
>
> Это **форк** репозитория [damnedpie/godot-cas](https://github.com/damnedpie/godot-cas),
> который ведёт Abyss Moth (RimuruDev) под свои игровые проекты.
>
> **Use at your own risk.** Форк заточен под нужды Abyss Moth и **не** является
> общим поддерживаемым релизом. Но мы используем его в проде, и у нас всё работает.
> Если нужен «канонический» широко протестированный плагин — берите оригинал.

Плагин CAS.ai SDK 4.7.4 для Godot (Android). Собираются оба модуля:

| Модуль   | Компилируется против                 | Plugin API |
|----------|--------------------------------------|------------|
| `godot4` | `org.godotengine:godot:4.7.1.stable` | v2 |
| `godot3` | `org.godotengine:godot:3.6.2.stable` | v1 |

Версия компиляции — это API, против которого слинкован AAR, а не нижняя граница движка:
зависимость `compileOnly`, поэтому плагин связывается с тем Godot, который лежит в твоём
export-шаблоне. [Официальная дока CAS](https://docs.page/cleveradssolutions/docs/general).

## Чем этот форк отличается от оригинала

| Новшество | Зачем |
|---|---|
| `isVpnActive()` в godot3 и godot4 | Нативное определение VPN (в дополнение к `isWifiOrMobileInternetEnabled()`). Доход с рекламы зависит от гео, поэтому VPN перекашивает fill rate и eCPM — это стоит уметь замечать |
| `AD_ID` объявлен, а не вырезан | Upstream глушит его через `tools:node="remove"`, но на Android 13+ без него реклама не получит рекламный идентификатор. `ACCESS_COARSE_LOCATION` и `READ_PHONE_STATE` остаются вырезанными |
| Godot 4.7.1 | Upstream собирает против 4.6.3 |
| Обновлялка в один двойной клик | macOS / Windows / Linux — см. ниже |
| Заточка под Abyss Moth | Конфиг-driven медиация/разрешения/consent живут в игровом проекте, а не здесь |

Всё остальное — как в оригинале (CAS SDK 4.7.4): Interstitial, Rewarded, Banner, App Open,
consent flow, COPPA/audience, Tenjin и т.д. Новых публичных методов, кроме `isVpnActive()`,
форк не добавляет.

## Пересборка / обновление

### Быстрый старт

| Платформа | Двойной клик     | Из терминала |
|-----------|------------------|--------------|
| macOS     | `update.command` | `./update.sh` или `python3 tools/cas.py update` |
| Windows   | `update.bat`     | `py -3 tools\cas.py update` |
| Linux     | —                | `./update.sh` или `python3 tools/cas.py update` |

Лаунчеры — тонкие обёртки: находят Python и передают управление в `tools/cas.py`.
`update.command` и `update.bat` дополнительно держат окно открытым, чтобы можно было
прочитать результат. Всё, что ниже, работает одинаково на всех трёх платформах.

### Что делает `update`

1. Берёт версию CAS SDK из живого списка медиации CAS и сверяет её с
   [релизами CAS-Android](https://github.com/cleveradssolutions/CAS-Android/releases),
   игнорируя пре-релизы.
2. Проверяет тулчейн и предлагает доустановить недостающие пакеты Android SDK.
3. Перегенерирует `GodotCas.gdap` из этого же списка.
4. Собирает оба AAR и ставит godot4-версию в аддон игры.
5. **Спрашивает** перед коммитом, тегом, пушем и публикацией — молча ничего не делает.

Почему список медиации, а не релизы GitHub: версии адаптеров привязаны именно к нему.
Если CAS-Android выложил 4.7.5, а список ещё отдаёт 4.7.4 — адаптеров под 4.7.5 ещё нет,
и пиниться на неё рано. Инструмент проверяет оба источника и предупредит о расхождении.

### Команды

| Команда   | Что делает |
|-----------|------------|
| `check`   | Показать версии и тулчейн. Ничего не меняет. |
| `update`  | Собрать оба AAR, поставить в аддон, предложить публикацию. Именно она запускается при двойном клике. |
| `release` | Собрать зип, закоммитить, затегать, запушить, создать GitHub release. |

### Опции

| Опция               | К чему    | Смысл |
|---------------------|-----------|-------|
| `--yes`             | ко всем   | Отвечать «да» на все вопросы. На реальных ошибках всё равно остановится. |
| `--no-release`      | `update`  | Только собрать и поставить, публикацию не предлагать. |
| `--cas <ver>`       | `update`  | Форсировать версию CAS SDK вместо той, что в списке медиации. Даунгрейд переспросит. |
| `--godot4 <ver>`    | `update`  | Сменить версию компиляции Godot 4, например `4.7.1`. Сначала проверяется наличие на Maven Central. |
| `--godot3 <ver>`    | `update`  | Сменить версию компиляции Godot 3, например `3.6.2`. |
| `--addon-dir <dir>` | `update`  | Ставить в этот каталог `addons/godot_cas/android`. |
| `--bump`            | `release` | Увеличить ревизию форка перед публикацией. |

```bash
python3 tools/cas.py check                   # версии и тулчейн, без изменений
python3 tools/cas.py update --no-release     # только собрать и поставить
python3 tools/cas.py update --godot4 4.7.1   # сменить версию компиляции Godot 4
python3 tools/cas.py release --bump          # опубликовать, увеличив ревизию форка
```

### Что нужно на машине

| Что          | Версия  | Примечание |
|--------------|---------|------------|
| JDK          | 17–21   | Gradle 8.7 **не запустится** на 22+. Инструмент сам ищет подходящий JDK и скажет, если его нет. |
| Android SDK  | platform 35, build-tools 35.0.0 | Недостающие пакеты предложит доставить через `sdkmanager`. |
| Python       | 3.9+    | Только стандартная библиотека, `pip install` не нужен. Проверено на 3.9 и 3.14. |

```bash
# macOS
brew install --cask temurin@21          # JDK; python3 идёт с Xcode CLT либо `brew install python`
# Linux
sdk install java 21-tem                 # либо пакет temurin-21-jdk из репозитория дистрибутива
# Windows
# JDK: https://adoptium.net/temurin/releases/?version=21
# Python: https://www.python.org/downloads/ (отметить «Add python.exe to PATH»)
```

Android SDK ставится через Android Studio либо через command line tools. `ANDROID_HOME`
учитывается; если не задан — берётся путь по умолчанию для платформы
(`~/Library/Android/sdk` на macOS, `~/Android/Sdk` на Linux,
`%LOCALAPPDATA%\Android\Sdk` на Windows).

### Установка в свой проект

Путь к аддону указывается один раз. Файл в `.gitignore`, поэтому личные пути в репозиторий
не попадают:

```jsonc
// cas.local.json
{ "addon_dir": "/path/to/YourGame/addons/godot_cas/android" }
```

Приоритет: `--addon-dir` → `GODOT_CAS_ADDON_DIR` → `cas.local.json`. Если не задано ничего,
инструмент попробует сам найти единственный соседний проект с `addons/godot_cas/android`;
не нашёл — шаг установки пропускается, AAR останутся в `release/`.

При установке заодно переписываются `godot_cas_export_plugin.gd`, `plugin.cfg` и
`README_RU.md` в проекте, чтобы прибитые там версии адаптеров совпадали с AAR.

## Версии

| Компонент              | Версия          | Где задано |
|------------------------|-----------------|------------|
| CAS SDK                | 4.7.4           | `build.gradle` → `pluginVersionName` |
| Ревизия форка          | 2               | `build.gradle` → `pluginVersionCode` |
| Godot 4, версия компиляции | 4.7.1.stable | `godot4/build.gradle` → `ext.godotVersion` |
| Godot 3, версия компиляции | 3.6.2.stable | `godot3/build.gradle` → `ext.godotVersion` |
| compileSdk / targetSdk | 35              | `godot*/build.gradle` |
| minSdk                 | 24              | `godot*/build.gradle` |
| Java source/target     | 17              | `godot*/build.gradle` |
| NDK                    | 28.1.13356709   | `godot*/build.gradle` |
| Build tools            | 35.0.0          | `godot*/build.gradle` |
| Android Gradle Plugin  | 8.6.1           | `godot*/build.gradle` |
| Gradle                 | 8.7             | `gradle/wrapper/gradle-wrapper.properties` |

`pluginVersionName` следует за версией CAS SDK. `pluginVersionCode` — ревизия **этого
форка**: сбрасывается в 1 при смене версии SDK и растёт на каждую пересборку форка на той
же SDK. Он намеренно **не** синхронизируется с upstream — там счётчик считает их
пересборки, а не наши. То же самое с `godotVersion`. Теги релизов — `v<sdk>-rev<n>`,
то есть текущий это `v4.7.4-rev2`.

## Что использовать — оригинал или форк?

- **Оригинал** ([damnedpie/godot-cas](https://github.com/damnedpie/godot-cas)) — если нужен
  «эталонный» плагин без наших правок.
- **Этот форк** — если хочешь определение VPN из коробки, свежий Godot и обновлялку в один
  клик. На свой страх и риск, но у нас работает.

## Установка / API

Подробности по установке и полный список методов — в основном `README.md` (EN).
