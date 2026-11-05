import Foundation
import SwiftData

/// Alimento del database (valori per 100 g). Macro nil = non ancora noti.
struct Food: Codable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let kcal: Double
    let protein: Double?
    let carbs: Double?
    let fat: Double?
    let portion: Double
    let portionLabel: String
    /// Micronutrienti per 100 g (chiavi di `Micro`), dalle tabelle USDA; nil per i piatti composti.
    let micros: [String: Double]?

    static let all: [Food] = {
        let url = Bundle.main.url(forResource: "foods", withExtension: "json")!
        return try! JSONDecoder().decode([Food].self, from: Data(contentsOf: url))
    }()
    static let byName = Dictionary(uniqueKeysWithValues: all.map { ($0.name, $0) })
}

/// Micronutrienti seguiti, con riferimento giornaliero adulto (LARN 2014: PRI/AI; limiti per sodio, zuccheri, saturi).
enum Micro: String, CaseIterable {
    case fiber, calcium, iron, magnesium, potassium, zinc, vitA, vitC, vitD, vitB12, folate, sodium, sugars, satFat

    var label: String {
        switch self {
        case .fiber: "fibre"; case .calcium: "calcio"; case .iron: "ferro"; case .magnesium: "magnesio"
        case .potassium: "potassio"; case .zinc: "zinco"; case .vitA: "vitamina A"; case .vitC: "vitamina C"
        case .vitD: "vitamina D"; case .vitB12: "vitamina B12"; case .folate: "folati"; case .sodium: "sodio"
        case .sugars: "zuccheri"; case .satFat: "grassi saturi"
        }
    }
    var unit: String {
        switch self {
        case .fiber, .sugars, .satFat: "g"
        case .vitA, .vitD, .vitB12, .folate: "µg"
        default: "mg"
        }
    }
    /// Sodio, zuccheri e saturi sono tetti da non superare, gli altri obiettivi da raggiungere.
    var isLimit: Bool { [.sodium, .sugars, .satFat].contains(self) }

    func reference(_ p: Profile) -> Double {
        let man = p.sex == .uomo
        return switch self {
        case .fiber: 25
        case .calcium: 1000
        case .iron: man || p.age >= 50 ? 10 : 18
        case .magnesium: 240
        case .potassium: 3900
        case .zinc: man ? 12 : 9
        case .vitA: man ? 700 : 600
        case .vitC: man ? 105 : 85
        case .vitD: 15
        case .vitB12: 2.4
        case .folate: 400
        case .sodium: 2000
        case .sugars: p.target * 0.15 / 4  // 15% delle kcal
        case .satFat: p.target * 0.10 / 9  // 10% delle kcal
        }
    }
}

/// Analisi ampia di una giornata, chiesta dall'utente dal diario.
@Model final class DayAnalysis {
    var day: Date
    var text: String

    init(day: Date, text: String) {
        self.day = day
        self.text = text
    }
}

/// Voce del diario: i valori sono copiati al momento dell'inserimento.
@Model final class Entry {
    var date: Date
    var name: String
    var grams: Double
    var kcal: Double
    var protein: Double?
    var carbs: Double?
    var fat: Double?
    var comment: String?  // non più usato: resta per non toccare lo schema SwiftData salvato
    var meal: Int?  // nil = voce segnata prima che esistessero i pasti

    init(food: Food, grams: Double, date: Date = .now, meal: Int? = nil) {
        let k = grams / 100
        self.date = date
        self.meal = meal
        self.name = food.name
        self.grams = grams
        self.kcal = food.kcal * k
        self.protein = food.protein.map { $0 * k }
        self.carbs = food.carbs.map { $0 * k }
        self.fat = food.fat.map { $0 * k }
    }

    /// Micronutrienti della voce. shortcut: letti dal database attuale per nome, non copiati all'inserimento;
    /// se un giorno i valori di foods.json cambiano, cambia anche lo storico.
    var micros: [Micro: Double]? {
        guard let m = Food.byName[name]?.micros else { return nil }
        return Dictionary(uniqueKeysWithValues: Micro.allCases.compactMap { k in m[k.rawValue].map { (k, $0 * grams / 100) } })
    }
}

enum Tone: String, CaseIterable, Identifiable {
    case gentile, diretto
    var id: String { rawValue }
}

enum Goal: String, Codable, CaseIterable, Identifiable {
    case dimagrire, mantenere, aumentare
    var id: String { rawValue }
}

enum Sex: String, Codable, CaseIterable, Identifiable {
    case uomo, donna
    var id: String { rawValue }
}

enum Activity: Double, Codable, CaseIterable, Identifiable {
    case sedentario = 1.2, leggero = 1.375, moderato = 1.55, intenso = 1.725
    var id: Double { rawValue }
    var label: String {
        switch self {
        case .sedentario: "Sedentario (ufficio, poco movimento)"
        case .leggero: "Leggero (sport 1–3 volte a settimana)"
        case .moderato: "Moderato (sport 3–5 volte a settimana)"
        case .intenso: "Intenso (sport 6–7 volte a settimana)"
        }
    }
}

/// Dati dell'utente e obiettivi, salvati in UserDefaults come JSON.
struct Profile: Codable, Equatable {
    var sex = Sex.uomo
    var age = 30
    var height = 175.0
    var weight = 75.0
    var activity = Activity.leggero
    var goal = Goal.mantenere
    var checkHour = 18
    var threshold: Double?  // nil = soglia calcolata
    var meals: Int?  // opzionale: i profili salvati prima dei pasti si decodificano senza perdere dati
    var mealCount: Int { meals ?? 3 }

    /// Metabolismo basale, formula di Mifflin-St Jeor.
    var bmr: Double { 10 * weight + 6.25 * height - 5 * Double(age) + (sex == .uomo ? 5 : -161) }
    var tdee: Double { bmr * activity.rawValue }
    var target: Double {
        switch goal {
        case .dimagrire: max(tdee - 500, bmr)  // mai sotto il basale
        case .mantenere: tdee
        case .aumentare: tdee + 300
        }
    }
    var protein: Double { weight * (goal == .mantenere ? 1.2 : 1.8) }
    /// Aumentare: entro l'ora del controllo almeno il 60% del target. Dimagrire: non oltre il 75%.
    var effectiveThreshold: Double { threshold ?? (target * (goal == .aumentare ? 0.6 : 0.75)).rounded() }

    static var current: Profile { decode(UserDefaults.standard.data(forKey: "profile")) }

    /// Per le view che osservano @AppStorage("profile").
    static func decode(_ data: Data?) -> Profile {
        data.flatMap { try? JSONDecoder().decode(Profile.self, from: $0) } ?? Profile()
    }

    func save() { UserDefaults.standard.set(try? JSONEncoder().encode(self), forKey: "profile") }
}

extension Double {
    var g: String { "\(Int(rounded())) g" }
}

extension Optional<Double> {
    var g: String { map(\.g) ?? "n.d." }
}
