#!/usr/bin/env python

import gobject
import gtk
import socket, errno, sys, os.path
import dbus, dbus.mainloop.glib

try:
	import appindicator
except:
	sys.stderr.write("[FATAL] indimpc: please install python-appindicator")
	sys.exit()
try:
	import pynotify
except:
	sys.stderr.write("[FATAL] indimpc: please install python-pynotify")
try:
	from mpd import MPDClient
except:
	sys.stderr.write("[FATAL] indimpc: please install python-mpd")

class IndiMPDClient():
	def __init__(self):
		self.setup_client()
		self.oldsongdata = ""
		self.oldstatus = ""

		self.grab_mmkeys()
		self.notifier = pynotify.init("indimpc")
		
		self.indicator = appindicator.Indicator ("indimpc", "media-playback-start", appindicator.CATEGORY_APPLICATION_STATUS)
		self.indicator.set_status(appindicator.STATUS_ACTIVE)
		gobject.timeout_add(500, self.status_loop)
	
	def setup_client(self):
		try:
			self.mpdclient = MPDClient()
			self.mpdclient.connect("localhost", 6600)
			self.oldstatus = self.mpdclient.status()["state"]
		except socket.error, e:
			sys.stderr.write("[FATAL] indimpc: can't connect to mpd. please check if it's running corectly")
			sys.exit()
	
	def setup_if_client_unusable(self):
		try:
			self.mpdclient.status()
		except socket.error, e:
			if e.errno == errno.EPIPE:
				self.setup_client()
	
	def grab_mmkeys(self):
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
		keysbus = bus.get_object("org.gnome.SettingsDaemon", "/org/gnome/SettingsDaemon/MediaKeys")
		keysbus.GrabMediaPlayerKeys("indimpc", 0, dbus_interface="org.gnome.SettingsDaemon.MediaKeys")
		keysbus.connect_to_signal("MediaPlayerKeyPressed", self.delegate_mediakeys)

	def delegate_mediakeys(self, *mmkeys):
		for key in mmkeys:
			if key == "Play":
				self.handle_action(None, "Toggle")
			elif key == "Stop":
				self.handle_action(None, "Stop")
			elif key == "Next":
				self.handle_action(None, "Next")
			elif key == "Previous":
				self.handle_action(None, "Prev")

	def handle_action(self, menu, action):
		self.setup_if_client_unusable()
		# toggle playback (silence/noise ;))
		if action == "Toggle":
			if self.mpdclient.playlistinfo() != []: #if there's a playlist
				if self.mpdclient.currentsong() != {}: #if there's a selected song
					state = self.mpdclient.status()['state']
					if state == "stop":
						self.notify()
						self.mpdclient.play() # play the song from the beginning.
					elif state in ("play", "pause"):
						if state == "pause": # we always notify if we recover from pause.
							self.notify()
						self.mpdclient.pause() # toggle play/pause
				else:
					self.mpdclient.play() # we play from the beginning of the playlist
			else: #there's no playlist
				no_music_notify = pynotify.Notification("Hey, there's nothing to play", 
				"Add some music to your MPD playlist, silly!", None)
				no_music_notify.show()
		# stop (only multimedia keys)
		elif action == "Stop":
			self.mpdclient.stop()
		# next song
		elif action == "Next":
			self.mpdclient.next()
		# previous song
		elif action == "Prev":
			self.mpdclient.previous()
		# notify of current song, overriding
		elif action == "Info":
			self.notify()
		# end application
		else:
			pass

	def status_loop(self):
		self.currentstatus = self.mpdclient.status()["state"]
		self.update_menu()
		self.update_icon()
		self.notify_currentsong()
		self.oldstatus = self.currentstatus
		return True

	def update_icon(self):
		if self.currentstatus != self.oldstatus:
			if self.currentstatus == "play":
				self.indicator.set_icon("media-playback-start")
			elif self.currentstatus == "pause":
				self.indicator.set_icon("media-playback-pause")
			elif self.currentstatus == "stop":
				self.indicator.set_icon("media-playback-stop")

	def update_menu(self):
		if self.currentstatus != self.oldstatus:
			menu = gtk.Menu()
			if self.mpdclient.status()["state"] in ("stop", "pause"):
				mn_toggle = gtk.MenuItem("Play")
			elif self.mpdclient.status()["state"] == "play":
				mn_toggle = gtk.MenuItem("Pause")
			mn_prev = gtk.MenuItem("Previous")
			mn_next = gtk.MenuItem("Next")
			mn_separator = gtk.SeparatorMenuItem()
			mn_info = gtk.MenuItem("Song Info")

			mn_toggle.connect("activate", self.handle_action, "Toggle")
			mn_prev.connect("activate", self.handle_action, "Prev")
			mn_next.connect("activate", self.handle_action, "Next")
			mn_info.connect("activate", self.handle_action, "Info")
			
			menu.append(mn_toggle)
			menu.append(mn_prev)
			menu.append(mn_next)
			menu.append(mn_separator)
			menu.append(mn_info)
			menu.show_all()

			self.indicator.set_menu(menu)

	# Looks for album art
	def get_coverart(self, songdata):
		# we look in the song folder first
		song_dirname = "/var/lib/mpd/music/" + os.path.dirname(songdata["file"]) + "/"
		if os.path.exists(song_dirname + "cover.jpg"):
			return song_dirname + "cover.jpg"
		elif os.path.exists(song_dirname + "album.jpg"):
			return song_dirname + "album.jpg"
		# we can take advantage of sonata's cover database in ~/.covers
		if songdata.has_key("album"):
			if os.path.exists(os.path.expanduser("~/.covers/" + self.get_artist(songdata) + "-" + songdata["album"] + ".jpg")):
				return os.path.expanduser("~/.covers/" + self.get_artist(songdata) + "-" + songdata["album"] + ".jpg")
		return "media-playback-start" #default

	# Returns song title
	def get_title(self, songdata):
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
	def get_artist(self, songdata):
		if songdata.has_key("name"): # we can assume it's a radio or stream
			if songdata.has_key("title"): # we grab the artist info from the title
				return songdata["title"].split(" - ")[0]
		elif songdata.has_key("artist"):
			return songdata["artist"]
		else: #there's no data
			return ""

	def notify(self):
		current_song_notification = pynotify.Notification(self.ctitle, self.cartist, self.ccover)
		current_song_notification.show()

	def notify_currentsong(self):
		currentsongdata = self.mpdclient.currentsong()

		if currentsongdata != {}:
			if currentsongdata != self.oldsongdata:
				self.ctitle = self.get_title(currentsongdata)
				self.cartist = self.get_artist(currentsongdata)
				self.ccover = self.get_coverart(currentsongdata)

				if self.oldsongdata == "":
					self.notify()
				else:
					self.notify()

				self.oldsongdata = currentsongdata
	

if __name__ == "__main__":
	indimpc = IndiMPDClient()
	gtk.main()
