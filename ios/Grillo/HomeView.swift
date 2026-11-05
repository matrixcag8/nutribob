import Charts
import SwiftData
import SwiftUI

struct HomeView: View {
    @Query(sort: \Entry.date, order: .reverse) private var entries: [Entry]
    @AppStorage("profile") private var profileData: Data?
    private let model = LocalModel.shared

    var body: some View {
        let profile = Profile.decode(profileData)
        let cal = Calendar.current
        let today = entries.filter { cal.isDateInToday($0.date) }
        let kcal = today.reduce(0) { $0 + $1.kcal }
        let sum = { (kp: KeyPath<Entry, Double?>) in today.reduce(0) { $0 + ($1[keyPath: kp] ?? 0) } }
        let week = Self.lastDays(7, entries)

        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    if !Grillo.hasAppleModel && !model.downloaded { modelCard }

                    Card {
                        HStack(spacing: 20) {
                            Ring(value: kcal / profile.target)
                                .overlay {
                                    VStack {
                                        Text("\(Int(kcal))").font(.title.bold()).monospacedDigit()
                                        Text("di \(Int(profile.target)) kcal").font(.caption).foregroundStyle(.secondary)
                                    }
                                }
                                .frame(width: 130, height: 130)
                            VStack(alignment: .leading, spacing: 10) {
                                MacroBar(name: "Proteine", value: sum(\.protein), target: profile.protein, color: .orange)
                                MacroBar(name: "Carboidrati", value: sum(\.carbs), target: nil, color: .blue)
                                MacroBar(name: "Grassi", value: sum(\.fat), target: nil, color: .purple)
                            }
                        }
                        Text(kcal <= profile.target
                             ? "Mancano \(Int(profile.target - kcal)) kcal al tuo obiettivo di oggi."
                             : "Sei \(Int(kcal - profile.target)) kcal sopra l'obiettivo di oggi.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }

                    HStack(spacing: 12) {
                        Stat(value: "\(Self.streak(entries))", label: "giorni di fila")
                        Stat(value: "\(Int(week.map(\.kcal).reduce(0, +) / Double(max(1, week.filter { $0.kcal > 0 }.count))))",
                             label: "media kcal 7 gg")
                        Stat(value: "\(today.count)", label: "voci oggi")
                    }

                    Card {
                        Text("Ultimi 7 giorni").font(.headline)
                        Chart {
                            ForEach(week, id: \.day) { d in
                                BarMark(x: .value("Giorno", d.day, unit: .day), y: .value("kcal", d.kcal))
                                    .foregroundStyle(.green.gradient)
                                    .cornerRadius(4)
                            }
                            RuleMark(y: .value("Obiettivo", profile.target))
                                .foregroundStyle(.secondary)
                                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                                .annotation(position: .top, alignment: .leading) {
                                    Text("obiettivo").font(.caption2).foregroundStyle(.secondary)
                                }
                        }
                        .chartXAxis {
                            AxisMarks(values: .stride(by: .day)) { AxisValueLabel(format: .dateTime.weekday(.narrow)) }
                        }
                        .frame(height: 160)
                    }
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Oggi")
        }
    }

    private var modelCard: some View {
        Card {
            if let progress = model.progress {
                ProgressView("Scarico il cervello del grillo…", value: progress)
            } else {
                Button("Scarica il cervello del grillo (~1 GB)") { Task { await model.load() } }
                    .buttonStyle(.borderedProminent)
                if let error = model.error { Text(error).font(.caption).foregroundStyle(.red) }
            }
            Text("Serve una volta sola, meglio in Wi-Fi. Poi il grillo funziona offline.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    /// kcal per giorno degli ultimi n giorni, oggi compreso (anche i giorni vuoti).
    static func lastDays(_ n: Int, _ entries: [Entry], now: Date = .now) -> [(day: Date, kcal: Double)] {
        let cal = Calendar.current
        let start = cal.startOfDay(for: now)
        return (0..<n).reversed().map { offset in
            let day = cal.date(byAdding: .day, value: -offset, to: start)!
            return (day, entries.filter { cal.isDate($0.date, inSameDayAs: day) }.reduce(0) { $0 + $1.kcal })
        }
    }

    /// Giorni consecutivi con almeno una voce; oggi vuoto non interrompe la serie.
    static func streak(_ entries: [Entry], now: Date = .now) -> Int {
        let cal = Calendar.current
        let days = Set(entries.map { cal.startOfDay(for: $0.date) })
        var day = cal.startOfDay(for: now)
        if !days.contains(day) { day = cal.date(byAdding: .day, value: -1, to: day)! }
        var count = 0
        while days.contains(day) {
            count += 1
            day = cal.date(byAdding: .day, value: -1, to: day)!
        }
        return count
    }
}

private struct Card<Content: View>: View {
    @ViewBuilder let content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 12) { content }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: 20))
    }
}

private struct Ring: View {
    let value: Double
    var body: some View {
        ZStack {
            Circle().stroke(.green.opacity(0.15), lineWidth: 14)
            Circle().trim(from: 0, to: min(value, 1))
                .stroke(value > 1 ? Color.orange : .green, style: StrokeStyle(lineWidth: 14, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
        .animation(.spring, value: value)
    }
}

private struct MacroBar: View {
    let name: String
    let value: Double
    let target: Double?
    let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(name).font(.caption)
                Spacer()
                Text(target.map { "\(Int(value))/\(Int($0)) g" } ?? "\(Int(value)) g").font(.caption).monospacedDigit()
            }
            if let target {
                ProgressView(value: min(value, target), total: target).tint(color)
            }
        }
    }
}

private struct Stat: View {
    let value: String
    let label: String
    var body: some View {
        VStack(spacing: 2) {
            Text(value).font(.title2.bold()).monospacedDigit()
            Text(label).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: 16))
    }
}
