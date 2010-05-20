#!/usr/bin/env python

import gobject
import gtk
import socket, errno, sys, os.path
import dbus, dbus.mainloop.glib
import appindicator
import pynotify
from mpd import MPDClient

# Looks for album art
def get_coverart(songdata):
	# we look in the song folder first
	song_dirname = "/var/lib/mpd/music/" + os.path.dirname(songdata["file"]) + "/"
	if os.path.exists(song_dirname + "cover.jpg"):
		return song_dirname + "cover.jpg"
	elif os.path.exists(song_dirname + "album.jpg"):
		return song_dirname + "album.jpg"
	# we can take advantage of sonata's cover database in ~/.covers
	if songdata.has_key("album"):
		if os.path.exists(os.path.expanduser("~/.covers/" + get_artist(songdata) + "-" + songdata["album"] + ".jpg")):
			return os.path.expanduser("~/.covers/" + get_artist(songdata) + "-" + songdata["album"] + ".jpg")
	return "media-playback-start" #default

# Returns song title
def get_title(songdata):
	if songdata.has_key("title"):
		if songdata.has_key("name"): # we can assume it's a radio or stream
			# we split the title from the info we have
			# for streams, "title" is usually of the form "artist - title"
			return songdata["title"].split(" - ")[1]
		else:
			return songdata["title"]
	else: # there's no data
		return songdata["file"] # we return the file path

# Returns song artist
def get_artist(songdata):
	if songdata.has_key("name"): # we can assume it's a radio or stream
		if songdata.has_key("title"): # we grab the artist info from the title
			return songdata["title"].split(" - ")[0]
	elif songdata.has_key("artist"):
		return songdata["artist"]
	else: #there's no data
		return ""

# Sends a notification with the current song data.
def current_song_notify(override=False):
	global mpdclient
	global oldsongdata
	
	currentsongdata = mpdclient.currentsong()
	
	if currentsongdata != {}: # we have data
		# if it's a new song or if we explicitly want to notify
		if currentsongdata != oldsongdata or override == True:
			# we get our info
			ctitle = get_title(currentsongdata)
			cartist = get_artist(currentsongdata)
			ccover = get_coverart(currentsongdata)
			
			# if it's a local file, unless we've just started, we wait 3 seconds, so we don't get
			#notified needlessly if we're just  quickly advancing in the playlist.
			#If it's a remote source (radio or stream), we notify as soon as the data changes.
			if not mpdclient.status()["time"].split(":")[0] == "3":
				if not currentsongdata.has_key("name"):
					if not oldsongdata == "":
						return True
				
			csong_notification = pynotify.Notification(ctitle, cartist, ccover)
			csong_notification.show()
			
			# we save the old info so we can check later for song changes
			oldsongdata = currentsongdata
	else: #we don't have data
		pass #we just wait for the next run
	
	return True # otherwise this function won't run again.

def action_handler(menu,action):
	global mpdclient
	try:
		mpdclient.status()
	except socket.error, e: 
		if e.errno == errno.EPIPE: #the pipe is broken
			print "WARNING: The client pipe was broken. Will attempt to restart the connection."
			client_setup() #let's restart the client

	# toggle playback (silence/noise ;))
	if action == "Toggle":
		if mpdclient.playlistinfo() != []: #if there's a playlist
			if mpdclient.currentsong() != {}: #if there's a selected song
				state = mpdclient.status()['state']
				if state == "stop":
					mpdclient.play() # play the song from the beginning.
				elif state in ("play", "pause"):
					mpdclient.pause() # toggle play/pause
					if state == "pause": # we always notify if we recover from pause.
						current_song_notify(override=True)
			else:
				mpdclient.play() # we play from the beginning of the playlist
		else: #there's no playlist
			no_music_notify = pynotify.Notification("Hey, there's nothing to play", 
			"Add some music to your MPD playlist, silly!", None)
			no_music_notify.show()
	# stop (only multimedia keys)
	elif action == "Stop":
		mpdclient.stop()
	# next song
	elif action == "Next":
		mpdclient.next()
	# previous song
	elif action == "Prev":
		mpdclient.previous()
	# notify of current song, overriding
	elif action == "Info":
		current_song_notify(override=True)
	# end application
	elif action == "Quit":
		gtk.main_quit()
	else:
		pass

# activates actions from the multimedya keys
def delegate_mediakeys(*mmkeys):
	for key in mmkeys:
		if key == "Play":
			action_handler(None, "Toggle")
		elif key == "Stop":
			action_handler(None, "Stop")
		elif key == "Next":
			action_handler(None, "Next")
		elif key == "Previous":
			action_handler(None, "Prev")

# setups the mpd client
def client_setup():
	global mpdclient
	try:
		mpdclient = MPDClient()
		mpdclient.connect("localhost", 6600)
	except socket.error, e:
		error_msg = ["ERROR! Can't connect to MPD server.", 
		"Maybe sudo /etd/init.d/mpd restart will help?", "Meanwhile, I'll quit."]
		no_connect_notify = pynotify.Notification(error_msg[0], error_msg[1]+"\n"+error_msg[2], None)
		no_connect_notify.show()
		print error_msg[0]
		print error_msg[1]
		sys.exit()

if __name__ == "__main__":
	client_setup()
	oldsongdata = ""

	
	#create the app indicator
	ind = appindicator.Indicator ("indimpc", "sonata", appindicator.CATEGORY_APPLICATION_STATUS)
	ind.set_status (appindicator.STATUS_ACTIVE)

	#prepare the notifications
	notifier = pynotify.init("indimpc")
	csong_timeout = gobject.timeout_add(500, current_song_notify)

	#grab multimedia keys
	dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
	bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
	keysbus = bus.get_object("org.gnome.SettingsDaemon", "/org/gnome/SettingsDaemon/MediaKeys")
	keysbus.GrabMediaPlayerKeys("indimpc", 0, dbus_interface="org.gnome.SettingsDaemon.MediaKeys")
	keysbus.connect_to_signal("MediaPlayerKeyPressed", delegate_mediakeys)

	# create a menu
	menu = gtk.Menu()

	mn_toggle = gtk.MenuItem("Play/Pause")
	mn_toggle.connect("activate", action_handler, "Toggle")
	mn_prev = gtk.MenuItem("Previous")
	mn_prev.connect("activate", action_handler, "Prev")
	mn_next = gtk.MenuItem("Next")
	mn_next.connect("activate", action_handler, "Next")
	mn_separator2 = gtk.SeparatorMenuItem()
	mn_info = gtk.MenuItem("Song Info")
	mn_info.connect("activate", action_handler, "Info")
	mn_separator1 = gtk.SeparatorMenuItem()
	mn_quit = gtk.MenuItem("Quit")
	mn_quit.connect("activate", action_handler, "Quit")

	menu.append(mn_toggle)
	menu.append(mn_prev)
	menu.append(mn_next)
	menu.append(mn_separator1)
	menu.append(mn_info)
	menu.append(mn_separator2)
	menu.append(mn_quit)
	menu.show_all()

	# assign the menu to the indicator
	ind.set_menu(menu)

	gtk.main()
