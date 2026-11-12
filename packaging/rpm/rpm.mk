RPMBUILD_DIR ?= $(CURDIR)/build/rpm

.PHONY: rpm

# O diretório de build (e o buildroot) fica num diretório temporário sem espaços: o brp add-det do
# rpmbuild não aceita espaços no caminho (o projeto pode estar numa pasta assim).
rpm: dist
	rm -rf "$(RPMBUILD_DIR)"
	mkdir -p "$(RPMBUILD_DIR)/SOURCES"
	cp "$(DISTDIR)/claude-aqui-$(VERSION).tar.gz" "$(RPMBUILD_DIR)/SOURCES/"
	root=$$(mktemp -d) && { \
		rpmbuild -bb packaging/rpm/claude-aqui.spec \
			--define "_topdir $(RPMBUILD_DIR)" --define "_builddir $$root" \
			--define "version $(VERSION)"; rc=$$?; rm -rf "$$root"; exit $$rc; }
	cp "$(RPMBUILD_DIR)"/RPMS/noarch/claude-aqui-$(VERSION)-*.rpm "$(DISTDIR)/"
