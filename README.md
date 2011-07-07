indimpc
=======

![indimpc](http://k.min.us/ibpk6S.png)

This is a minimalistic MPD client with support for the gnome-shell indication system and multimedia keys via dbus.

It depends on:

 + pyhton-dbus
 + python-notify
 + python-mpd

## Notes

You must install the indimpc.rc file included in ~/.config/indimpc/

indimpc has recently included some support for guake commands. For it to work, you mast patch /usr/lib/guake/dbusiface.py with the guake.patch file provided.

Felipe Morales, Fri, 9 Apr 2011 00:03:00 -0400
(hel.sheep@gmail.com)
