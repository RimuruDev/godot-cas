@tool
extends EditorPlugin

var _android_export_plugin: EditorExportPlugin


func _enter_tree() -> void:
	_android_export_plugin = GodotCasAndroidExportPlugin.new()
	add_export_plugin(_android_export_plugin)


func _exit_tree() -> void:
	if _android_export_plugin != null:
		remove_export_plugin(_android_export_plugin)
		_android_export_plugin = null


class GodotCasAndroidExportPlugin:
	extends EditorExportPlugin

	const PLUGIN_NAME := "GodotCas"
	const RELEASE_AAR := "godot_cas/android/GodotCas.4.7.4.release.aar"
	const ADS_CONFIG_PATH_SETTING := "abyss_moth/ads/config_path"
	const DEFAULT_ADS_CONFIG_PATH := "res://abyss_moth/data/ads/default_ad_config.tres"
	const LEGACY_ADMOB_APPLICATION_ID_SETTING := "abyss_moth/ads/admob_application_id"
	const SAMPLE_ADMOB_APPLICATION_ID := "ca-app-pub-3940256099942544~3347511713"

	# Версии адаптеров привязаны к версии AAR (GodotCas 4.7.4). Обновлять вместе с aar.
	const CORE_DEPENDENCIES := [
		"com.google.android.gms:play-services-ads-identifier:18.1.0",
		"com.cleveradssolutions:cas-sdk:4.7.4",
	]
	const NETWORK_DEPENDENCIES := {
		"google": "com.cleveradssolutions:google:25.2.0.4",
		"applovin": "com.cleveradssolutions:applovin:13.6.3.0",
		"unity": "com.cleveradssolutions:unity:4.18.1.0",
		"ironsource": "com.cleveradssolutions:ironsource:9.4.3.1",
		"vungle": "com.cleveradssolutions:vungle:7.7.4.1",
		"inmobi": "com.cleveradssolutions:inmobi:11.3.0.2",
		"mintegral": "com.cleveradssolutions:mintegral:17.1.61.2",
		"pangle": "com.cleveradssolutions:pangle:8.1.0.4",
		"bigo": "com.cleveradssolutions:bigo:5.9.0.0",
		"yango": "com.cleveradssolutions:yango:8.1.0.0",
		"facebook": "com.cleveradssolutions:facebook:6.21.0.1",
		"ysonetwork": "com.cleveradssolutions:ysonetwork:1.3.6.0",
		"cas_exchange": "com.cleveradssolutions:cas-exchange:4.6.6",
		"maticoo": "com.cleveradssolutions:maticoo:1.8.6.3",
		"monetrix": "com.cleveradssolutions:monetrix:1.2.0.2",
	}
	# Доп. maven-репозитории, нужные только если включена соответствующая сеть.
	const NETWORK_REPOS := {
		"mintegral": "https://dl-maven-android.mintegral.com/repository/mbridge_android_sdk_oversea",
		"pangle": "https://artifact.bytedance.com/repository/pangle",
		"ysonetwork": "https://ysonetwork.s3.eu-west-3.amazonaws.com/sdk/android",
	}
	const ALL_NETWORK_KEYS := [
		"google", "applovin", "unity", "ironsource", "vungle", "inmobi", "mintegral",
		"pangle", "bigo", "yango", "facebook", "ysonetwork", "cas_exchange", "maticoo", "monetrix",
	]


	func _get_name() -> String:
		return PLUGIN_NAME


	func _supports_platform(platform: EditorExportPlatform) -> bool:
		return platform is EditorExportPlatformAndroid


	func _export_begin(_features: PackedStringArray, is_debug: bool, path: String, _flags: int) -> void:
		# В release AdConfig авто-форсит боевой режим (LIVE/PRODUCTION) на рантайме,
		# поэтому переключать ничего не нужно. Просто информируем, если в конфиге стоит TEST/SIMULATED.
		if is_debug:
			return

		var config := _load_ads_config()

		if config != null and config.has_method(&"is_production_build"):
			print("[GodotCas] RELEASE-экспорт (%s): реклама запустится в боевом режиме (LIVE/PRODUCTION) автоматически, тест/симуляция в конфиге игнорируются." % path)


	func _load_ads_config() -> Resource:
		var config_path := str(ProjectSettings.get_setting(
			ADS_CONFIG_PATH_SETTING,
			DEFAULT_ADS_CONFIG_PATH
		)).strip_edges()

		if config_path.is_empty():
			return null

		return ResourceLoader.load(config_path)


	func _get_android_libraries(_platform: EditorExportPlatform, _debug: bool) -> PackedStringArray:
		return PackedStringArray([RELEASE_AAR])


	func _get_android_dependencies(_platform: EditorExportPlatform, _debug: bool) -> PackedStringArray:
		var dependencies := PackedStringArray(CORE_DEPENDENCIES)

		for network_key in _get_enabled_networks():
			if NETWORK_DEPENDENCIES.has(network_key):
				dependencies.append(NETWORK_DEPENDENCIES[network_key])

		return dependencies


	func _get_android_dependencies_maven_repos(_platform: EditorExportPlatform, _debug: bool) -> PackedStringArray:
		var repos := PackedStringArray()

		for network_key in _get_enabled_networks():
			if NETWORK_REPOS.has(network_key):
				repos.append(NETWORK_REPOS[network_key])

		return repos


	func _get_android_manifest_element_contents(_platform: EditorExportPlatform, _debug: bool) -> String:
		var config := _load_ads_config()
		var contents := ""

		if _config_bool(config, &"inject_ad_id_permission", true):
			contents += '\n    <uses-permission android:name="com.google.android.gms.permission.AD_ID" />'

		if _config_bool(config, &"inject_read_phone_state_permission", false):
			contents += '\n    <uses-permission android:name="android.permission.READ_PHONE_STATE" />'

		return contents


	# Список включённых сетей из конфига; если конфига/метода нет — все сети (как раньше).
	func _get_enabled_networks() -> Array:
		var config := _load_ads_config()

		if config != null and config.has_method(&"get_enabled_ad_networks"):
			return Array(config.call(&"get_enabled_ad_networks"))

		return ALL_NETWORK_KEYS


	func _config_bool(config: Resource, key: StringName, default_value: bool) -> bool:
		if config != null and key in config:
			return bool(config.get(key))

		return default_value


	func _get_android_manifest_application_element_contents(
		_platform: EditorExportPlatform,
		debug: bool
	) -> String:
		var application_id := _get_admob_application_id(debug)

		if application_id.is_empty():
			return ""

		return (
			'\n        <meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" '
			+ 'android:value="%s" />'
		) % application_id


	func _get_admob_application_id(is_debug_export: bool) -> String:
		var config_path := str(ProjectSettings.get_setting(
			ADS_CONFIG_PATH_SETTING,
			DEFAULT_ADS_CONFIG_PATH
		)).strip_edges()
		var config := ResourceLoader.load(config_path) if not config_path.is_empty() else null
		var application_id := ""

		# В release-экспорте подставляем БОЕВОЙ admob id (не тестовый), даже если в конфиге TEST.
		if config != null and config.has_method(&"get_admob_application_id_for_export"):
			application_id = str(config.call(&"get_admob_application_id_for_export", is_debug_export)).strip_edges()
		elif config != null and config.has_method(&"get_admob_application_id"):
			application_id = str(config.call(&"get_admob_application_id")).strip_edges()

		if application_id.is_empty():
			application_id = str(ProjectSettings.get_setting(
				LEGACY_ADMOB_APPLICATION_ID_SETTING,
				SAMPLE_ADMOB_APPLICATION_ID
			)).strip_edges()

		if application_id.is_empty():
			return SAMPLE_ADMOB_APPLICATION_ID

		return application_id
