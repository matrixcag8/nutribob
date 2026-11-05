import SwiftUI
import SwiftData

struct DiaryView: View {
    @Query(sort: \Entry.date, order: .reverse) private var entries: [Entry]
    @Query private var analyses: [DayAnalysis]
    @Environment(\.modelContext) private var context
    @AppStorage("profile") private var profileData: Data?
    @AppStorage("tone") private var tone = Tone.gentile
    @State private var addMeal: Int?
    @State private var analyzing: Set<Date> = []
    @State private var failed: Set<Date> = []
    @State private var open: Set<Date> = []  // giorni passati aperti: partono tutti chiusi

    private var days: [(day: Date, items: [Entry])] {
        var groups = Dictionary(grouping: entries) { Calendar.current.startOfDay(for: $0.date) }
        groups[Calendar.current.startOfDay(for: .now), default: []] += []  // oggi sempre, per i pasti fissi vuoti
        return groups.map { ($0.key, $0.value.sorted { $0.date < $1.date }) }.sorted { $0.day > $1.day }
    }

    /// Oggi: pasti fissi + quelli usati; giorni passati: solo quelli usati. 0 = voci senza pasto.
    private func meals(_ day: Date, _ items: [Entry]) -> [Int] {
        let used = Set(items.map { $0.meal ?? 0 })
        let fixed = Calendar.current.isDateInToday(day) ? Set(1...Profile.decode(profileData).mealCount) : []
        return used.union(fixed).sorted()
    }

    var body: some View {
        NavigationStack {
            List {
                ForEach(days, id: \.day) { day in
                    let today = Calendar.current.isDateInToday(day.day)
                    Section {
                        if today || open.contains(day.day) {
                        ForEach(meals(day.day, day.items), id: \.self) { meal in
                            let items = day.items.filter { ($0.meal ?? 0) == meal }
                            MealHeader(meal: meal, items: items, onAdd: today && meal > 0 ? { addMeal = meal } : nil)
                            let targets = MealSlots.options(fixed: Profile.decode(profileData).mealCount, used: day.items.compactMap(\.meal))
                            ForEach(items) { entry in
                                EntryRow(entry: entry)
                                    .contextMenu {
                                        Menu("Sposta in", systemImage: "arrow.up.arrow.down") {
                                            ForEach(targets.filter { $0 != entry.meal }, id: \.self) { target in
                                                Button(MealSlots.name(target)) { entry.meal = target }
                                            }
                                        }
                                    }
                            }
                                .onDelete { $0.forEach { context.delete(items[$0]) } }
                        }
                        if !day.items.isEmpty { analysisRow(day.day, day.items) }
                        }
                    } header: {
                        if today {
                            DayHeader(day: day.day, items: day.items)
                        } else {
                            Button {
                                withAnimation { if open.contains(day.day) { open.remove(day.day) } else { open.insert(day.day) } }
                            } label: {
                                HStack {
                                    DayHeader(day: day.day, items: day.items)
                                    Spacer()
                                    Image(systemName: "chevron.right").rotationEffect(.degrees(open.contains(day.day) ? 90 : 0))
                                }
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityHint(open.contains(day.day) ? "Chiudi il giorno" : "Apri il giorno")
                        }
                    }
                }
            }
            .navigationTitle("Diario")
            .sheet(isPresented: Binding(get: { addMeal != nil }, set: { if !$0 { addMeal = nil } })) {
                AddFoodView(meal: addMeal)
            }
        }
    }

    @ViewBuilder private func analysisRow(_ day: Date, _ items: [Entry]) -> some View {
        let saved = analyses.first { $0.day == day }
        let ready = Grillo.hasAppleModel || LocalModel.shared.downloaded
        VStack(alignment: .leading, spacing: 8) {
            if let saved {
                Label("Analisi del grillo", systemImage: "ant").font(.headline).foregroundStyle(.green)
                Text(saved.text).font(.callout)
            }
            if analyzing.contains(day) {
                ProgressView("Il grillo ci sta pensando…")
            } else {
                Button(saved == nil ? "Analizza la giornata" : "Rifai l'analisi", systemImage: "sparkles") {
                    analyze(day, items, saved)
                }
                .disabled(!ready)
                if !ready { Text("Prima scarica il cervello del grillo dalla Home.").font(.caption).foregroundStyle(.secondary) }
                if failed.contains(day) { Text("Il grillo non è riuscito a rispondere, riprova.").font(.caption).foregroundStyle(.red) }
            }
        }
        .padding(.vertical, 4)
    }

    private func analyze(_ day: Date, _ items: [Entry], _ saved: DayAnalysis?) {
        analyzing.insert(day)
        failed.remove(day)
        let tone = tone
        Task {
            if let text = await Grillo.analyze(day: items, tone: tone) {
                if let saved { saved.text = text } else { context.insert(DayAnalysis(day: day, text: text)) }
            } else {
                failed.insert(day)
            }
            analyzing.remove(day)
        }
    }
}

private struct DayHeader: View {
    let day: Date
    let items: [Entry]

    var body: some View {
        let sum = { (kp: KeyPath<Entry, Double?>) in items.reduce(0) { $0 + ($1[keyPath: kp] ?? 0) } }
        VStack(alignment: .leading) {
            Text(day.formatted(.dateTime.weekday(.wide).day().month()))
            Text("\(Int(items.reduce(0) { $0 + $1.kcal })) kcal · P \(sum(\.protein).g) · C \(sum(\.carbs).g) · G \(sum(\.fat).g)")
                .monospacedDigit()
        }
    }
}

private struct MealHeader: View {
    let meal: Int
    let items: [Entry]
    let onAdd: (() -> Void)?

    var body: some View {
        HStack {
            Text(meal == 0 ? "Senza pasto" : MealSlots.name(meal)).font(.subheadline.bold()).foregroundStyle(.green)
            Text(items.isEmpty ? "vuoto" : "\(Int(items.reduce(0) { $0 + $1.kcal })) kcal")
                .font(.caption).foregroundStyle(.secondary).monospacedDigit()
            Spacer()
            if let onAdd {
                Button("Aggiungi a \(MealSlots.name(meal))", systemImage: "plus.circle.fill", action: onAdd)
                    .labelStyle(.iconOnly).buttonStyle(.borderless).foregroundStyle(.green)
            }
        }
    }
}

private struct EntryRow: View {
    let entry: Entry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(entry.name.capitalized).font(.headline)
                Spacer()
                Text("\(Int(entry.kcal)) kcal").monospacedDigit()
            }
            Text("\(entry.grams.g) · P \(entry.protein.g) · C \(entry.carbs.g) · G \(entry.fat.g)")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
}
