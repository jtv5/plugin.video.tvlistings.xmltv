from xbmcswift2 import Plugin
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import re

import requests

from datetime import datetime,timedelta
import time
import urllib
import HTMLParser
import xbmcplugin
import xml.etree.ElementTree as ET
import sqlite3
import os

plugin = Plugin()
big_list_view = False

def log2(v):
    xbmc.log(repr(v))

def log(v):
    xbmc.log(re.sub(',',',\n',repr(v)))

def get_icon_path(icon_name):
    addon_path = xbmcaddon.Addon().getAddonInfo("path")
    return os.path.join(addon_path, 'resources', 'img', icon_name+".png")

def get_tvdb_id(name):
    tvdb_url = "http://thetvdb.com//api/GetSeries.php?seriesname=%s" % name
    try:
        r = requests.get(tvdb_url)
    except:
        return ''
    tvdb_html = r.text
    tvdb_id = ''
    tvdb_match = re.search(r'<seriesid>(.*?)</seriesid>', tvdb_html, flags=(re.DOTALL | re.MULTILINE))
    if tvdb_match:
        tvdb_id = tvdb_match.group(1)
    return tvdb_id

def write_channel_file():
    xbmcvfs.mkdir('special://userdata/addon_data/plugin.video.tvlistings.xmltv')
    file_name = 'special://userdata/addon_data/plugin.video.tvlistings.xmltv/plugin.video.tvlistings.xmltv.ini'
    f = xbmcvfs.File(file_name,'w')
    write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next channel add.\n\n[plugin.video.tvlistings.xmltv]\n"
    f.write(write_str.encode("utf8"))
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    for channel in sorted(channels):
        write_str = "%s=%s\n" % (channel,channels[channel])
        f.write(write_str)
    f.close()
    
@plugin.route('/add_channel/<channel_name>/<path>/<icon>/<ask>')
def add_channel(channel_name,path,icon,ask):
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    channel_name = urllib.unquote(channel_name)
    channel_name = re.sub('\[.*?\]','',channel_name)
    if ask == 'true':
        dialog = xbmcgui.Dialog()
        channel_name = dialog.input('TV Listings (xmltv) - Name channel', channel_name, type=xbmcgui.INPUT_ALPHANUM)
    if not channel_name:
        return
    channels[channel_name] = urllib.unquote(path)
    channels.sync()
    
    write_channel_file()

@plugin.route('/remove_channel/<channel_name>/<path>/<icon>')
def remove_channel(channel_name,path,icon):
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    channel_name = urllib.unquote(channel_name)
    channel_name = re.sub('\[.*?\]','',channel_name)
    if not channel_name in channels:
        return
    del channels[channel_name]
    channels.sync()
    
    write_channel_file()

    
@plugin.route('/channel_list')
def channel_list():
    global big_list_view
    big_list_view = True
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    items = []
    for channel in sorted(channels):
        label = "%s" % (channel)
        img_url = ''
        item = {'label':label,'icon':img_url,'thumbnail':img_url,'is_playable': True}
        item['path'] = channels[channel]
        log2(channels[channel])
        items.append(item)

    return items
        
@plugin.route('/channel_remap')
def channel_remap():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    c.execute('SELECT * FROM channels')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        if channel_name in channels:
            label = "[COLOR red][B]%s[/B][/COLOR]" % (channel_name)
        else:
            label = "[COLOR yellow][B]%s[/B][/COLOR]" % (channel_name)
        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('select_channel', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))
        items.append(item)
    c.close()

    return items
    
@plugin.route('/select_channel/<channel_id>/<channel_name>')
def select_channel(channel_id,channel_name):
    global big_list_view
    big_list_view = True
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    items = []
    for channel in sorted(channels):
        if channel == channel_name:
            label = "[COLOR red][B]%s[/B][/COLOR]" % (channel)
        else:
            label = "[COLOR yellow][B]%s[/B][/COLOR]" % (channel)
        img_url = ''
        item = {'label':label,'icon':img_url,'thumbnail':img_url,'is_playable': False}
        item['path'] = plugin.url_for('choose_channel', channel_id=channel_name, channel=channel, path=urllib.quote(channels[channel],safe=''))
        items.append(item)

    return items
    
@plugin.route('/choose_channel/<channel_id>/<channel>/<path>')
def choose_channel(channel_id,channel,path):
    remove_channel(channel_id,'','')
    add_channel(channel_id,path,'','false')
    
    
@plugin.route('/play_channel/<channel_id>/<title>/<start>')
def play_channel(channel_id,title,start):
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    if not channel_id in channels:
        return
    path = channels[channel_id]
    plugin.set_setting('playing_channel',channel_id)
    plugin.set_setting('playing_title',title)
    plugin.set_setting('playing_start',start)
    xbmc.executebuiltin('PlayMedia(%s)' % path)

@plugin.route('/stop_playing/<channel_id>/<title>/<start>')
def stop_playing(channel_id,title,start):
    if plugin.get_setting('playing_channel') != channel_id:
        return
    elif plugin.get_setting('playing_start') != start:
        return
    plugin.set_setting('playing_channel','')
    plugin.set_setting('playing_title','')
    plugin.set_setting('playing_start','')
    xbmc.executebuiltin('PlayerControl(Stop)')

def get_conn():
    profilePath = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
    if not os.path.exists(profilePath):
        os.makedirs(profilePath)
    databasePath = os.path.join(profilePath, 'source.db')

    conn = sqlite3.connect(databasePath, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn

@plugin.route('/clear_reminders')
def clear_reminders():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM remind')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            title = row['title']
            xbmc.executebuiltin('CancelAlarm(%s,False)' % (channel_id+title+str(start)))

        c.execute('SELECT * FROM watch')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            title = row['title']
            xbmc.executebuiltin('CancelAlarm(%s-start,False)' % (channel_id+title+str(start)))
            xbmc.executebuiltin('CancelAlarm(%s-stop,False)' % (channel_id+title+str(start)))
    except:
        pass

    c.execute('DELETE FROM remind')
    c.execute('DELETE FROM watch')
    conn.commit()
    conn.close()


def refresh_reminders():
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute('SELECT * FROM remind')
        for row in c:
            start = row['start']
            t = datetime.fromtimestamp(float(start)) - datetime.now()
            timeToNotification = ((t.days * 86400) + t.seconds) / 60
            icon = ''
            description = "%s: %s" % (row['channel'],row['title'])
            xbmc.executebuiltin('AlarmClock(%s,Notification(%s,%s,10000,%s),%d)' %
                (row['channel']+row['title']+str(start), row['title'], description, icon, timeToNotification - int(plugin.get_setting('remind_before'))))

        c.execute('SELECT * FROM watch')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            stop = row['stop']
            path = channels[channel_id]
            t = datetime.fromtimestamp(float(start)) - datetime.now()
            timeToNotification = ((t.days * 86400) + t.seconds) / 60
            xbmc.executebuiltin('AlarmClock(%s-start,PlayMedia(plugin://plugin.video.tvlistings.xmltv/play_channel/%s),%d,False)' %
                (channel_id+title+str(start), channel_id, timeToNotification - int(plugin.get_setting('remind_before'))))

            if plugin.get_setting('watch_and_stop') == 'true':
                t = datetime.fromtimestamp(float(stop)) - datetime.now()
                timeToNotification = ((t.days * 86400) + t.seconds) / 60
                xbmc.executebuiltin('AlarmClock(%s-stop,PlayMedia(plugin://plugin.video.tvlistings.xmltv/stop_playing),%d,True)' %
                    (channel_id+title+str(start), timeToNotification + int(plugin.get_setting('remind_after'))))

        conn.commit()
        conn.close()
    except:
        pass

@plugin.route('/remind/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def remind(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)
    xbmc.executebuiltin('AlarmClock(%s,Notification(%s,%s,10000,%s),%d)' %
        (channel_id+title+str(start), title, description, icon, timeToNotification - int(plugin.get_setting('remind_before'))))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    row = c.fetchone()
    c.execute("INSERT OR IGNORE INTO remind(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [row['channel'] ,row['title'] , row['sub_title'] , row['start'] , row['stop'], row['date'], row['description'] , row['series'] , row['episode'] , row['categories']])
    conn.commit()
    conn.close()

@plugin.route('/watch/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def watch(channel_id,channel_name,title,season,episode,start,stop):
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    if not channel_id in channels:
        return
    path = channels[channel_id]
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    xbmc.executebuiltin('AlarmClock(%s-start,PlayMedia(plugin://plugin.video.tvlistings.xmltv/play_channel/%s/%s/%s),%d,False)' %
        (channel_id+title+str(start), channel_id,title,str(start), timeToNotification - int(plugin.get_setting('remind_before'))))

    #TODO check for overlapping times
    if plugin.get_setting('watch_and_stop') == 'true':
        t = datetime.fromtimestamp(float(stop)) - datetime.now()
        timeToNotification = ((t.days * 86400) + t.seconds) / 60
        xbmc.executebuiltin('AlarmClock(%s-stop,PlayMedia(plugin://plugin.video.tvlistings.xmltv/stop_playing/%s/%s/%s),%d,True)' %
            (channel_id+title+str(start), channel_id,title,str(start), timeToNotification + int(plugin.get_setting('remind_after'))))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    row = c.fetchone()
    c.execute("INSERT OR IGNORE INTO watch(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [row['channel'] ,row['title'] , row['sub_title'] , row['start'] , row['stop'], row['date'], row['description'] , row['series'] , row['episode'] , row['categories']])
    conn.commit()
    conn.close()


@plugin.route('/cancel_remind/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def cancel_remind(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)
    xbmc.executebuiltin('CancelAlarm(%s,False)' % (channel_id+title+str(start)))

    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM remind WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])

    conn.commit()
    conn.close()


@plugin.route('/cancel_watch/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def cancel_watch(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)

    xbmc.executebuiltin('CancelAlarm(%s-start,False)' % (channel_id+title+str(start)))
    xbmc.executebuiltin('CancelAlarm(%s-stop,False)' % (channel_id+title+str(start)))

    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM watch WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    conn.commit()
    conn.close()


@plugin.route('/play/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def play(channel_id,channel_name,title,season,episode,start,stop):
    global big_list_view
    big_list_view = True
    channel_items = channel(channel_id,channel_name)
    items = []
    tvdb_id = ''
    if int(season) > 0 and int(episode) > 0:
        tvdb_id = get_tvdb_id(title)
    addon = xbmcaddon.Addon('plugin.video.meta')
    meta_icon = addon.getAddonInfo('icon')
    if tvdb_id:
        if season and episode:
            meta_url = "plugin://plugin.video.meta/tv/play/%s/%s/%s/%s" % (tvdb_id,season,episode,'select')
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]S%sE%s[/B][/COLOR] [COLOR green][B]Meta episode[/B][/COLOR]' % (title,season,episode),
            'path': meta_url,
            'thumbnail': meta_icon,
            'icon': meta_icon,
            'is_playable': True,
             })
        if season:
            meta_url = "plugin://plugin.video.meta/tv/tvdb/%s/%s" % (tvdb_id,season)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]S%s[/B][/COLOR] [COLOR green][B]Meta season[/B][/COLOR]' % (title,season),
            'path': meta_url,
            'thumbnail': meta_icon,
            'icon': meta_icon,
            'is_playable': False,
             })
        meta_url = "plugin://plugin.video.meta/tv/tvdb/%s" % (tvdb_id)
        items.append({
        'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta TV search[/B][/COLOR]' % (title),
        'path': meta_url,
        'thumbnail': meta_icon,
        'icon': meta_icon,
        'is_playable': False,
         })
        try:
            addon = xbmcaddon.Addon('plugin.video.sickrage')
            sick_icon =  addon.getAddonInfo('icon')
            if addon:
                items.append({
                'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]SickRage[/B][/COLOR]' % (title),
                'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                'thumbnail': sick_icon,
                'icon': sick_icon,
                })
        except:
            pass
    else:
        match = re.search(r'(.*?)\(([0-9]*)\)$',title)
        if match:
            movie = match.group(1)
            year =  match.group(2) #TODO: Meta doesn't support year yet
            meta_url = "plugin://plugin.video.meta/movies/search_term/%s/1" % (movie)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta movie[/B][/COLOR]' % (title),
            'path': meta_url,
            'thumbnail': meta_icon,
            'icon': meta_icon,
            'is_playable': False,
             })
            try:
                addon = xbmcaddon.Addon('plugin.video.couchpotato_manager')
                couch_icon =  addon.getAddonInfo('icon')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]CouchPotato[/B][/COLOR]' % (title),
                    'path':"plugin://plugin.video.couchpotato_manager/movies/add/?title=%s" % (title),
                    'thumbnail': couch_icon,
                    'icon': couch_icon,
                    })
            except:
                pass
        else:
            meta_url = "plugin://plugin.video.meta/tv/search_term/%s/1" % (title)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta TV search[/B][/COLOR]' % (title),
            'path': meta_url,
            'thumbnail': meta_icon,
            'icon': meta_icon,
            'is_playable': False,
             })
            meta_url = "plugin://plugin.video.meta/movies/search_term/%s/1" % (title)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta movie search[/B][/COLOR]' % (title),
            'path': meta_url,
            'thumbnail': meta_icon,
            'icon': meta_icon,
            'is_playable': False,
             })
            try:
                addon = xbmcaddon.Addon('plugin.video.sickrage')
                sick_icon =  addon.getAddonInfo('icon')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]SickRage[/B][/COLOR]' % (title),
                    'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                    'thumbnail': sick_icon,
                    'icon': sick_icon,
                    })
            except:
                pass
    clock_icon = get_icon_path('alarm')
    items.append({
    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]Remind[/B][/COLOR]' % (title),
    'path':plugin.url_for('remind', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
    'thumbnail': clock_icon,
    'icon': clock_icon,
    })
    items.append({
    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]Cancel[/B][/COLOR]' % (title),
    'path':plugin.url_for('cancel_remind', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
    'thumbnail': clock_icon,
    'icon': clock_icon,
    })
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    if channel_id in channels:
        items.append({
        'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR blue][B]Watch[/B][/COLOR]' % (title),
        'path':plugin.url_for('watch', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
        'thumbnail': clock_icon,
        'icon': clock_icon,
        })
        items.append({
        'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR blue][B]Cancel[/B][/COLOR]' % (title),
        'path':plugin.url_for('cancel_watch', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
        'thumbnail': clock_icon,
        'icon': clock_icon,
        })

    items.extend(channel_items)
    return items


@plugin.route('/channel/<channel_id>/<channel_name>')
def channel(channel_id,channel_name):
    items = []
    
    channels = plugin.get_storage('plugin.video.tvlistings.xmltv')
    if channel_name in channels:
        addon = xbmcaddon.Addon()
        icon = addon.getAddonInfo('icon')
        item = {
        'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR]' % (re.sub('_',' ',channel_name),'Default Player'),
        'path': channels[channel_name],
        'thumbnail': icon,
        'icon': icon,
        'is_playable': True,
        }
        items.append(item)
        
    addons = plugin.get_storage('addons')

    for addon in addons:
        channels = plugin.get_storage(addon)
        if not channel_id in channels:
            continue
        path = channels[channel_id]
        try:
            addon = xbmcaddon.Addon(addon)
            if addon:
                icon = addon.getAddonInfo('icon')
                item = {
                'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR]' % (re.sub('_',' ',channel_name),addon.getAddonInfo('name')),
                'path': path,
                'thumbnail': icon,
                'icon': icon,
                'is_playable': True,
                }
                items.append(item)
        except:
            pass


            
    addon = xbmcaddon.Addon('plugin.video.meta')
    meta_icon = addon.getAddonInfo('icon')
    meta_url = "plugin://plugin.video.meta/live/search_term/%s" % (channel_name)
    items.append({
    'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR]' % (channel_name,'Meta Live'),
    'path': meta_url,
    'thumbnail': meta_icon,
    'icon': meta_icon,
    'is_playable': False,
     })
    return items

def utc2local (utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset


def local_time(ttime,year,month,day):
    match = re.search(r'(.{1,2}):(.{2}) {0,1}(.{2})',ttime)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3)
        if ampm == "pm":
            if hour < 12:
                hour = hour + 12
                hour = hour % 24
        else:
            if hour == 12:
                hour = 0

        utc_dt = datetime(int(year),int(month),int(day),hour,minute,0)
        loc_dt = utc2local(utc_dt)
        ttime = "%02d:%02d" % (loc_dt.hour,loc_dt.minute)
    return ttime




def get_url(url):
    headers = {'user-agent': 'Mozilla/5.0 (BB10; Touch) AppleWebKit/537.10+ (KHTML, like Gecko) Version/10.0.9.2372 Mobile Safari/537.10+'}
    try:
        r = requests.get(url,headers=headers)
        html = HTMLParser.HTMLParser().unescape(r.content.decode('utf-8'))
        return html
    except:
        return ''


def store_channels():
    if plugin.get_setting('ini_reload') == 'true':
        plugin.set_setting('ini_reload','false')
    else:
        return

    addons = plugin.get_storage('addons')
    items = []
    for addon in addons:
        channels = plugin.get_storage(addon)
        channels.clear()
    addons.clear()

    if plugin.get_setting('ini_type') == '1':
        url = plugin.get_setting('ini_url')
        r = requests.get(url)
        file_name = 'special://userdata/addon_data/plugin.video.tvlistings.xmltv/addons.ini'
        xmltv_f = xbmcvfs.File(file_name,'w')
        xml = r.content
        xmltv_f.write(xml)
        xmltv_f.seek(0,0)
        #NOTE not xmltv_f.close()
        ini_file = file_name
        dt = datetime.now()
        now = int(time.mktime(dt.timetuple()))
        plugin.set_setting("ini_url_last",str(now))
    else:
        ini_file = plugin.get_setting('ini_file')
        path = xbmc.translatePath(plugin.get_setting('ini_file'))
        stat = xbmcvfs.Stat(path)
        modified = str(stat.st_mtime())
        plugin.set_setting('ini_last_modified',modified)

    try:
        if plugin.get_setting('ini_type') == '1':
            f = xmltv_f
        else:
            f = xbmcvfs.File(ini_file)
        items = f.read().splitlines()
        f.close()
        addon = 'nothing'
        addons = plugin.get_storage('addons')
        for item in items:
            if item.startswith('['):
                addon = item.strip('[] \t')
                channels = plugin.get_storage(addon)
            elif item.startswith('#'):
                pass
            else:
                name_url = item.split('=',1)
                if len(name_url) == 2:
                    name = name_url[0]
                    url = name_url[1]
                    if url:
                        channels[name] = url
                        addons[addon] = addon
        addons.sync()
        for addon in addons:
            channels = plugin.get_storage(addon)
            channels.sync()
    except:
        pass



def xml2utc(xml):
    match = re.search(r'([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2}) ([+-])([0-9]{2})([0-9]{2})',xml)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        second = int(match.group(6))
        sign = match.group(7)
        hours = int(match.group(8))
        minutes = int(match.group(9))
        dt = datetime(year,month,day,hour,minute,second)
        td = timedelta(hours=hours,minutes=minutes)
        if sign == '+':
            dt = dt - td
        else:
            dt = dt + td
        return dt
    return ''

class FileWrapper(object):
    def __init__(self, filename):
        self.vfsfile = xbmcvfs.File(filename)
        self.size = self.vfsfile.size()
        self.bytesRead = 0

    def close(self):
        self.vfsfile.close()

    def read(self, byteCount):
        self.bytesRead += byteCount
        return self.vfsfile.read(byteCount)

    def tell(self):
        return self.bytesRead


def xml_channels():
    try:
        updating = plugin.get_setting('xmltv_updating')
    except:
        updating = 'false'
        plugin.set_setting('xmltv_updating', updating)
    if updating == 'true':
        return
    xmltv_type = plugin.get_setting('xmltv_type')
    if plugin.get_setting('xml_reload') == 'true':
        plugin.set_setting('xml_reload','false')
    else:
        try:
            xmltv_type_last = plugin.get_setting('xmltv_type_last')
        except:
            xmltv_type_last = xmltv_type
            plugin.set_setting('xmltv_type_last', xmltv_type)
        if xmltv_type == xmltv_type_last:
            if plugin.get_setting('xmltv_type') == '0': # File
                if plugin.get_setting('xml_reload_modified') == 'true':
                    path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
                    stat = xbmcvfs.Stat(path)
                    modified = str(stat.st_mtime())
                    last_modified = plugin.get_setting('xmltv_last_modified')
                    if last_modified == modified:
                        return
                    else:
                        pass
                else:
                    return
            else:
                dt = datetime.now()
                now_seconds = int(time.mktime(dt.timetuple()))
                try:
                    xmltv_url_last = int(plugin.get_setting("xmltv_url_last"))
                except:
                    xmltv_url_last = 0
                if xmltv_url_last + 24*3600 < now_seconds:
                    pass
                else:
                    return
        else:
            pass

    xbmc.log("XMLTV UPDATE")
    plugin.set_setting('xmltv_type_last',xmltv_type)

    dialog = xbmcgui.Dialog()

    xbmcvfs.mkdir('special://userdata/addon_data/plugin.video.tvlistings.xmltv')
    if not xbmcvfs.exists('special://userdata/addon_data/plugin.video.tvlistings.xmltv/myaddons.ini'):
        f = xbmcvfs.File('special://userdata/addon_data/plugin.video.tvlistings.xmltv/myaddons.ini','w')
        f.close()

    file_name = 'special://userdata/addon_data/plugin.video.tvlistings.xmltv/template.ini'
    f = xbmcvfs.File(file_name,'w')
    write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next channel reload.\n\n[plugin.video.all]\n"
    f.write(write_str.encode("utf8"))

    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    conn.execute('DROP TABLE IF EXISTS channels')
    conn.execute('DROP TABLE IF EXISTS programmes')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS channels(id TEXT, name TEXT, icon TEXT, PRIMARY KEY (id))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS programmes(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS remind(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS watch(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')

    dialog.notification("TV Listings (xmltv)","downloading xmltv file")
    if plugin.get_setting('xmltv_type') == '1':
        url = plugin.get_setting('xmltv_url')
        r = requests.get(url)
        file_name = 'special://userdata/addon_data/plugin.video.tvlistings.xmltv/xmltv.xml'
        xmltv_f = xbmcvfs.File(file_name,'w')
        xml = r.content
        xmltv_f.write(xml)
        xmltv_f.close()
        xmltv_file = file_name
        dt = datetime.now()
        now = int(time.mktime(dt.timetuple()))
        plugin.set_setting("xmltv_url_last",str(now))
    else:
        xmltv_file = plugin.get_setting('xmltv_file')
        path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
        stat = xbmcvfs.Stat(path)
        modified = str(stat.st_mtime())
        plugin.set_setting('xmltv_last_modified',modified)

    dialog.notification("TV Listings (xmltv)","finished downloading xmltv file")

    xml_f = FileWrapper(xmltv_file)
    if xml_f.size == 0:
        return
    context = ET.iterparse(xml_f, events=("start", "end"))
    context = iter(context)
    event, root = context.next()
    last = datetime.now()
    for event, elem in context:
        if event == "end":
            now = datetime.now()
            if elem.tag == "channel":
                id = elem.attrib['id']
                display_name = elem.find('display-name').text
                try:
                    icon = elem.find('icon').attrib['src']
                except:
                    icon = ''
                    if plugin.get_setting('logo_type') == 0:
                        path = plugin.get_setting('logo_folder')
                        if path:
                            icon = os.path.join(path,display_name,".png")
                    else:
                        path = plugin.get_setting('logo_url')
                        if path:
                            icon = "%s/%s.png" % (path,display_name)

                write_str = "%s=\n" % (id)
                f.write(write_str.encode("utf8"))
                conn.execute("INSERT OR IGNORE INTO channels(id, name, icon) VALUES(?, ?, ?)", [id, display_name, icon])
                if (now - last).seconds > 0.5:
                    dialog.notification("TV Listings (xmltv)","loading channels: "+display_name)
                    last = now

            elif elem.tag == "programme":
                programme = elem
                start = programme.attrib['start']
                start = xml2utc(start)
                start = utc2local(start)
                stop = programme.attrib['stop']
                stop = xml2utc(stop)
                stop = utc2local(stop)
                channel = programme.attrib['channel']
                title = programme.find('title').text
                match = re.search(r'(.*?)"}.*?\(\?\)$',title) #BUG in webgrab
                if match:
                    title = match.group(1)
                try:
                    sub_title = programme.find('sub-title').text
                except:
                    sub_title = ''
                try:
                    date = programme.find('date').text
                except:
                    date = ''
                try:
                    description = programme.find('desc').text
                except:
                    description = ''
                try:
                    episode_num = programme.find('episode-num').text
                except:
                    episode_num = ''
                series = 0
                episode = 0
                match = re.search(r'(.*?)\.(.*?)[\./]',episode_num)
                if match:
                    try:
                        series = int(match.group(1)) + 1
                        episode = int(match.group(2)) + 1
                    except:
                        pass
                series = str(series)
                episode = str(episode)
                categories = ''
                for category in programme.findall('category'):
                    categories = ','.join((categories,category.text)).strip(',')

                total_seconds = time.mktime(start.timetuple())
                start = int(total_seconds)
                total_seconds = time.mktime(stop.timetuple())
                stop = int(total_seconds)
                conn.execute("INSERT OR IGNORE INTO programmes(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [channel ,title , sub_title , start , stop, date, description , series , episode , categories])
                if (now - last).seconds > 0.5:
                    dialog.notification("TV Listings (xmltv)","loading programmes: "+channel)
                    last = now
            root.clear()

    conn.commit()
    conn.close()
    plugin.set_setting('xmltv_updating', 'false')

@plugin.route('/channels')
def channels():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT * FROM channels')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        label = "[COLOR yellow][B]%s[/B][/COLOR]" % (channel_name)
        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))
        items.append(item)
    c.close()

    return items

@plugin.route('/now_next_time/<seconds>')
def now_next_time(seconds):
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT *, name FROM channels')
    channels = [(row['id'], row['name'], row['icon']) for row in c]

    now = datetime.fromtimestamp(float(seconds))
    total_seconds = time.mktime(now.timetuple())

    items = []
    for (channel_id, channel_name, img_url) in channels:
        c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id])
        remind = [row['start'] for row in c]
        c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id])
        watch = [row['start'] for row in c]
        c.execute('SELECT start FROM programmes WHERE channel=? ORDER BY start', [channel_id])
        programmes = [row['start'] for row in c]

        times = sorted(programmes)
        max = len(times)
        less = [i for i in times if i <= total_seconds]
        index = len(less) - 1
        if index < 0:
            continue
        now_start = times[index]

        c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,now_start])
        now = datetime.fromtimestamp(now_start)
        now = "%02d:%02d" % (now.hour,now.minute)
        row = c.fetchone()
        now_title = row['title']
        now_stop = row['stop']
        if now_stop < total_seconds:
            now_title = "[I]%s[/I]" % now_title
        else:
            now_title = "[B]%s[/B]" % now_title

        if now_start in watch:
            now_title_format = "[COLOR blue]%s[/COLOR]" % now_title
        elif now_start in remind:
            now_title_format = "[COLOR red]%s[/COLOR]" % now_title
        else:
            now_title_format = "[COLOR orange]%s[/COLOR]" % now_title

        next = ''
        next_title = ''
        if index+1 < max:
            next_start = times[index + 1]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,next_start])
            next = datetime.fromtimestamp(next_start)
            next = "%02d:%02d" % (next.hour,next.minute)
            next_title = c.fetchone()['title']

        if next_start in watch:
            next_title_format = "[COLOR blue][B]%s[/B][/COLOR]" % next_title
        elif next_start in remind:
            next_title_format = "[COLOR red][B]%s[/B][/COLOR]" % next_title
        else:
            next_title_format = "[COLOR white][B]%s[/B][/COLOR]" % next_title

        after = ''
        after_title = ''
        if (index+2) < max:
            after_start = times[index + 2]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,after_start])
            after = datetime.fromtimestamp(after_start)
            after = "%02d:%02d" % (after.hour,after.minute)
            after_title = c.fetchone()['title']

        if after_start in watch:
            after_title_format = "[COLOR blue][B]%s[/B][/COLOR]" % after_title
        elif after_start in remind:
            after_title_format = "[COLOR red][B]%s[/B][/COLOR]" % after_title
        else:
            after_title_format = "[COLOR grey][B]%s[/B][/COLOR]" % after_title

        if  plugin.get_setting('show_channel_name') == 'true':
            label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s %s %s %s %s" % \
            (channel_name,now,now_title_format,next,next_title_format,after,after_title_format)
        else:
            label = "%s %s %s %s %s %s" % \
            (now,now_title_format,next,next_title_format,after,after_title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))

        items.append(item)

    return items

@plugin.route('/hourly')
def hourly():
    global big_list_view
    big_list_view = True
    items = []

    dt = datetime.now()
    dt = dt.replace(hour=0, minute=0, second=0)

    for day in ("Today","Tomorrow"):
        label = "[COLOR red][B]%s[/B][/COLOR]" % (day)
        items.append({'label':label,'path':plugin.url_for('hourly')})
        for hour in range(0,24):
            label = "[COLOR blue][B]%02d:00[/B][/COLOR]" % (hour)
            total_seconds = str(time.mktime(dt.timetuple()))
            items.append({'label':label,'path':plugin.url_for('now_next_time',seconds=total_seconds)})
            dt = dt + timedelta(hours=1)

    return items


@plugin.route('/prime')
def prime():
    prime = plugin.get_setting('prime')
    dt = datetime.now()
    dt = dt.replace(hour=int(prime), minute=0, second=0)
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds)
    return items


@plugin.route('/now_next')
def now_next():
    dt = datetime.now()
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds)
    return items

@plugin.route('/listing/<channel_id>/<channel_name>')
def listing(channel_id,channel_name):
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)
    c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    remind = [row['start'] for row in c]
    c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    watch = [row['start'] for row in c]
    c.execute('SELECT * FROM programmes WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    items = channel(channel_id,channel_name)
    last_day = ''
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        dt = datetime.fromtimestamp(start)
        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR red][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,'is_playable':True,'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        ttime = "%02d:%02d" % (dt.hour,dt.minute)


        if start in watch:
            title_format = "[COLOR blue][B]%s[/B][/COLOR]" % title
        elif start in remind:
            title_format = "[COLOR red][B]%s[/B][/COLOR]" % title
        else:
            title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s %s" % (channel_name,ttime,title_format,plot)
            else:
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s" % (channel_name,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)


        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        items.append(item)
    c.close()

    return items


@plugin.route('/search/<programme_name>')
def search(programme_name):
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)

    c.execute('SELECT * FROM remind ORDER BY channel, start')
    remind = {}
    for row in c:
        if not row['channel'] in remind:
            remind[row['channel']] = []
        remind[row['channel']].append(row['start'])
    c.execute('SELECT * FROM watch ORDER BY channel, start')
    watch = {}
    for row in c:
        if not row['channel'] in watch:
            watch[row['channel']] = []
        watch[row['channel']].append(row['start'])

    c.execute("SELECT * FROM programmes WHERE LOWER(title) LIKE LOWER(?) ORDER BY start, channel", ['%'+programme_name.decode("utf8")+'%'])
    last_day = ''
    items = []
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        dt = datetime.fromtimestamp(start)
        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR red][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,'is_playable':True,'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        ttime = "%02d:%02d" % (dt.hour,dt.minute)

        title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title
        if channel_id in remind:
            if start in remind[channel_id]:
                title_format = "[COLOR red][B]%s[/B][/COLOR]" % title
        if channel_id in watch:
            if start in watch[channel_id]:
                title_format = "[COLOR blue][B]%s[/B][/COLOR]" % title

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s %s" % (channel_name,ttime,title_format,plot)
            else:
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s" % (channel_name,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        items.append(item)
    c.close()
    return items

@plugin.route('/reminders')
def reminders():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)

    c.execute('SELECT * FROM remind ORDER BY channel, start')
    remind = {}
    for row in c:
        if not row['channel'] in remind:
            remind[row['channel']] = []
        remind[row['channel']].append(row['start'])
    c.execute('SELECT * FROM watch ORDER BY channel, start')
    watch = {}
    for row in c:
        if not row['channel'] in watch:
            watch[row['channel']] = []
        watch[row['channel']].append(row['start'])

    c.execute('SELECT * FROM remind UNION SELECT * FROM watch ORDER BY start, channel')
    last_day = ''
    items = []
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        dt = datetime.fromtimestamp(start)
        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR red][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,'is_playable':True,'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        ttime = "%02d:%02d" % (dt.hour,dt.minute)

        title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title
        if channel_id in remind:
            if start in remind[channel_id]:
                title_format = "[COLOR red][B]%s[/B][/COLOR]" % title
        if channel_id in watch:
            if start in watch[channel_id]:
                title_format = "[COLOR blue][B]%s[/B][/COLOR]" % title

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s %s" % (channel_name,ttime,title_format,plot)
            else:
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s" % (channel_name,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        items.append(item)
    c.close()
    return items


@plugin.route('/search_dialog')
def search_dialog():
    dialog = xbmcgui.Dialog()
    name = dialog.input('Search for programme', type=xbmcgui.INPUT_ALPHANUM)
    if name:
        return search(name)



@plugin.route('/')
def index():
    items = [
    {
        'label': '[COLOR green][B]Now Next[/B][/COLOR]',
        'path': plugin.url_for('now_next'),
    },
    {
        'label': '[COLOR blue][B]Hourly[/B][/COLOR]',
        'path': plugin.url_for('hourly'),
    },
    {
        'label': '[COLOR orange][B]Prime Time[/B][/COLOR]',
        'path': plugin.url_for('prime'),
    },
    {
        'label': '[COLOR red][B]Listings[/B][/COLOR]',
        'path': plugin.url_for('channels'),
    },
    {
        'label': '[COLOR yellow][B]Search[/B][/COLOR]',
        'path': plugin.url_for('search_dialog'),
    },
    {
        'label': '[COLOR blue][B]Reminders[/B][/COLOR]',
        'path': plugin.url_for('reminders'),
    },
    {
        'label': '[COLOR yello][B]Channels[/B][/COLOR]',
        'path': plugin.url_for('channel_list'),
    },    
    {
        'label': '[COLOR yello][B]Channels Remap[/B][/COLOR]',
        'path': plugin.url_for('channel_remap'),
    },    
    ]
    return items

if __name__ == '__main__':
    xml_channels()
    store_channels()
    plugin.run()
    if big_list_view == True: 
        plugin.set_view_mode(51)