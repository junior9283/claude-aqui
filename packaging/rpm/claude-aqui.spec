%{!?version: %global version 0.1.0}
# Sem bytecompile automático: evita __pycache__ fora da lista de arquivos
%global __brp_python_bytecompile %{nil}

Name:           claude-aqui
Version:        %{version}
Release:        1%{?dist}
Summary:        Abre o Claude Code a partir do menu do gerenciador de arquivos
License:        MIT
BuildArch:      noarch
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  make
Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Recommends:     libnotify

%description
Claude Aqui adiciona a opção "Abrir Claude Code aqui" ao menu de contexto do
gerenciador de arquivos e inclui um aplicativo GTK4/libadwaita para ativar,
desativar e conferir a integração.

%prep
%autosetup -n %{name}-%{version}

%build

%install
make install DESTDIR="%{buildroot}" PREFIX=%{_prefix}

%files
%{_bindir}/claude-aqui
%{_bindir}/claude-aqui-launch
%{_prefix}/lib/claude-aqui
%{_datadir}/applications/claude-aqui.desktop
%{_datadir}/icons/hicolor/scalable/apps/claude-aqui.svg

%changelog
* Thu Nov 12 2026 Claude Aqui <noreply@example.com> - 0.1.0-1
- Primeiro pacote
