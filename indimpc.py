#!/usr/bin/env python

import gobject
import gtk
import socket, errno, sys, os.path
import dbus, dbus.mainloop.glib
import appindicator
import pynotify
from mpd import MPDClient

# Sends a notification with the current song data.
def current_song_notify(override=False):
	global mpdclient
	global oldsongdata
	
	currentsongdata = mpdclient.currentsong()
	
	# if we have new data about the song, or we explicitly said we wanted to notify
	if (currentsongdata != {} and currentsongdata != oldsongdata) or override==True:
		# if 3 seconds have passed since the beggining of the song (so we don't notify while 
		# quickly advancing in the playlist), or we explicitly said we wanted to notify
		if (mpdclient.status()["time"].split(":")[0] == "3") or override==True:
			
			# check for title info
			if currentsongdata.has_key("title"):
				# if we have a name, we can assume it's a radio stream.
				# we must get our metadata from "title". we won't have "artist" or "album".
				if currentsongdata.has_key("name"):
					# usually "title" will be of the form "artist - title"
					cartist, ctitle = currentsongdata["title"].split(" - ")
				else:
					ctitle = currentsongdata["title"]
			else: # if we dont have a title
				ctitle = currentsongdata["file"]
			
			# check for artist info
			if currentsongdata.has_key("artist"):
				cartist = currentsongdata["artist"]
			else:
				cartist = ""
			
			# look for cover art.
			# first, check for album.
			# we default to this.
			ccover = "media-playback-start"
			
			if currentsongdata.has_key("album"):
				# we take advantage of sonata's behaviour.
				if os.path.exists(os.path.expanduser("~/.covers/"+cartist+"-"+currentsongdata["album"]+".jpg")):
					ccover = os.path.expanduser("~/.covers/"+cartist+"-"+currentsongdata["album"]+".jpg")
				else:
					ccover = "media-playback-start"
			# now, we look in the current directory
			if os.path.exists("/var/lib/mpd/music/" + os.path.dirname(currentsongdata["file"])+"/cover.jpg"):
				ccover = "/var/lib/mpd/music/" + os.path.dirname(currentsongdata["file"])+"/cover.jpg"

			oldsongdata = currentsongdata

			current_song = pynotify.Notification(ctitle, cartist, ccover)
			current_song.show()

		# if we have "name", we can assume we are listening to a radio.
		elif currentsongdata.has_key("name"):
			if currentsongdata.has_key("title"):
				oldsongdata = currentsongdata
				cartist, ctitle = currentsongdata["title"].split(" - ")
				current_song = pynotify.Notification(ctitle, cartist, "media-playback-start")
				current_song.show()
	
	return True #otherwise this function won't run again.

def action_handler(menu,action):
	global mpdclient
	try:
		mpdclient.status()
	except socket.error, e: 
		if e.errno == errno.EPIPE: #the pipe is broken
			print "WARNING: The client pipe was broken. Will attempt to restart the connection."
			client_setup() #let's restart the client

	# play/pause
	if action == "Toggle":
		# if mpd is stopped, but there's a song we can play
		if mpdclient.status()['state'] == 'stop' and mpdclient.currentsong() != {}:
			mpdclient.play()
		# if mpd is playing or paused, we simply toggle
		elif mpdclient.status()['state'] in ('play', 'pause'):
			# if we recover from pause, we notify of the song
			if mpdclient.status()['state'] == 'pause':
				current_song_notify(override=True)
			mpdclient.pause()
		# if there is no selected song, but we have a playlist
		elif mpdclient.currentsong() == {} and mpdclient.playlistinfo() != []:
			mpdclient.play() # plays the first song in the playlist
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
	
	#create the app indicator
	ind = appindicator.Indicator ("indimpc", "sonata", appindicator.CATEGORY_APPLICATION_STATUS)
	ind.set_status (appindicator.STATUS_ACTIVE)

	#prepare the notifications
	notifier = pynotify.init("indimpc")
	csong_timeout = gobject.timeout_add(500, current_song_notify)
	oldsongdata = ""

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
