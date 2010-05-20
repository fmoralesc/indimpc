#!/usr/bin/env python
from py2deb import Py2deb

version = "0.1.3"
changelog = open("changelog.txt", "r").read()

p = Py2deb("indimpc")
p.author = "Felipe Morales"
p.mail = "hel.sheep@gmail.com"
p.description = "Minimalistic MPD client with support for appindicator, multimedia keys and notifications."
p.url = "http://github.com/fmoralesc/indimpc"
p.depends = "python-dbus, python-notify, python-appindicator, python-mpd"
p.license = "gpl"
p.section = "sound"
p.arch = "all"

p["/usr/bin"] = ["indimpc.py|indimpc"]

p.generate(version, changelog)
