# Godot CAS — памятка (RU)

Addon-обёртка над форком [godot-cas](https://github.com/RimuruDev/godot-cas) (CAS.ai SDK 4.7.4,
Android). Подключает нативный синглтон `GodotCas` и через export-плагин добавляет
рекламные SDK, репозитории, разрешения и AdMob App ID — **всё управляется конфигом**
`res://abyss_moth/data/ads/default_ad_config.tres` (`AdConfig`).

Высокоуровневая логика игры (инициализация, награды, consent) — в
`res://abyss_moth/codebase/services/ad/`. См. `docs/abyssmoth/Реклама CAS и награды.md`.

## Что управляется из AdConfig

| Раздел в конфиге | Что делает |
|---|---|
| Режим работы | `LIVE` (реальный CAS) или `SIMULATED` (имитация без SDK/аккаунта) |
| Идентификаторы | CAS Manager ID, AdMob App ID (для манифеста), prod/test |
| Согласие и аудитория | COPPA-аудитория (`setTaggedAudience`), force-testing consent |
| Рекламные сети | вкл/выкл каждой сети медиации (см. ниже) |
| Android-разрешения | AD_ID, READ_PHONE_STATE |

При экспорте `godot_cas_export_plugin.gd` читает этот конфиг и сам формирует список
зависимостей/репозиториев/разрешений. Отдельная «Resolve»-кнопка не нужна — резолв
происходит на сборке.

## Рекламные сети (медиация)

Включаются галочками в `AdConfig` (по умолчанию все включены). Версии адаптеров
заданы в `godot_cas_export_plugin.gd` (`NETWORK_DEPENDENCIES`) и привязаны к версии AAR.

| Ключ | Сеть | Доп. репозиторий |
|---|---|---|
| google | Google AdMob / Ad Manager | — |
| applovin | AppLovin MAX | — |
| unity | Unity Ads / LevelPlay | — |
| ironsource | ironSource | — |
| vungle | Liftoff Monetize (Vungle) | — |
| inmobi | InMobi | — |
| mintegral | Mintegral (⚠️ ВЫКЛ по умолчанию) | dl-maven-android.mintegral.com |
| pangle | Pangle | artifact.bytedance.com |
| bigo | BIGO Ads | — |
| yango | Yango (Yandex) | — |
| facebook | Meta Audience Network | — |
| ysonetwork | YSO Network | ysonetwork s3 |
| cas_exchange | CAS Exchange | — |
| maticoo | Maticoo | — |
| monetrix | Monetrix | — |

Всегда подключаются (ядро): `com.cleveradssolutions:cas-sdk` и
`com.google.android.gms:play-services-ads-identifier`.

Выключение лишних сетей уменьшает размер сборки. Если выключить pangle/ysonetwork —
их доп. репозитории тоже не добавятся.

> ⚠️ **Mintegral выключен по умолчанию.** Его maven-репозиторий
> `dl-maven-android.mintegral.com` не резолвится (NXDOMAIN) и ломает Android-сборку
> (`Could not resolve com.mbridge.msdk.oversea:mbridge_android_sdk`). Включай `net_mintegral`
> только если CAS даст рабочий URL репозитория Mintegral. Остальные 14 сетей собираются.

## Разрешения (Android)

В манифесте самого AAR форка уже есть: `INTERNET`, `ACCESS_NETWORK_STATE`,
`ACCESS_WIFI_STATE`, `AD_ID`. Export-плагин дополнительно может добавить
(управляется `AdConfig`):

- **AD_ID** (`inject_ad_id_permission`, по умолчанию ВКЛ) — `com.google.android.gms.permission.AD_ID`.
  Нужно для рекламного идентификатора. Дубликат с манифестом AAR безвреден (мерджер схлопнет).
- **READ_PHONE_STATE** (`inject_read_phone_state_permission`, по умолчанию ВЫКЛ) —
  чувствительное разрешение. **CAS сам удаляет его** из своего манифеста
  (`tools:node="remove"`), поэтому по умолчанию мы его не добавляем. Включай только
  если поддержка CAS прямо потребует; учти, что из-за `tools:node="remove"` в AAR
  может потребоваться пересборка AAR без этой строки, и сверься с правилами Google Play
  (sensitive permission → нужна декларация).

> AdMob App ID добавляется в `<application>` как `com.google.android.gms.ads.APPLICATION_ID`
> из `AdConfig.production_admob_application_id` (или sample в тестовом режиме).

## Перенос плагина в новый проект

1. Скопируй папку `addons/godot_cas/` в новый проект и включи плагин в Project Settings.
2. Скопируй сервисы `codebase/services/ad/` и создай `AdConfig`-ресурс (или скопируй
   `data/ads/default_ad_config.tres` + `default_reward_catalog.tres`).
3. Укажи путь к конфигу в `ProjectSettings`: `abyss_moth/ads/config_path`
   (по умолчанию `res://abyss_moth/data/ads/default_ad_config.tres`).
4. Настрой `AdConfig` под новый проект: режим, сети, аудиторию, package id/CAS id.
5. Собери — export-плагин сам подтянет нужные зависимости/разрешения.

## Пересборка AAR (новая версия CAS или правки GodotCas.java)

В форке `/Users/rimurutempest/RimuruDev/GodotProjects/godot-cas`:

```bash
bash rebuild_aar.command
# или двойной клик в Finder
```

Скрипт соберёт `godot4` AAR (Gradle 8.7, нужен JDK 17–21 и Android SDK) и положит его
в `release/godot4/` и в `addons/godot_cas/android/` этого проекта (или в `GODOT_CAS_ADDON_DIR`).

После смены версии CAS обнови в `godot_cas_export_plugin.gd`:
- `RELEASE_AAR` (имя файла aar),
- `CORE_DEPENDENCIES` (cas-sdk версия),
- `NETWORK_DEPENDENCIES` (версии адаптеров).

> Godot 3 из форка удалён — поддерживается только Godot 4.

## Данные для регистрации в CAS (этот проект)

- Package id: `com.AbyssMoth.MurderDronesCatClicker`
- Форматы: Interstitial, Rewarded Video
- Ориентация: портретная
- Design for family: нет (COPPA не применяется) → аудитория NOT_CHILDREN
- Максимальный рейтинг рекламы: Mature
