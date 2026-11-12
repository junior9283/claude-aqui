ARCHDIR = build/arch

.PHONY: arch-src

# Prepara a pasta para o makepkg: tarball de `make dist` + PKGBUILD com a versão ajustada
arch-src: dist
	mkdir -p "$(ARCHDIR)"
	cp "$(DISTDIR)/claude-aqui-$(VERSION).tar.gz" "$(ARCHDIR)/"
	sed 's|^pkgver=.*|pkgver=$(VERSION)|' packaging/arch/PKGBUILD > "$(ARCHDIR)/PKGBUILD"
