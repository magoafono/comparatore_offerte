"""Motore di filtri per le offerte."""

from typing import List, Callable
from parser import Offerta
from config import BLACKLIST_CONDIZIONI_DEFAULT, REGIONI_MAP


class FiltroOfferte:
    """Classe per applicare filtri concatenabili alle offerte."""

    def __init__(self, offerte: List[Offerta]):
        self.offerte = offerte

    def filtra(self, condizione: Callable[[Offerta], bool]) -> "FiltroOfferte":
        self.offerte = [o for o in self.offerte if condizione(o)]
        return self

    def by_tipo_cliente(self, tipo: str) -> "FiltroOfferte":
        if tipo:
            return self.filtra(lambda o: o.tipo_cliente == tipo)
        return self

    def by_tipo_offerta(self, tipo: str) -> "FiltroOfferte":
        if tipo and tipo != "tutte":
            return self.filtra(lambda o: o.tipo_offerta == tipo)
        return self

    def by_tipologia_fasce(self, fasce: str) -> "FiltroOfferte":
        if fasce and fasce != "tutte":
            return self.filtra(lambda o: o.tipologia_fasce == fasce)
        return self

    def by_consumo_range(self, consumo: int) -> "FiltroOfferte":
        if consumo is None or consumo <= 0:
            return self
        return self.filtra(
            lambda o: (
                (o.consumo_min is None or consumo >= o.consumo_min)
                and (o.consumo_max is None or consumo <= o.consumo_max)
            )
        )

    def by_potenza_range(self, potenza: float) -> "FiltroOfferte":
        if potenza is None or potenza <= 0:
            return self
        # Alcune offerte hanno limiti di potenza impliciti; per ora filtriamo per consumo
        # che è correlato. Se in futuro il XML include potenza min/max, aggiorniamo.
        return self

    def by_venditori(self, venditori: List[str]) -> "FiltroOfferte":
        if not venditori:
            return self
        venditori_lower = [v.lower() for v in venditori]
        return self.filtra(lambda o: o.piva_utente.lower() in venditori_lower)

    def by_solo_semplici(self, attivo: bool) -> "FiltroOfferte":
        if not attivo:
            return self
        # Escludi offerte con LIMITANTE=01 o con parole chiave nella descrizione
        return self.filtra(
            lambda o: (
                all(not c.limitante for c in o.condizioni)
                and not any(
                    kw in o.descrizione.lower()
                    for kw in BLACKLIST_CONDIZIONI_DEFAULT
                )
            )
        )

    def by_no_oneri_recesso(self, attivo: bool) -> "FiltroOfferte":
        if not attivo:
            return self
        # Il sito esclude tutte le offerte con condizioni limitanti (LIMITANTE=01)
        # quando l'utente seleziona "Escludi oneri di recesso"
        return self.filtra(
            lambda o: not any(c.limitante for c in o.condizioni)
        )

    def by_esclude_condizioni_keyword(self, keywords: List[str]) -> "FiltroOfferte":
        if not keywords:
            return self
        keywords_lower = [k.lower() for k in keywords]
        return self.filtra(
            lambda o: not any(
                any(kw in c.descrizione.lower() for kw in keywords_lower)
                for c in o.condizioni
            )
        )

    def by_tipo_attivazione(self, tipi: List[str]) -> "FiltroOfferte":
        if not tipi or "tutte" in tipi:
            return self
        return self.filtra(
            lambda o: any(t in o.tipologie_att_contr for t in tipi)
        )

    def by_zone_geografiche(self, zona: str = "") -> "FiltroOfferte":
        if not zona:
            return self
        if zona in REGIONI_MAP:
            zona_key = zona
        else:
            zona_key = next((k for k, v in REGIONI_MAP.items() if v == zona.lower()), None)
        if zona_key is None:
            return self.filtra(lambda o: len(o.regioni) == 0)
        return self.filtra(
            lambda o: len(o.regioni) == 0 or zona_key in o.regioni
        )

    def get(self) -> List[Offerta]:
        return self.offerte
