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

            { "tab.wifi", new[] { "Wi-Fi", "Wi-Fi" } },
            { "tab.boot", new[] { "Startup", "Avvio" } },

            { "wifi.title", new[] { "Wi-Fi networks saved in Windows", "Reti Wi-Fi salvate in Windows" } },
            { "wifi.col.ssid", new[] { "Network", "Rete" } },
            { "wifi.col.security", new[] { "Security", "Sicurezza" } },
            { "wifi.col.state", new[] { "In Linux", "In Linux" } },
            { "wifi.sec.open", new[] { "Open", "Aperta" } },
            { "wifi.sec.wpa-psk", new[] { "WPA/WPA2", "WPA/WPA2" } },
            { "wifi.sec.sae", new[] { "WPA3", "WPA3" } },
            { "wifi.state.same", new[] { "Same password", "Stessa password" } },
            { "wifi.state.different", new[] { "Different password", "Password diversa" } },
            { "wifi.state.windows_only", new[] { "Not saved in Linux", "Non salvata in Linux" } },
            { "wifi.state.unknown", new[] { "Unknown", "Sconosciuto" } },
            { "wifi.none", new[] { "No saved Wi-Fi networks (or no Wi-Fi on this PC).", "Nessuna rete Wi-Fi salvata (o nessun Wi-Fi su questo PC)." } },
            { "wifi.none_saved", new[] { "No saved Wi-Fi networks that can be shared (enterprise networks are not shared).", "Nessuna rete Wi-Fi salvata che si possa condividere (le reti aziendali non vengono condivise)." } },
            { "wifi.err.service", new[] { "Wi-Fi is off or missing on this PC (the WLAN AutoConfig service is not running).", "Il Wi-Fi è spento o assente su questo PC (il servizio Configurazione automatica WLAN non è attivo)." } },
            { "wifi.err.adapter", new[] { "No Wi-Fi adapter found.", "Nessuna scheda Wi-Fi trovata." } },
            { "wifi.err.other", new[] { "The saved networks cannot be read: {0}", "Non riesco a leggere le reti salvate: {0}" } },
            { "agent.failed", new[] { "The DualPair service did not answer, the data may be old: {0}", "Il servizio di DualPair non ha risposto, i dati potrebbero essere vecchi: {0}" } },
            { "wifi.send", new[] { "Send selected to Linux", "Invia selezionate a Linux" } },
            { "wifi.sent", new[] { "{0} network(s) ready for Linux, with their passwords. Open DualPair in Linux to import them.\n\nThey stay on the EFI partition until Linux imports them (at most 7 days).", "{0} reti pronte per Linux, con le password. Apri DualPair in Linux per importarle.\n\nRestano sulla partizione EFI finché Linux non le importa (al massimo 7 giorni)." } },
            { "wifi.pending", new[] { "Networks sent from Linux ({0})", "Reti inviate da Linux ({0})" } },
            { "wifi.pending.desc", new[] { "Import them to use them in Windows too, without typing the passwords.", "Importale per usarle anche in Windows, senza riscrivere le password." } },
            { "wifi.pending.new", new[] { "new", "nuova" } },
            { "wifi.pending.different", new[] { "replaces the password saved in Windows", "sostituisce la password salvata in Windows" } },
            { "wifi.pending.same", new[] { "already the same", "già uguale" } },
            { "wifi.import", new[] { "Import selected", "Importa selezionate" } },
            { "wifi.imported", new[] { "Imported {0} network(s).", "Importate {0} reti." } },

            { "fast.title", new[] { "Fast Startup", "Avvio rapido" } },
            { "fast.desc", new[] { "With Fast Startup, shutting down Windows actually hibernates it. Linux then sees the Windows disk as locked: it can only read it, and what it reads may be out of date. With dual boot it is better off.", "Con l'avvio rapido, spegnere Windows in realtà lo iberna. Linux vede allora il disco di Windows come bloccato: può solo leggerlo, e quello che legge può essere vecchio. Con il dual boot è meglio disattivarlo." } },
            { "fast.on", new[] { "Fast Startup is on.", "L'avvio rapido è attivo." } },
            { "fast.off", new[] { "Fast Startup is off.", "L'avvio rapido è disattivato." } },
            { "fast.unknown", new[] { "Fast Startup is not configured (Windows default).", "L'avvio rapido non è configurato (impostazione di Windows)." } },
            { "fast.turn_off", new[] { "Turn Fast Startup off (recommended)", "Disattiva l'avvio rapido (consigliato)" } },
            { "fast.turn_on", new[] { "Turn Fast Startup on", "Riattiva l'avvio rapido" } },
            { "fast.done", new[] { "Done. It takes effect from the next shutdown.", "Fatto. Vale dal prossimo spegnimento." } },

            { "boot.title", new[] { "Boot order", "Ordine di avvio" } },
            { "boot.desc", new[] { "Some Windows updates put Windows first in the boot order, so the PC starts Windows directly and the Linux menu is not shown.", "Alcuni aggiornamenti di Windows mettono Windows per primo nell'ordine di avvio: il PC parte direttamente con Windows e il menu di Linux non compare." } },
            { "boot.first_linux", new[] { "Linux is first: the PC shows the Linux boot menu.", "Linux è per primo: il PC mostra il menu di avvio di Linux." } },
            { "boot.first_windows", new[] { "Windows is first: the PC starts Windows directly.", "Windows è per primo: il PC parte direttamente con Windows." } },
            { "boot.first_other", new[] { "First in the boot order: {0}", "Per primo nell'ordine di avvio: {0}" } },
            { "boot.unknown", new[] { "The boot order cannot be read on this PC.", "Su questo PC non riesco a leggere l'ordine di avvio." } },
            { "boot.keep_on", new[] { "Kept first as asked in DualPair for Linux: if an update moves Windows first, DualPair puts Linux back at the next start.", "Mantenuto per primo come richiesto in DualPair per Linux: se un aggiornamento mette Windows per primo, DualPair rimette Linux al prossimo avvio." } },
            { "boot.keep_off", new[] { "To keep Linux first after Windows updates, turn it on in DualPair for Linux (Startup tab).", "Per mantenere Linux per primo dopo gli aggiornamenti di Windows, attivalo in DualPair per Linux (scheda Avvio)." } },
            { "boot.fixed", new[] { "Last restored: {0}", "Ultimo ripristino: {0}" } },
            { "boot.put_linux_first", new[] { "Put Linux first now", "Metti Linux per primo adesso" } },
            { "boot.no_linux", new[] { "The Linux entry is not known yet: open DualPair in Linux once.", "Non conosco ancora la voce di Linux: apri DualPair in Linux una volta." } },
            { "boot.done", new[] { "Done: at the next start the PC shows the Linux boot menu.", "Fatto: al prossimo avvio il PC mostra il menu di avvio di Linux." } },

            { "notify.wifi", new[] { "Linux sent {0} Wi-Fi network(s). Open DualPair to import them?", "Linux ha inviato {0} reti Wi-Fi. Vuoi aprire DualPair per importarle?" } },
            { "notify.fast_off", new[] { "As requested in DualPair for Linux, Fast Startup is now off. It takes effect from the next shutdown.", "Come richiesto in DualPair per Linux, l'avvio rapido ora è disattivato. Vale dal prossimo spegnimento." } },
            { "notify.fast_on", new[] { "As requested in DualPair for Linux, Fast Startup is on again.", "Come richiesto in DualPair per Linux, l'avvio rapido è di nuovo attivo." } },
            { "notify.boot_fixed", new[] { "A Windows update had put Windows first in the boot order. As you asked, DualPair put Linux back first.", "Un aggiornamento di Windows aveva messo Windows per primo nell'ordine di avvio. Come avevi chiesto, DualPair ha rimesso Linux per primo." } },
            { "err.no_wifi", new[] { "There are no Wi-Fi networks to send.", "Non ci sono reti Wi-Fi da inviare." } },
            { "err.no_linux_entry", new[] { "The Linux boot entry was not found.", "Non trovo la voce di avvio di Linux." } },
            { "err.boot_failed", new[] { "Could not change the boot order.", "Non riesco a cambiare l'ordine di avvio." } },

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
