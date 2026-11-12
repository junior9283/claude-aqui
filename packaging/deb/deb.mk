DEBDIR ?= build/deb

.PHONY: deb

deb:
	rm -rf "$(DEBDIR)"
	$(MAKE) install DESTDIR="$(DEBDIR)" PREFIX=/usr
	install -d "$(DEBDIR)/DEBIAN" "$(DISTDIR)"
	sed 's|@VERSION@|$(VERSION)|' packaging/deb/control.in > "$(DEBDIR)/DEBIAN/control"
	dpkg-deb --root-owner-group --build "$(DEBDIR)" "$(DISTDIR)/claude-aqui_$(VERSION)_all.deb"
