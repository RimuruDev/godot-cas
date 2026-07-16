> ## ⚠️ Abyss Moth fork — read this first
>
> This is a **fork** of [damnedpie/godot-cas](https://github.com/damnedpie/godot-cas),
> maintained by Abyss Moth (RimuruDev) for our own game projects.
>
> **What this fork changes on top of upstream:**
> - Native VPN detection: `isVpnActive()` on both Godot 3 and Godot 4 (alongside the
>   existing `isWifiOrMobileInternetEnabled()`), handy to gate/adjust ad logic on the
>   game side. Ad revenue is geo-dependent, so a VPN skews fill rate and eCPM.
> - The `AD_ID` permission is **declared** rather than stripped — upstream tags it
>   `tools:node="remove"`, but ads need the advertising id on Android 13+.
>   `ACCESS_COARSE_LOCATION` and `READ_PHONE_STATE` stay removed.
> - Godot 4 builds against the current Godot **4.7.1** Android library (upstream: 4.6.3).
> - One double-click updater for macOS / Windows / Linux — see *Rebuilding* below.
> - Tuned for the Abyss Moth ad stack (config-driven mediation/permissions/consent lives
>   in the game project, not here).
>
> **Use at your own risk.** This fork is shaped around Abyss Moth's needs and is **not**
> a general-purpose, supported release — but we do ship it in production and it works fine
> for us. For the canonical, broadly-tested plugin, prefer upstream.

# Godot CAS 4.7.4 (Abyss Moth fork)
[![CAS.AI](https://img.shields.io/badge/CAS.AI_SDK_4.7.4-blue?style=for-the-badge&logoSize=auto)](https://cas.ai/)
[![Godot](https://img.shields.io/badge/Godot%20Engine-4.7.x%20%7C%203.6.x-blue?style=for-the-badge&logo=godotengine&logoSize=auto)](https://godotengine.org/)
[![GitHub License](https://img.shields.io/github/license/damnedpie/godot-cas?style=for-the-badge)](https://github.com/damnedpie/godot-cas/blob/main/LICENSE)

CAS SDK 4.7.4 Android plugin for Godot. Ships both modules:

| Module   | Compiled against                  | Plugin API |
|----------|-----------------------------------|------------|
| `godot4` | `org.godotengine:godot:4.7.1.stable` | v2 |
| `godot3` | `org.godotengine:godot:3.6.2.stable` | v1 |

The compile target is the API the AAR links against, not a floor on your engine version —
`compileOnly` means the plugin binds to whatever Godot ships in your export template.

[**Official Docs**](https://docs.page/cleveradssolutions/docs/general)

## Rebuilding / updating

| Platform | How |
|----------|-----|
| macOS    | double-click `update.command` |
| Windows  | double-click `update.bat` |
| Linux    | `./update.sh` |

All three are thin launchers over `tools/cas.py`, which:

1. reads the CAS SDK version from CAS's live mediation list (and cross-checks it against
   the [CAS-Android releases](https://github.com/cleveradssolutions/CAS-Android/releases),
   ignoring pre-releases);
2. verifies the toolchain — JDK 17–21 (Gradle 8.7 will not run on 22+) and the Android
   SDK, offering to install missing SDK packages;
3. regenerates `GodotCas.gdap` from that mediation list;
4. builds both AARs and installs the Godot 4 one into a game addon;
5. asks — never assumes — before committing, tagging, pushing and publishing a release.

Other entry points:

```bash
python3 tools/cas.py check                # report versions and toolchain, change nothing
python3 tools/cas.py update --no-release   # build and install only
python3 tools/cas.py update --godot4 4.7.1 # move the Godot 4 compile target
python3 tools/cas.py release --bump        # publish, incrementing the fork revision
```

To install into a project, point the tool at its addon once — this file is gitignored, so
personal paths never land in the repo:

```jsonc
// cas.local.json
{ "addon_dir": "/path/to/YourGame/addons/godot_cas/android" }
```

`GODOT_CAS_ADDON_DIR` and `--addon-dir` override it.

### Versioning

`pluginVersionName` tracks the CAS SDK. `pluginVersionCode` is **this fork's** revision: it
resets to 1 when the SDK version moves and increments on every fork rebuild of the same SDK.
It is deliberately never synced from upstream — upstream's revision counts upstream's
rebuilds, not ours. Same for `godotVersion`. Releases are tagged `v<sdk>-rev<n>`.

## Setup

### Project integration

#### Option 1: Manual

1. Add plugin files (.gd, .gdap, .aar) from the `godot4` folder into your project's `android/plugins`.

2. Add `GodotCas.gd` as a singleton (autoload) to your project.

3. Add your Google AdMob ID to `android/build/AndroidManifest.xml`:
	```xml
	<application android:label="@string/godot_project_name_string" android:allowBackup="false" android:isGame="true" android:hasFragileUserData="false" android:requestLegacyExternalStorage="false" tools:ignore="GoogleAppIndexingWarning" android:icon="@mipmap/icon">
			<meta-data
				android:name="com.google.android.gms.ads.APPLICATION_ID"
				android:value="ca-app-pub-YOUR_ADMOB_ID_HERE" />
				<!-- Other metadata... -->
	```

4. Get your `cas_settings[settings_id].json` file from CAS dashboard and put it into `android/build/res/raw` folder.

5. (Optional) Add `com.google.android.gms.permission.AD_ID` permission to your Android export template if you want to use AD ID (which is usually the case). You can also add `android.permission.ACCESS_COARSE_LOCATION` and `android.permission.READ_PHONE_STATE` permissions if your app has real usecases for those (this can improve monetization).

#### Option 2: CAS Gradle plugin

CAS AI provides a Gradle plugin to make integration easier. It injects all the required dependencies, Google AdMob Pub ID, Tenjin (optional) and Ads Identifier (optional) dependencies into your Android build automatically.

To use CAS Gradle plugin, there are some key differences from Manual integration flow that you have to ensure.

1. Make sure that Godot CAS config file (.gdap) doesn't contain any dependencies or repositores:
```
[config]

name="GodotCas"
binary_type="local"
binary="GodotCas.4.6.5.release.aar"

[dependencies]

remote=[]
custom_maven_repos=[]
```

2. Make sure that your `android/build/AndroidManifest.xml` **DOES NOT** contain Google AdMob Pub ID to avoid conflicts with the injection that CAS Gradle plugin will make.

Now, to include CAS Gradle plugin:

1. Go to your `android/build/build.gradle` and add CAS Gradle plugin to the `plugins` section in the top of the file:

```groovy
/ Gradle build config for Godot Engine's Android port.
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
    // CAS Gradle Plugin
    id 'com.cleveradssolutions.gradle-plugin' version "4.6.5"
	//...
	//...
}
```

2. Add the repositories CAS SDK and adapters need to fetch the dependencies (actual informattion [here](https://docs.page/cleveradssolutions/docs/Android#maven-repositories)) into the allProjects / dependencies block:

```groovy
allprojects {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
        maven { url "https://plugins.gradle.org/m2/" }
        maven { url "https://central.sonatype.com/repository/maven-snapshots/"}

        // CAS AI repositories
        maven {
            name = "MintegralAdsRepo"
            url = uri("https://dl-maven-android.mintegral.com/repository/mbridge_android_sdk_oversea")
            content { includeGroup("com.mbridge.msdk.oversea") }
        }
        maven {
            name = "PangleAdsRepo"  
            url = uri("https://artifact.bytedance.com/repository/pangle")
            content { includeGroup("com.pangle.global") }
        }
        maven {
            name = "ChartboostAdsRepo"  
            url = uri("https://cboost.jfrog.io/artifactory/chartboost-ads/")
            content {
                includeGroup("com.chartboost")
                includeGroup("com.iab.omid.library")
            }
        }
        maven {
            name = "YSONetworkRepo"
            url = uri("https://ysonetwork.s3.eu-west-3.amazonaws.com/sdk/android")
            content { includeGroup("com.ysocorp") }
        }
        maven {
            name = "OguryAdsRepo"  
            url = uri("https://maven.ogury.co")
            content {
                includeGroup("co.ogury")
                includeGroup("co.ogury.module")
            }
        }
        maven {
            name = "SmaatoAdsRepo"
            url = uri("https://s3.amazonaws.com/smaato-sdk-releases/")
            content { 
                includeGroup("com.smaato.android.sdk")
                includeGroup("com.verve")
            }
        }
        maven {
            name = "VerveAdsRepo"
            url = uri("https://verve.jfrog.io/artifactory/verve-gradle-release")
            content {
                includeGroup("net.pubnative")
                includeGroup("com.verve")
            }
        }

        // Godot user plugins custom maven repos
        String[] mavenRepos = getGodotPluginsMavenRepos()
        if (mavenRepos != null && mavenRepos.size() > 0) {
            for (String repoUrl : mavenRepos) {
                maven {
                    url repoUrl
                }
            }
        }
    }
}
```

3. Add the `cas{}` configuration block somewhere below `plugins{}` block. Here's an example of configuration for Optimal Ads with Tenjin and Advertising Identifier included:

```groovy
// Gradle build config for Godot Engine's Android port.
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
    // CAS Gradle Plugin
    id 'com.cleveradssolutions.gradle-plugin' version "4.6.5"
}

cas {
    includeOptimalAds = true
    includeTenjinSDK = true
    useAdvertisingId = true
}
```

Note that you don't need to specify casId here due to it usually being your package name (e.g. "com.yourstudio.yourgame") and it is specified by Godot Android build as applicationId which CAS Gradle plugin fetches on its own.

### Ad network adapters

This plugin's configuration file `GodotCas.gdap` contains all adapters out of the box (excluding beta and cross-promo). Usually it's not desirable because your app may be not making use of all of them and having unnecessary adapters present will increase build size. Feel free to add/remove adapters and their repositories according to your needs.

Make sure to check out [**this list of adapters**](https://github.com/cleveradssolutions/CAS-Android/tree/master/Adapters#casai-mediation-adapters) and also [**this guide page**](https://docs.page/cleveradssolutions/docs/Android/Manual-setup) from CAS official wiki.

Also check `adapters-list.txt` for precise dependencies and repositories for Optimal and Families presets.

### Other optional dependencies

`com.google.android.gms:play-services-ads-identifier` dependency is required if you want to use AD ID (which is usually the case).

`com.tenjin:android-sdk` dependency would be necessary if you want to enable automatic revenue reporting for Tenjin. [**See this wiki page for more details**](https://docs.page/cleveradssolutions/docs/Android/Impression-Level-Data#tenjin).

## Initialization

Wrapper script `GodotCas.gd` has `initialize()` method which you are supposed to edit and then call in runtime. There are some methods that tweak initialization options for the SDK, and you have to call them before `initializeCAS()` is executed. Each method in the wrapper is documented by a comment, so make sure to inspect it.

### Initialization settings

All methods below should come before `initializeCAS()` if called.

```gdscript
# Mandatory. Sets CAS ID (usually your app package or bundle ID).
# Not setting the ID before initializeCas() will lead to plugin crash.
setCasId(id:String) -> void

# CAS built in consent manager is enabled by default, but you can disable it.
# It's still recommended to use their consent manager, so better leave it be.
setUseBuiltInConsentManager(enabled:bool) -> void

# If enabled, turns test ads mode on.
setTestAdMode(enabled:bool) -> void

# See https://docs.page/cleveradssolutions/docs/Android/Impression-Level-Data#automatic-collect-ad-revenue
# If using this, make sure you have TenjinSDK dependency in GodotCas.gdap configuration.
setTenjinKey(key:String) -> void

# See https://docs.page/cleveradssolutions/docs/Android/Additional-Meta-AudienceNetwork-steps
setFacebookLDU(enabled:bool) -> void
```

### Testing and debugging

```gdscript
# Debug Mode displays debug info with log tag "CAS". Disabled by default for performance.
setDebugMode(enabled:bool) -> void

# Adds testing device ID.
# see https://docs.page/cleveradssolutions/docs/Android/Enabling-test-ads#enable-test-devices
addTestDeviceId(id:String) -> void
```

## Working with user data consent

[**Official wiki page**](https://docs.page/cleveradssolutions/docs/Android/User-Consent-Flow)

### Automatic flow

CAS SDK provides automated consent screen workflow with their own consent screen.

```gdscript
# Shows consent manager if it is required (e.g. based on user's geo).
showConsentManagerIfRequired() -> void

# Force-shows the consent manager.
showConsentManager() -> void
```

### Manual flow

In case you use your own consent screen, consent status can be set via these methods:

```gdscript
enum CONSENT_STATUS {
	UNDEFINED = 0
	ACCEPTED = 1
	DENIED = 2
}

# Use this if using your own consent manager. See CONSENT_STATUS enum.
setConsentStatus(status:int) -> void

enum CCPA_STATUS {
	UNDEFINED = 0
	OPT_OUT_SALE = 1
	OPT_IN_SALE = 2
}

# Use this if using your own consent manager. See CCPA_STATUS enum.
setCcpaStatus(status:int) -> void
```

### Testing consent flow
You can also test consent screen behavior to make sure everything works as intended.

```gdscript
# Returns possible consent flow statuses as String : int dict for lookup.
getPossibleConsentFlowStatuses() -> Dictionary

# Returns possible debug geographies as String : int dict for lookup.
getPossibleDebugGeographies() -> Dictionary

# Sets debug geography for consent manager testing.
# Will have no effect unless force testing is enabled for consent manager.
setConsentDebugGeography(geography:int) -> void

# Enabled forced testing for consent manager.
setConsentForceTesting(enabled:bool) -> void
```

## Children-directed treatment
[**Official wiki page**](https://docs.page/cleveradssolutions/docs/Android/Initialize-CAS#prohibition-on-personal-information-from-children)

Developers who have knowledge of specific individuals as being COPPA-applicable should make use of the API discussed below to inform CAS and all downstream consumers of this information.

```gdscript
enum AUDIENCE {
	UNDEFINED = 0
	CHILDRED = 1
	NOT_CHILDREN = 2
}

# Specify what audience is the user in. See AUDIENCE enum.
setTaggedAudience(audienceType:int) -> void

```

## Ad types

This plugin supports Interstitial, Rewarded, Banner and App Open ad types. Native ad type is not currently implemented due to having extremely few use cases in games.

Every ad-type has a corresponding initialization function: `initializeInterstitial()`, `initializeRewarded()` and so on. Make sure you call such a function before calling other methods relevant to an ad type.

### Interstitial
[**Official wiki page** ](https://docs.page/cleveradssolutions/docs/Android/Interstitial-Ads)

```gdscript
# Initializes the CASInterstitial object in the plugin and creates callbacks.
initializeInterstitial() -> void

# Loads the interstitial ad.
loadInterstitial() -> void

# Returns false is ad is not loaded yet or the CASInterstitial object hasn't been initialized.
isInterstitialLoaded() -> bool

# Shows the interstitial ad.
showInterstitial() -> void

# Destroys the interstitial ad instance.
destroyInterstitial() -> void

# Sets autoloading for interstitials, disabled by default.
setAutoloadInterstitial(enabled:bool) -> void

# Sets an interval between interstitial ad shows prohibiting ads from showing during it.
setMinIntervalInterstitial(seconds:int) -> void

# Restarts the interval specified by setMinIntervalInterstitial().
restartIntervalInterstitial() -> void
```

### Rewarded
[**Official wiki page**](https://docs.page/cleveradssolutions/docs/Android/Rewarded-Ads)
```gdscript
# Initializes the CASRewarded object in the plugin and creates callbacks.
initializeRewarded() -> void

# Loads the rewarded ad.
loadRewarded() -> void

# Returns false is ad is not loaded yet or the CASRewarded object hasn't been initialized.
isRewardedLoaded() -> bool

# Shows the rewarded ad.
showRewarded() -> void

# Destroys the rewarded ad instance.
destroyRewarded() -> void

# Sets autoloading for rewarded, disabled by default.
setAutoloadRewarded(enabled:bool) -> void

# Enabled by default. Sets if an interstitial ad should be displayed in case there is no-fill for rewarded.
setRewardedExtraFillInterstitial(enabled:bool) -> void
```

### Banner
[**Official wiki page**](https://docs.page/cleveradssolutions/docs/Android/Banner-Ads)
```gdscript
# Initializes CASBannerView. See BANNER_SIZE enum.
# Also see https://docs.page/cleveradssolutions/docs/Android/Banner-Ads#create-ad-view
initializeBanner(bannerSize:int) -> void

# Initializes CASBannerView with adaptive size.
# See https://docs.page/cleveradssolutions/docs/Android/Banner-Ads#get-the-ad-size
initializeAdaptiveBanner(maxWidthDpi:int) -> void

# Loads the banner ad.
loadBanner() -> void

# Returns false if ad is not loaded yet or the CASBannerView object hasn't been initialized.
isBannerLoaded() -> bool

# Sets banner visibility.
setBannerVisible(isVisible:bool) -> void

# Destroys the banner ad instance.
destroyBanner() -> void

# Sets autoloading for banner. Enabled by default.
setAutoloadBanner(enabled:bool) -> void

# Sets banner refresh interval. Should be longer than 10 seconds, 30 considered optimal (default).
setBannerRefreshInterval(seconds:int) -> void

# Disables ad refresh for banner.
disableBannerAdRefresh() -> void

# Sets banner position in device's actual viewport.
setBannerPosition(posX:float, posY:float) -> void

# Returns banner width in device's actual viewport.
getBannerWidth() -> int

# Returns banner height in device's actual viewport.
getBannerHeight() -> int
```

### App Open ads
[**Official wiki page**](https://docs.page/cleveradssolutions/docs/Android/App-Open-Ads)
```gdscript
# Initializes the CASAppOpen object in the plugin and creates callbacks.
initializeAppOpenAd() -> void

# Loads the AppOpen ad.
loadAppOpenAd() -> void

# Returns false if ad is not loaded yet or the CASAppOpen object hasn't been initialized.
isAppOpenAdLoaded() -> bool

# Shows the AppOpen ad.
showAppOpenAd() -> void

# Destroys the AppOpen ad instance.
destroyAppOpenAd() -> void

# Sets autoloading for AppOpen ad, disabled by default.
setAutoloadAppOpenAd(enabled:bool) -> void

# Sets autoshowing for AppOpen ad, disabled by default.
setAutoshowAppOpenAd(enabled:bool) -> void
```

## IAP logging with Tenjin

You can log in-app purchase events to Tenjin with this plugin. Just make sure to obtain the necessary `purchase` data from Godot Google Play Billing Library Plugin.

You will probably be calling this from inside `purchases_updated` signal of Billing Plugin, but I strongly advise you call logging with some delay (like 2 seconds). Reason being, TenjinSDK might be suspended in this particular moment and there's a possibility that your logging attempt won't go through.

Make sure that Tenjin dependency is present in plugins GDAP file.

More info on data required can be found in [Tenjin docs](https://docs.tenjin.com/docs/android-sdk#purchase-events)
```gdscript
# Data for arguments is supposed to be obtained from Google Billing Library plugin for Godot.
# CAS should be initialized with Tenjin key for this to work (might cause crash otherwise).
logTenjinPurchaseEvent(sku:String, currencyCode:String, quantity:int, price:float, originalJson:String, signature:String) -> void
```

## Targeting options

[**Official wiki page**](https://docs.page/cleveradssolutions/docs/Android/Targeting-options)

```gdscript
# See https://docs.page/cleveradssolutions/docs/Android/Targeting-options#user-id
setUserID(userID:String) -> void

# See https://docs.page/cleveradssolutions/docs/Android/Targeting-options#user-age
setUserAge(age:int) -> void

enum GENDER {
	UNKNOWN = 0,
	MALE = 1,
	FEMALE = 2
}

# See GENDER enum for the argument.
# See https://docs.page/cleveradssolutions/docs/Android/Targeting-options#user-gender
setUserGender(gender:int) -> void

# See https://docs.page/cleveradssolutions/docs/Android/Targeting-options#user-location-auto-collection
setUserLocationAutocollection(enabled:bool) -> void

# See https://docs.page/cleveradssolutions/docs/Android/Targeting-options#app-keywords
setUserAppKeywords(keywords:PoolStringArray) -> void

# See https://docs.page/cleveradssolutions/docs/Android/Targeting-options#app-content-url
setAppContentUrl(contentUrl:String) -> void
```

## Utilities

CAS SDK can output integration status to logcat, displaying what adapters are integrated or not.
```gdscript
# Call Integration Helper and check current integration in logcat. LOG TAG: CASIntegrationHelper
validateIntegration() -> void
```

You can check if user has WIFI/Mobile traffic enabled on their device. This DOES NOT guarantee a working internet connection and only checks the status of WIFI and mobile traffic enabled in Android. For example, if user is connected to a WIFI but this WIFI doesn't give access to Internet, this will still return true.
```gdscript
# Returns true if the device has WIFI or Mobile traffic enabled. This doesn't guarantee real internet connection.
isWifiOrMobileInternetEnabled() -> bool

```
