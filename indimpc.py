#!/usr/bin/python2

import gobject
import gtk
import socket, errno, sys, os.path
import dbus, dbus.mainloop.glib
from ConfigParser import RawConfigParser as configparser
from subprocess import Popen

try:
	import pynotify
except:
	sys.stderr.write("[FATAL] indimpc: please install python-pynotify\n")
try:
	from mpd import MPDClient
except:
	sys.stderr.write("[FATAL] indimpc: please install python-mpd\n")

class IndiMPCPreferences(gtk.Window):
	def __init__(self):
		self.configfile = os.path.expanduser("~/.config/indimpc/indimpc.rc")

		gtk.Window.__init__(self)
		self.connect("destroy", self.write_config)

		self.config = configparser()
		with open(self.configfile, "r") as configfile:
			self.config.readfp(configfile)

		self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.set_position(gtk.WIN_POS_CENTER)
		self.set_resizable(False)
		self.set_title("indimpc preferences")
		self.set_border_width(4)

		prefs_vbox = gtk.VBox()
		self.add(prefs_vbox)
		
		server_prefs_frame = gtk.Frame("MPD")
		server_prefs = gtk.VBox()
		server_prefs.set_border_width(4)
		server_prefs_frame.add(server_prefs)
		prefs_vbox.add(server_prefs_frame)
		host_hbox = gtk.HBox()
		host_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		host_label = gtk.Label("Host:")
		host_label_align.add(host_label)
		host_hbox.pack_start(host_label_align)
		host_entry = gtk.Entry()
		host_entry.set_text(self.config.get("MPD", "host"))
		host_entry.connect("activate", self.change_host)
		host_hbox.pack_end(host_entry, expand=False,fill=False)
		server_prefs.add(host_hbox)
		port_hbox = gtk.HBox()
		port_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		port_label = gtk.Label("Port:")
		port_label_align.add(port_label)
		port_hbox.pack_start(port_label_align)
		port_spin = gtk.SpinButton(gtk.Adjustment(lower=1.0, upper=64000.0, step_incr=100.0))
		port_spin.set_value(self.config.getint("MPD", "port"))
		port_spin.connect("value-changed", self.change_port)
		port_hbox.pack_end(port_spin, expand=False, fill=False)
		server_prefs.add(port_hbox)
		
		client_prefs_frame = gtk.Frame("Client")
		client_prefs = gtk.VBox()
		client_prefs.set_border_width(4)
		client_prefs_frame.add(client_prefs)
		name_hbox = gtk.HBox()
		name_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		name_label = gtk.Label("Name:")
		name_label_align.add(name_label)
		name_hbox.pack_start(name_label_align)
		name_entry = gtk.Entry()
		name_entry.set_text(self.config.get("Client", "name"))
		name_entry.connect("activate", self.set_client_name)
		name_hbox.add(name_entry)
		client_prefs.pack_start(name_hbox, expand=False,fill=False)
		mode_hbox = gtk.HBox()
		mode_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		mode_label = gtk.Label("Mode:")
		mode_label_align.add(mode_label)
		mode_hbox.pack_start(mode_label_align)
		mode_entry = gtk.combo_box_entry_new_text()
		mode_entry.insert_text(0, "standalone")
		mode_entry.insert_text(0, "guake")
		if self.config.get("Client", "mode") not in ("standalone", "guake"):
			mode_entry.insert_text(0, self.config.get("Client", "mode"))
		mode_entry.set_active(0)
		mode_entry.connect("changed", self.set_client_mode)
		mode_hbox.add(mode_entry)
		client_prefs.pack_start(mode_hbox, expand=False,fill=False)
		command_hbox = gtk.HBox()
		command_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		command_label = gtk.Label("Command:")
		command_label_align.add(command_label)
		command_hbox.pack_start(command_label_align)
		command_entry = gtk.Entry()
		command_entry.set_text(self.config.get("Client", "command"))
		command_entry.connect("activate", self.set_client_command)
		command_hbox.add(command_entry)
		client_prefs.pack_start(command_hbox, expand=False,fill=False)
		prefs_vbox.add(client_prefs_frame)
		prefs_vbox.show_all()

		self.show()

	def change_host(self, entry):
		self.config.set("MPD", "host", entry.get_text())

	def change_port(self, spin):
		self.config.set("MPD", "port", str(int(spin.get_value())))

	def set_client_name(self, entry):
		self.config.set("Client", "name", entry.get_text())

	def set_client_mode(self, comboentry):
		self.config.set("Client", "mode", comboentry.get_model()[comboentry.get_active()][0])
	
	def set_client_command(self, entry):
		self.config.set("Client", "command", entry.get_text())

	def write_config(self, *args):
		with open(self.configfile, "w") as configfile:
			self.config.write(configfile)
		Popen(["indimpc"])
		gtk.main_quit()

class IndiMPDClient(object):
	def __init__(self):
		self.configfile = os.path.expanduser("~/.config/indimpc/indimpc.rc")
		self.config = configparser()
		with open(self.configfile, "r") as configfile:
			self.config.readfp(configfile)
		# the name of the client, the command for it, and how to run it ("mode"). if mode is "standalone", launch directly; if "guake", launch within guake; anythin else will asume the mode is a terminal emulator.
		self.client = {"name": self.config.get("Client", "name"),
				"mode": self.config.get("Client", "mode"),
				"command": self.config.get("Client", "command")}
	
		self.setup_dbus()
		self.setup_client()
		self.oldstatus = ""
		self.oldsongdata = ""

		pynotify.init("indimpc")
		self.notification = pynotify.Notification("indiMPC started")
		self.notification.set_hint("action-icons", True)
		gobject.timeout_add(500, self.status_loop)

		self.grab_mmkeys()

	def setup_dbus(self):
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
	
	def setup_client(self):
		global MPD
		try:
			self.mpdclient = MPDClient()
			self.mpdclient.connect(self.config.get("MPD", "host"), int(self.config.get("MPD", "port")))
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
		keysbus = self.bus.get_object("org.gnome.SettingsDaemon", "/org/gnome/SettingsDaemon/MediaKeys")
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
				self.notification.clear_actions()
				self.notification.add_action(self.client["name"], self.client["name"], self.launch_player)
				self.notification.show()
		# stop (only multimedia keys)
		elif action == "Stop":
			self.stop()
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
		currentstatus = self.mpdclient.status()["state"]
		if currentstatus != self.oldstatus:
			if currentstatus == "play":
				self.nstatus = "media-playback-start"
			elif currentstatus == "pause":
				self.nstatus = "media-playback-pause"
			elif currentstatus == "stop":
				self.nstatus = "media-playback-stop"
		currentsongdata = self.mpdclient.currentsong()
		if currentsongdata != {}:
			if currentsongdata != self.oldsongdata:
				self.ntitle = self.get_title(currentsongdata)
				self.nartist = self.get_artist(currentsongdata)
			if currentsongdata != self.oldsongdata or currentstatus != self.oldstatus:
				self.notify()
		
		self.oldsongdata = currentsongdata
		self.oldstatus = currentstatus
		return True

	def notify(self):
		self.notification.set_property("summary", self.ntitle)
		self.notification.set_property("body", "by <i>" + self.nartist + "</i>")
		self.notification.set_property("icon-name", self.nstatus)
		self.notification.clear_actions()
		self.notification.add_action(self.client["name"], self.client["name"], self.launch_player)
		self.notification.add_action("P", "P", self.open_preferences)
		self.notification.add_action("media-skip-backward", "Previous", self.play_previous)
		currentstatus = self.mpdclient.status()["state"]
		if currentstatus == "play":
			self.notification.add_action("media-playback-pause", "Toggle", self.toggle_playback)
		elif currentstatus == "pause":
			self.notification.add_action("media-playback-start", "Toggle", self.toggle_playback)
		elif currentstatus == "stop":
			self.notification.add_action("media-playback-start", "Play", self.start_playing)
		self.notification.add_action("media-playback-stop", "Stop", self.stop)
		self.notification.add_action("media-skip-forward", "Next", self.play_next)
		self.notification.show()

	def close(self):
		self.notification.close()

	def play_next(self, *args):
		self.mpdclient.next()
		self.notify()

	def play_previous(self, *args):
		self.mpdclient.previous()
		self.notify()

	def toggle_playback(self, *args):
		if self.mpdclient.status()["state"] == "pause":
			self.mpdclient.play()
		else:
			self.mpdclient.pause()
		self.notify()
	
	def start_playing(self, *args):
		self.mpdclient.play()
		self.notify()

	def stop(self, *args):
		self.mpdclient.stop()
		self.notify()

	def open_preferences(self, *args):
		IndiMPCPreferences()
		self.notify()

	def launch_player(self, *args):
		if self.client["mode"] == "guake":
			# we will control guake via DBus
			guake = self.bus.get_object('org.guake.RemoteControl', '/org/guake/RemoteControl')
			guake.execute_command("q\n" + self.client["command"], dbus_interface="org.guake.RemoteControl") # "q\n" is a hack so ncmpcpp will quit if it's already running in the terminal (we can't do better with the guake DBus API)
			guake.show_forced(dbus_interface="org.guake.RemoteControl") # this depends on our patch for guake
		elif self.client["mode"] == "standalone":
			pargs = self.client["command"].split()
			Popen(pargs)
		else: # we will assume we are running a terminal client; the mode is the terminal emulator we will use
			pargs = [self.client["mode"], "-e"] # gnome-terminal, xterm and uxterm work with -e
			pargs.extend(self.client["command"].split())
			Popen(pargs)
		self.notify()

if __name__ == "__main__":
	indimpc = IndiMPDClient()
	gtk.quit_add(0, indimpc.close)
	gtk.main()
