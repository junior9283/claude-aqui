"""Auxiliares comuns aos gerenciadores baseados em arquivos .desktop/.nemo_action."""
from __future__ import annotations

import re

ACTION_NAME = "Abrir Claude Code aqui"
ICON = "claude-aqui"


def exec_line(stub: object, code: str) -> str:
    """Valor de `Exec`: stub entre aspas duplas (Desktop Entry Spec) + código de campo.

    Dentro das aspas, `"`, `` ` ``, `$` e `\\` levam barra invertida; como o valor
    é uma string do arquivo, cada barra invertida é dobrada de novo. `%` vira `%%`.
    """
    exec_level = re.sub(r'([\\"`$])', r"\\\1", str(stub).replace("%", "%%"))
    file_level = exec_level.replace("\\", "\\\\")
    return f'"{file_level}" {code}'
