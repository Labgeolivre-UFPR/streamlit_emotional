# i18n.py
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

# Idiomas suportados e padrão
SUPPORTED = ("pt", "en")
DEFAULT_LANG = "pt"

# Pasta de traduções
LOCALES_DIR = Path(__file__).parent / "locales"

class _SafeDict(dict):
    """Mantém placeholders não fornecidos (ex.: '{name}') em vez de quebrar."""
    def __missing__(self, key):
        return "{" + key + "}"

@lru_cache(maxsize=None)
def _load(lang: str) -> Dict[str, Any]:
    """Carrega um YAML de idioma do disco, com cache."""
    if lang not in SUPPORTED:
        lang = DEFAULT_LANG
    path = LOCALES_DIR / f"{lang}.yml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data

def _nget(data: Dict[str, Any], dotted_key: str) -> Optional[Any]:
    """Acesso a chaves aninhadas via 'a.b.c'."""
    cur: Any = data
    for part in dotted_key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur

def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """
    Tradução com fallback:
      1) lang solicitado
      2) DEFAULT_LANG (se diferente)
      3) 'en' e 'pt' (na ordem que faltar)
      4) devolve a própria chave
    Suporta placeholders: t("greet", lang, name="Silvana")
    """
    # ordem de fallback sem duplicatas
    fallbacks = [lang]
    if DEFAULT_LANG not in fallbacks:
        fallbacks.append(DEFAULT_LANG)
    for base in ("en", "pt"):
        if base not in fallbacks:
            fallbacks.append(base)

    value: Optional[Any] = None
    for L in fallbacks:
        value = _nget(_load(L), key)
        if value is not None:
            break

    if value is None:
        return key  # fallback final

    # Normaliza para string (usamos majoritariamente textos)
    if isinstance(value, str):
        # mantém placeholders não fornecidos
        return value.format_map(_SafeDict(kwargs))
    # Caso alguém queira recuperar um dict/list da árvore:
    return str(value)

def exists(key: str, lang: str = DEFAULT_LANG) -> bool:
    """Checa se a chave existe para um idioma (sem considerar fallbacks)."""
    return _nget(_load(lang), key) is not None

def available_languages() -> tuple[str, ...]:
    """Idiomas com arquivo presente na pasta locales/."""
    return tuple(
        L for L in SUPPORTED
        if (LOCALES_DIR / f"{L}.yml").exists()
    )

def reload_locales() -> None:
    """Limpa o cache de arquivos de tradução (caso edite YAMLs em runtime)."""
    _load.cache_clear()
