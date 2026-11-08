"""Tiny translation table (English + Italian). Language from LANGUAGE/LC_ALL/LC_MESSAGES/LANG."""
import os

STRINGS = {
    "en": {
        # errors
        "err.not_root": "Administrator rights are needed to read the Bluetooth settings.",
        "err.no_windows": "No Windows installation was found on this computer's disks.",
        "err.no_windows_at": "No Windows installation found in {path}.",
        "err.bitlocker": "The Windows disk is encrypted with BitLocker ({devices}), so Linux cannot read it. "
                         "In Windows, open DualPair for Windows and choose \u201cExport for Linux\u201d, then scan again here.",
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
        "err.clock_failed": "Could not change the Linux clock setting: {detail}",
        "err.no_esp": "The EFI partition, used to exchange data with DualPair for Windows, was not found.",
        "err.unknown_message": "Unknown message: {id}.",
        "newer.linux": "paired last on Linux", "newer.windows": "paired last on Windows",
        "cli.sent": "Sent {n} device(s) to DualPair for Windows: open it in Windows to import them.",
        "cli.no_pending": "Nothing waiting for Windows.",
        "cli.pending_item": "Waiting for DualPair for Windows: {type} ({id})",
        "cli.clock.pending": "A change for Windows is waiting: DualPair for Windows applies it at the next start.",
        "note.no_bt_keys": "Windows has no paired Bluetooth devices.",
        "note.no_linux_adapter": "No Bluetooth adapter found in Linux: turn Bluetooth on to sync devices.",
        "clock.std.utc": "UTC", "clock.std.local": "local time",
        "clock.state.ok_utc": "Both systems read the hardware clock as UTC: the time stays right on both.",
        "clock.state.ok_local": "Both systems read the hardware clock as local time: it works, but the "
                                "time can be wrong for a while after daylight-saving changes.",
        "clock.state.conflict": "Linux reads the hardware clock as UTC and Windows as local time: after "
                                "using Linux, Windows shows the wrong time (and the other way round).",
        "clock.state.conflict_reverse": "Linux reads the hardware clock as local time and Windows as UTC: "
                                        "the time is wrong after switching system.",
        "cli.clock": "Hardware clock: Linux reads it as {linux}, Windows as {windows}.",
        "cli.clock.fix_windows": "Recommended fix, in Windows (administrator Command Prompt): {command}",
        "cli.clock.fix_linux": "Or, from here: sudo dualpair-cli clock --set linux-local",
        "cli.clock.fix_reverse": "Fix: sudo dualpair-cli clock --set linux-utc",
        "tab.bluetooth": "Bluetooth",
        "tab.clock": "Clock",
        "gui.source.export": "Linux cannot read the Windows disk (BitLocker): these keys come from \u201cExport for Linux\u201d in DualPair for Windows.",
        "gui.pending.keys": "Waiting for Windows: keys of {devices}. DualPair for Windows will offer to import them at the next start.",
        "gui.pending.cancel": "Cancel",
        "gui.pending.cancelled": "Cancelled.",
        "gui.group.to_windows": "Paired last on Linux",
        "gui.group.to_windows.desc": "These devices now use the Linux key. Send it to Windows so they work there too "
                                     "(DualPair for Windows asks you to confirm at the next start).",
        "gui.send": "Send to Windows",
        "gui.send.need_app": "To send keys to Windows, install DualPair for Windows. Or pair these devices again in Windows and sync here.",
        "gui.sent": "Sent {n} device(s). At the next Windows start, DualPair asks you to import them.",
        "gui.winapp.seen": "DualPair for Windows {version}, last update {written}.",
        "gui.winapp.none": "DualPair for Windows not found: install it to send keys to Windows and fix the clock from here.",
        "gui.clock.fix_win.next_boot": "From here: DualPair for Windows applies it at the next Windows start.",
        "gui.clock.fix_win.manual": "Or do it by hand in Windows",
        "gui.clock.pending_utc": "Waiting for Windows: at the next start it will read the clock as UTC.",
        "gui.clock.pending_local": "Waiting for Windows: at the next start it will read the clock as local time.",

        "gui.clock.title": "Hardware clock",
        "gui.clock.desc": "The computer has one hardware clock, shared by both systems. They must read it "
                          "the same way, or the time is wrong after switching system.",
        "gui.clock.linux": "Linux reads it as",
        "gui.clock.windows": "Windows reads it as",
        "gui.clock.fixes": "How to fix it",
        "gui.clock.fix_win.title": "Windows in UTC (recommended)",
        "gui.clock.fix_win.desc": "Done once in Windows. Linux stays as it is.",
        "gui.clock.fix_win.step1": "In Windows, open DualPair for Windows and choose \u201cUse UTC\u201d.",
        "gui.clock.fix_win.step2": "Or run this in a Command Prompt opened as administrator, then restart Windows:",
        "gui.clock.copy": "Copy",
        "gui.clock.copied": "Command copied.",
        "gui.clock.fix_linux.title": "Linux in local time",
        "gui.clock.fix_linux.desc": "One click, from here. Not recommended by systemd: the time can be wrong "
                                    "for a while after daylight-saving changes.",
        "gui.clock.apply": "Apply",
        "gui.clock.linux_utc.title": "Linux back to UTC",
        "gui.clock.linux_utc.desc": "Windows already reads the clock as UTC: put Linux back to UTC too.",
        "gui.clock.to_utc.title": "Prefer UTC on both? (recommended)",
        "gui.clock.to_utc.desc": "First put Windows in UTC, then come back here and put Linux back to UTC.",
        "gui.clock.applied": "Clock setting changed.",
        "gui.clock.after": "Then start Windows once: the time may be wrong for a moment until it syncs.",
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
        "gui.start.title": "Windows and Linux, without the hassle",
        "gui.start.desc": "DualPair fixes what breaks when Windows and Linux share a PC: Bluetooth devices "
                          "that must be paired again, and a clock that is wrong after switching. "
                          "Click Scan: Windows is only read, never modified.",
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
                         "In Windows apri DualPair per Windows e scegli \u201cEsporta per Linux\u201d, poi cerca di nuovo qui.",
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
        "err.clock_failed": "Non riesco a cambiare l'impostazione dell'orologio di Linux: {detail}",
        "err.no_esp": "Non trovo la partizione EFI, che serve per scambiare dati con DualPair per Windows.",
        "err.unknown_message": "Messaggio sconosciuto: {id}.",
        "newer.linux": "associato per ultimo su Linux", "newer.windows": "associato per ultimo su Windows",
        "cli.sent": "Inviati {n} dispositivi a DualPair per Windows: aprilo in Windows per importarli.",
        "cli.no_pending": "Niente in attesa per Windows.",
        "cli.pending_item": "In attesa di DualPair per Windows: {type} ({id})",
        "cli.clock.pending": "C'è una modifica in attesa per Windows: DualPair per Windows la applica al prossimo avvio.",
        "note.no_bt_keys": "In Windows non ci sono dispositivi Bluetooth associati.",
        "note.no_linux_adapter": "Nessun adattatore Bluetooth in Linux: accendi il Bluetooth per sincronizzare i dispositivi.",
        "clock.std.utc": "UTC", "clock.std.local": "ora locale",
        "clock.state.ok_utc": "Entrambi i sistemi leggono l'orologio hardware in UTC: l'ora resta giusta su tutti e due.",
        "clock.state.ok_local": "Entrambi i sistemi leggono l'orologio hardware in ora locale: funziona, ma "
                                "dopo il cambio dell'ora legale l'orario può essere sbagliato per un po'.",
        "clock.state.conflict": "Linux legge l'orologio hardware in UTC e Windows in ora locale: dopo aver "
                                "usato Linux, Windows mostra l'ora sbagliata (e viceversa).",
        "clock.state.conflict_reverse": "Linux legge l'orologio hardware in ora locale e Windows in UTC: "
                                        "l'ora è sbagliata quando cambi sistema.",
        "cli.clock": "Orologio hardware: Linux lo legge in {linux}, Windows in {windows}.",
        "cli.clock.fix_windows": "Soluzione consigliata, in Windows (Prompt dei comandi come amministratore): {command}",
        "cli.clock.fix_linux": "Oppure, da qui: sudo dualpair-cli clock --set linux-local",
        "cli.clock.fix_reverse": "Soluzione: sudo dualpair-cli clock --set linux-utc",
        "tab.bluetooth": "Bluetooth",
        "tab.clock": "Orario",
        "gui.source.export": "Linux non può leggere il disco di Windows (BitLocker): queste chiavi vengono da \u201cEsporta per Linux\u201d in DualPair per Windows.",
        "gui.pending.keys": "In attesa di Windows: chiavi di {devices}. DualPair per Windows proporrà di importarle al prossimo avvio.",
        "gui.pending.cancel": "Annulla",
        "gui.pending.cancelled": "Annullato.",
        "gui.group.to_windows": "Associati per ultimi su Linux",
        "gui.group.to_windows.desc": "Questi dispositivi ora usano la chiave di Linux. Inviala a Windows perché funzionino anche lì "
                                     "(DualPair per Windows ti chiede conferma al prossimo avvio).",
        "gui.send": "Invia a Windows",
        "gui.send.need_app": "Per inviare le chiavi a Windows installa DualPair per Windows. Oppure associa di nuovo questi dispositivi in Windows e sincronizza qui.",
        "gui.sent": "Inviati {n} dispositivi. Al prossimo avvio di Windows, DualPair ti chiede di importarli.",
        "gui.winapp.seen": "DualPair per Windows {version}, ultimo aggiornamento {written}.",
        "gui.winapp.none": "DualPair per Windows non trovato: installalo per inviare chiavi a Windows e sistemare l'orario da qui.",
        "gui.clock.fix_win.next_boot": "Da qui: DualPair per Windows la applica al prossimo avvio di Windows.",
        "gui.clock.fix_win.manual": "Oppure a mano, in Windows",
        "gui.clock.pending_utc": "In attesa di Windows: al prossimo avvio leggerà l'orologio in UTC.",
        "gui.clock.pending_local": "In attesa di Windows: al prossimo avvio leggerà l'orologio in ora locale.",

        "gui.clock.title": "Orologio hardware",
        "gui.clock.desc": "Il computer ha un solo orologio hardware, condiviso dai due sistemi. Devono leggerlo "
                          "allo stesso modo, altrimenti l'ora è sbagliata quando cambi sistema.",
        "gui.clock.linux": "Linux lo legge in",
        "gui.clock.windows": "Windows lo legge in",
        "gui.clock.fixes": "Come risolvere",
        "gui.clock.fix_win.title": "Windows in UTC (consigliata)",
        "gui.clock.fix_win.desc": "Si fa una volta da Windows. Linux resta com'è.",
        "gui.clock.fix_win.step1": "In Windows apri DualPair per Windows e scegli \u201cUsa UTC\u201d.",
        "gui.clock.fix_win.step2": "Oppure esegui questo comando in un Prompt dei comandi aperto come amministratore, poi riavvia Windows:",
        "gui.clock.copy": "Copia",
        "gui.clock.copied": "Comando copiato.",
        "gui.clock.fix_linux.title": "Linux in ora locale",
        "gui.clock.fix_linux.desc": "Un clic, da qui. Sconsigliata da systemd: dopo il cambio dell'ora legale "
                                    "l'orario può essere sbagliato per un po'.",
        "gui.clock.apply": "Applica",
        "gui.clock.linux_utc.title": "Linux di nuovo in UTC",
        "gui.clock.linux_utc.desc": "Windows legge già l'orologio in UTC: rimetti in UTC anche Linux.",
        "gui.clock.to_utc.title": "Preferisci UTC su entrambi? (consigliato)",
        "gui.clock.to_utc.desc": "Metti prima Windows in UTC, poi torna qui e rimetti Linux in UTC.",
        "gui.clock.applied": "Impostazione dell'orologio cambiata.",
        "gui.clock.after": "Poi avvia Windows una volta: l'ora potrebbe essere sbagliata per un attimo, finché non si sincronizza.",
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
        "gui.start.title": "Windows e Linux, senza problemi",
        "gui.start.desc": "DualPair sistema quello che si rompe quando Windows e Linux condividono un PC: "
                          "dispositivi Bluetooth da riassociare e orario sbagliato quando cambi sistema. "
                          "Premi Cerca: Windows viene solo letto, mai modificato.",
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
