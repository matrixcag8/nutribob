import Foundation
import UserNotifications

/// Il grillo ti richiama all'ora del controllo se sei fuori soglia rispetto all'obiettivo.
/// Le notifiche si pianificano in anticipo, quindi vanno ricalcolate a ogni modifica del diario.
enum Reminder {
    static func message(_ profile: Profile, kcal: Double) -> String? {
        let soglia = Int(profile.effectiveThreshold), k = Int(kcal), ora = profile.checkHour
        switch profile.goal {
        case .aumentare where kcal < profile.effectiveThreshold:
            return k == 0
                ? "Sono le \(ora) e non hai ancora segnato niente. Per salire di peso a quest'ora dovresti essere ad almeno \(soglia) kcal: cosa mangi adesso?"
                : "Sono le \(ora) e sei a \(k) kcal, sotto le \(soglia) che ti servono a quest'ora per salire. Cosa ci metti adesso?"
        case .dimagrire where kcal > profile.effectiveThreshold:
            return "Sono le \(ora) e sei già a \(k) kcal, oltre la soglia di \(soglia). Come imposti il resto della giornata?"
        default:
            return nil
        }
    }

    static func update(todayKcal: Double) async {
        let center = UNUserNotificationCenter.current()
        center.removeAllPendingNotificationRequests()
        let profile = Profile.current
        let cal = Calendar.current
        // oggi con le kcal reali, i 6 giorni dopo come se non si aprisse più l'app (0 kcal)
        for offset in 0..<7 {
            guard let day = cal.date(byAdding: .day, value: offset, to: .now),
                  let fire = cal.date(bySettingHour: profile.checkHour, minute: 0, second: 0, of: day),
                  fire > .now,
                  let body = message(profile, kcal: offset == 0 ? todayKcal : 0) else { continue }
            let content = UNMutableNotificationContent()
            content.title = "Il grillo"
            content.body = body
            content.sound = .default
            let when = cal.dateComponents([.year, .month, .day, .hour, .minute], from: fire)
            try? await center.add(UNNotificationRequest(
                identifier: "check-\(offset)", content: content,
                trigger: UNCalendarNotificationTrigger(dateMatching: when, repeats: false)))
        }
    }
}
