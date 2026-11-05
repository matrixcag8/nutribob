import SwiftUI
import SwiftData

struct AddFoodView: View {
    var meal: Int?  // pasto già scelto dal diario; nil = si sceglie nella schermata della quantità
    @State private var query = ""

    private var results: [Food] {
        query.isEmpty ? Food.all : Food.all.filter { $0.name.localizedStandardContains(query) }
    }

    var body: some View {
        NavigationStack {
            List(results) { food in
                NavigationLink(value: food) {
                    HStack {
                        Text(food.name.capitalized)
                        Spacer()
                        Text("\(Int(food.kcal)) kcal/100 g").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Cerca alimento")
            .navigationTitle("Cosa hai mangiato?")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: Food.self) { QuantityView(food: $0, meal: meal) }
        }
    }
}

private struct QuantityView: View {
    let food: Food
    @State private var grams: Double
    @State private var meal: Int
    @State private var day = Date.now
    @AppStorage("profile") private var profileData: Data?
    @Environment(\.modelContext) private var context
    @Environment(\.dismiss) private var dismiss
    @Query private var history: [Entry]

    init(food: Food, meal: Int?) {
        self.food = food
        _grams = State(initialValue: food.portion)
        _meal = State(initialValue: meal ?? 0)  // 0 = da decidere quando arriva lo storico
        let weekAgo = Date.now.addingTimeInterval(-7 * 86400)
        _history = Query(filter: #Predicate<Entry> { $0.date > weekAgo }, sort: \.date)
    }

    private var dayMeals: [Int] { history.filter { Calendar.current.isDate($0.date, inSameDayAs: day) }.compactMap(\.meal) }
    // stessa finestra dello storico caricato, così i pasti proposti sono quelli veri di quel giorno
    private var days: ClosedRange<Date> { Calendar.current.startOfDay(for: .now.addingTimeInterval(-6 * 86400))...Date.now }

    var body: some View {
        let preview = Entry(food: food, grams: grams)
        Form {
            Section {
                TextField("Grammi", value: $grams, format: .number)
                    .keyboardType(.decimalPad)
                Button("Porzione standard: \(food.portionLabel) (\(food.portion.g))") { grams = food.portion }
            } header: { Text("Quantità in grammi") }
            Section {
                DatePicker("Giorno", selection: $day, in: days, displayedComponents: .date)
                let options = MealSlots.options(fixed: Profile.decode(profileData).mealCount, used: dayMeals)
                Picker("Pasto", selection: $meal) {
                    ForEach(options, id: \.self) { Text(MealSlots.name($0)).tag($0) }
                }
            }
            Section {
                LabeledContent("Calorie", value: "\(Int(preview.kcal)) kcal")
                LabeledContent("Proteine", value: preview.protein.g)
                LabeledContent("Carboidrati", value: preview.carbs.g)
                LabeledContent("Grassi", value: preview.fat.g)
            }
        }
        .dismissableKeyboard()
        .navigationTitle(food.name.capitalized)
        .onAppear { if meal == 0 { meal = dayMeals.last ?? 1 } }
        .toolbar {
            Button("Segna", action: save).disabled(grams <= 0)
        }
    }

    private func save() {
        let cal = Calendar.current
        // giorno scelto con l'ora di adesso: l'ordine dentro al giorno resta sensato
        let time = cal.dateComponents([.hour, .minute, .second], from: .now)
        let date = cal.isDateInToday(day) ? .now : cal.date(byAdding: time, to: cal.startOfDay(for: day)) ?? day
        let entry = Entry(food: food, grams: grams, date: date, meal: meal)
        context.insert(entry)
        dismiss()
    }
}

/// Pasti di un giorno: quelli fissi del profilo sempre, più uno in più per aggiungerne man mano.
enum MealSlots {
    static func options(fixed: Int, used: [Int]) -> [Int] {
        Array(1...max(fixed, (used.max() ?? 0) + 1))
    }

    static func name(_ meal: Int) -> String { "Pasto \(meal)" }
}
