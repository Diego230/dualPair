// English and Italian strings, chosen from the Windows display language.
using System.Collections.Generic;
using System.Globalization;

namespace DualPair
{
    public static class Strings
    {
        static readonly bool It = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "it";

        static readonly Dictionary<string, string[]> S = new Dictionary<string, string[]>
        {
            // { key, { English, Italiano } }
            { "app.subtitle", new[] { "Windows and Linux on the same PC, without the hassle", "Windows e Linux sullo stesso PC, senza problemi" } },
            { "tab.bluetooth", new[] { "Bluetooth", "Bluetooth" } },
            { "tab.clock", new[] { "Clock", "Orario" } },
            { "busy", new[] { "Working…", "Un momento…" } },
            { "refresh", new[] { "Refresh", "Aggiorna" } },
            { "close", new[] { "Close", "Chiudi" } },

            { "linux.none", new[] { "DualPair for Linux not found yet: install it in Linux and open it once.", "DualPair per Linux non ancora trovato: installalo in Linux e aprilo una volta." } },
            { "linux.seen", new[] { "DualPair for Linux {0}, last update {1}.", "DualPair per Linux {0}, ultimo aggiornamento {1}." } },
            { "esp.none", new[] { "The EFI partition is not reachable: DualPair for Linux cannot be reached.", "La partizione EFI non è raggiungibile: non posso comunicare con DualPair per Linux." } },

            { "bt.devices", new[] { "Bluetooth devices paired in Windows", "Dispositivi Bluetooth associati in Windows" } },
            { "bt.col.name", new[] { "Device", "Dispositivo" } },
            { "bt.col.address", new[] { "Address", "Indirizzo" } },
            { "bt.col.kind", new[] { "Type", "Tipo" } },
            { "bt.col.state", new[] { "In Linux", "In Linux" } },
            { "kind.classic", new[] { "Classic", "Classico" } },
            { "kind.le", new[] { "Bluetooth LE", "Bluetooth LE" } },
            { "kind.dual", new[] { "Classic + LE", "Classico + LE" } },
            { "state.same", new[] { "Same key: works on both", "Stessa chiave: funziona su entrambi" } },
            { "state.different", new[] { "Different key", "Chiave diversa" } },
            { "state.windows_only", new[] { "Not paired in Linux", "Non associato in Linux" } },
            { "state.unknown", new[] { "Unknown", "Sconosciuto" } },
            { "bt.none", new[] { "No paired Bluetooth devices.", "Nessun dispositivo Bluetooth associato." } },
            { "bt.export", new[] { "Export for Linux", "Esporta per Linux" } },
            { "bt.export.tip", new[] { "Use it when Linux cannot read the Windows disk (BitLocker). DualPair for Linux will offer to import the keys.", "Serve quando Linux non può leggere il disco di Windows (BitLocker). DualPair per Linux proporrà di importare le chiavi." } },
            { "bt.exported", new[] { "Keys of {0} device(s) ready for Linux. Start Linux, open DualPair and click Scan.\n\nThey stay on the EFI partition until Linux imports them (at most 7 days).", "Chiavi di {0} dispositivi pronte per Linux. Avvia Linux, apri DualPair e premi Cerca.\n\nRestano sulla partizione EFI finché Linux non le importa (al massimo 7 giorni)." } },
            { "bt.pending", new[] { "Keys sent from Linux ({0})", "Chiavi inviate da Linux ({0})" } },
            { "bt.pending.desc", new[] { "These devices were paired last on Linux. Import their keys so they work in Windows too.", "Questi dispositivi sono stati associati per ultimi su Linux. Importa le chiavi per farli funzionare anche in Windows." } },
            { "bt.pending.not_paired", new[] { "not paired in Windows: pair it once in Windows first", "non associato in Windows: associalo prima una volta in Windows" } },
            { "bt.pending.same", new[] { "already the same key", "chiave già uguale" } },
            { "bt.import", new[] { "Import selected", "Importa selezionati" } },
            { "bt.discard", new[] { "Discard", "Scarta" } },
            { "bt.imported", new[] { "Imported {0} device(s). Restart Windows to use the new keys.", "Importati {0} dispositivi. Riavvia Windows per usare le nuove chiavi." } },
            { "bt.skipped", new[] { "Not imported (not paired in Windows): {0}", "Non importati (non associati in Windows): {0}" } },
            { "bt.restore", new[] { "Undo last import", "Annulla l'ultima importazione" } },
            { "bt.restored", new[] { "Previous keys restored. Restart Windows.", "Chiavi precedenti ripristinate. Riavvia Windows." } },

            { "clock.title", new[] { "Clock for dual boot", "Orologio per il dual boot" } },
            { "clock.desc", new[] { "The PC has one hardware clock, shared by Windows and Linux. Both must read it the same way.", "Il PC ha un solo orologio hardware, condiviso da Windows e Linux. Devono leggerlo allo stesso modo." } },
            { "clock.utc", new[] { "Windows reads the hardware clock as UTC.", "Windows legge l'orologio hardware in UTC." } },
            { "clock.local", new[] { "Windows reads the hardware clock as local time (the Windows default).", "Windows legge l'orologio hardware in ora locale (l'impostazione di Windows)." } },
            { "clock.linux.utc", new[] { "Linux reads it as UTC.", "Linux lo legge in UTC." } },
            { "clock.linux.local", new[] { "Linux reads it as local time.", "Linux lo legge in ora locale." } },
            { "clock.linux.unknown", new[] { "How Linux reads it is not known yet (open DualPair in Linux once).", "Non so ancora come lo legge Linux (apri DualPair in Linux una volta)." } },
            { "clock.ok", new[] { "Both agree: the time stays right when you switch system.", "Sono d'accordo: l'ora resta giusta quando cambi sistema." } },
            { "clock.conflict", new[] { "They disagree: the time is wrong after switching system.", "Non sono d'accordo: l'ora è sbagliata quando cambi sistema." } },
            { "clock.set_utc", new[] { "Use UTC (recommended with Linux)", "Usa UTC (consigliato con Linux)" } },
            { "clock.set_local", new[] { "Back to local time (Windows default)", "Torna all'ora locale (impostazione di Windows)" } },
            { "clock.sync", new[] { "Sync the time now", "Sincronizza l'ora adesso" } },
            { "clock.done_utc", new[] { "Done: Windows now reads the hardware clock as UTC.\nIf in DualPair for Linux you had chosen 'Linux in local time', put Linux back to UTC there (Clock tab).", "Fatto: ora Windows legge l'orologio hardware in UTC.\nSe in DualPair per Linux avevi scelto 'Linux in ora locale', rimetti Linux in UTC (scheda Orario)." } },
            { "clock.done_local", new[] { "Done: Windows reads the hardware clock as local time again.", "Fatto: Windows legge di nuovo l'orologio hardware in ora locale." } },
            { "clock.synced", new[] { "The time has been synced.", "L'ora è stata sincronizzata." } },
            { "clock.not_synced", new[] { "If the time is still wrong, restart Windows.", "Se l'ora è ancora sbagliata, riavvia Windows." } },
            { "clock.tz", new[] { "Time zone: {0}", "Fuso orario: {0}" } },

            { "notify.keys", new[] { "Linux sent the keys of {0} Bluetooth device(s). Open DualPair to import them?", "Linux ha inviato le chiavi di {0} dispositivi Bluetooth. Vuoi aprire DualPair per importarle?" } },
            { "notify.clock_utc", new[] { "As requested in DualPair for Linux, Windows now reads the hardware clock as UTC. If the time is wrong, it will be right after the next restart.", "Come richiesto in DualPair per Linux, ora Windows legge l'orologio hardware in UTC. Se l'ora è sbagliata, sarà giusta dopo il prossimo riavvio." } },
            { "notify.clock_local", new[] { "As requested in DualPair for Linux, Windows reads the hardware clock as local time again.", "Come richiesto in DualPair per Linux, Windows legge di nuovo l'orologio hardware in ora locale." } },

            { "err.no_esp", new[] { "The EFI partition is not reachable.", "La partizione EFI non è raggiungibile." } },
            { "err.no_devices", new[] { "Windows has no paired Bluetooth devices.", "In Windows non ci sono dispositivi Bluetooth associati." } },
            { "err.unknown_message", new[] { "That message from Linux is no longer there.", "Quel messaggio da Linux non c'è più." } },
            { "err.no_backups", new[] { "There is nothing to undo.", "Non c'è niente da annullare." } },
            { "err.unknown_request", new[] { "Unknown request.", "Richiesta sconosciuta." } },
            { "err.no_agent", new[] { "The DualPair service did not answer. Reinstall DualPair.", "Il servizio di DualPair non ha risposto. Reinstalla DualPair." } },
        };

        public static string T(string key, params object[] args)
        {
            string[] v;
            var s = S.TryGetValue(key, out v) ? v[It ? 1 : 0] : key;
            return args.Length > 0 ? string.Format(CultureInfo.CurrentCulture, s, args) : s;
        }
    }
}
