import immutabledict
import re

apps_dict = {
    "桌面": "com.google.android.apps.nexuslauncher",
    "Spotify": "com.spotify.music",
    "Contacts": "com.google.android.contacts",
    "Settings": "com.android.settings",
    "Setting": "com.android.settings",
    "Android-System-Setting": "com.android.settings",
    "设置": "com.android.settings",
    "Clock": "com.google.android.deskclock",
    "TikTok": "com.zhiliaoapp.musically",
    "Clash": "com.github.kr328.clash",
    "Amazon Shopping": "com.amazon.mShop.android.shopping",
    "AmazonShopping": "com.amazon.mShop.android.shopping",
    "Snapchat": "com.snapchat.android",
    "Slack": "com.Slack",
    "Uber": "com.ubercab",
    "Reddit": "com.reddit.frontpage",
    "Twitter": "com.twitter.android",
    "X": "com.twitter.android",
    "Quora": "com.quora.android",
    "Zoom": "us.zoom.videomeetings",
    "Booking": "com.booking",
    "Instagram": "com.instagram.android",
    "Facebook": "com.facebook.katana",
    "WhatsApp": "com.whatsapp",
    "Google_Maps": "com.google.android.apps.maps",
    "GoogleMap": "com.google.android.apps.maps",
    "YouTube": "com.google.android.youtube",
    "Netflix": "com.netflix.mediaclient",
    "LinkedIn": "com.linkedin.android",
    "Google Drive": "com.google.android.apps.docs",
    "GoogleDrive": "com.google.android.apps.docs",
    "Gmail": "com.google.android.gm",
    "Chrome": "com.android.chrome",
    "Twitch": "tv.twitch.android.app",
    "Wechat": "com.tencent.mm",
    "微信": "com.tencent.mm",
    "高德地图": "com.autonavi.minimap",
    "高德": "com.autonavi.minimap",
    "美团": "com.sankuai.meituan",
    "meituan": "com.sankuai.meituan",
    "Calendar": "com.skuld.calendario",
    "weather": "org.breezyweather",
    "Map.me": "com.mapswithme.maps.pro",
    "Map": "com.mapswithme.maps.pro",
    "bleucoins": "com.rammigsoftware.bluecoins",
    "Cantook": "com.aldiko.android",
    "PiMusicPlayer": "com.Project100Pi.themusicplayer",
    "Firefox": "org.mozilla.firefox",
    "simple_notepad": "org.mightyfrog.android.simplenotepad",
    #"tasks": "com.tarento.tasks",
    "vlc": "org.videolan.vlc",
}

_PATTERN_TO_ACTIVITY = immutabledict.immutabledict({
    'google chrome|chrome': (
        'com.android.chrome/com.google.android.apps.chrome.Main'
    ),
    'google chat': 'com.google.android.apps.dynamite/com.google.android.apps.dynamite.startup.StartUpActivity',
    'settings|system settings': 'com.android.settings/.Settings',
    'youtube|yt': 'com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity',
    'google play|play store|gps': (
        'com.android.vending/com.google.android.finsky.activities.MainActivity'
    ),
    'gmail|gemail|google mail|google email|google mail client': (
        'com.google.android.gm/.ConversationListActivityGmail'
    ),
    'google maps|gmaps|maps|google map': (
        'com.google.android.apps.maps/com.google.android.maps.MapsActivity'
    ),
    'google photos|gphotos|photos|google photo|google pics|google images': 'com.google.android.apps.photos/com.google.android.apps.photos.home.HomeActivity',
    'google calendar|gcal': (
        'com.google.android.calendar/com.android.calendar.AllInOneActivity'
    ),
    'camera': 'com.android.camera2/com.android.camera.CameraLauncher',
    'audio recorder': 'com.dimowner.audiorecorder/com.dimowner.audiorecorder.app.welcome.WelcomeActivity',
    'google drive|gdrive|drive': (
        'com.google.android.apps.docs/.drive.startup.StartupActivity'
    ),
    'google keep|gkeep|keep': (
        'com.google.android.keep/.activities.BrowseActivity'
    ),
    'grubhub': (
        'com.grubhub.android/com.grubhub.dinerapp.android.splash.SplashActivity'
    ),
    'tripadvisor': 'com.tripadvisor.tripadvisor/com.tripadvisor.android.ui.launcher.LauncherActivity',
    'starbucks': 'com.starbucks.mobilecard/.main.activity.LandingPageActivity',
    'google docs|gdocs|docs': 'com.google.android.apps.docs.editors.docs/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'google sheets|gsheets|sheets': 'com.google.android.apps.docs.editors.sheets/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'google slides|gslides|slides': 'com.google.android.apps.docs.editors.slides/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'clock': 'com.google.android.deskclock/com.android.deskclock.DeskClock',
    'google search|google': 'com.google.android.googlequicksearchbox/com.google.android.googlequicksearchbox.SearchActivity',
    'contacts': 'com.google.android.contacts/com.android.contacts.activities.PeopleActivity',
    'facebook|fb': 'com.facebook.katana/com.facebook.katana.LoginActivity',
    'whatsapp|wa': 'com.whatsapp/com.whatsapp.Main',
    'instagram|ig': (
        'com.instagram.android/com.instagram.mainactivity.MainActivity'
    ),
    'twitter|tweet': 'com.twitter.android/com.twitter.app.main.MainActivity',
    'snapchat|sc': 'com.snapchat.android/com.snap.mushroom.MainActivity',
    'telegram|tg': 'org.telegram.messenger/org.telegram.ui.LaunchActivity',
    'linkedin': (
        'com.linkedin.android/com.linkedin.android.authenticator.LaunchActivity'
    ),
    'spotify|spot': 'com.spotify.music/com.spotify.music.MainActivity',
    'netflix': 'com.netflix.mediaclient/com.netflix.mediaclient.ui.launch.UIWebViewActivity',
    'amazon shopping|amazon|amzn': (
        'com.amazon.mShop.android.shopping/com.amazon.mShop.home.HomeActivity'
    ),
    'tiktok|tt': 'com.zhiliaoapp.musically/com.ss.android.ugc.aweme.splash.SplashActivity',
    'discord': 'com.discord/com.discord.app.AppActivity$Main',
    'reddit': 'com.reddit.frontpage/com.reddit.frontpage.MainActivity',
    'pinterest': 'com.pinterest/com.pinterest.activity.PinterestActivity',
    'android world': 'com.example.androidworld/.MainActivity',
    'files': 'com.google.android.documentsui/com.android.documentsui.files.FilesActivity',
    'markor': 'net.gsantner.markor/net.gsantner.markor.activity.MainActivity',
    'clipper': 'ca.zgrs.clipper/ca.zgrs.clipper.Main',
    'messages': 'com.google.android.apps.messaging/com.google.android.apps.messaging.ui.ConversationListActivity',
    'simple sms messenger|simple sms': 'com.simplemobiletools.smsmessenger/com.simplemobiletools.smsmessenger.activities.MainActivity',
    'dialer|phone': 'com.google.android.dialer/com.google.android.dialer.extensions.GoogleDialtactsActivity',
    'simple calendar pro|simple calendar': 'com.simplemobiletools.calendar.pro/com.simplemobiletools.calendar.pro.activities.MainActivity',
    'simple gallery pro|simple gallery': 'com.simplemobiletools.gallery.pro/com.simplemobiletools.gallery.pro.activities.MainActivity',
    'miniwob': 'com.google.androidenv.miniwob/com.google.androidenv.miniwob.app.MainActivity',
    'simple draw pro': 'com.simplemobiletools.draw.pro/com.simplemobiletools.draw.pro.activities.MainActivity',
    'pro expense|pro expense app': (
        'com.arduia.expense/com.arduia.expense.ui.MainActivity'
    ),
    'broccoli|broccoli app|broccoli recipe app|recipe app': (
        'com.flauschcode.broccoli/com.flauschcode.broccoli.MainActivity'
    ),
    'caa|caa test|context aware access': 'com.google.ccc.hosted.contextawareaccess.thirdpartyapp/.ChooserActivity',
    'osmand': 'net.osmand/net.osmand.plus.activities.MapActivity',
    'tasks|tasks app|tasks.org:': (
        'org.tasks/com.todoroo.astrid.activity.MainActivity'
    ),
    'open tracks sports tracker|activity tracker|open tracks|opentracks': (
        'de.dennisguse.opentracks/de.dennisguse.opentracks.TrackListActivity'
    ),
    'joplin|joplin app': 'net.cozic.joplin/.MainActivity',
    'vlc|vlc app|vlc player': 'org.videolan.vlc/.gui.MainActivity',
    'retro music|retro|retro player': (
        'code.name.monkey.retromusic/.activities.MainActivity'
    ),
})

package_dict_en = {
    'com.spotify.music': 'Spotify',
    'com.google.android.contacts': 'Contacts',
    'com.android.settings': 'Android-System-Settings',
    'com.google.android.deskclock': 'Clock',
    'com.zhiliaoapp.musically': 'TikTok',
    'com.github.kr328.clash': 'Clash',
    'com.amazon.mShop.android.shopping': 'Amazon-Shopping',
    'com.snapchat.android': 'Snapchat',
    'com.Slack': 'Slack',
    'com.ubercab': 'Uber',
    'com.reddit.frontpage': 'Reddit',
    'com.twitter.android': 'X',
    'com.quora.android': 'Quora',
    'us.zoom.videomeetings': 'Zoom',
    'com.booking': 'Booking',
    'com.instagram.android': 'Instagram',
    'com.facebook.katana': 'Facebook',
    'com.whatsapp': 'WhatsApp',
    'com.google.android.apps.maps': 'Google-Map',
    'com.google.android.youtube': 'YouTube',
    'com.netflix.mediaclient': 'Netflix',
    'com.linkedin.android': 'LinkedIn',
    'com.google.android.apps.docs': 'GoogleDrive',
    'com.google.android.gm': 'Gmail',
    'com.android.chrome': 'Chrome',
    'tv.twitch.android.app': 'Twitch',
    'com.google.android.calendar': 'Calendar',
    'org.breezyweather': 'weather',
    'com.mapswithme.maps.pro': 'Map.me',
    'cn.wps.moffice_i18n': 'WPS-Office',
    "com.oplus.notificationmanager": "OPlus-Notification-Manager",
    "com.sec.android.app.clockpackage": "Samsung-Clock",
    "ctrip.english": "Ctrip-(English)",
    "com.ebay.mobile": "eBay",
    "com.lht.icruise": "iCruise",
    "com.amtrak.rider": "Amtrak-Rider",
    "com.vivo.familycare.local": "Vivo-Family-Care",
    "com.tarento.tasks": "Tarento-Tasks",
    "com.coloros.alarmclock": "ColorOS-Alarm-Clock",
    "com.ticktick.task": "TickTick",
    "com.calendar.schedule.event": "Calendar-Schedule-Event",
    "com.strava": "Strava",
    "com.google.android.keep": "Google-Keep",
    "com.agoda.mobile.consumer": "Agoda",
    "com.coloros.calculator": "ColorOS-Calculator",
    "com.huawei.security.privacycenter": "Huawei-Privacy-Center",
    "com.washingtonpost.android": "The-Washington-Post",
    "com.android.BBKCrontab": "BBK-Crontab",
    "com.android.documentsui": "Android-Documents-UI",
    "com.infraware.office.link": "Infraware-OfficeLink",
    "com.android.printspooler": "Android-Print-Spooler",
    "com.aggrego.loop": "Aggrego-Loop",
    "com.gspace.android": "GSpace",
    "com.google.android.documentsui": "Google-Documents-UI",
    "com.transsion.calendar": "Transsion-Calendar",
    "com.android.intentresolver": "Android-Intent-Resolver",
    "com.android.vending": "Google-Play-Store",
    "com.sec.android.gallery3d": "Samsung-Gallery",
    "com.vivo.upslide": "Vivo-Upslide",
    "com.vivo.floatingball": "Vivo-Floating-Ball",
    "android": "Android-System",
    "com.memrise.android.memrisecompanion": "Memrise-Companion",
    "com.vivo.SmartKey": "Vivo-SmartKey",
    "ru.yandex.weatherplugin": "Yandex-Weather-Plugin",
    "com.vivo.permissionmanager": "Vivo-Permission-Manager",
    "com.android.permissioncontroller": "Android-Permission-Controller",
    "com.android.systemui": "Android-System-UI",
    "com.wunderground.android.weather": "Weather-Underground",
    "com.google.android.providers.media.module": "Google-Media-Provider",
    "cn.wps.moffice_eng": "WPS-Office-(English)",
    "com.miui.cloudservice": "MIUI-Cloud-Service",
    "com.miui.powerkeeper": "MIUI-Power-Keeper",
    "com.Project100Pi.themusicplayer": "Project100Pi-Music-Player",
    "com.android.server.telecom": "Android-Telecom-Server",
    "com.vivo.systemuiplugin": "Vivo-System-UI-Plugin",
    "com.iqoo.powersaving": "iQOO-Power-Saving",
    "com.mcdonalds.mobileapp": "McDonald's-App",
    "de.flixbus.app": "FlixBus",
    "com.miui.weather2": "MIUI-Weather",
    "com.anydo": "Any.do",
    "com.google.android.apps.tasks": "Google-Tasks",
    "com.ixigo": "ixigo",
    "com.aldiko.android": "Aldiko-Book-Reader",
    "com.samsung.android.app.galaxyfinder": "Samsung-Galaxy-Finder",
    "com.evernote": "Evernote",
    "com.devhd.feedly": "Feedly",
    "com.pizzahut.phd": "Pizza-Hut",
    "net.skyscanner.android.main": "Skyscanner",
    "com.transsion.resolver": "Transsion-Resolver",
    "com.google.android.apps.fitness": "Google-Fit",
    "com.huawei.android.hwouc": "Huawei-OEM-Update-Center",
    "com.huawei.android.FloatTasks": "Huawei-Float-Tasks",
    "com.google.android.apps.dynamite": "Google-Dynamite",
    "com.google.android.apps.docs.editors.docs": "Google-Docs",
    "com.coloros.gallery3d": "ColorOS-Gallery",
    "com.android.launcher": "Android-Launcher",
    "com.iqoo.secure": "iQOO-Secure",
    "com.samsung.ecomm.global.gbr": "Samsung-Ecomm-(UK)",
    "com.cf.flightsearch": "CF-Flight-Search",
    "com.google.android.apps.magazines": "Google-Play-Magazines",
    "com.nytimes.android": "The-New-York-Times",
    "bbc.mobile.news.ww": "BBC-News",
    "com.starbucks.id": "Starbucks",
    "com.huawei.systemmanager": "Huawei-System-Manager",
    "com.duolingo": "Duolingo",
    "com.sec.android.app.launcher": "Samsung-Launcher",
    "com.phonegap.dominos": "Domino's-Pizza",
    "com.android.providers.media.module": "Android-Media-Provider",
    "com.transsion.XOSLauncher": "Transsion-XOS-Launcher",
    "com.android.thememanager": "Android-Theme-Manager",
    "com.sec.android.app.myfiles": "Samsung-My-Files",
    "org.videolan.vlc": "VLC",
    "com.foxit.mobile.pdf.lite": "Foxit-PDF-Lite",
    "com.discord": "Discord",
    "com.babbel.mobile.android.en": "Babbel-(English)",
    "com.bokeriastudio.timezoneconverter": "Timezone-Converter-by-BokeriaStudio",
    "com.android.deskclock": "Android-Desk-Clock",
    "com.whatsapp.w4b": "WhatsApp-Business",
    "je.fit": "JE-Fit",
    "com.xiaomi.misettings": "Xiaomi-MI-Settings",
    "Panel:com.ubercab": "Uber",
    "com.google.android.apps.youtube.music": "YouTube-Music",
    "com.miui.gallery": "MIUI-Gallery",
    "com.oppo.quicksearchbox": "Oppo-Quick-Search-Box",
    "com.zte.zdm": "ZTE-ZDM",
    "com.coloros.weather2": "ColorOS-Weather",
    "com.teslacoilsw.launcher": "Nova-Launcher",
    "com.skype.raider": "Skype",
    "com.google.android.apps.nbu.files": "Google-Files-by-Google",
    "com.sephora.digital": "Sephora",
    "com.expedia.bookings": "Expedia",
    "com.bbk.calendar": "BBK-Calendar",
    "com.miui.cloudbackup": "MIUI-Cloud-Backup",
    "com.android.settings.intelligence": "Android-Settings-Intelligence",
    "com.google.android.settings.intelligence": "Android-Settings-Intelligence",
    "com.rammigsoftware.bluecoins": "BlueCoins",
    "com.google.android.apps.docs.editors.sheets": "Google-Sheets",
    "com.goeuro.rosie": "GoEuro-Rosie",
    "com.makemytrip": "MakeMyTrip",
    "com.vivo.card": "Vivo-Card",
    "com.application.zomato": "Zomato",
    "com.easemytrip.android": "EaseMyTrip",
    "com.miui.notes": "MIUI-Notes",
    "com.vivo.smartunlock": "Vivo-Smart-Unlock",
    "com.android.contacts": "Android-Contacts",
    "com.huawei.parentcontrol": "Huawei-Parent-Control",
    "com.vivo.findphone": "Vivo-Find-Phone",
    "com.google.android.googlequicksearchbox": "Google-Search",
    "plant.identification.snap": "Plant-Identification-by-Snap",
    "com.transsion.deskclock": "Transsion-Desk-Clock",
    "com.google.android.apps.wallpaper": "Google-Wallpapers",
    "com.huawei.localBackup": "Huawei-Local-Backup",
    "com.yahoo.mobile.client.android.finance": "Yahoo-Finance",
    "com.flipkart.android": "Flipkart",
    "com.heytap.market": "HeyTap-Market",
    "com.einnovation.temu": "Temu",
    "com.amazon.avod.thirdpartyclient": "Amazon-AVOD-Third-Party-Client",
    "com.android.calendar": "Android-Calendar",
    "com.rome2rio.www.rome2rio": "Rome2Rio",
    "com.amazon.dee.app": "Amazon-Dee",
    "com.miui.virtualsim": "MIUI-Virtual-SIM",
    "com.miui.notification": "MIUI-Notification",
    "com.xe.currency": "XE-Currency",
    "com.rccl.celebrity": "Royal-Caribbean-Celebrity",
    "com.miui.home": "MIUI-Home",
    "com.google.android.calculator": "Google-Calculator",
    "com.android.launcher3": "Android-Launcher3",
    "com.huawei.hidisk": "Huawei-HiDisk",
    "org.khanacademy.android": "Khan-Academy",
    "homeworkout.homeworkouts.noequipment": "Home-Workouts-(No-Equipment)",
    "gymworkout.gym.gymlog.gymtrainer": "Gym-Workout-Gym-Log-Gym-Trainer",
    "com.android.browser": "Android-Browser",
    "com.accuweather.android": "AccuWeather",
    "com.huawei.android.launcher": "Huawei-Launcher",
    "com.miui.backup": "MIUI-Backup",
    "com.google.android.apps.photos": "Google-Photos",
    "com.mi.android.globallauncher": "MI-Launcher",
    "com.tripadvisor.tripadvisor": "TripAdvisor",
    "com.xiaomi.account": "Xiaomi-Account",
    "com.google.android.apps.messaging": "Google-Messages",
    "com.oplus.camera": "OPlus-Camera",
    "com.bbk.updater": "BBK-Updater",
    "com.google.android.permissioncontroller": "Google-Permission-Controller",
    "com.skuld.calendario": "Calendario-by-Skuld",
    "com.atistudios.mondly.languages": "Mondly-Languages",
    "com.huawei.trustagent": "Huawei-Trust-Agent",
    "com.android.phone": "Android-Phone",
    "com.huawei.languagedownloader": "Huawei-Language-Downloader",
    "com.ss.android.ugc.trill": "Triller",
    "com.miui.securitycenter": "MIUI-Security-Center",
    "com.tencent.mobileqq": "QQ",
    "com.weatherteam.rainy.forecast.radar.widgets": "Rainy-Forecast-Radar-Widgets",
    "AtchDlg:com.whatsapp": "WhatsApp",
    "com.trivago": "Trivago",
    "org.mightyfrog.android.simplenotepad": "Simple-Notepad-by-MightyFrog",
    "com.loco2.loco2": "Loco2",
    "com.bbk.cloud": "BBK-Cloud",
    "com.google.android.gms": "Google-Play-Services",
    "com.kayak.android": "Kayak",
    "com.railyatri.in.mobile": "RailYatri",
    "com.miui.touchassistant": "MIUI-Touch-Assistant",
    "com.cleartrip.android": "Cleartrip",
    "com.google.android.packageinstaller": "Google-Package-Installer",
    "com.google.android.apps.wellbeing": "Google-Digital-Wellbeing",
    "com.google.android.dialer": "Google-Phone-Call",
    "com.google.android.apps.nexuslauncher": "Google-Nexus-Launcher",
    "org.mozilla.firefox": "Firefox",
}

for key, activity in _PATTERN_TO_ACTIVITY.items():
    key = key.split('|')[0]
    activity = activity.split('/')[0]
    package_dict_en[activity] = key





from Levenshtein import distance

def get_activity_key(activity_name: str) -> str:
    for key, activity in _PATTERN_TO_ACTIVITY.items():
        if isinstance(activity, tuple):
            activity = activity[0]
        package = activity.split('/')[0]
        if package == activity_name:
            return key
    return None  # 返回 None 代表未找到匹配项


def extract_package_name(activity: str) -> str:
  """Extract the package name from the activity string."""
  return activity.split('/')[0]

def find_closest(input_str, dict):
    if input_str in dict:
        return dict[input_str]
    elif input_str.replace(" ", "").lower() in dict:
        return dict[input_str.replace(" ", "").lower()]

    input_str = input_str.replace(" ", "").lower()
    # 初始化变量来追踪最小编辑距离及其对应的key
    min_distance = float('inf')
    closest_key = None

    # 遍历字典中的所有key，找到与输入字符串编辑距离最小的key
    for key in dict:
        origin_key = key
        key = key.replace(" ", "").lower()
        current_distance = distance(input_str, key)
        if current_distance < min_distance:
            min_distance = current_distance
            closest_key = origin_key

    # 返回编辑距离最小的key的value
    return dict[closest_key]


def find_package(input_str: str) -> str:
    # 如果input_str在apps_dict中，则返回apps_dict[input_str]，否则如果input_str满足_PATTERN_TO_ACTIVITY中的某个模式，则返回_PATTERN_TO_ACTIVITY[input_str]，否则返回find_closest(input_str, apps_dict)
    if input_str in apps_dict:
        return apps_dict[input_str]
    elif get_adb_activity(input_str) is not None:
        package_name = extract_package_name(get_adb_activity(input_str))
        return package_name
    else:
        return find_closest(input_str, apps_dict)
    
#按照find_package的逻辑 写一个由package name找到app name的函数
def find_app(package_name: str) -> str:
    if package_name in package_dict_en:
        return package_dict_en[package_name]
    else:
        return find_closest(package_name, package_dict_en)


#def find_app(input_str: str) -> str:
    # inverse_dict = {v: k for k, v in apps_dict.items()}
    #return find_closest(input_str, package_dict_en)

def get_adb_activity(app_name: str) -> str:
    """Get a mapping of regex patterns to ADB activities top Android apps."""
    for pattern, activity in _PATTERN_TO_ACTIVITY.items():
        if re.match(pattern.lower(), app_name.lower()):
            return activity
    app_name = app_name.replace("_", " ")
    for pattern, activity in _PATTERN_TO_ACTIVITY.items():
        if re.match(pattern.lower(), app_name.lower()):
            return activity
    return None

if __name__ == "__main__":
    print(find_package("chrome"))
    print(find_app("com.Project100Pi.themusicplayer"))
