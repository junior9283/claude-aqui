PREFIX ?= /usr
DESTDIR ?=
VERSION ?= 0.1.0
DISTDIR ?= dist

BINDIR = $(DESTDIR)$(PREFIX)/bin
LIBDIR = $(DESTDIR)$(PREFIX)/lib/claude-aqui
APPDIR = $(DESTDIR)$(PREFIX)/share/applications
ICONDIR = $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps

# escapa o valor para uso no lado de substituição do sed
sedq = $(shell printf '%s' '$(1)' | sed 's/[\\&|]/\\&/g')
INST_LAUNCHER = $(call sedq,$(PREFIX)/bin/claude-aqui-launch)
INST_LIB = $(call sedq,$(PREFIX)/lib/claude-aqui)

PKG_FILES = $(shell find claude_aqui -name '*.py' | sort)

.PHONY: install uninstall dist

install:
	install -d "$(BINDIR)" "$(LIBDIR)/claude_aqui/managers" "$(APPDIR)" "$(ICONDIR)"
	install -m 755 bin/claude-aqui-launch "$(BINDIR)/claude-aqui-launch"
	install -m 755 bin/claude-aqui "$(BINDIR)/claude-aqui"
	sed -i 's|^LIB_DIR = .*|LIB_DIR = "$(INST_LIB)"|' "$(BINDIR)/claude-aqui"
	for f in $(PKG_FILES); do install -m 644 "$$f" "$(LIBDIR)/$$f"; done
	sed -i 's|^DEFAULT_LAUNCHER = .*|DEFAULT_LAUNCHER = "$(INST_LAUNCHER)"|' "$(LIBDIR)/claude_aqui/base.py"
	install -m 644 data/claude-aqui.desktop "$(APPDIR)/claude-aqui.desktop"
	install -m 644 data/claude-aqui.svg "$(ICONDIR)/claude-aqui.svg"

uninstall:
	rm -f "$(BINDIR)/claude-aqui" "$(BINDIR)/claude-aqui-launch" \
		"$(APPDIR)/claude-aqui.desktop" "$(ICONDIR)/claude-aqui.svg"
	rm -rf "$(LIBDIR)"

dist:
	mkdir -p "$(DISTDIR)"
	tar czf "$(DISTDIR)/claude-aqui-$(VERSION).tar.gz" \
		--transform 's|^|claude-aqui-$(VERSION)/|' \
		bin $(PKG_FILES) data Makefile README.md
