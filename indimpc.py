#!/usr/bin/python2

import gobject
import gtk
import socket, errno, sys, os.path
import dbus, dbus.mainloop.glib

try:
	import pynotify
except:
	sys.stderr.write("[FATAL] indimpc: please install python-pynotify\n")
try:
	from mpd import MPDClient
except:
	sys.stderr.write("[FATAL] indimpc: please install python-mpd\n")

class IndiMPDClient():
	def __init__(self):
		self.setup_client()
		self.oldstatus = ""
		self.oldsongdata = ""

		pynotify.init("indimpc")
		self.notification = pynotify.Notification("indiMPC started")
		self.notification.set_hint("action-icons", True)
		gobject.timeout_add(500, self.status_loop)

		self.grab_mmkeys()
	
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
						self.mpdclient.play() # play the song from the beginning.
					elif state in ("play", "pause"):
						self.mpdclient.pause() # toggle play/pause
				else:
					self.mpdclient.play() # we play from the beginning of the playlist
			else: #there's no playlist
				self.notification.set_property("summary", "Hey!")
				self.notification.set_property("body", "Add some music to your MPD playlist first, silly!")
				self.notification.set_property("icon-name", "dialog-warning")
				self.notification.show()
		# stop (only multimedia keys)
		elif action == "Stop":
			self.mpdclient.stop()
		# next song
		elif action == "Next":
			self.play_next()
		# previous song
		elif action == "Prev":
			self.play_previous()

	# Returns song title
	def get_title(self, songdata):
		if songdata.has_key("title"):
			if songdata.has_key("name"): # we can assume it's a radio or stream
				# we split the title from the info we have
				# for streams, "title" is usually of the form "artist - title"
				return songdata["title"].split(" - ")[1]
			else:
				return songdata["title"]
		return songdata["file"] # we return the file path

	# Returns song artist
	def get_artist(self, songdata):
		if songdata.has_key("name"): # we can assume it's a radio or stream
			if songdata.has_key("title"): # we grab the artist info from the title
				return songdata["title"].split(" - ")[0]
		elif songdata.has_key("artist"):
			return songdata["artist"]
		return ""

	def status_loop(self):
		self.currentstatus = self.mpdclient.status()["state"]
		if self.currentstatus != self.oldstatus:
			if self.currentstatus == "play":
				self.nstatus = "media-playback-start"
			elif self.currentstatus == "pause":
				self.nstatus = "media-playback-pause"
			elif self.currentstatus == "stop":
				self.nstatus = "media-playback-stop"
		currentsongdata = self.mpdclient.currentsong()
		if currentsongdata != {}:
			if currentsongdata != self.oldsongdata:
				self.ntitle = self.get_title(currentsongdata)
				self.nartist = self.get_artist(currentsongdata)
			if currentsongdata != self.oldsongdata or self.currentstatus != self.oldstatus:
				self.notify()
		
		self.oldsongdata = currentsongdata
		self.oldstatus = self.currentstatus
		return True

	def notify(self):
		self.notification.set_property("summary", self.ntitle)
		self.notification.set_property("body", "by <i>" + self.nartist + "</i>")
		self.notification.set_property("icon-name", self.nstatus)
		self.notification.clear_actions()
		self.notification.add_action("media-skip-backward", "Previous", self.play_previous)
		if self.currentstatus == "play":
			self.notification.add_action("media-playback-pause", "Toggle", self.toggle_playback)
		elif self.currentstatus == "pause":
			self.notification.add_action("media-playback-start", "Toggle", self.toggle_playback)
		self.notification.add_action("media-skip-forward", "Next", self.play_next)
		self.notification.show()

	def close(self):
		self.notification.close()

	def play_next(self, *args):
		self.mpdclient.next()

	def play_previous(self, *args):
		self.mpdclient.previous()

	def toggle_playback(self, *args):
		self.mpdclient.pause()

if __name__ == "__main__":
	indimpc = IndiMPDClient()
	gtk.quit_add(0, indimpc.close)
	gtk.main()
