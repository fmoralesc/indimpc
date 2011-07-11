#!/usr/bin/python2

import gobject
import gtk
import socket, errno, sys, os.path, os
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

class IndiMPCConfiguration(object):
	def __init__(self, custom_config_path=None):
		xdg_config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
		xdg_config_path = os.path.join(xdg_config_dir, 'indimpc/indimpc.rc')
		if custom_config_path:
			self.config_path = custom_config_path
		elif os.path.isfile(xdg_config_path):
			self.config_path = xdg_config_path
		else:
			self.config_path = xdg_config_path

		self.config_parser = configparser()
		if self.config_path:
			self.config_parser.read(self.config_path)
		else:
			self.config_path = xdg_config_path

		if self.config_parser.has_section("General"):
			self.general_grab_keys = self.config_parser.getboolean("General", "grab_keys")
		else:
			self.general_grab_keys = True
		
		if self.config_parser.has_section("MPD"):
			self.mpd_host = self.config_parser.get("MPD", "host")
			self.mpd_port = self.config_parser.getint("MPD", "port")
			self.mpd_password = self.config_parser.get("MPD", "password")
		else:
			env_host = os.environ.get("MPD_HOST", "localhost")
			if "@" in env_host:
				self.mpd_password, self.mpd_host = env_host.split("@", 1)
			else:
				self.mpd_password, self.mpd_host = "", env_host

			env_port = os.environ.get("MPD_PORT", 6600)
			self.mpd_port = int(env_port)

		if self.config_parser.has_section("Client"):
			self.client_name = self.config_parser.get("Client", "name")
			self.client_mode = self.config_parser.get("Client", "mode")
			self.client_command = self.config_parser.get("Client", "command")
		else:
			self.client_name = "ncmpc++"
			self.client_mode = "gnome-terminal"
			self.client_command = "ncmpcpp"
	 
	def set(self, section, key, value):
		def is_exe(path):
			return os.path.exists(path) and os.access(path, os.X_OK)
		
		def is_proper_executable_path(program):
			fpath, fname = os.path.split(program)
			if fpath:
				if is_exe(program):
					return True
			else:
				for path in os.environ["PATH"].split(os.pathsep):
					exe_file = os.path.join(path, program)
					if is_exe(exe_file):
						return True
			return False
		
		if not self.config_parser.has_section(section):
			self.config_parser.add_section(section)
		
		if (section, key) == ("Client", "command") and not is_proper_executable_path(value):
			# we have an invalid command, so we simply return
			return
		else:
			self.config_parser.set(section, key, value)
			self.__dict__["_".join((section.lower(), key.lower()))] = value # we update self.property this way
	
	def write(self):
		if self.config_path:
			with open(self.config_path, "w") as configfile:
				self.config_parser.write(configfile)
	
class IndiMPCPreferencesDialog(gtk.Window):
	def __init__(self):
		self.config = IndiMPCConfiguration()
		self.mpdclient = MPDClient()
		self.mpdclient.connect(self.config.mpd_host, self.config.mpd_port)
		if self.config.mpd_password not in (None, ""):
			self.mpdclient.password(self.config.mpd_password)

		gtk.Window.__init__(self)
		self.connect("key-press-event", self.keyboard_handler)
		self.connect("destroy", self.write_config)

		self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
		self.set_position(gtk.WIN_POS_CENTER)
		self.set_resizable(False)
		self.set_title("indimpc preferences")
		self.set_border_width(4)

		prefs_vbox = gtk.Notebook()
		self.add(prefs_vbox)

		playback_modes = gtk.VBox()
		playback_modes.set_border_width(4)
		playback_modes.set_spacing(2)
		prefs_vbox.append_page(playback_modes, gtk.Label("Playback"))
		self.repeat_check = gtk.CheckButton("Repeat")
		self.repeat_check.set_active(bool(int(self.mpdclient.status()["repeat"])))
		self.repeat_check.connect("toggled", lambda a: self.mpdclient.repeat(int(not bool(int(self.mpdclient.status()["repeat"])))))
		playback_modes.pack_start(self.repeat_check, fill=False, expand=False)
		self.random_check = gtk.CheckButton("Random")
		self.random_check.set_active(bool(int(self.mpdclient.status()["random"])))
		self.random_check.connect("toggled", lambda a: self.mpdclient.random(int(not bool(int(self.mpdclient.status()["random"])))))
		playback_modes.pack_start(self.random_check, fill=False, expand=False)
		self.consume_check = gtk.CheckButton("Consume")
		self.consume_check.set_active(bool(int(self.mpdclient.status()["consume"])))
		self.consume_check.connect("toggled", lambda a: self.mpdclient.consume(int(not bool(int(self.mpdclient.status()["consume"])))))
		playback_modes.pack_start(self.consume_check, fill=False, expand=False)
		self.single_check = gtk.CheckButton("Single")
		self.single_check.set_active(bool(int(self.mpdclient.status()["single"])))
		self.single_check.connect("toggled", lambda a: self.mpdclient.single(int(not bool(int(self.mpdclient.status()["single"])))))
		playback_modes.pack_start(self.single_check, fill=False, expand=False)

		general_prefs = gtk.VBox()
		general_prefs.set_border_width(4)
		self.grab_mmkeys_check = gtk.CheckButton("Grab multimedia keys")
		self.grab_mmkeys_check.set_active(self.config.general_grab_keys)
		general_prefs.pack_start(self.grab_mmkeys_check, fill=False, expand=False)
		prefs_vbox.append_page(general_prefs, gtk.Label("Desktop/UI"))
		
		server_prefs = gtk.VBox()
		server_prefs.set_border_width(4)
		server_prefs.set_spacing(2)
		prefs_vbox.append_page(server_prefs, gtk.Label("MPD"))
		host_hbox = gtk.HBox()
		host_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		host_label = gtk.Label("Host:")
		host_label_align.add(host_label)
		host_hbox.pack_start(host_label_align)
		self.host_entry = gtk.Entry()
		self.host_entry.set_text(self.config.mpd_host)
		host_hbox.pack_end(self.host_entry, expand=False,fill=False)
		server_prefs.pack_start(host_hbox,expand=False, fill=False)
		port_hbox = gtk.HBox()
		port_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		port_label = gtk.Label("Port:")
		port_label_align.add(port_label)
		port_hbox.pack_start(port_label_align)
		self.port_spin = gtk.SpinButton(gtk.Adjustment(lower=1.0, upper=64000.0, step_incr=100.0))
		self.port_spin.set_value(self.config.mpd_port)
		port_hbox.pack_end(self.port_spin, expand=False, fill=False)
		server_prefs.pack_start(port_hbox, expand=False, fill=False)
		password_hbox = gtk.HBox()
		password_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		password_label = gtk.Label("Password:")
		password_label_align.add(password_label)
		password_hbox.pack_start(password_label_align)
		self.password_entry = gtk.Entry()
		self.password_entry.set_visibility(False)
		self.password_entry.connect("button-press-event", self.toggle_password)
		self.password_entry.set_text(self.config.mpd_password)
		password_hbox.pack_end(self.password_entry, expand=False,fill=False)
		server_prefs.pack_start(password_hbox, expand=False, fill=False)
		
		client_prefs = gtk.VBox()
		client_prefs.set_border_width(4)
		client_prefs.set_spacing(2)
		prefs_vbox.append_page(client_prefs, gtk.Label("Client"))
		name_hbox = gtk.HBox()
		name_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		name_label = gtk.Label("Name:")
		name_label_align.add(name_label)
		name_hbox.pack_start(name_label_align)
		self.name_entry = gtk.Entry()
		self.name_entry.set_text(self.config.client_name)
		name_hbox.add(self.name_entry)
		client_prefs.pack_start(name_hbox, expand=False,fill=False)
		mode_hbox = gtk.HBox()
		mode_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		mode_label = gtk.Label("Mode:")
		mode_label_align.add(mode_label)
		mode_hbox.pack_start(mode_label_align)
		self.mode_entry = gtk.combo_box_entry_new_text()
		self.mode_entry.insert_text(0, "standalone")
		self.mode_entry.insert_text(0, "guake")
		self.mode_entry.insert_text(0, "gnome-terminal")
		if self.config.client_mode not in ("standalone", "guake", "gnome-terminal"):
			self.mode_entry.insert_text(0, self.config.client_mode)
		self.mode_entry.set_active(0)
		mode_hbox.add(self.mode_entry)
		client_prefs.pack_start(mode_hbox, expand=False,fill=False)
		command_hbox = gtk.HBox()
		command_label_align = gtk.Alignment(xalign=0.0, yalign=0.5)
		command_label = gtk.Label("Command:")
		command_label_align.add(command_label)
		command_hbox.pack_start(command_label_align)
		self.command_entry = gtk.Entry()
		self.command_entry.set_text(self.config.client_command)
		command_hbox.add(self.command_entry)
		client_prefs.pack_start(command_hbox, expand=False,fill=False)
		prefs_vbox.show_all()
		self.show()

	def keyboard_handler(self, event, data=None):
		key = gtk.gdk.keyval_name(data.keyval)
		if key == "Escape":
			self.write_config()

	def toggle_password(self, entry, event):
		if event.type == gtk.gdk._2BUTTON_PRESS:
			if self.password_entry.get_visibility() == False:
				self.password_entry.set_visibility(True)
			else:
				self.password_entry.set_visibility(False)

	def write_config(self, *args):
		self.config.set("General", "grab_keys", self.grab_mmkeys_check.get_active())
		self.config.set("MPD", "host", self.host_entry.get_text())
		self.config.set("MPD", "port", int(self.port_spin.get_value()))
		self.config.set("MPD", "password", self.password_entry.get_text())
		self.config.set("Client", "name", self.name_entry.get_text())
		self.config.set("Client", "mode", self.mode_entry.get_model()[self.mode_entry.get_active()][0])
		self.config.set("Client", "command", self.command_entry.get_text())
		self.config.write()
		Popen(["indimpc"])
		gtk.main_quit()

class IndiMPDClient(object):
	def __init__(self):
		self.config = IndiMPCConfiguration()
	
		self.setup_dbus()
		self.setup_client()
		self.oldstatus = ""
		self.oldsongdata = ""

		pynotify.init("indimpc")
		self.notification = pynotify.Notification("indiMPC started")
		self.notification.set_hint("action-icons", True)
		gobject.timeout_add(500, self.status_loop)

		if self.config.general_grab_keys:
			self.grab_mmkeys()

	def setup_dbus(self):
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
	
	def setup_client(self):
		global MPD
		try:
			self.mpdclient = MPDClient()
			self.mpdclient.connect(self.config.mpd_host, self.config.mpd_port)
			if self.config.mpd_password not in ("", None):
				self.mpdclient.password(self.config.mpd_password)
			self.oldstatus = self.mpdclient.status()["state"]
		except socket.error, e:
			sys.stderr.write("[FATAL] indimpc: can't connect to mpd. please check if it's running corectly\n")
			sys.exit()
	
	def setup_if_client_unusable(self):
		try:
			self.mpdclient.status()
		except socket.error, e:
			if e.errno == errno.EPIPE:
				self.setup_client()
	
	def grab_mmkeys(self):
		try:
			keysbus = self.bus.get_object("org.gnome.SettingsDaemon", "/org/gnome/SettingsDaemon/MediaKeys")
			keysbus.GrabMediaPlayerKeys("indimpc", 0, dbus_interface="org.gnome.SettingsDaemon.MediaKeys")
			keysbus.connect_to_signal("MediaPlayerKeyPressed", self.delegate_mediakeys)
		except:
			sys.stderr.write("[WARNING] indimpc: can't grab multimedia keys using gnome-settings-daemon.\n")
			try:
				import keybinder
				keybinder.bind("XF86AudioPlay", self.toggle_playback)
				keybinder.bind("XF86AudioStop", self.stop)
				keybinder.bind("XF86AudioPrev", self.play_previous)
				keybinder.bind("Xf86AudioNext", self.play_next)
			except:
				sys.stderr.write("[WARNING] indimpc: can't grab multimedia keys using keybinder either.")

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
				self.notification.add_action(self.config.client_name, self.config.client_name, self.launch_player)
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
		self.notification.add_action(self.config.client_name, self.config.client_name, self.launch_player)
		self.notification.add_action("system-run", "P", self.open_preferences)
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
		IndiMPCPreferencesDialog()
		self.notify()

	def launch_player(self, *args):
		if self.config.client_mode == "guake":
			# we will control guake via DBus
			guake = self.bus.get_object('org.guake.RemoteControl', '/org/guake/RemoteControl')
			guake.execute_command("q\n" + self.config.client_command, dbus_interface="org.guake.RemoteControl") # "q\n" is a hack so ncmpcpp will quit if it's already running in the terminal (we can't do better with the guake DBus API)
			guake.show_forced(dbus_interface="org.guake.RemoteControl") # this depends on our patch for guake
		elif self.config.client_mode == "standalone":
			pargs = self.config.client_command.split()
			Popen(pargs)
		else: # we will assume we are running a terminal client; the mode is the terminal emulator we will use
			pargs = [self.config.client_mode, "-e"] # gnome-terminal, xterm and uxterm work with -e
			pargs.extend(self.config.client_command.split())
			Popen(pargs)
		self.notify()

if __name__ == "__main__":
	if "-p" in sys.argv:
		IndiMPCPreferencesDialog()
	else:
		indimpc = IndiMPDClient()
		gtk.quit_add(0, indimpc.close)
	gtk.main()
