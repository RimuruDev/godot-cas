# Godot CAS 4.7.3 — форк Abyss Moth (RU)

> ## ⚠️ Прочитай сначала
>
> Это **форк** репозитория [damnedpie/godot-cas](https://github.com/damnedpie/godot-cas),
> который ведёт Abyss Moth (RimuruDev) под свои игровые проекты.
>
> **Godot 3 здесь НЕ поддерживается.** Модуль `godot3` удалён — форк только под Godot 4.
> Нужна поддержка Godot 3 — берите оригинал: https://github.com/damnedpie/godot-cas
>
> **Use at your own risk.** Форк заточен под нужды Abyss Moth и **не** является
> общим поддерживаемым релизом. Но мы используем его в проде, и у нас всё работает.
> Если нужен «канонический» широко протестированный плагин — берите оригинал.

Плагин CAS.ai SDK 4.7.3 для Godot (Android). Собирается под Godot 4.6.x.
[Официальная дока CAS](https://docs.page/cleveradssolutions/docs/general).

## Чем этот форк отличается от оригинала

| Новшество | Зачем |
|---|---|
| `isVpnActive()` | Нативное определение VPN (в дополнение к `isWifiOrMobileInternetEnabled()`) — удобно подстраивать рекламную логику на стороне игры |
| Удалён `godot3` | Легче, только Godot 4 |
| `rebuild_aar.command` | Одной командой пересобрать Godot 4 AAR (Gradle 8.7, JDK 17–22) и положить в addon проекта |
| Заточка под Abyss Moth | Конфиг-driven медиация/разрешения/consent живут в игровом проекте, а не здесь |

Всё остальное — как в оригинале (CAS SDK 4.7.3): Interstitial, Rewarded, Banner, App Open,
consent flow, COPPA/audience, Tenjin и т.д. Новых публичных методов, кроме `isVpnActive()`,
форк не добавляет.

## Что использовать — оригинал или форк?

- **Оригинал** ([damnedpie/godot-cas](https://github.com/damnedpie/godot-cas)) — если нужен
  Godot 3, либо «эталонный» плагин без наших правок.
- **Этот форк** — если ты под Godot 4 и хочешь определение VPN из коробки + готовый
  скрипт пересборки AAR. На свой страх и риск, но у нас работает.

## Пересборка AAR

```bash
bash rebuild_aar.command   # или двойной клик в Finder
```

Собирает `godot4` AAR и кладёт его в `release/godot4/` и в addon проекта
(`addons/godot_cas/android/`, либо в `GODOT_CAS_ADDON_DIR`). Требуется Android SDK и
JDK 17–22 (Gradle 8.7 не дружит с JDK 25).

После смены версии CAS обнови версию в `build.gradle` (`pluginVersionName`) и версии
адаптеров на стороне проекта (в export-плагине игры).

## Установка / API

Подробности по установке и полный список методов — в основном `README.md` (EN).
