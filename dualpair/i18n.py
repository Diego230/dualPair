"""Tiny translation table (English + Italian). Language from LANGUAGE/LC_ALL/LC_MESSAGES/LANG."""
import os

STRINGS = {
    "en": {
        # errors
        "err.not_root": "Administrator rights are needed to read the Bluetooth settings.",
        "err.no_windows": "No Windows installation was found on this computer's disks.",
        "err.no_windows_at": "No Windows installation found in {path}.",
        "err.bitlocker": "The Windows disk is encrypted with BitLocker ({devices}), so Linux cannot read it. "
                         "Unlock it first (with its recovery key) or export the keys from Windows.",
        "err.hive_invalid": "The Windows registry file could not be read ({path}).",
        "err.no_bt_keys": "Windows has no paired Bluetooth devices.",
        "err.no_linux_adapter": "No Bluetooth adapter found in Linux. Turn Bluetooth on and try again.",
        "err.hive_dirty": "Windows was not fully shut down, so its data may be out of date. Start Windows, "
                          "then shut it down while holding Shift (or turn off Fast Startup), and try again.",
        "err.unknown_device": "Unknown device: {address}.",
        "err.no_backups": "There are no backups to restore.",
        "err.unknown_backup": "Backup {backup} does not exist.",
        "err.helper_failed": "The helper stopped unexpectedly: {detail}",
        "err.auth_cancelled": "Authorization was cancelled.",
        "err.option_not_allowed": "Not allowed when started from the app: {option}.",
        "err.read_only": "This helper can only read; '{command}' is not allowed.",
        "err.bad_backup": "Backup {backup} is damaged or was not made by DualPair: not restored.",
        "err.internal": "Unexpected error: {detail}",
        # statuses
        "status.needs_sync": "Keys differ: copy them from Windows",
        "status.windows_only": "Paired only in Windows: import it",
        "status.in_sync": "Works on both systems",
        "status.linux_only": "Paired only in Linux: pair it in Windows, then come back",
        "kind.classic": "Classic", "kind.le": "Bluetooth LE", "kind.dual": "Classic + LE",
        "experimental": "experimental",
        # notes
        "note.adapter_mapped": "The Bluetooth adapter has a different address in Windows ({windows}) "
                               "and Linux ({linux}). Assuming it is the same one.",
        "note.adapter_unmatched": "Windows adapter {windows} does not match any Linux adapter.",
        "note.hive_dirty": "Windows was not fully shut down: its data may be out of date. Shut Windows down "
                           "while holding Shift, or turn off Fast Startup, before syncing.",
        # CLI
        "cli.source": "Windows: {source}",
        "cli.none": "No paired devices found.",
        "cli.applied": "Synced {n} device(s). Backup: {backup}",
        "cli.nothing": "Nothing to sync.",
        "cli.restored": "Restored backup {backup}.",
        "cli.no_backups": "No backups.",
        "cli.hint_sync": "Run with 'sync --all' to copy the keys from Windows.",
        # GUI
        "app.title": "DualPair",
        "gui.start.title": "Bluetooth for Windows and Linux",
        "gui.start.desc": "Pair your devices in Windows first. Then scan here: DualPair copies the keys "
                          "into Linux, so the same devices work on both systems without pairing again.",
        "gui.scan": "Scan",
        "gui.rescan": "Scan again",
        "gui.scanning": "Reading Windows and Linux Bluetooth settings…",
        "gui.syncing": "Copying keys…",
        "gui.error.title": "Something went wrong",
        "gui.retry": "Try again",
        "gui.group.todo": "To sync",
        "gui.group.todo.desc": "These devices will work in Linux after syncing. Windows is not modified.",
        "gui.group.ok": "Already working",
        "gui.group.linux": "Only in Linux",
        "gui.sync_n": "Sync {n} device(s)",
        "gui.sync_none": "Select devices to sync",
        "gui.all_ok.title": "Everything is in sync",
        "gui.all_ok.desc": "Every device paired in Windows also works in Linux.",
        "gui.done": "Synced {n} device(s). Move or use them to reconnect.",
        "gui.restore": "Undo last sync",
        "gui.restored": "Last sync undone.",
        "gui.about": "About DualPair",
        "gui.source": "Windows found on {source}",
        "gui.experimental.tip": "Imported with a guessed key type: if it does not connect, pair it in Linux "
                                "too and sync again.",
    },
    "it": {
        "err.not_root": "Servono i permessi di amministratore per leggere le impostazioni Bluetooth.",
        "err.no_windows": "Non ho trovato un'installazione di Windows sui dischi di questo computer.",
        "err.no_windows_at": "Nessuna installazione di Windows in {path}.",
        "err.bitlocker": "Il disco di Windows è cifrato con BitLocker ({devices}) e Linux non può leggerlo. "
                         "Sbloccalo prima (con la chiave di ripristino) oppure esporta le chiavi da Windows.",
        "err.hive_invalid": "Non riesco a leggere il file del registro di Windows ({path}).",
        "err.no_bt_keys": "In Windows non ci sono dispositivi Bluetooth associati.",
        "err.no_linux_adapter": "Nessun adattatore Bluetooth in Linux. Accendi il Bluetooth e riprova.",
        "err.hive_dirty": "Windows non è stato spento del tutto, quindi i suoi dati potrebbero essere vecchi. "
                          "Avvia Windows, spegnilo tenendo premuto Maiusc (o disattiva l'avvio rapido) e riprova.",
        "err.unknown_device": "Dispositivo sconosciuto: {address}.",
        "err.no_backups": "Non ci sono backup da ripristinare.",
        "err.unknown_backup": "Il backup {backup} non esiste.",
        "err.helper_failed": "L'helper si è interrotto: {detail}",
        "err.auth_cancelled": "Autorizzazione annullata.",
        "err.option_not_allowed": "Non consentito quando viene avviato dall'app: {option}.",
        "err.read_only": "Questo helper può solo leggere: '{command}' non è consentito.",
        "err.bad_backup": "Il backup {backup} è danneggiato o non è stato creato da DualPair: non ripristinato.",
        "err.internal": "Errore imprevisto: {detail}",
        "status.needs_sync": "Chiavi diverse: copiale da Windows",
        "status.windows_only": "Associato solo in Windows: importalo",
        "status.in_sync": "Funziona su entrambi i sistemi",
        "status.linux_only": "Associato solo in Linux: associalo in Windows, poi torna qui",
        "kind.classic": "Classico", "kind.le": "Bluetooth LE", "kind.dual": "Classico + LE",
        "experimental": "sperimentale",
        "note.adapter_mapped": "L'adattatore Bluetooth ha un indirizzo diverso in Windows ({windows}) "
                               "e in Linux ({linux}). Lo considero lo stesso.",
        "note.adapter_unmatched": "L'adattatore di Windows {windows} non corrisponde a nessun adattatore di Linux.",
        "note.hive_dirty": "Windows non è stato spento del tutto: i dati potrebbero essere vecchi. Prima di "
                           "sincronizzare, spegni Windows tenendo premuto Maiusc o disattiva l'avvio rapido.",
        "cli.source": "Windows: {source}",
        "cli.none": "Nessun dispositivo associato.",
        "cli.applied": "Sincronizzati {n} dispositivi. Backup: {backup}",
        "cli.nothing": "Niente da sincronizzare.",
        "cli.restored": "Ripristinato il backup {backup}.",
        "cli.no_backups": "Nessun backup.",
        "cli.hint_sync": "Esegui 'sync --all' per copiare le chiavi da Windows.",
        "app.title": "DualPair",
        "gui.start.title": "Bluetooth per Windows e Linux",
        "gui.start.desc": "Associa prima i dispositivi in Windows. Poi cerca qui: DualPair copia le chiavi "
                          "in Linux, così gli stessi dispositivi funzionano su entrambi senza riassociarli.",
        "gui.scan": "Cerca",
        "gui.rescan": "Cerca di nuovo",
        "gui.scanning": "Leggo le impostazioni Bluetooth di Windows e Linux…",
        "gui.syncing": "Copio le chiavi…",
        "gui.error.title": "Qualcosa non va",
        "gui.retry": "Riprova",
        "gui.group.todo": "Da sincronizzare",
        "gui.group.todo.desc": "Dopo la sincronizzazione funzioneranno anche in Linux. Windows non viene modificato.",
        "gui.group.ok": "Già funzionanti",
        "gui.group.linux": "Solo in Linux",
        "gui.sync_n": "Sincronizza {n} dispositivi",
        "gui.sync_none": "Seleziona i dispositivi da sincronizzare",
        "gui.all_ok.title": "È tutto sincronizzato",
        "gui.all_ok.desc": "Ogni dispositivo associato in Windows funziona anche in Linux.",
        "gui.done": "Sincronizzati {n} dispositivi. Muovili o usali per ricollegarli.",
        "gui.restore": "Annulla l'ultima sincronizzazione",
        "gui.restored": "Ultima sincronizzazione annullata.",
        "gui.about": "Informazioni su DualPair",
        "gui.source": "Windows trovato su {source}",
        "gui.experimental.tip": "Importato con un tipo di chiave stimato: se non si collega, associalo anche "
                                "in Linux e sincronizza di nuovo.",
    },
}


def _lang():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v:
            code = v.split(":")[0][:2].lower()
            return code if code in STRINGS else "en"
    return "en"


LANG = _lang()


def t(key: str, **kw) -> str:
    s = STRINGS[LANG].get(key) or STRINGS["en"].get(key) or key
    try:
        return s.format(**kw)
    except (KeyError, IndexError):
        return s
