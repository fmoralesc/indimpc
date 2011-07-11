indimpc
=======

[screenshots](http://min.us/mcMTiaX)

This is a minimalistic MPD client with support for the gnome-shell indication system and multimedia keys. It is easily configurable and can launch a more featured client when needed.

It depends on:

 + `python-dbus` (dbus-python in some systems)
 + `python-notify`
 + `python-mpd`
 + `python-keybinder` (not needed if using Gnome)

For its normal operation, indimpc requires a notifications daemon, hopefully with support for action-icons, body-markup and persistence (gnome-shell is recommended). If there is no instance of gnome-settings-daemon running, it will fallback to python-keybinder to grab the multimedia keys.

## Notes

You must copy the `indimpc.rc` file included to `~/.config/indimpc`'. To connect to mpd via a socket, you must provide the full socket path as `host`.

indimpc has recently included some support for guake commands. For it to work, you must patch `/usr/lib/guake/dbusiface.py` with the `guake.patch` file provided.

Felipe Morales, <hel.sheep@gmail.com> 

vie jul  8 22:11:08 CLT 2011
